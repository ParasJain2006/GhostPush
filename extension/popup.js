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

function isSupportedUrl(url) {
  if (!url || typeof url !== "string") return false;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return (
      hostname.endsWith("leetcode.com") ||
      hostname.endsWith("geeksforgeeks.org") ||
      hostname.endsWith("codeforces.com") ||
      hostname.endsWith("hackerrank.com")
    );
  } catch (e) {
    return false;
  }
}

function sendMessagePromise(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

function injectContentScript(tabId) {
  return new Promise((resolve, reject) => {
    if (typeof chrome !== "undefined" && chrome.scripting && chrome.scripting.executeScript) {
      chrome.scripting.executeScript(
        {
          target: { tabId: tabId },
          files: ["content.js"]
        },
        (results) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(results);
          }
        }
      );
    } else {
      reject(new Error("chrome.scripting API not available"));
    }
  });
}

/**
 * Fetches Monaco editor code and language selector text from the page's MAIN
 * JavaScript world. Content scripts run in an isolated world and cannot access
 * window.monaco directly; chrome.scripting.executeScript with world:'MAIN'
 * bridges that gap.
 *
 * Returns { code: string|null, langText: string|null } or null on failure.
 */
async function getLeetCodeEditorData(tabId) {
  if (
    typeof chrome === "undefined" ||
    !chrome.scripting ||
    !chrome.scripting.executeScript
  ) {
    return null;
  }
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tabId },
      world: "MAIN",
      func: () => {
        // --- Code via Monaco model API ---
        let code = null;
        try {
          if (window.monaco && window.monaco.editor) {
            const models = window.monaco.editor.getModels();
            if (models && models.length > 0) {
              // Prefer the model whose URI suggests it's the solution file.
              // LeetCode names models like "solution.java", "solution.py" etc.
              const solutionModel = models.find(m =>
                m.uri && /solution\.|Solution\.|code\./.test(m.uri.path || m.uri.toString()))
                || models[0];
              code = solutionModel.getValue();
            }
          }
        } catch (e) {
          // Monaco not available or not ready
          code = null;
        }

        // --- Language via LeetCode's language picker ---
        // LeetCode renders the currently selected language inside a button/div
        // in the editor toolbar. We read it here in the MAIN world where the
        // React state is populated.
        let langText = null;
        try {
          // Try multiple known selectors in priority order
          const candidates = [
            // Current LeetCode design (headlessui popover button containing the language)
            document.querySelector("button[id*='headlessui-popover-button']"),
            // Alternate: look for element whose text matches known language names
            // inside the editor area
            document.querySelector("[data-cy='lang-select']"),
            document.querySelector("div[class*='ant-select-selection-selected-value']"),
          ];
          for (const el of candidates) {
            if (el && el.textContent && el.textContent.trim()) {
              langText = el.textContent.trim();
              break;
            }
          }

          // If above selectors failed, try inferring from Monaco model URI
          // (e.g., solution.java -> "Java", solution.py -> "Python")
          if (!langText && code !== null) {
            try {
              const models = window.monaco && window.monaco.editor.getModels();
              const mdl = models && (models.find(m =>
                m.uri && /solution\.|Solution\.|code\./.test(m.uri.path || m.uri.toString()))
                || models[0]);
              if (mdl && mdl.getModeId) {
                langText = mdl.getModeId();
              } else if (mdl && mdl.getLanguageId) {
                // Monaco 0.32+
                langText = mdl.getLanguageId();
              }
            } catch (_) { /* ignore */ }
          }
        } catch (e) {
          langText = null;
        }

        return { code, langText };
      }
    });

    if (results && results[0] && results[0].result) {
      return results[0].result;
    }
    return null;
  } catch (e) {
    console.log("[GhostPush] MAIN-world Monaco extraction failed (non-fatal):", e.message);
    return null;
  }
}

async function ensureContentScript(tabId, tabUrl) {
  // 0. Pre-fetch Monaco data from the page's MAIN world (LeetCode only)
  let monacoData = null;
  const isLeetCode = tabUrl && tabUrl.includes("leetcode.com");
  if (isLeetCode) {
    monacoData = await getLeetCodeEditorData(tabId);
    console.log("[GhostPush] MAIN-world Monaco data:",
      monacoData ? `code=${monacoData.code ? monacoData.code.length + " chars" : "null"}, lang=${monacoData.langText}` : "unavailable"
    );
  }

  // Build the message payload — content.js will use monacoData when present
  const message = { action: "extract_problem", monacoData };

  // 1. Try communicating first with existing content script
  try {
    const response = await sendMessagePromise(tabId, message);
    if (response) return response;
  } catch (firstErr) {
    console.log("[GhostPush] First message attempt failed, checking fallback injection:", firstErr.message);
  }

  // 2. Validate URL is supported before attempting dynamic injection
  if (!isSupportedUrl(tabUrl)) {
    throw new Error("UNSUPPORTED_PAGE");
  }

  // 3. Inject content script into current tab
  try {
    await injectContentScript(tabId);
  } catch (injErr) {
    throw new Error(`Content script injection failed: ${injErr.message}`);
  }

  // 4. Retry extraction message after injection (pass monacoData again)
  try {
    const response = await sendMessagePromise(tabId, message);
    if (response) return response;
    throw new Error("No response received from content script after injection.");
  } catch (retryErr) {
    throw new Error(`Messaging failed after injection: ${retryErr.message}`);
  }
}

let extractedUrl = "";

async function extractFromCurrentTab() {
  if (typeof chrome === "undefined" || !chrome.tabs) return;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      alert("Could not access active tab. Please enter details manually.");
      return;
    }

    const tabUrl = tab.url || "";
    if (tabUrl) extractedUrl = tabUrl;

    if (!isSupportedUrl(tabUrl)) {
      alert("GhostPush metadata extraction is only supported on LeetCode, GeeksforGeeks, Codeforces, and HackerRank.");
      return;
    }

    const response = await ensureContentScript(tab.id, tabUrl);

    if (!response) {
      alert("Could not extract metadata from current page. Please enter details manually.");
      return;
    }

    if (response.url) extractedUrl = response.url;
    if (response.platform) document.getElementById("platform").value = response.platform;
    if (response.title) document.getElementById("title").value = response.title.replace(/^\d+\.\s*/, "").trim();
    if (response.difficulty) document.getElementById("difficulty").value = response.difficulty;
    if (response.language) document.getElementById("language").value = response.language;
    if (response.tags) document.getElementById("tags").value = Array.isArray(response.tags) ? response.tags.join(", ") : response.tags;
    if (response.code) document.getElementById("code").value = response.code;

  } catch (err) {
    if (err.message === "UNSUPPORTED_PAGE") {
      alert("GhostPush metadata extraction is only supported on LeetCode, GeeksforGeeks, Codeforces, and HackerRank.");
    } else {
      console.warn("[GhostPush] Metadata extraction error:", err);
      alert(`Could not extract metadata from current page (${err.message}). Please enter details manually.`);
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
  const rawTitle = document.getElementById("title").value.trim();
  const title = rawTitle.replace(/^\d+\.\s*/, "").trim();
  const difficulty = document.getElementById("difficulty").value;
  const language = document.getElementById("language").value;
  const tagsRaw = document.getElementById("tags").value.trim();
  const tags = tagsRaw ? tagsRaw.split(",").map(t => t.trim()).filter(Boolean) : [];
  const code = document.getElementById("code").value;
  const repoPath = document.getElementById("repo-path").value.trim();

  let problemUrl = extractedUrl;
  if (!problemUrl && typeof chrome !== "undefined" && chrome.tabs) {
    try {
      const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (activeTab && activeTab.url) {
        problemUrl = activeTab.url;
      }
    } catch (e) {
      console.warn("[GhostPush] Could not query active tab URL:", e);
    }
  }

  const payload = {
    api_version: "1.0",
    job_id: jobId,
    platform: platform,
    problem: {
      title: title,
      difficulty: difficulty,
      url: problemUrl,
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
  } else if (status === "FAILED" || status === "ERROR") {
    statusBadge.style.background = "rgba(239, 68, 68, 0.2)";
    statusBadge.style.color = "#ef4444";
  } else if (status === "WARNING") {
    statusBadge.style.background = "rgba(245, 158, 11, 0.2)";
    statusBadge.style.color = "#f59e0b";
  } else {
    statusBadge.style.background = "rgba(99, 102, 241, 0.2)";
    statusBadge.style.color = "#818cf8";
  }
}
