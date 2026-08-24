/**
 * GhostPush Content Script
 * Extracts problem title, difficulty, tags, and solution code from supported CP platforms.
 * Phase 12A: Automatic LeetCode Accepted-submission sync via SubmissionMonitor.
 */

(function () {
  if (window.__ghostPushContentScriptInjected) return;
  window.__ghostPushContentScriptInjected = true;

  // Listen for extraction requests from popup.js.
  // The message may optionally carry { monacoData: { code, langText } }
  // pre-fetched by popup.js via chrome.scripting MAIN-world execution.
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extract_problem") {
      const data = extractPageMetadata(request.monacoData || null);
      sendResponse(data);
    }
    if (request.action === "ghostpush_autojob_result") {
      // Ack from background after auto job creation — used for logging.
      sendResponse({ received: true });
    }
    return true;
  });

  /**
   * Normalize a raw language label from the LeetCode selector or Monaco model
   * language ID into GhostPush's language enum values.
   * Returns null if no match found (caller falls back to code heuristics).
   */
  function normalizeLangText(raw) {
    if (!raw || typeof raw !== "string") return null;
    const norm = raw.trim().toLowerCase();
    // Exact matches first
    if (norm === "c++" || norm === "cpp") return "cpp";
    if (norm === "java") return "java";
    // "python3" or "python"
    if (norm.startsWith("python")) return "python";
    if (norm === "javascript" || norm === "js") return "javascript";
    if (norm === "typescript" || norm === "ts") return "typescript";
    if (norm === "golang" || norm === "go") return "go";
    if (norm === "rust") return "rust";
    if (norm === "kotlin") return "kotlin";
    if (norm === "swift") return "swift";
    if (norm === "scala") return "scala";
    if (norm === "ruby") return "ruby";
    if (norm === "php") return "php";
    if (norm === "c") return "c";
    if (norm === "racket") return "racket";
    if (norm === "erlang") return "erlang";
    if (norm === "elixir") return "elixir";
    if (norm === "dart") return "dart";
    // Partial / compound labels like "C++ (GCC)" or "Python3 (3.12)"
    if (norm.includes("c++") || norm.includes("cpp")) return "cpp";
    if (norm.includes("java") && !norm.includes("javascript")) return "java";
    if (norm.includes("python")) return "python";
    if (norm.includes("javascript") || (norm.includes("js") && !norm.includes("json"))) return "javascript";
    if (norm.includes("typescript")) return "typescript";
    if (norm.includes("kotlin")) return "kotlin";
    if (norm.includes("rust")) return "rust";
    if (norm.includes("swift")) return "swift";
    if (norm.includes("golang") || norm.includes(" go")) return "go";
    return null;
  }

  /**
   * Code-based language heuristics — used as FALLBACK only when no selector
   * or MAIN-world language text is available.
   */
  function detectLanguageFromCode(code) {
    if (!code || typeof code !== "string") return "python";

    // C++ heuristics (check first to distinguish C++ class Solution from Java)
    if (/#include\s*<|\bstd::|\bvector\s*<|\bpublic\s*:/.test(code)) {
      return "cpp";
    }

    // Java heuristics
    if (
      /\bpublic\s+class\b/.test(code) ||
      /\bimport\s+java\./.test(code) ||
      /\bSystem\.out\./.test(code) ||
      /\bnew\s+int\s*\[/.test(code) ||
      /\bint\s*\[\s*\]/.test(code) ||
      /\bpublic\s+(static\s+)?(int|void|boolean|String|double|float|long|int\[\]|List|TreeNode|ListNode)\b/.test(code) ||
      (/\bclass\s+Solution\b/.test(code) && !/\bclass\s+Solution\s*:/.test(code))
    ) {
      return "java";
    }

    // Python heuristics
    if (
      /\bdef\s+\w+\s*\(/.test(code) ||
      /\bclass\s+Solution\s*:/.test(code) ||
      /\bfrom\s+typing\b/.test(code) ||
      /\bimport\s+typing\b/.test(code) ||
      /\bself\./.test(code)
    ) {
      return "python";
    }

    // JS / TS heuristics
    if (/\b(function|const|let|var)\b/.test(code)) {
      if (/\b(interface|type)\s+\w+/.test(code) || /:\s*(number|string|boolean)\[\]?/.test(code)) {
        return "typescript";
      }
      return "javascript";
    }

    return "python";
  }

  /**
   * Determine language.
   * Priority: normalizeLangText(domText) > detectLanguageFromCode(code)
   */
  function detectLanguage(domText, code) {
    const fromDom = normalizeLangText(domText);
    if (fromDom) return fromDom;
    return detectLanguageFromCode(code);
  }

  /**
   * Main extraction entry point.
   * @param {Object|null} monacoData - Optional pre-fetched data from MAIN world:
   *   { code: string|null, langText: string|null }
   *   When provided, code and langText take priority over DOM/heuristic fallbacks.
   */
  function extractPageMetadata(monacoData) {
    const url = window.location.href;
    let platform = "leetcode";

    if (url.includes("geeksforgeeks.org")) {
      platform = "gfg";
    } else if (url.includes("codeforces.com")) {
      platform = "codeforces";
    } else if (url.includes("hackerrank.com")) {
      platform = "hackerrank";
    }

    let title = "";
    let difficulty = "Easy";
    let tags = [];
    let language = "python";
    let code = "";

    try {
      if (platform === "leetcode") {
        // --- Title ---
        const titleEl = document.querySelector("div[class*='text-title-large'] a, span[class*='title']");
        title = titleEl ? titleEl.textContent.trim() : document.title.split("-")[0].trim();

        // --- Difficulty ---
        const diffEl = document.querySelector("div[class*='text-difficulty']");
        if (diffEl) {
          difficulty = diffEl.textContent.trim();
        }

        // --- Tags ---
        const tagEls = document.querySelectorAll("a[href*='/tag/']");
        tags = Array.from(tagEls).map(el => el.textContent.trim()).filter(Boolean);

        // --- Language ---
        // Priority 1: MAIN-world langText (from popup.js MAIN-world execution or auto bridge)
        // Priority 2: Isolated-world DOM selector
        // Priority 3: Code heuristics
        let domLangText = "";

        if (monacoData && monacoData.langText) {
          // Highest priority: actual selector text captured from page context
          domLangText = monacoData.langText;
        } else {
          // Fallback: read language button from isolated DOM using targeted selectors
          // Ordered from most specific to least, avoiding generic button[class*='rounded']
          const langSelectors = [
            // LeetCode's headlessui language popover button (current design)
            "button[id*='headlessui-popover-button']",
            // data-cy attribute (older LeetCode versions)
            "[data-cy='lang-select']",
            // ant-design select (older UI)
            "div[class*='ant-select-selection-selected-value']",
            // LeetCode 2024 redesign: language button inside the editor toolbar
            "div[class*='editor'] button[class*='dropdown']",
            "div[class*='editor-toolbar'] button",
          ];
          for (const sel of langSelectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent.trim()) {
              domLangText = el.textContent.trim();
              break;
            }
          }
        }

        // --- Code ---
        // Priority 1: MAIN-world Monaco model getValue() (complete buffer)
        // Priority 2: Visible .view-lines DOM (partial — only rendered viewport)
        if (monacoData && monacoData.code && monacoData.code.trim()) {
          code = monacoData.code;
        } else {
          // Fallback: visible rendered lines only (incomplete for large files)
          const codeLines = document.querySelectorAll(".view-lines .view-line");
          if (codeLines.length > 0) {
            code = Array.from(codeLines).map(l => l.textContent).join("\n");
          }
        }

        // Determine language: langText > code heuristics
        language = detectLanguage(domLangText, code);

      } else if (platform === "gfg") {
        // GFG extraction
        const titleEl = document.querySelector("h3[class*='problem-tab']");
        title = titleEl ? titleEl.textContent.trim() : document.title.split("|")[0].trim();

        const diffEl = document.querySelector("span[class*='difficulty']");
        if (diffEl) {
          difficulty = diffEl.textContent.trim();
        }
      } else {
        // Fallback for title on other platforms
        title = document.title.split("-")[0].split("|")[0].trim();
      }
    } catch (e) {
      console.warn("[GhostPush] Metadata extraction warning:", e);
    }

    return {
      platform,
      title: title || "Unknown Problem",
      difficulty: difficulty || "Easy",
      url,
      tags: tags.length > 0 ? tags : ["Algorithm"],
      language,
      code
    };
  }

  // =============================================================
  // Phase 12A: Automatic LeetCode Accepted-Submission Sync
  // =============================================================

  // ----- Pure helpers exported for testing via window.__ghostPushTestHelpers -----
  function normalizeProblemUrl(url) {
    if (!url || typeof url !== "string") return "";
    try {
      const u = new URL(url);
      // Keep origin + pathname without trailing slash, lowercase path for dedup.
      let path = u.pathname.replace(/\/+$/, "");
      // For LeetCode problems, canonicalize to /problems/<slug>/ form without extra segments
      // e.g., https://leetcode.com/problems/two-sum/submissions/ -> https://leetcode.com/problems/two-sum
      const m = path.match(/\/problems\/[^\/]+/);
      if (m) path = m[0];
      return (u.origin + path).toLowerCase();
    } catch (_e) {
      return url.trim().toLowerCase();
    }
  }

  function isLeetCodeProblemPage(url) {
    if (!url || typeof url !== "string") return false;
    return url.includes("leetcode.com/problems/");
  }

  function classifySubmissionStatus(statusMsg, state) {
    if (!statusMsg && !state) return "Unknown";
    const msg = (statusMsg || "").trim();
    const st = (state || "").trim();
    // Only exact Accepted with SUCCESS/PENDING resolved to SUCCESS triggers sync.
    // All other states are ignored (fail closed).
    if (msg === "Accepted" && (st === "SUCCESS" || st === "")) return "Accepted";
    // Normalize known ignored states
    const ignored = new Set([
      "Wrong Answer",
      "Runtime Error",
      "Compile Error",
      "Time Limit Exceeded",
      "Memory Limit Exceeded",
      "Output Limit Exceeded",
      "Pending",
      "Running",
      "Processing",
      "Unknown"
    ]);
    if (ignored.has(msg)) return msg;
    if (msg === "Test Case Passed" || msg === "All test cases passed" || msg === "All Test Cases Passed") return "Test Case Passed";
    if (st === "PENDING" || st === "STARTED") return "Pending";
    return "Unknown";
  }

  function isAcceptedStatus(statusMsg, state) {
    return classifySubmissionStatus(statusMsg, state) === "Accepted";
  }

  function buildDedupKeySync(platform, normalizedUrl, submissionId, language, codeHash) {
    if (submissionId) {
      return platform + ":" + normalizedUrl + ":" + String(submissionId);
    }
    return platform + ":" + normalizedUrl + ":" + language + ":" + codeHash;
  }

  async function sha256Hex(text) {
    if (!text) return "";
    try {
      if (window.crypto && window.crypto.subtle && window.crypto.subtle.digest) {
        const enc = new TextEncoder().encode(text);
        const buf = await window.crypto.subtle.digest("SHA-256", enc);
        const arr = Array.from(new Uint8Array(buf));
        return arr.map(b => b.toString(16).padStart(2, "0")).join("");
      }
    } catch (_e) { /* fallback below */ }
    // Fallback: simple hash (not cryptographically strong, but deterministic for dedup fallback)
    let h = 0;
    for (let i = 0; i < text.length; i++) {
      h = ((h << 5) - h + text.charCodeAt(i)) | 0;
    }
    return "fallback-" + Math.abs(h).toString(16);
  }

  function generateJobId() {
    const ts = Math.floor(Date.now() / 1000);
    const rand = Math.floor(Math.random() * 9000 + 1000);
    return "JOB-EXT-" + ts + "-" + rand;
  }

  // Expose helpers for testing (not for page consumption)
  try {
    window.__ghostPushTestHelpers = {
      normalizeLangText,
      detectLanguageFromCode,
      detectLanguage,
      normalizeProblemUrl,
      isLeetCodeProblemPage,
      classifySubmissionStatus,
      isAcceptedStatus,
      buildDedupKeySync,
      generateJobId
    };
  } catch (_e) { /* ignore */ }

  // ----- Submission Monitor (singleton, LeetCode only) -----
  if (window.__ghostPushSubmissionMonitorStarted) {
    console.log("[GhostPush][SubmissionMonitor] Monitor already started — skipping duplicate init");
  } else {
    window.__ghostPushSubmissionMonitorStarted = true;

    const LOG_PREFIX = "[GhostPush][SubmissionMonitor]";
    const DEDUP_STORAGE_KEY = "ghostpush_seen_submissions";
    const PENDING_TTL_MS = 5 * 60 * 1000; // 5 minutes

    // Only activate on LeetCode problem pages; still install lightweight SPA watcher elsewhere
    // so navigation to a problem page starts monitoring.
    let currentProblemUrl = window.location.href;
    let currentNormalizedUrl = normalizeProblemUrl(currentProblemUrl);
    let pendingSubmissions = new Map(); // submissionId -> { timestamp, url }
    let pendingSubmitFlag = null; // { timestamp, url } for submit without id
    let lastSeenUrl = window.location.href;

    function logEvent(status, message, extra) {
      const ts = new Date().toISOString();
      const idPart = extra && extra.submissionId ? " id=" + extra.submissionId : "";
      const dur = extra && extra.durationMs ? " duration=" + extra.durationMs + "ms" : "";
      console.log(LOG_PREFIX + " " + status + " ts=" + ts + idPart + dur + " " + message);
    }

    function isOnLeetCodeProblem() {
      return isLeetCodeProblemPage(window.location.href);
    }

    function resetProblemStateIfChanged() {
      const nowUrl = window.location.href;
      if (nowUrl !== lastSeenUrl) {
        const oldNorm = currentNormalizedUrl;
        const newNorm = normalizeProblemUrl(nowUrl);
        if (oldNorm !== newNorm) {
          logEvent("SPA_NAV", "Problem changed from " + oldNorm + " to " + newNorm, null);
          // Clear pending submissions from previous problem — they must not bleed.
          pendingSubmissions.clear();
          pendingSubmitFlag = null;
          currentProblemUrl = nowUrl;
          currentNormalizedUrl = newNorm;
        }
        lastSeenUrl = nowUrl;
      }
    }

    // Lightweight SPA detection: patch history + popstate + MutationObserver on title
    (function installSpaWatcher() {
      try {
        const origPush = history.pushState;
        const origReplace = history.replaceState;
        if (origPush) {
          history.pushState = function () {
            const ret = origPush.apply(this, arguments);
            window.dispatchEvent(new Event("ghostpush_locationchange"));
            return ret;
          };
        }
        if (origReplace) {
          history.replaceState = function () {
            const ret = origReplace.apply(this, arguments);
            window.dispatchEvent(new Event("ghostpush_locationchange"));
            return ret;
          };
        }
        window.addEventListener("popstate", () => window.dispatchEvent(new Event("ghostpush_locationchange")));
        window.addEventListener("ghostpush_locationchange", () => {
          setTimeout(resetProblemStateIfChanged, 100);
        });
        // Also observe title changes (LeetCode updates title on SPA nav)
        const titleEl = document.querySelector("title");
        if (titleEl) {
          const obs = new MutationObserver(() => resetProblemStateIfChanged());
          obs.observe(titleEl, { childList: true, subtree: true, characterData: true });
        }
        // Fallback lightweight poll but throttled to 2000ms and only check URL string, no DOM work
        setInterval(resetProblemStateIfChanged, 2000);
      } catch (e) {
        console.warn(LOG_PREFIX + " SPA watcher install failed", e);
      }
    })();

    // ----- Dedup storage helpers (chrome.storage.local with fallback) -----
    async function isDuplicateDedupKey(key) {
      try {
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          const data = await new Promise(resolve => {
            try {
              chrome.storage.local.get([DEDUP_STORAGE_KEY], resolve);
            } catch (_e) { resolve({}); }
          });
          const map = (data && data[DEDUP_STORAGE_KEY]) || {};
          return !!map[key];
        }
      } catch (_e) { /* fallback */ }
      try {
        const raw = window.localStorage.getItem(DEDUP_STORAGE_KEY);
        if (raw) {
          const map = JSON.parse(raw);
          return !!map[key];
        }
      } catch (_e) { /* ignore */ }
      return false;
    }

    async function markSeenDedupKey(key) {
      try {
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          const data = await new Promise(resolve => {
            try { chrome.storage.local.get([DEDUP_STORAGE_KEY], resolve); } catch (_e) { resolve({}); }
          });
          const map = (data && data[DEDUP_STORAGE_KEY]) || {};
          map[key] = Date.now();
          // Prune entries older than 30 days to bound storage
          const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
          for (const k of Object.keys(map)) {
            if (map[k] < cutoff) delete map[k];
          }
          await new Promise(resolve => {
            try { chrome.storage.local.set({ [DEDUP_STORAGE_KEY]: map }, resolve); } catch (_e) { resolve(); }
          });
          return;
        }
      } catch (_e) { /* fallback */ }
      try {
        const raw = window.localStorage.getItem(DEDUP_STORAGE_KEY);
        const map = raw ? JSON.parse(raw) : {};
        map[key] = Date.now();
        window.localStorage.setItem(DEDUP_STORAGE_KEY, JSON.stringify(map));
      } catch (_e) { /* ignore */ }
    }

    // ----- MAIN-world bridge injection -----
    // Inject a <script> that runs in MAIN world to patch fetch/XHR and serve editor data.
    function injectMainWorldBridge() {
      if (document.getElementById("ghostpush-main-bridge")) return;
      const script = document.createElement("script");
      script.id = "ghostpush-main-bridge";
      script.textContent = "(" + function () {
        if (window.__ghostPushMainBridgeInstalled) return;
        window.__ghostPushMainBridgeInstalled = true;

        // Helper to post to content script
        function notifyContent(msg) {
          try { window.postMessage(Object.assign({ source: "ghostpush-main" }, msg), "*"); } catch (_e) { }
        }

        function isSubmitUrl(url) {
          if (!url) return false;
          const u = String(url).toLowerCase();
          // LeetCode submit endpoints: /problems/<slug>/submit or graphql with questionSubmit
          if (u.includes("/submit") && !u.includes("interpret") && !u.includes("run")) return true;
          return false;
        }
        function isRunUrl(url) {
          if (!url) return false;
          const u = String(url).toLowerCase();
          if (u.includes("interpret") || u.includes("/run/") || u.includes("runcode")) return true;
          return false;
        }
        function isCheckUrl(url) {
          if (!url) return false;
          const u = String(url).toLowerCase();
          if (u.includes("/check") || u.includes("submissions/detail") || u.includes("submissiondetails") || u.includes("submissions_detail")) return true;
          return false;
        }
        function bodyContainsSubmit(body) {
          if (!body || typeof body !== "string") return false;
          const b = body.toLowerCase();
          // GraphQL submit markers; interpret markers must be checked first
          if (b.includes("interpret") || b.includes("runcode") || b.includes("testcase")) return false;
          if (b.includes("questionsubmit") || b.includes("submitcode") || (b.includes("questionid") && b.includes("lang"))) return true;
          return false;
        }
        function bodyContainsRun(body) {
          if (!body || typeof body !== "string") return false;
          const b = body.toLowerCase();
          return b.includes("interpret") || b.includes("runcode") || b.includes("testcase");
        }

        // Extract submission id from submit response JSON
        function extractSubmissionId(json, url) {
          try {
            if (!json || typeof json !== "object") return null;
            if (json.submission_id) return String(json.submission_id);
            if (json.submissionId) return String(json.submissionId);
            if (json.id) return String(json.id);
            if (json.data) {
              if (json.data.questionSubmit && json.data.questionSubmit.submissionId) return String(json.data.questionSubmit.submissionId);
              if (json.data.submitCode && json.data.submitCode.submissionId) return String(json.data.submitCode.submissionId);
              if (json.data.questionId) return null;
            }
            // Check URL for id: /submissions/detail/<id>/check
            const m = String(url || "").match(/\/submissions\/detail\/(\d+)\/check/);
            if (m) return m[1];
            const m2 = String(url || "").match(/submission[_-]?id[^0-9]*(\d+)/i);
            if (m2) return m2[1];
          } catch (_e) { }
          return null;
        }

        function extractCheckResult(json, url) {
          try {
            if (!json || typeof json !== "object") return null;
            // LeetCode /check endpoint: { state: "SUCCESS", status_msg: "Accepted", ... }
            if (json.state || json.status_msg || json.statusMsg || json.displayStatus) {
              const state = json.state || json.status || "";
              const msg = json.status_msg || json.statusMsg || json.displayStatus || json.statusDisplay || "";
              const sid = extractSubmissionId(json, url) || json.submission_id || json.submissionId || null;
              return { state: String(state), status_msg: String(msg), submissionId: sid ? String(sid) : null };
            }
            if (json.data) {
              // GraphQL submissionDetails
              const d = json.data;
              const node = d.submissionDetails || d.submissionDetail || d.submission || d.questionSubmissionDetail || null;
              if (node) {
                const state = node.status || node.state || "";
                const msg = node.statusMsg || node.status_msg || node.displayStatus || "";
                return { state: String(state), status_msg: String(msg), submissionId: node.id ? String(node.id) : extractSubmissionId(json, url) };
              }
            }
          } catch (_e) { }
          return null;
        }

        // Patch fetch
        try {
          const origFetch = window.fetch;
          if (origFetch) {
            window.fetch = async function () {
              const args = Array.prototype.slice.call(arguments);
              let url = args[0];
              let opts = args[1] || {};
              // Resolve url string
              let urlStr = "";
              try {
                if (typeof url === "string") urlStr = url;
                else if (url && url.url) urlStr = url.url;
                else urlStr = String(url);
              } catch (_e) { urlStr = ""; }
              let bodyStr = "";
              try {
                if (opts && opts.body) bodyStr = typeof opts.body === "string" ? opts.body : "";
                else if (typeof url !== "string" && url && url.body) bodyStr = typeof url.body === "string" ? url.body : "";
              } catch (_e) { bodyStr = ""; }

              const submitCandidate = isSubmitUrl(urlStr) || bodyContainsSubmit(bodyStr);
              const runCandidate = isRunUrl(urlStr) || bodyContainsRun(bodyStr);
              const checkCandidate = isCheckUrl(urlStr);

              let response;
              try {
                response = await origFetch.apply(this, args);
              } catch (e) { throw e; }

              // Inspect response asynchronously (clone)
              try {
                const clone = response.clone();
                const ctype = clone.headers.get("content-type") || "";
                if (ctype.includes("application/json") || urlStr.includes("/check") || urlStr.includes("graphql") || urlStr.includes("/submit")) {
                  clone.json().then(function (json) {
                    try {
                      // Submit response
                      if (submitCandidate && !runCandidate) {
                        const sid = extractSubmissionId(json, urlStr);
                        // Only notify if it looks like a submit (has submission id or submit marker)
                        if (sid || bodyContainsSubmit(bodyStr) || isSubmitUrl(urlStr)) {
                          notifyContent({ type: "GP_SUBMIT_DETECTED", submissionId: sid || null, url: String(window.location.href), rawUrl: urlStr, timestamp: Date.now() });
                        }
                      }
                      // Check response
                      if (checkCandidate || json.state || json.status_msg) {
                        const res = extractCheckResult(json, urlStr);
                        if (res && (res.state || res.status_msg)) {
                          // Attempt to recover sid from URL if not in JSON
                          let sid = res.submissionId;
                          if (!sid) {
                            const m = String(urlStr).match(/\/(\d+)\/check/);
                            if (m) sid = m[1];
                          }
                          notifyContent({ type: "GP_SUBMISSION_RESULT", submissionId: sid || null, state: res.state, status_msg: res.status_msg, url: String(window.location.href), rawUrl: urlStr, timestamp: Date.now() });
                        }
                      }
                      // Also handle graphql result that directly contains final status (some flows return Accepted immediately)
                      if (json.data && json.data.questionSubmit) {
                        const qs = json.data.questionSubmit;
                        if (qs.statusMsg || qs.status_msg) {
                          notifyContent({ type: "GP_SUBMISSION_RESULT", submissionId: qs.submissionId || qs.id || null, state: qs.status || qs.state || "SUCCESS", status_msg: qs.statusMsg || qs.status_msg, url: String(window.location.href), rawUrl: urlStr, timestamp: Date.now() });
                        }
                      }
                    } catch (_e) { }
                  }).catch(function () { /* non-json */ });
                }
              } catch (_e) { }

              return response;
            };
          }
        } catch (_e) { }

        // Patch XHR
        try {
          const origOpen = XMLHttpRequest.prototype.open;
          const origSend = XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open = function (method, url) {
            this._gpUrl = url;
            this._gpMethod = method;
            return origOpen.apply(this, arguments);
          };
          XMLHttpRequest.prototype.send = function (body) {
            this._gpBody = body ? String(body) : "";
            const xhr = this;
            const urlStr = xhr._gpUrl || "";
            const bodyStr = xhr._gpBody || "";
            const submitCandidate = isSubmitUrl(urlStr) || bodyContainsSubmit(bodyStr);
            const runCandidate = isRunUrl(urlStr) || bodyContainsRun(bodyStr);
            const checkCandidate = isCheckUrl(urlStr);
            function handleLoad() {
              try {
                const ctype = xhr.getResponseHeader && xhr.getResponseHeader("content-type") || "";
                const text = xhr.responseText || "";
                if (!text) return;
                let json = null;
                try { json = JSON.parse(text); } catch (_e) { return; }
                if (!json) return;
                if (submitCandidate && !runCandidate) {
                  const sid = extractSubmissionId(json, urlStr);
                  if (sid || bodyContainsSubmit(bodyStr) || isSubmitUrl(urlStr)) {
                    notifyContent({ type: "GP_SUBMIT_DETECTED", submissionId: sid || null, url: String(window.location.href), rawUrl: urlStr, timestamp: Date.now() });
                  }
                }
                if (checkCandidate || json.state || json.status_msg) {
                  const res = extractCheckResult(json, urlStr);
                  if (res && (res.state || res.status_msg)) {
                    let sid = res.submissionId;
                    if (!sid) {
                      const m = String(urlStr).match(/\/(\d+)\/check/);
                      if (m) sid = m[1];
                    }
                    notifyContent({ type: "GP_SUBMISSION_RESULT", submissionId: sid || null, state: res.state, status_msg: res.status_msg, url: String(window.location.href), rawUrl: urlStr, timestamp: Date.now() });
                  }
                }
              } catch (_e) { }
            }
            try { xhr.addEventListener("load", handleLoad); } catch (_e) { }
            return origSend.apply(this, arguments);
          };
        } catch (_e) { }

        // Serve editor data on request from isolated world
        window.addEventListener("message", function (event) {
          try {
            const d = event.data;
            if (!d || d.source !== "ghostpush-content") return;
            if (d.type === "GP_GET_EDITOR_DATA") {
              let code = null;
              let langText = null;
              let langId = null;
              try {
                if (window.monaco && window.monaco.editor) {
                  const models = window.monaco.editor.getModels();
                  if (models && models.length > 0) {
                    let mdl = models.find(function (m) {
                      try { return m.uri && /solution\.|Solution\.|code\./.test(m.uri.path || m.uri.toString()); } catch (_e) { return false; }
                    }) || models[0];
                    if (mdl) {
                      try { code = mdl.getValue(); } catch (_e) { code = null; }
                      try {
                        if (mdl.getModeId) langId = mdl.getModeId();
                        else if (mdl.getLanguageId) langId = mdl.getLanguageId();
                        else if (mdl.getLanguageIdentifier) langId = mdl.getLanguageIdentifier().language;
                      } catch (_e) { langId = null; }
                    }
                  }
                }
              } catch (_e) { code = null; }
              // Also try language selector in MAIN world
              try {
                const candidates = [
                  document.querySelector("button[id*='headlessui-popover-button']"),
                  document.querySelector("[data-cy='lang-select']"),
                  document.querySelector("div[class*='ant-select-selection-selected-value']")
                ];
                for (let i = 0; i < candidates.length; i++) {
                  const el = candidates[i];
                  if (el && el.textContent && el.textContent.trim()) { langText = el.textContent.trim(); break; }
                }
                if (!langText && langId) langText = langId;
              } catch (_e) { }
              notifyContent({ type: "GP_EDITOR_DATA", requestId: d.requestId, code: code, langText: langText, langId: langId });
            }
          } catch (_e) { }
        });

        // Also emit a ready signal
        notifyContent({ type: "GP_BRIDGE_READY" });
      }.toString() + ")();";
      // Inject into page
      try {
        (document.head || document.documentElement).appendChild(script);
        // Remove after a tick to keep DOM clean (script already executed)
        setTimeout(function () { try { script.remove(); } catch (_e) { } }, 1000);
      } catch (_e) {
        console.warn("[GhostPush][SubmissionMonitor] MAIN bridge injection failed", _e);
      }
    }

    // Only inject on LeetCode pages; still monitor SPA to re-inject on navigation
    function maybeInjectBridge() {
      if (isOnLeetCodeProblem() || window.location.hostname.includes("leetcode.com")) {
        injectMainWorldBridge();
      }
    }
    maybeInjectBridge();
    window.addEventListener("ghostpush_locationchange", maybeInjectBridge);

    // ----- Content-side message handling from MAIN bridge -----
    let pendingEditorRequests = new Map(); // requestId -> { resolve, timeout }

    function requestEditorData(timeoutMs) {
      timeoutMs = timeoutMs || 2000;
      return new Promise(resolve => {
        const reqId = "req_" + Date.now() + "_" + Math.random().toString(36).slice(2, 7);
        const timer = setTimeout(() => {
          pendingEditorRequests.delete(reqId);
          resolve(null);
        }, timeoutMs);
        pendingEditorRequests.set(reqId, {
          resolve: (data) => { clearTimeout(timer); resolve(data); },
          timeout: timer
        });
        try {
          window.postMessage({ source: "ghostpush-content", type: "GP_GET_EDITOR_DATA", requestId: reqId }, "*");
        } catch (_e) {
          clearTimeout(timer);
          pendingEditorRequests.delete(reqId);
          resolve(null);
        }
      });
    }

    window.addEventListener("message", function (event) {
      // Only accept messages from self (MAIN bridge uses window.postMessage with source ghostpush-main)
      // event.source should be window for same-page messages.
      if (event.source !== window) return;
      const data = event.data;
      if (!data || data.source !== "ghostpush-main") return;

      if (data.type === "GP_BRIDGE_READY") {
        logEvent("READY", "MAIN bridge ready", null);
        return;
      }
      if (data.type === "GP_EDITOR_DATA") {
        const entry = pendingEditorRequests.get(data.requestId);
        if (entry) {
          pendingEditorRequests.delete(data.requestId);
          entry.resolve(data);
        }
        return;
      }
      if (data.type === "GP_SUBMIT_DETECTED") {
        resetProblemStateIfChanged();
        if (!isOnLeetCodeProblem()) return;
        const sid = data.submissionId ? String(data.submissionId) : null;
        const now = Date.now();
        if (sid) {
          pendingSubmissions.set(sid, { timestamp: now, url: window.location.href });
        } else {
          pendingSubmitFlag = { timestamp: now, url: window.location.href };
        }
        // Prune stale pending entries
        const cutoff = now - PENDING_TTL_MS;
        for (const [k, v] of Array.from(pendingSubmissions.entries())) {
          if (v.timestamp < cutoff) pendingSubmissions.delete(k);
        }
        if (pendingSubmitFlag && pendingSubmitFlag.timestamp < cutoff) pendingSubmitFlag = null;
        logEvent("Submit detected", "submit id=" + (sid || "unknown") + " url=" + window.location.href, { submissionId: sid });
        console.log(LOG_PREFIX + " Waiting for result id=" + (sid || "unknown"));
        return;
      }
      if (data.type === "GP_SUBMISSION_RESULT") {
        resetProblemStateIfChanged();
        if (!isOnLeetCodeProblem()) return;
        const state = data.state || "";
        const msg = data.status_msg || data.statusMsg || "";
        const sid = data.submissionId ? String(data.submissionId) : null;
        const classification = classifySubmissionStatus(msg, state);

        // Gate: ignore if no pending submit (prevents Run Code false positives)
        let hasPending = false;
        if (sid && pendingSubmissions.has(sid)) hasPending = true;
        else if (!sid && pendingSubmitFlag) {
          // No sid in result: check if there was any pending submit recently (within TTL)
          const now = Date.now();
          if (pendingSubmitFlag && (now - pendingSubmitFlag.timestamp) < PENDING_TTL_MS) hasPending = true;
          // Also if any pending submission exists recently, consider it
          for (const v of pendingSubmissions.values()) {
            if ((now - v.timestamp) < PENDING_TTL_MS) { hasPending = true; break; }
          }
        } else if (sid) {
          // Fallback: if we missed submit detection but state is SUCCESS/Accepted, still allow if
          // there was a generic pending flag recently (covers graphql batching)
          if (pendingSubmitFlag && (Date.now() - pendingSubmitFlag.timestamp) < PENDING_TTL_MS) hasPending = true;
        }

        if (classification === "Accepted") {
          if (!hasPending) {
            logEvent("Ignored Accepted without pending submit", "msg=" + msg + " state=" + state + " sid=" + (sid || "none"), { submissionId: sid });
            return;
          }
          logEvent("Accepted", "submissionId=" + (sid || "unknown") + " state=" + state + " msg=" + msg, { submissionId: sid });
          // Consume pending to avoid re-processing same result multiple times due to polling
          if (sid) pendingSubmissions.delete(sid);
          else pendingSubmitFlag = null;
          handleAcceptedSubmission(sid);
        } else if (["Pending", "Running", "Processing"].includes(classification) || state === "PENDING" || state === "STARTED") {
          // Still waiting — do not clear pending
          logEvent("Waiting for result", "state=" + state + " msg=" + msg + " sid=" + (sid || "none"), { submissionId: sid });
        } else {
          // Rejected / error — ignore and clear pending for this sid to prevent lingering
          if (classification !== "Unknown") {
            logEvent("Rejected - ignored", "classification=" + classification + " msg=" + msg + " state=" + state, { submissionId: sid });
            if (sid) pendingSubmissions.delete(sid);
            // Keep generic pending for a bit but don't auto-clear on every non-accepted check to handle polling
            // Instead only clear if message is terminal rejected state
            const terminalRejected = ["Wrong Answer", "Runtime Error", "Compile Error", "Time Limit Exceeded", "Memory Limit Exceeded", "Output Limit Exceeded"];
            if (terminalRejected.includes(classification)) {
              // If we have no sid, clear generic flag after a terminal result
              if (!sid) pendingSubmitFlag = null;
            }
          }
        }
        return;
      }
    });

    // ----- Automatic job creation on Accepted -----
    async function handleAcceptedSubmission(submissionId) {
      const startMs = Date.now();
      try {
        if (!isOnLeetCodeProblem()) {
          logEvent("Abort", "Not on LeetCode problem page", { submissionId: submissionId });
          return;
        }

        // 1. Extract complete solution via MAIN bridge
        let editorData = null;
        try {
          editorData = await requestEditorData(2500);
        } catch (_e) { editorData = null; }

        // Also fetch metadata via extractPageMetadata for title/tags/difficulty (uses monacoData if available)
        const metadata = extractPageMetadata(editorData || null);

        // Fail closed checks
        if (!editorData || !editorData.code || !editorData.code.trim()) {
          // editorData may be null if MAIN bridge not ready — try metadata.code as fallback only if non-empty
          // But per spec: DOM visible-line extraction ONLY as final fallback must fail safely if truncated.
          // We have metadata.code which could be DOM partial; require MAIN success.
          if (!metadata.code || !metadata.code.trim()) {
            logEvent("Abort", "Missing complete source — failing closed (no code)", { submissionId: submissionId });
            console.warn(LOG_PREFIX + " Missing complete source - aborting automatic sync");
            return;
          }
          // If MAIN returned null but DOM gave code, treat as incomplete and fail closed with warning per spec
          if (!editorData || editorData.code === null) {
            logEvent("Abort", "MAIN bridge did not return complete source — failing closed to avoid truncated commit", { submissionId: submissionId });
            console.warn(LOG_PREFIX + " MAIN bridge unavailable — refusing to sync truncated visible-line code");
            return;
          }
        }

        const completeCode = (editorData && editorData.code ? editorData.code : metadata.code).trim();
        if (!completeCode) {
          logEvent("Abort", "Empty solution code — failing closed", { submissionId: submissionId });
          return;
        }

        // Rough truncation guard: if we fell back to DOM and code looks suspiciously short while editor says unavailable, abort.
        // Already handled above, but extra guard for very short code (<10 chars) is likely not a real solution.
        if (completeCode.length < 10) {
          logEvent("Abort", "Solution code suspiciously short (" + completeCode.length + " chars) — failing closed", { submissionId: submissionId });
          return;
        }

        // 2. Determine language reliably
        let langText = (editorData && (editorData.langText || editorData.langId)) || "";
        let language = metadata.language;
        // Prefer normalize of langText/langId before heuristic fallback
        const normalizedFromBridge = normalizeLangText(langText);
        if (normalizedFromBridge) language = normalizedFromBridge;
        else if (langText) {
          // try again with raw
          const n2 = normalizeLangText(String(langText));
          if (n2) language = n2;
        }
        // Validate supported enums
        const supported = new Set(["python", "java", "cpp", "javascript", "typescript"]);
        if (!supported.has(language)) {
          // Map other languages to closest supported via fallback — remain compatible
          // Keep as python fallback per existing contract.
          logEvent("Warn", "Language '" + language + "' not in core enum, mapping to fallback", { submissionId: submissionId });
          // Still allow if heuristic gave it
        }

        // 3. Validate problem identity
        const problemUrl = metadata.url || window.location.href;
        const normalizedUrl = normalizeProblemUrl(problemUrl);
        if (!normalizedUrl || !isLeetCodeProblemPage(problemUrl)) {
          logEvent("Abort", "Missing reliable problem identity — failing closed", { submissionId: submissionId });
          return;
        }
        if (!metadata.title || metadata.title === "Unknown Problem") {
          logEvent("Abort", "Missing problem title — failing closed", { submissionId: submissionId });
          return;
        }

        // 4. Deduplication
        let dedupKey;
        if (submissionId) {
          dedupKey = buildDedupKeySync("leetcode", normalizedUrl, String(submissionId), "", "");
        } else {
          const codeHash = await sha256Hex(completeCode);
          dedupKey = buildDedupKeySync("leetcode", normalizedUrl, null, language, codeHash);
        }
        const dup = await isDuplicateDedupKey(dedupKey);
        if (dup) {
          logEvent("Duplicate submission - ignored", "key=" + dedupKey, { submissionId: submissionId });
          console.log(LOG_PREFIX + " Duplicate submission - ignored key=" + dedupKey);
          return;
        }

        logEvent("Extracted complete solution", language + " " + completeCode.length + " chars url=" + normalizedUrl, { submissionId: submissionId });

        // 5. Construct payload and delegate to background for POST (handles config + CORS)
        const payload = {
          api_version: "1.0",
          job_id: generateJobId(),
          platform: "leetcode",
          problem: {
            title: metadata.title.replace(/^\d+\.\s*/, "").trim(),
            difficulty: metadata.difficulty || "Easy",
            url: problemUrl,
            tags: metadata.tags || ["Algorithm"]
          },
          solution: {
            language: language,
            code: completeCode
          },
          repository_path: "" // filled by background from /api/v1/config
        };

        // Send to background for execution; background will fill repository_path and POST to /api/v1/jobs
        const result = await new Promise(resolve => {
          try {
            chrome.runtime.sendMessage({ action: "ghostpush_auto_submit", payload: payload, dedupKey: dedupKey, submissionId: submissionId }, response => {
              if (chrome.runtime.lastError) {
                resolve({ ok: false, error: chrome.runtime.lastError.message });
              } else {
                resolve(response || { ok: false, error: "no response from background" });
              }
            });
          } catch (e) {
            resolve({ ok: false, error: String(e) });
          }
        });

        const durationMs = Date.now() - startMs;
        if (result && result.ok) {
          await markSeenDedupKey(dedupKey);
          logEvent("Automatic job created", "job_id=" + (result.jobId || payload.job_id) + " dedupKey=" + dedupKey, { submissionId: submissionId, durationMs: durationMs });
          console.log(LOG_PREFIX + " Automatic job created job_id=" + (result.jobId || payload.job_id));
        } else {
          const errMsg = result && result.error ? result.error : "unknown error";
          // If background reports duplicate (409), still mark seen to prevent retries
          if (errMsg && errMsg.includes("already exists")) {
            await markSeenDedupKey(dedupKey);
            logEvent("Duplicate submission - ignored (backend 409)", errMsg, { submissionId: submissionId, durationMs: durationMs });
          } else {
            logEvent("Auto job failed", errMsg, { submissionId: submissionId, durationMs: durationMs });
            console.warn(LOG_PREFIX + " Automatic job failed: " + errMsg);
          }
        }

      } catch (e) {
        console.warn(LOG_PREFIX + " handleAcceptedSubmission error", e);
        logEvent("Error", "handleAcceptedSubmission exception: " + String(e), { submissionId: submissionId });
      }
    }

    // Initial log
    console.log(LOG_PREFIX + " Monitor started on " + window.location.href);
    logEvent("Monitor started", "url=" + window.location.href, null);
  }
})();

