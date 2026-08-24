/**
 * GhostPush Background Service Worker (Manifest V3)
 * Phase 12A: relay for automatic LeetCode Accepted job creation.
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("[GhostPush] Extension background service worker initialized.");
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ping") {
    sendResponse({ status: "pong", version: "1.0.0" });
    return true;
  }

  if (request.action === "ghostpush_auto_submit") {
    // Security: only accept from LeetCode tabs (or extension itself for tests).
    // sender.tab may be undefined in tests; allow when no tab (extension contexts).
    try {
      const tabUrl = sender && sender.tab && sender.tab.url ? sender.tab.url : "";
      if (tabUrl && !tabUrl.includes("leetcode.com")) {
        console.warn("[GhostPush][Background] Rejected auto_submit from non-LeetCode sender:", tabUrl);
        sendResponse({ ok: false, error: "Only LeetCode pages may trigger automatic sync" });
        return true;
      }
    } catch (_e) { /* allow */ }

    (async () => {
      try {
        const payload = request.payload;
        if (!payload || !payload.solution || !payload.solution.code) {
          sendResponse({ ok: false, error: "Missing solution code — failing closed" });
          return;
        }
        if (!payload.problem || !payload.problem.url || !payload.platform) {
          sendResponse({ ok: false, error: "Missing problem identity — failing closed" });
          return;
        }

        // Fill repository_path from backend config if not provided
        let repoPath = payload.repository_path;
        if (!repoPath) {
          try {
            const cfgRes = await fetch("http://127.0.0.1:8000/api/v1/config");
            if (cfgRes.ok) {
              const cfg = await cfgRes.json();
              repoPath = cfg.repository_path || cfg.repositoryPath || "";
            }
          } catch (e) {
            console.warn("[GhostPush][Background] Could not fetch repository_path from config:", e);
          }
        }
        if (!repoPath) {
          // Try chrome.storage for last known path (survives backend down)
          try {
            const stored = await new Promise(resolve => {
              chrome.storage.local.get(["ghostpush_repo_path"], resolve);
            });
            if (stored && stored.ghostpush_repo_path) repoPath = stored.ghostpush_repo_path;
          } catch (_e) { /* ignore */ }
        }
        if (!repoPath) {
          sendResponse({ ok: false, error: "Missing repository_path — configure in Tray App" });
          return;
        }
        payload.repository_path = repoPath;
        // Cache for next time
        try { chrome.storage.local.set({ ghostpush_repo_path: repoPath }); } catch (_e) {}

        // POST to backend job queue (reuse existing contract)
        const res = await fetch("http://127.0.0.1:8000/api/v1/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const bodyText = await res.text();
        let bodyJson = null;
        try { bodyJson = JSON.parse(bodyText); } catch (_e) { bodyJson = { raw: bodyText }; }

        if (!res.ok) {
          const detail = (bodyJson && (bodyJson.detail || bodyJson.message)) || bodyText || ("HTTP " + res.status);
          sendResponse({ ok: false, error: detail });
          return;
        }

        const jobId = (bodyJson && (bodyJson.job_id || bodyJson.jobId)) || payload.job_id;
        console.log("[GhostPush][Background] Automatic job created job_id=" + jobId + " dedupKey=" + (request.dedupKey || ""));
        sendResponse({ ok: true, jobId: jobId, status: bodyJson && bodyJson.status ? bodyJson.status : "QUEUED" });
      } catch (e) {
        console.warn("[GhostPush][Background] auto_submit error:", e);
        sendResponse({ ok: false, error: String(e && e.message ? e.message : e) });
      }
    })();
    // Keep channel open for async response
    return true;
  }

  return true;
});
