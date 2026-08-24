/**
 * GhostPush Background Service Worker (Manifest V3)
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("[GhostPush] Extension background service worker initialized.");
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ping") {
    sendResponse({ status: "pong", version: "1.0.0" });
  }
  return true;
});
