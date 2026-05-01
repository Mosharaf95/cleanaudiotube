import os
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from processing import VideoProcessor, JobStatus
from utils import validate_youtube_url, cleanup_old_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CleanAudioTube API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, JobStatus] = {}
processor = VideoProcessor()

BASE_DIR = Path(__file__).parent
WORK_DIR = BASE_DIR / "work"
WORK_DIR.mkdir(exist_ok=True)

FRONTEND_DIR = BASE_DIR.parent / "frontend"


class ProcessRequest(BaseModel):
    url: str
    mode: str = "remove_music"


class ProcessResponse(BaseModel):
    job_id: str
    message: str


# ── Serve frontend ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse("<h1>CleanAudioTube API running</h1>")


@app.get("/app.js")
async def serve_js():
    p = FRONTEND_DIR / "app.js"
    if p.exists():
        return FileResponse(str(p), media_type="application/javascript")
    raise HTTPException(status_code=404)


@app.get("/styles.css")
async def serve_css():
    p = FRONTEND_DIR / "styles.css"
    if p.exists():
        return FileResponse(str(p), media_type="text/css")
    raise HTTPException(status_code=404)


# ── API ───────────────────────────────────────────────────────────────────────
@app.post("/process", response_model=ProcessResponse)
async def process_video(request: ProcessRequest, background_tasks: BackgroundTasks):
    url = request.url.strip()
    if not validate_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    job_id = str(uuid.uuid4())
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    job = JobStatus(
        job_id=job_id, status="queued", progress=0,
        message="Job queued", mode=request.mode,
    )
    jobs[job_id] = job
    background_tasks.add_task(processor.run_pipeline, job_id, url, job_dir, jobs)
    logger.info(f"Job {job_id} created for URL: {url}")
    return ProcessResponse(job_id=job_id, message="Processing started")


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "job_id": job_id, "status": job.status,
        "progress": job.progress, "message": job.message,
        "error": job.error, "file_size": job.file_size, "duration": job.duration,
    }


@app.get("/preview/{job_id}")
async def preview_video(job_id: str, request: Request):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if jobs[job_id].status != "complete":
        raise HTTPException(status_code=400, detail="Video not ready yet")

    output_path = WORK_DIR / job_id / "output_clean.mp4"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    file_size = output_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0])
        end = int(ranges[1]) if ranges[1] else file_size - 1

        def iter_range(path, s, e):
            with open(path, "rb") as f:
                f.seek(s)
                remaining = e - s + 1
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(output_path, start, end),
            status_code=206, media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
            },
        )

    def iterfile(path, chunk_size=1024 * 1024):
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    return StreamingResponse(
        iterfile(output_path), media_type="video/mp4",
        headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"},
    )


@app.get("/preview-original/{job_id}")
async def preview_original(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dir = WORK_DIR / job_id
    for ext in ["mp4", "mkv", "webm", "mov"]:
        orig = job_dir / f"original.{ext}"
        if orig.exists():
            file_size = orig.stat().st_size
            def iterfile(path=orig, chunk_size=1024*1024):
                with open(path, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            return StreamingResponse(
                iterfile(), media_type="video/mp4",
                headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"},
            )
    raise HTTPException(status_code=404, detail="Original not found")


@app.get("/download/{job_id}")
async def download_video(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if jobs[job_id].status != "complete":
        raise HTTPException(status_code=400, detail="Video not ready")
    output_path = WORK_DIR / job_id / "output_clean.mp4"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(output_path), media_type="video/mp4",
        filename="clean_audio_video.mp4",
        headers={"Content-Disposition": "attachment; filename=clean_audio_video.mp4"},
    )


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    import shutil
    job_dir = WORK_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    del jobs[job_id]
    return {"message": "Job deleted"}


@app.get("/health")
async def health():
    from utils import check_dependencies
    return {"status": "ok", "dependencies": check_dependencies()}


@app.on_event("startup")
async def startup_event():
    logger.info("CleanAudioTube API started")
    cleanup_old_jobs(WORK_DIR)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
