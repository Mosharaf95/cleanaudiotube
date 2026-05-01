import os
import asyncio
import subprocess
import logging
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict
import time

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 7200  # 2 hours


@dataclass
class JobStatus:
    job_id: str
    status: str  # queued | downloading | extracting | separating | merging | complete | error
    progress: int  # 0-100
    message: str
    mode: str = "remove_music"
    error: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None


class VideoProcessor:
    """Handles the full pipeline: download → extract audio → Demucs → merge"""

    async def run_pipeline(
        self,
        job_id: str,
        url: str,
        job_dir: Path,
        jobs: Dict[str, JobStatus],
    ):
        job = jobs[job_id]
        try:
            # Step 1: Download video
            await self._update_job(job, "downloading", 5, "Downloading video from YouTube...")
            video_path = await self._download_video(url, job_dir)

            # Step 2: Validate duration
            await self._update_job(job, "downloading", 15, "Validating video duration...")
            duration = await self._get_duration(video_path)
            if duration and duration > MAX_DURATION_SECONDS:
                raise ValueError(f"Video too long ({duration/3600:.1f}h). Max is 2 hours.")
            job.duration = duration

            # Step 3: Extract audio
            await self._update_job(job, "extracting", 25, "Extracting audio track...")
            audio_path = await self._extract_audio(video_path, job_dir)

            # Step 4: Run Demucs separation
            await self._update_job(job, "separating", 35, "Running AI audio separation (this takes a while)...")
            stems_dir = await self._run_demucs(audio_path, job_dir, job, jobs)

            # Step 5: Mix stems (keep vocals, remove music)
            await self._update_job(job, "separating", 75, "Mixing clean audio stems...")
            clean_audio = await self._mix_stems(stems_dir, job_dir, job.mode)

            # Step 6: Merge clean audio with video
            await self._update_job(job, "merging", 85, "Merging clean audio with video...")
            output_path = await self._merge_audio_video(video_path, clean_audio, job_dir)

            # Done
            file_size = output_path.stat().st_size
            job.file_size = file_size
            await self._update_job(job, "complete", 100, "Processing complete! Your video is ready.")
            logger.info(f"Job {job_id} completed successfully. Output: {output_path}")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            job.status = "error"
            job.progress = 0
            job.error = str(e)
            job.message = f"Error: {str(e)}"

    async def _update_job(self, job: JobStatus, status: str, progress: int, message: str):
        job.status = status
        job.progress = progress
        job.message = message
        logger.info(f"Job {job.job_id} [{progress}%] {message}")
        await asyncio.sleep(0)  # yield control

    async def _download_video(self, url: str, job_dir: Path) -> Path:
        """Download video using yt-dlp"""
        output_template = str(job_dir / "original.%(ext)s")
        cmd = [
            "yt-dlp",
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "--output", output_template,
            "--no-playlist",
            "--max-filesize", "4G",
            "--socket-timeout", "30",
            "--retries", "3",
            url,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(job_dir),
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {stderr.decode()}")

        # Find the downloaded file
        for ext in ["mp4", "mkv", "webm", "mov"]:
            candidate = job_dir / f"original.{ext}"
            if candidate.exists():
                return candidate

        raise RuntimeError("Downloaded file not found")

    async def _get_duration(self, video_path: Path) -> Optional[float]:
        """Get video duration in seconds using ffprobe"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(video_path),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            import json
            data = json.loads(stdout.decode())
            return float(data["format"]["duration"])
        except Exception:
            return None

    async def _extract_audio(self, video_path: Path, job_dir: Path) -> Path:
        """Extract audio as WAV for Demucs"""
        audio_path = job_dir / "audio.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(audio_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {stderr.decode()}")
        return audio_path

    async def _run_demucs(
        self, audio_path: Path, job_dir: Path, job: JobStatus, jobs: Dict
    ) -> Path:
        """
        Run Facebook Demucs for stem separation.
        Uses htdemucs model (4-stem: drums, bass, other, vocals).
        Streams progress from stderr.
        """
        stems_output = job_dir / "stems"
        stems_output.mkdir(exist_ok=True)

        # Use htdemucs (best quality, 4 stems)
        cmd = [
            "python", "-m", "demucs",
            "--name", "htdemucs",
            "--two-stems", "vocals",  # faster: only vocals vs everything else
            "--out", str(stems_output),
            str(audio_path),
        ]

        # If mode is "remove_music", use full 4-stem to preserve drums/ambiance
        if job.mode == "remove_music":
            cmd = [
                "python", "-m", "demucs",
                "--name", "htdemucs",
                "--out", str(stems_output),
                str(audio_path),
            ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Stream progress from stderr
        async def read_progress():
            progress_base = 35
            progress_range = 38  # from 35% to 73%
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                if "%" in line_str:
                    try:
                        # Demucs prints lines like: "  7%|..."
                        pct_str = line_str.split("%")[0].strip().split()[-1]
                        pct = float(pct_str)
                        mapped = int(progress_base + (pct / 100) * progress_range)
                        job.progress = mapped
                        job.message = f"AI separating audio... {int(pct)}%"
                    except Exception:
                        pass

        await asyncio.gather(
            proc.wait(),
            read_progress(),
        )

        if proc.returncode != 0:
            stderr_out = await proc.stderr.read()
            raise RuntimeError(f"Demucs failed (code {proc.returncode}): {stderr_out.decode()}")

        # Return path to separated stems
        # Demucs output structure: stems_output/htdemucs/audio/vocals.wav etc.
        model_dir = stems_output / "htdemucs" / "audio"
        if not model_dir.exists():
            # Try finding it
            for d in stems_output.rglob("vocals.wav"):
                return d.parent
            raise RuntimeError("Could not find Demucs output directory")
        return model_dir

    async def _mix_stems(
        self, stems_dir: Path, job_dir: Path, mode: str
    ) -> Path:
        """
        Mix stems to produce clean audio.

        remove_music mode:
          - Keep: vocals + drums (light, for footsteps/rhythm) + small amount of "other"
          Actually: Remove pure music background. Keep vocals fully.
          For natural sounds: we keep a bit of drums at reduced volume.

        voice_only mode:
          - Keep ONLY vocals stem
        """
        clean_audio = job_dir / "clean_audio.wav"

        if mode == "voice_only":
            # Strict: only vocals
            vocals = stems_dir / "vocals.wav"
            if not vocals.exists():
                raise RuntimeError("Vocals stem not found")
            shutil.copy(vocals, clean_audio)
            return clean_audio

        # remove_music: Keep vocals fully + drums at 40% (for footsteps/natural percussion)
        # Remove bass + other (music/instrumental)
        vocals = stems_dir / "vocals.wav"
        drums = stems_dir / "drums.wav"
        bass = stems_dir / "bass.wav"
        other = stems_dir / "other.wav"

        # Two-stem mode fallback (vocals vs no_vocals)
        if not drums.exists():
            # Two-stem mode: just use vocals
            if vocals.exists():
                shutil.copy(vocals, clean_audio)
                return clean_audio
            raise RuntimeError("No vocal stem found")

        # Full 4-stem: mix vocals (100%) + drums (35% for ambient/footstep feel)
        # This keeps speech crystal clear while removing music
        cmd = [
            "ffmpeg", "-y",
            "-i", str(vocals),
            "-i", str(drums),
            "-filter_complex",
            "[0:a]volume=1.0[v];[1:a]volume=0.35[d];[v][d]amix=inputs=2:duration=longest",
            "-ar", "44100",
            "-ac", "2",
            str(clean_audio),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg stem mixing failed: {stderr.decode()}")

        return clean_audio

    async def _merge_audio_video(
        self, video_path: Path, audio_path: Path, job_dir: Path
    ) -> Path:
        """Merge clean audio back with the original video"""
        output_path = job_dir / "output_clean.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",           # keep original video stream (fast, no re-encode)
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",          # video from original
            "-map", "1:a:0",          # audio from clean mix
            "-shortest",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg merge failed: {stderr.decode()}")
        return output_path
