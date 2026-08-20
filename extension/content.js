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

  function detectLanguage(domText, code) {
    if (domText && typeof domText === "string") {
      const norm = domText.trim().toLowerCase();
      if (norm.includes("java") && !norm.includes("javascript")) return "java";
      if (norm.includes("c++") || norm.includes("cpp")) return "cpp";
      if (norm.includes("python")) return "python";
      if (norm.includes("javascript") || norm.includes("js")) return "javascript";
      if (norm.includes("typescript") || norm.includes("ts")) return "typescript";
    }

    if (code && typeof code === "string") {
      // C++ heuristics (check first to distinguish C++ class Solution from Java)
      if (/#include\s*<|\bstd::|\bvector\s*<|\bpublic\s*:/.test(code)) {
        return "cpp";
      }

      // Java heuristics: public class, import java., System.out., new int[], int[], public/private int, class Solution (without :)
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

      // Python heuristics: def twoSum, class Solution:, from typing, import typing, self.
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
    }

    return "python";
  }

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

        // Try extracting language from LeetCode DOM selector buttons
        const langBtn = document.querySelector("button[id*='headlessui-popover-button'], button[class*='select'], [data-cy='lang-select'], div[class*='ant-select-selection-selected-value'], button[class*='rounded'], div[class*='editor'] button");
        const domLangText = langBtn ? langBtn.textContent.trim() : "";

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
