# TOMMI Claim Checker — Chrome Extension

Detect hallucinations and verify factual claims in any text on the web, powered by TOMMI's claim extraction and grounding engine.

## Architecture

```
Chrome Extension  ──────►  FastAPI Backend (:8100)
  - Context menu              - ClaimExtractor (regex extraction)
  - Popup (config)            - GroundingAnalyzer (claim classification)
  - Content script            - Reuses agents/base/claims.py
    (highlights + panel)
```

## Quick Start

### 1. Start the backend server

```bash
cd claim_checker/server
pip install -r requirements.txt
python claim_checker_server.py
```

The server starts on `http://localhost:8100`.

### 2. Load the Chrome extension

1. Open `chrome://extensions/` in Chrome
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `claim_checker/extension/` directory

### 3. Use it

1. Click the TOMMI extension icon in the toolbar
2. Paste trusted reference text (e.g. Wikipedia article, paper, documentation)
3. Click "Save settings"
4. Select any text on a web page (ChatGPT, Gemini, news article, etc.)
5. Right-click → "Check claims with TOMMI"
6. See green highlights (grounded) and red highlights (ungrounded) + floating results panel

## API

### POST /api/analyze

```json
{
  "text": "The text to analyze",
  "reference_text": "The trusted source text",
  "strategy": "reference"
}
```

Returns claim breakdown, badge, and highlight data.

### GET /api/health

Returns `{"status": "ok"}`.

## Reused Components

| Component | Source | Purpose |
|-----------|--------|---------|
| `ClaimExtractor` | `agents/base/claims.py` | 7 regex strategies for claim extraction |
| `GroundingAnalyzer` | `agents/base/claims.py` | Claim classification (grounded vs ungrounded) |
| Highlight pattern | `web/static/app.js` | TreeWalker DOM highlighting |

## Roadmap

- **Phase 1 (current)**: Reference text comparison
- **Phase 2**: Web search auto-verification (no reference text needed)
- **Phase 3**: LLM-based factual assessment
- **Phase 4**: Academic features (export, history, batch analysis)
