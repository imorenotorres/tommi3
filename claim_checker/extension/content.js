// TOMMI Claim Checker — Content script
// Handles inline highlighting and results panel on any web page

(function () {
  "use strict";

  let panelRoot = null; // Shadow DOM host for results panel
  let mutationObserver = null;

  // Listen for messages from background worker
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "analyzeSelection") {
      handleAnalyzeSelection(msg.text);
    }
    if (msg.action === "analyzeResult") {
      applyResults(msg.data);
    }
    if (msg.action === "clearHighlights") {
      clearAll();
    }
  });

  // ------------------------------------------------------------------
  // Main flow: user triggers analysis via context menu or popup
  // ------------------------------------------------------------------

  async function handleAnalyzeSelection(text) {
    // Get config (reference text, strategy) from storage
    const config = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "getConfig" }, resolve);
    });

    if (!config.referenceText && config.strategy === "reference") {
      showPanel({
        error:
          "No reference text set. Open the TOMMI extension popup and paste your reference/source text first.",
      });
      return;
    }

    showPanel({ loading: true });

    // Route API call through background worker (avoids CSP)
    chrome.runtime.sendMessage(
      {
        action: "analyze",
        text: text,
        referenceText: config.referenceText,
        strategy: config.strategy,
      },
      (response) => {
        if (chrome.runtime.lastError) {
          showPanel({ error: `Extension error: ${chrome.runtime.lastError.message}` });
          return;
        }
        if (!response || !response.success) {
          showPanel({
            error: response
              ? response.error
              : "No response from backend. Is the server running?",
          });
          return;
        }
        applyResults(response.data);
      }
    );
  }

  // ------------------------------------------------------------------
  // Apply highlights to the user's selection range
  // ------------------------------------------------------------------

  function applyResults(data) {
    if (data.error) {
      showPanel({ error: data.error });
      return;
    }

    // Clear previous highlights
    clearHighlights();

    const highlights = data.highlights;
    if (!highlights) {
      showPanel({ data: data, highlighted: 0 });
      return;
    }

    // Build items sorted longest-first
    const items = [];
    (highlights.grounded || []).forEach((c) =>
      items.push({
        text: c,
        cls: "tommi-claim-grounded",
        tip: "Grounded in reference text",
      })
    );
    (highlights.ungrounded || []).forEach((c) =>
      items.push({
        text: c,
        cls: "tommi-claim-ungrounded",
        tip: "Not found in reference text (potential hallucination)",
      })
    );
    items.sort((a, b) => b.text.length - a.text.length);

    // Get user selection range to scope highlighting
    const selection = window.getSelection();
    let scope = document.body;
    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0);
      scope = range.commonAncestorContainer;
      if (scope.nodeType === Node.TEXT_NODE) scope = scope.parentElement;
    }

    // Highlight claims using TreeWalker (adapted from app.js)
    const highlighted = new Set();

    for (const item of items) {
      if (highlighted.has(item.text)) continue;

      const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          const parent = node.parentElement;
          if (!parent) return NodeFilter.FILTER_REJECT;
          const tag = parent.tagName;
          if (
            tag === "SCRIPT" ||
            tag === "STYLE" ||
            tag === "TEXTAREA" ||
            tag === "INPUT"
          )
            return NodeFilter.FILTER_REJECT;
          if (parent.closest("a[href]")) return NodeFilter.FILTER_REJECT;
          if (parent.closest(".tommi-panel-host")) return NodeFilter.FILTER_REJECT;
          if (parent.classList.contains("tommi-claim-grounded") ||
              parent.classList.contains("tommi-claim-ungrounded"))
            return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        },
      });

      let node;
      while ((node = walker.nextNode())) {
        const text = node.nodeValue;
        const idx = text.indexOf(item.text);
        if (idx === -1) continue;

        const before = text.substring(0, idx);
        const match = text.substring(idx, idx + item.text.length);
        const after = text.substring(idx + item.text.length);

        const span = document.createElement("span");
        span.className = item.cls;
        span.title = item.tip;
        span.textContent = match;

        const frag = document.createDocumentFragment();
        if (before) frag.appendChild(document.createTextNode(before));
        frag.appendChild(span);
        if (after) frag.appendChild(document.createTextNode(after));

        node.parentNode.replaceChild(frag, node);
        highlighted.add(item.text);
        break; // first occurrence only
      }
    }

    showPanel({ data: data, highlighted: highlighted.size });
  }

  // ------------------------------------------------------------------
  // Results panel (Shadow DOM overlay)
  // ------------------------------------------------------------------

  function showPanel(opts) {
    removePanel();

    const host = document.createElement("div");
    host.className = "tommi-panel-host";
    host.style.cssText =
      "position:fixed;top:16px;right:16px;z-index:2147483647;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;";
    const shadow = host.attachShadow({ mode: "closed" });

    const style = document.createElement("style");
    style.textContent = `
      .panel { background:#fff; border:1px solid #ddd; border-radius:10px; box-shadow:0 4px 24px rgba(0,0,0,0.15); width:340px; max-height:80vh; overflow-y:auto; padding:16px; font-size:13px; color:#333; }
      .panel-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
      .panel-title { font-size:15px; font-weight:700; color:#1a1a1a; }
      .close-btn { background:none; border:none; font-size:18px; cursor:pointer; color:#999; padding:0 4px; }
      .close-btn:hover { color:#333; }
      .badge { display:inline-block; padding:4px 10px; border-radius:6px; font-weight:700; font-size:13px; margin-bottom:10px; }
      .badge-high { background:#d4edda; color:#155724; }
      .badge-good { background:#fff3cd; color:#856404; }
      .badge-poor { background:#f8d7da; color:#721c24; }
      .stat { margin:4px 0; font-size:12px; color:#666; }
      .claim-section { margin-top:10px; }
      .claim-section h4 { margin:0 0 4px; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; }
      .claim-list { list-style:none; padding:0; margin:0; }
      .claim-list li { padding:3px 6px; margin:2px 0; border-radius:4px; font-size:12px; word-break:break-word; }
      .claim-grounded { background:rgba(40,167,69,0.12); border-left:3px solid #28a745; }
      .claim-ungrounded { background:rgba(220,53,69,0.12); border-left:3px solid #dc3545; }
      .actions { margin-top:12px; display:flex; gap:8px; }
      .actions button { flex:1; padding:6px 0; border:1px solid #ddd; border-radius:6px; background:#f8f9fa; cursor:pointer; font-size:12px; }
      .actions button:hover { background:#e9ecef; }
      .loading { text-align:center; padding:24px 0; color:#666; }
      .error { color:#dc3545; padding:8px; background:#f8d7da; border-radius:6px; font-size:12px; }
      .legend { display:flex; gap:12px; margin-top:8px; font-size:11px; color:#888; }
      .legend-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:4px; vertical-align:middle; }
    `;
    shadow.appendChild(style);

    const panel = document.createElement("div");
    panel.className = "panel";

    // Header
    const header = document.createElement("div");
    header.className = "panel-header";
    header.innerHTML = `<span class="panel-title">TOMMI Claim Checker</span>`;
    const closeBtn = document.createElement("button");
    closeBtn.className = "close-btn";
    closeBtn.textContent = "\u00d7";
    closeBtn.addEventListener("click", () => {
      clearAll();
    });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Loading state
    if (opts.loading) {
      panel.innerHTML +=
        '<div class="loading">Analyzing claims\u2026</div>';
      shadow.appendChild(panel);
      document.body.appendChild(host);
      panelRoot = host;
      return;
    }

    // Error state
    if (opts.error) {
      panel.innerHTML +=
        `<div class="error">${escapeHtml(opts.error)}</div>`;
      shadow.appendChild(panel);
      document.body.appendChild(host);
      panelRoot = host;
      return;
    }

    // Results
    const data = opts.data;
    const badge = data.badge || {};
    const claims = data.claims || {};

    // Badge
    const badgeClass =
      badge.label === "High"
        ? "badge-high"
        : badge.label === "Good"
        ? "badge-good"
        : "badge-poor";
    panel.innerHTML += `<span class="badge ${badgeClass}">${badge.label} reliability (${badge.confidence}%)</span>`;

    // Stats
    const grounded = (claims.grounded || []).length;
    const ungrounded = (claims.ungrounded || []).length;
    panel.innerHTML += `
      <div class="stat">Total claims: ${claims.total || 0}</div>
      <div class="stat">Grounded: ${grounded} | Ungrounded: ${ungrounded}</div>
      <div class="stat">Highlighted on page: ${opts.highlighted || 0}</div>
    `;

    // Legend
    panel.innerHTML += `
      <div class="legend">
        <span><span class="legend-dot" style="background:#28a745"></span>Grounded</span>
        <span><span class="legend-dot" style="background:#dc3545"></span>Ungrounded</span>
      </div>
    `;

    // Claim lists
    if (grounded > 0) {
      const section = document.createElement("div");
      section.className = "claim-section";
      section.innerHTML = `<h4 style="color:#28a745;">Grounded claims</h4>`;
      const ul = document.createElement("ul");
      ul.className = "claim-list";
      for (const c of claims.grounded) {
        const li = document.createElement("li");
        li.className = "claim-grounded";
        li.textContent = c;
        ul.appendChild(li);
      }
      section.appendChild(ul);
      panel.appendChild(section);
    }

    if (ungrounded > 0) {
      const section = document.createElement("div");
      section.className = "claim-section";
      section.innerHTML = `<h4 style="color:#dc3545;">Ungrounded claims</h4>`;
      const ul = document.createElement("ul");
      ul.className = "claim-list";
      for (const c of claims.ungrounded) {
        const li = document.createElement("li");
        li.className = "claim-ungrounded";
        li.textContent = c;
        ul.appendChild(li);
      }
      section.appendChild(ul);
      panel.appendChild(section);
    }

    // Action buttons
    const actions = document.createElement("div");
    actions.className = "actions";

    const clearBtn = document.createElement("button");
    clearBtn.textContent = "Clear";
    clearBtn.addEventListener("click", () => clearAll());

    const exportBtn = document.createElement("button");
    exportBtn.textContent = "Export JSON";
    exportBtn.addEventListener("click", () => exportResults(data));

    actions.appendChild(clearBtn);
    actions.appendChild(exportBtn);
    panel.appendChild(actions);

    shadow.appendChild(panel);
    document.body.appendChild(host);
    panelRoot = host;
  }

  // ------------------------------------------------------------------
  // Cleanup
  // ------------------------------------------------------------------

  function clearHighlights() {
    const spans = document.querySelectorAll(
      ".tommi-claim-grounded, .tommi-claim-ungrounded"
    );
    spans.forEach((span) => {
      const text = document.createTextNode(span.textContent);
      span.parentNode.replaceChild(text, span);
    });
    // Merge adjacent text nodes
    document.body.normalize();
  }

  function removePanel() {
    if (panelRoot) {
      panelRoot.remove();
      panelRoot = null;
    }
  }

  function clearAll() {
    clearHighlights();
    removePanel();
  }

  // ------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function exportResults(data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tommi-claims-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
})();
