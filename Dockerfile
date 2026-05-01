FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod a+rx /usr/local/bin/yt-dlp

WORKDIR /app

RUN pip install --no-cache-dir \
    torch==2.3.0 \
    torchaudio==2.3.0 \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./backend/main.py
COPY processing.py ./backend/processing.py
COPY utils.py ./backend/utils.py

COPY index.html ./frontend/index.html
COPY app.js ./frontend/app.js
COPY styles.css ./frontend/styles.css

RUN mkdir -p /app/backend/work

RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs')" || true

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
