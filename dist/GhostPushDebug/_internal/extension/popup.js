/**
 * GhostPush Extension Popup Script
 */

const API_BASE = "http://127.0.0.1:8000/api/v1";
const WS_URL = "ws://127.0.0.1:8000/api/v1/ws/notifications";

let currentJobId = null;
let ws = null;

document.addEventListener("DOMContentLoaded", async () => {
  await checkBackendStatus();
  await loadDefaultConfig();
  setupEventListeners();
  connectWebSocket();
});

async function checkBackendStatus() {
  const statusEl = document.getElementById("backend-status");
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      const data = await res.json();
      statusEl.textContent = `Online (v${data.api_version})`;
      statusEl.className = "status-badge status-online";
    } else {
      throw new Error();
    }
  } catch {
    statusEl.textContent = "Offline (Backend)";
    statusEl.className = "status-badge status-offline";
  }
}

async function loadDefaultConfig() {
  try {
    const res = await fetch(`${API_BASE}/config`);
    if (res.ok) {
      const config = await res.json();
      if (config.repository_path) {
        document.getElementById("repo-path").value = config.repository_path;
      }
    }
  } catch (e) {
    console.log("[GhostPush] Could not fetch default config:", e);
  }
}

function setupEventListeners() {
  document.getElementById("btn-autofill").addEventListener("click", extractFromCurrentTab);
  document.getElementById("submission-form").addEventListener("submit", handleFormSubmit);
}

async function extractFromCurrentTab() {
  if (typeof chrome !== "undefined" && chrome.tabs) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id) {
      chrome.tabs.sendMessage(tab.id, { action: "extract_problem" }, (response) => {
        if (chrome.runtime.lastError || !response) {
          alert("Could not extract metadata from current page. Please enter details manually.");
          return;
        }
        if (response.platform) document.getElementById("platform").value = response.platform;
        if (response.title) document.getElementById("title").value = response.title;
        if (response.difficulty) document.getElementById("difficulty").value = response.difficulty;
        if (response.language) document.getElementById("language").value = response.language;
        if (response.tags) document.getElementById("tags").value = response.tags.join(", ");
        if (response.code) document.getElementById("code").value = response.code;
      });
    }
  }
}

function generateJobId() {
  const ts = Math.floor(Date.now() / 1000);
  const rand = Math.floor(Math.random() * 9000 + 1000);
  return `JOB-EXT-${ts}-${rand}`;
}

async function handleFormSubmit(e) {
  e.preventDefault();

  const jobId = generateJobId();
  currentJobId = jobId;

  const platform = document.getElementById("platform").value;
  const title = document.getElementById("title").value.trim();
  const difficulty = document.getElementById("difficulty").value;
  const language = document.getElementById("language").value;
  const tagsRaw = document.getElementById("tags").value.trim();
  const tags = tagsRaw ? tagsRaw.split(",").map(t => t.trim()).filter(Boolean) : [];
  const code = document.getElementById("code").value;
  const repoPath = document.getElementById("repo-path").value.trim();

  const payload = {
    api_version: "1.0",
    job_id: jobId,
    platform: platform,
    problem: {
      title: title,
      difficulty: difficulty,
      url: window.location ? window.location.href : "",
      tags: tags
    },
    solution: {
      language: language,
      code: code
    },
    repository_path: repoPath
  };

  showProgress(jobId, "QUEUED", "Submitting job to GhostPush backend...");

  try {
    const res = await fetch(`${API_BASE}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Submission failed");
    }

    const jobResult = await res.json();
    showProgress(jobId, jobResult.status || "QUEUED", "Job enqueued successfully!");
  } catch (err) {
    showProgress(jobId, "FAILED", `Error: ${err.message}`);
  }
}

function connectWebSocket() {
  try {
    ws = new WebSocket(WS_URL);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (currentJobId && data.job_id === currentJobId) {
          showProgress(data.job_id, data.status, data.message);
        }
      } catch (e) {
        console.warn("[GhostPush] WebSocket message parse error:", e);
      }
    };
    ws.onclose = () => {
      // Reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };
  } catch (e) {
    console.warn("[GhostPush] WebSocket connection failed:", e);
  }
}

function showProgress(jobId, status, message) {
  const container = document.getElementById("progress-container");
  const idDisplay = document.getElementById("job-id-display");
  const statusBadge = document.getElementById("job-status-badge");
  const logMessage = document.getElementById("log-message");

  container.style.display = "block";
  idDisplay.textContent = `Job: ${jobId}`;
  statusBadge.textContent = status;
  logMessage.textContent = message;

  if (status === "COMPLETED" || status === "SUCCESS") {
    statusBadge.style.background = "rgba(16, 185, 129, 0.2)";
    statusBadge.style.color = "#10b981";
  } else if (status === "FAILED") {
    statusBadge.style.background = "rgba(239, 68, 68, 0.2)";
    statusBadge.style.color = "#ef4444";
  } else {
    statusBadge.style.background = "rgba(99, 102, 241, 0.2)";
    statusBadge.style.color = "#818cf8";
  }
}
