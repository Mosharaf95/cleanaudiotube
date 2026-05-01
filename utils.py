import re
import time
import shutil
import logging
from pathlib import Path
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

YOUTUBE_URL_PATTERNS = [
    r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
    r"^https?://youtu\.be/[\w-]+",
    r"^https?://(www\.)?youtube\.com/shorts/[\w-]+",
    r"^https?://m\.youtube\.com/watch\?v=[\w-]+",
]


def validate_youtube_url(url: str) -> bool:
    """Validate that a string is a proper YouTube URL."""
    url = url.strip()
    for pattern in YOUTUBE_URL_PATTERNS:
        if re.match(pattern, url):
            return True
    return False


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    # youtu.be format
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0].split("&")[0]

    # youtube.com/watch?v=
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if "v" in params:
        return params["v"][0]

    # shorts
    if "/shorts/" in url:
        return url.split("/shorts/")[-1].split("?")[0]

    return None


def cleanup_old_jobs(work_dir: Path, max_age_hours: int = 24):
    """Remove job directories older than max_age_hours."""
    cutoff = time.time() - (max_age_hours * 3600)
    if not work_dir.exists():
        return

    removed = 0
    for job_dir in work_dir.iterdir():
        if job_dir.is_dir():
            try:
                mtime = job_dir.stat().st_mtime
                if mtime < cutoff:
                    shutil.rmtree(job_dir)
                    removed += 1
            except Exception as e:
                logger.warning(f"Could not clean {job_dir}: {e}")

    if removed:
        logger.info(f"Cleaned up {removed} old job(s)")


def format_file_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024**2):.1f} MB"
    else:
        return f"{size_bytes / (1024**3):.2f} GB"


def check_dependencies() -> dict[str, bool]:
    """Check if required system tools are installed."""
    import subprocess
    deps = {}
    for tool in ["ffmpeg", "ffprobe", "yt-dlp"]:
        try:
            result = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                timeout=5,
            )
            deps[tool] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            deps[tool] = False

    # Check demucs (Python package)
    try:
        import demucs
        deps["demucs"] = True
    except ImportError:
        deps["demucs"] = False

    return deps
