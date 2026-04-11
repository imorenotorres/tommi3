// TOMMI Claim Checker — Popup script

const backendUrlInput = document.getElementById("backendUrl");
const strategySelect = document.getElementById("strategy");
const referenceTextarea = document.getElementById("referenceText");
const saveBtn = document.getElementById("saveBtn");
const clearBtn = document.getElementById("clearBtn");
const statusEl = document.getElementById("status");

// Load saved settings
chrome.storage.local.get(
  ["backendUrl", "referenceText", "strategy"],
  (items) => {
    backendUrlInput.value = items.backendUrl || "http://localhost:8100";
    referenceTextarea.value = items.referenceText || "";
    strategySelect.value = items.strategy || "reference";
  }
);

// Save settings
saveBtn.addEventListener("click", () => {
  const settings = {
    backendUrl: backendUrlInput.value.trim().replace(/\/+$/, ""),
    referenceText: referenceTextarea.value,
    strategy: strategySelect.value,
  };

  chrome.storage.local.set(settings, () => {
    showStatus("Settings saved!", "success");

    // Test backend connectivity
    fetch(`${settings.backendUrl}/api/health`)
      .then((r) => {
        if (r.ok) showStatus("Settings saved! Backend connected.", "success");
        else showStatus("Saved, but backend returned an error.", "error");
      })
      .catch(() => {
        showStatus(
          "Saved. Warning: could not reach backend at " + settings.backendUrl,
          "error"
        );
      });
  });
});

// Clear highlights on active tab
clearBtn.addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "clearHighlights" });
      showStatus("Highlights cleared.", "success");
    }
  });
});

function showStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = "status " + (type || "");
  if (type === "success") {
    setTimeout(() => {
      statusEl.textContent = "";
      statusEl.className = "status";
    }, 3000);
  }
}
