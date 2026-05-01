// CleanAudioTube — Frontend App Logic
// Auto-detects API URL — works on Railway AND locally

const API_BASE = window.location.origin;

let currentJobId = null;
let pollInterval = null;
let selectedMode = "remove_music";

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const urlInput      = document.getElementById("urlInput");
const clearBtn      = document.getElementById("clearBtn");
const processBtn    = document.getElementById("processBtn");
const modeButtons   = document.querySelectorAll(".mode-btn");

const inputSection  = document.getElementById("inputSection");
const progressSec   = document.getElementById("progressSection");
const resultSec     = document.getElementById("resultSection");
const errorSec      = document.getElementById("errorSection");

const progressFill  = document.getElementById("progressFill");
const progressPct   = document.getElementById("progressPct");
const progressLabel = document.getElementById("progressLabel");

const cancelBtn     = document.getElementById("cancelBtn");
const compareToggle = document.getElementById("compareToggle");
const playerLabel   = document.getElementById("playerLabel");
const videoPlayer   = document.getElementById("videoPlayer");
const originalPlayer= document.getElementById("originalPlayer");
const originalWrap  = document.getElementById("originalWrap");
const downloadBtn   = document.getElementById("downloadBtn");
const fileInfo      = document.getElementById("fileInfo");
const resultMeta    = document.getElementById("resultMeta");
const errorMsg      = document.getElementById("errorMsg");
const retryBtn      = document.getElementById("retryBtn");
const newBtn        = document.getElementById("newBtn");

// ─── Step map ─────────────────────────────────────────────────────────────────
const STEP_MAP = {
  downloading: "step-downloading",
  extracting:  "step-extracting",
  separating:  "step-separating",
  merging:     "step-merging",
};

// ─── Mode selection ───────────────────────────────────────────────────────────
modeButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    modeButtons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedMode = btn.dataset.mode;
  });
});

// ─── URL input handling ───────────────────────────────────────────────────────
urlInput.addEventListener("input", () => {
  clearBtn.style.opacity = urlInput.value ? "1" : "0";
});

clearBtn.addEventListener("click", () => {
  urlInput.value = "";
  clearBtn.style.opacity = "0";
  urlInput.focus();
});

urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") startProcessing();
});

// ─── Process ──────────────────────────────────────────────────────────────────
processBtn.addEventListener("click", startProcessing);

async function startProcessing() {
  const url = urlInput.value.trim();

  if (!url) {
    shake(urlInput.closest(".url-input-wrap"));
    return;
  }

  if (!isValidYouTubeUrl(url)) {
    showError("Please enter a valid YouTube URL (youtube.com or youtu.be)");
    return;
  }

  try {
    processBtn.disabled = true;
    processBtn.querySelector(".btn-text").textContent = "Submitting...";

    const res = await fetch(`${API_BASE}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, mode: selectedMode }),
    });

    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || "Failed to start processing");
    }

    const data = await res.json();
    currentJobId = data.job_id;

    showSection("progress");
    startPolling(currentJobId);
  } catch (err) {
    processBtn.disabled = false;
    processBtn.querySelector(".btn-text").textContent = "Process Video";
    showErrorSection(err.message);
  }
}

// ─── Polling ──────────────────────────────────────────────────────────────────
function startPolling(jobId) {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(() => pollStatus(jobId), 1500);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function pollStatus(jobId) {
  try {
    const res = await fetch(`${API_BASE}/status/${jobId}`);
    if (!res.ok) throw new Error("Status check failed");

    const data = await res.json();
    updateProgress(data);

    if (data.status === "complete") {
      stopPolling();
      showResults(data);
    } else if (data.status === "error") {
      stopPolling();
      showErrorSection(data.error || "An unexpected error occurred");
    }
  } catch (err) {
    console.error("Poll error:", err);
    // Keep polling — transient network error
  }
}

function updateProgress(data) {
  const pct = data.progress || 0;
  progressFill.style.width = `${pct}%`;
  progressPct.textContent = `${pct}%`;
  progressLabel.textContent = data.message || "Processing...";

  // Update steps
  Object.entries(STEP_MAP).forEach(([status, stepId]) => {
    const el = document.getElementById(stepId);
    if (!el) return;
    el.classList.remove("active", "done");

    const order = Object.keys(STEP_MAP);
    const statusIdx = order.indexOf(status);
    const currentIdx = order.indexOf(data.status);

    if (statusIdx < currentIdx) {
      el.classList.add("done");
    } else if (status === data.status) {
      el.classList.add("active");
    }
  });
}

// ─── Results ──────────────────────────────────────────────────────────────────
function showResults(data) {
  showSection("result");

  const cleanUrl   = `${API_BASE}/preview/${currentJobId}`;
  const origUrl    = `${API_BASE}/preview-original/${currentJobId}`;
  const downloadUrl= `${API_BASE}/download/${currentJobId}`;

  videoPlayer.src = cleanUrl;
  originalPlayer.src = origUrl;
  downloadBtn.href = downloadUrl;

  if (data.file_size) {
    fileInfo.textContent = `MP4 · ${formatBytes(data.file_size)}`;
  }

  if (data.duration) {
    resultMeta.textContent = `${formatDuration(data.duration)} video`;
  }

  processBtn.disabled = false;
  processBtn.querySelector(".btn-text").textContent = "Process Video";
}

// ─── Compare toggle ───────────────────────────────────────────────────────────
compareToggle.addEventListener("change", () => {
  if (compareToggle.checked) {
    originalWrap.classList.remove("hidden");
    playerLabel.textContent = "CLEANED VIDEO";
  } else {
    originalWrap.classList.add("hidden");
  }
});

// ─── Cancel ───────────────────────────────────────────────────────────────────
cancelBtn.addEventListener("click", () => {
  stopPolling();
  if (currentJobId) {
    fetch(`${API_BASE}/job/${currentJobId}`, { method: "DELETE" }).catch(() => {});
    currentJobId = null;
  }
  showSection("input");
  processBtn.disabled = false;
  processBtn.querySelector(".btn-text").textContent = "Process Video";
});

// ─── Retry / New ─────────────────────────────────────────────────────────────
retryBtn.addEventListener("click", () => {
  showSection("input");
  processBtn.disabled = false;
  processBtn.querySelector(".btn-text").textContent = "Process Video";
});

newBtn.addEventListener("click", () => {
  videoPlayer.src = "";
  originalPlayer.src = "";
  urlInput.value = "";
  clearBtn.style.opacity = "0";
  currentJobId = null;
  showSection("input");
  processBtn.disabled = false;
  processBtn.querySelector(".btn-text").textContent = "Process Video";
});

// ─── Section management ───────────────────────────────────────────────────────
function showSection(name) {
  [inputSection, progressSec, resultSec, errorSec].forEach(el => el.classList.add("hidden"));
  const map = {
    input:    inputSection,
    progress: progressSec,
    result:   resultSec,
    error:    errorSec,
  };
  const el = map[name];
  if (el) {
    el.classList.remove("hidden");
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function showErrorSection(msg) {
  errorMsg.textContent = msg;
  showSection("error");
  processBtn.disabled = false;
  processBtn.querySelector(".btn-text").textContent = "Process Video";
}

function showError(msg) {
  // Inline error on input — brief flash
  const note = document.querySelector(".input-note");
  const orig = note.textContent;
  note.style.color = "#ff4560";
  note.textContent = "⚠ " + msg;
  setTimeout(() => {
    note.style.color = "";
    note.textContent = orig;
  }, 3000);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function isValidYouTubeUrl(url) {
  return /^https?:\/\/(www\.)?(youtube\.com\/watch\?|youtu\.be\/|youtube\.com\/shorts\/)/.test(url);
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 ** 3)   return `${(bytes / (1024**2)).toFixed(1)} MB`;
  return `${(bytes / (1024**3)).toFixed(2)} GB`;
}

function formatDuration(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s}s`;
}

function shake(el) {
  el.style.animation = "none";
  el.getBoundingClientRect();
  el.style.animation = "shake 0.4s ease";
  setTimeout(() => { el.style.animation = ""; }, 400);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
clearBtn.style.opacity = "0";

// Add shake keyframe dynamically
const style = document.createElement("style");
style.textContent = `
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%       { transform: translateX(-6px); }
  40%       { transform: translateX(6px); }
  60%       { transform: translateX(-4px); }
  80%       { transform: translateX(4px); }
}
`;
document.head.appendChild(style);
