/**
 * GhostPush Content Script
 * Extracts problem title, difficulty, tags, and solution code from supported CP platforms.
 */

(function () {
  // Listen for extraction requests from popup.js
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extract_problem") {
      const data = extractPageMetadata();
      sendResponse(data);
    }
    return true;
  });

  function extractPageMetadata() {
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
        // LeetCode extraction
        const titleEl = document.querySelector("div[class*='text-title-large'] a, span[class*='title']");
        title = titleEl ? titleEl.textContent.trim() : document.title.split("-")[0].trim();

        const diffEl = document.querySelector("div[class*='text-difficulty']");
        if (diffEl) {
          difficulty = diffEl.textContent.trim();
        }

        const tagEls = document.querySelectorAll("a[href*='/tag/']");
        tags = Array.from(tagEls).map(el => el.textContent.trim()).filter(Boolean);

        // Try extracting code from Monaco editor or code lines
        const codeLines = document.querySelectorAll(".view-lines .view-line");
        if (codeLines.length > 0) {
          code = Array.from(codeLines).map(l => l.textContent).join("\n");
        }
      } else if (platform === "gfg") {
        // GFG extraction
        const titleEl = document.querySelector("h3[class*='problem-tab']");
        title = titleEl ? titleEl.textContent.trim() : document.title.split("|")[0].trim();

        const diffEl = document.querySelector("span[class*='difficulty']");
        if (diffEl) {
          difficulty = diffEl.textContent.trim();
        }
      } else {
        // Fallback for title
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
})();
