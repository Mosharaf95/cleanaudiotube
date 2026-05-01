# CleanAudioTube 🎙️

> Remove background music from any YouTube video while preserving speech, footsteps, and ambient sounds — powered by Meta's Demucs AI.

---

## 📸 What It Does

1. You paste a YouTube URL
2. The app downloads the video via **yt-dlp**
3. **FFmpeg** extracts the audio track
4. **Meta Demucs** (htdemucs model) separates audio into 4 stems:
   - `vocals` — speech, voice
   - `drums` — percussion, footsteps
   - `bass` — bass lines
   - `other` — melodic/harmonic music
5. Music is removed (`bass` + `other` dropped; `drums` kept at 35% for natural ambiance)
6. Clean audio is merged back with the original video
7. Preview + download the result in MP4

**Two modes:**
- **Remove Music Only** — keeps vocals + light drums (footsteps/ambient)
- **Voice Only (strict)** — keeps *only* vocals stem

---

## 🗂 Project Structure

```
CleanAudioTube/
├── backend/
│   ├── main.py          FastAPI app + endpoints
│   ├── processing.py    Full pipeline (download → Demucs → merge)
│   └── utils.py         Helpers (URL validation, cleanup)
├── frontend/
│   ├── index.html       Single-page UI
│   ├── styles.css       Dark industrial design system
│   └── app.js           Frontend logic + API communication
├── requirements.txt
└── README.md
```

---

## ⚙️ Prerequisites

### 1. Python 3.10+

```bash
python3 --version  # Must be 3.10 or newer
```

### 2. FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install -y ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html, add to PATH.

Verify:
```bash
ffmpeg -version
ffprobe -version
```

### 3. yt-dlp

```bash
pip install yt-dlp
# or
brew install yt-dlp
```

Verify:
```bash
yt-dlp --version
```

### 4. PyTorch (required for Demucs)

**CPU only (any machine):**
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**CUDA GPU (NVIDIA — much faster for long videos):**
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**Apple Silicon (M1/M2/M3):**
```bash
pip install torch torchaudio
```

---

## 🚀 Installation

```bash
# 1. Clone or download the project
git clone <your-repo-url>
cd CleanAudioTube

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Demucs will auto-download the htdemucs model on first run (~100MB)
```

---

## ▶️ Running Locally

### Start the backend:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be at: `http://localhost:8000`

### Open the frontend:

Option A — Open directly in browser:
```
frontend/index.html
```

Option B — Serve via Python:
```bash
cd frontend
python3 -m http.server 3000
# Open http://localhost:3000
```

Option C — Backend serves the frontend automatically if both are in the right directories.

---

## 🔌 API Reference

### `POST /process`
Start processing a YouTube video.

**Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "mode": "remove_music"   // or "voice_only"
}
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "message": "Processing started"
}
```

---

### `GET /status/{job_id}`
Poll job status.

**Response:**
```json
{
  "job_id": "...",
  "status": "separating",    // queued|downloading|extracting|separating|merging|complete|error
  "progress": 52,
  "message": "AI separating audio... 47%",
  "error": null,
  "file_size": 54321678,
  "duration": 312.4
}
```

---

### `GET /preview/{job_id}`
Stream the processed MP4 video (for the in-page player).

---

### `GET /preview-original/{job_id}`
Stream the original downloaded video.

---

### `GET /download/{job_id}`
Download the final clean MP4 video.

---

### `DELETE /job/{job_id}`
Cancel and clean up a job.

---

## ⏱️ Processing Time Estimates

| Video Length | CPU (no GPU) | NVIDIA GPU  |
|-------------|-------------|-------------|
| 5 minutes   | ~8 min      | ~1 min      |
| 30 minutes  | ~45 min     | ~6 min      |
| 1 hour      | ~90 min     | ~12 min     |
| 2 hours     | ~3 hours    | ~25 min     |

> Demucs is the bottleneck. A GPU makes a *huge* difference for long videos.

---

## 🐳 Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system deps
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod a+rx /usr/local/bin/yt-dlp

WORKDIR /app

# Install Python deps (CPU torch first)
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build and run:

```bash
docker build -t cleanaudiotube .
docker run -p 8000:8000 cleanaudiotube
```

---

## ☁️ Cloud Deployment

### Railway (easiest)

1. Push to GitHub
2. Connect to Railway (railway.app)
3. Set `START_COMMAND` to: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add a persistent volume at `/app/backend/work`
5. Deploy

### Render

1. Create a new Web Service
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add persistent disk at `/app/backend/work`

### VPS (DigitalOcean, Linode, etc.)

```bash
# Install system deps
sudo apt install -y python3-pip ffmpeg

# Install yt-dlp
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
  -o /usr/local/bin/yt-dlp && sudo chmod a+rx /usr/local/bin/yt-dlp

# Clone and set up
git clone <repo> && cd CleanAudioTube
python3 -m venv venv && source venv/bin/activate
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# Run with systemd or screen
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## 🔧 Configuration

Edit `backend/processing.py` to tweak:

```python
MAX_DURATION_SECONDS = 7200   # Max video length (default 2 hours)
```

Stem mix ratios in `_mix_stems()`:
```python
# Current: vocals 100% + drums 35%
"[0:a]volume=1.0[v];[1:a]volume=0.35[d];..."
```

---

## 🛠️ Troubleshooting

**`demucs` not found:**
```bash
pip install demucs
# or
python -m pip install demucs
```

**ffmpeg not found:**
```bash
which ffmpeg   # should return a path
# If not: brew install ffmpeg  (Mac) or  apt install ffmpeg  (Linux)
```

**yt-dlp download fails:**
```bash
yt-dlp --update   # update to latest version
```

**CUDA out of memory:**
Add to `_run_demucs()` in `processing.py`:
```python
"--device", "cpu"   # force CPU
```

**First run is slow:**
Demucs downloads the `htdemucs` model (~100MB) on first use. Subsequent runs use the cached model.

---

## 📋 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.11 |
| AI Model | Meta Demucs (htdemucs) |
| Download | yt-dlp |
| Audio/Video | FFmpeg |
| Frontend | Vanilla HTML/CSS/JS |
| Fonts | Syne + Space Mono |

---

## 📄 License

MIT License — free to use, modify, and deploy.
