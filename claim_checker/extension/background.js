// TOMMI Claim Checker — Background service worker
// Handles context menu creation and API routing (bypasses CSP on content pages)

const DEFAULT_BACKEND = "http://localhost:8100";

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "tommi-check-claims",
    title: "Check claims with TOMMI",
    contexts: ["selection"],
  });
});

// Handle context menu click
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "tommi-check-claims" && info.selectionText) {
    chrome.tabs.sendMessage(tab.id, {
      action: "analyzeSelection",
      text: info.selectionText,
    });
  }
});

// Handle messages from content script and popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "analyze") {
    analyzeText(msg.text, msg.referenceText, msg.strategy)
      .then((result) => sendResponse({ success: true, data: result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // keep channel open for async response
  }

  if (msg.action === "getConfig") {
    chrome.storage.local.get(
      ["backendUrl", "referenceText", "strategy"],
      (items) => {
        sendResponse({
          backendUrl: items.backendUrl || DEFAULT_BACKEND,
          referenceText: items.referenceText || "",
          strategy: items.strategy || "reference",
        });
      }
    );
    return true;
  }
});

async function analyzeText(text, referenceText, strategy) {
  const config = await chrome.storage.local.get(["backendUrl"]);
  const backendUrl = config.backendUrl || DEFAULT_BACKEND;

  const response = await fetch(`${backendUrl}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: text,
      reference_text: referenceText || "",
      strategy: strategy || "reference",
    }),
  });

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
