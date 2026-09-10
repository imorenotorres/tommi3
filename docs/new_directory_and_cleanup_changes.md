# New Directory features, `web/apps` cleanup, and auth de-duplication

This document summarizes a series of changes made to the UNINOVIS Directory app
(`web/apps/new_directory/`), a cleanup of unused code under `web/apps/`, and a
de-duplication of shared authentication helpers across the FastAPI apps.

## 1. New Directory (`web/apps/new_directory/`)

### 1.1 Sortable "Name" column (People tab)

- **What:** The People table already sorted alphabetically by family name on
  every render. Added a clickable "Name" column header with a ▲/▼ indicator
  that toggles ascending/descending order.
- **Why:** The user wanted a way to actually control sort direction, not just
  a fixed default order.
- **Files:** `static/index.html` (`renderPeople`, new `togglePeopleSort`).

### 1.2 Unit/subunit editing

- **What:** Added a unified way to edit a unit or subunit's name, parent
  (reparenting), leaders, and direct members, plus the ability to delete a
  unit.
  - Backend: `PUT /api/units/{unit_id}` replaces the old leaders-only
    `PUT /api/units/{unit_id}/leaders` endpoint. It now handles renaming,
    reparenting, and setting leaders in one call. `DELETE /api/units/{unit_id}`
    was added to remove a unit.
  - Permission model mirrors unit *creation*: `content_manager`/`superuser`
    can edit or delete any unit; a `wp_leader` can edit/delete a unit they
    lead, or one nested under a work package they lead. A `wp_leader` cannot
    reparent a unit to top-level or create a cycle (moving a unit under
    itself or its own descendant is rejected).
  - Deleting a unit **promotes its direct subunits to top-level** rather than
    cascade-deleting them, and only removes that unit's own direct
    memberships — so erasing a parent unit can't silently destroy a whole
    subtree of subunits and their members.
  - Frontend: a global "Edit" toggle in the Units tab (matching the existing
    People tab pattern) reveals a red "✕ Erase" and an "Edit" button to the
    **left** of each unit/subunit name, shown only for units the current user
    is allowed to edit. The Edit modal shows the unit's name, its leaders
    (add/remove picker), and either a read-only list of its subunits (for a
    top-level unit) or a parent-unit dropdown (for a subunit, scoped to a
    `wp_leader`'s own led units while always keeping the unit's *actual*
    current parent selectable, so an untouched save can't silently reparent
    it).
  - A **Members** section was added to the same modal: rows of
    person + role that let you add any person in the directory to the unit,
    or remove existing direct members, without touching that person's
    memberships in other units.
- **Why:** The user asked for the ability to manage units/subunits (rename,
  move, delete, manage membership) the same way people can already be
  edited, with the same role-based access as unit creation.
- **Files:** `new_directory.py` (`UnitEditUpdate`, `update_unit`,
  `delete_unit`, `_unit_descendant_ids`, `_require_unit_edit_access`),
  `static/index.html` (`openEditUnitModal`, `unitRowButtons`,
  `confirmDeleteUnit`, member-row helpers, `toggleUnitsEditMode`).

### 1.3 Per-unit role shown instead of job position

- **What:** `_build_unit_tree` now attaches each member's role *within that
  specific unit* (`unit_role`) alongside their person record. In the Units
  and Org Chart tabs, a member's tag now shows their unit-specific role when
  one is set, falling back to their general job position otherwise.
- **Why:** Previously the Units/Org Chart views always showed a person's
  general job position next to their name, even when someone had been given
  a specific role for that unit (e.g. "coordinator") — that role never
  surfaced anywhere.
- **Files:** `new_directory.py` (`_build_unit_tree`), `static/index.html`
  (`renderUnitNode`).

### 1.4 University website editing

- **What:** Added `PUT /api/universities/{code}` (content_manager/superuser
  only) to set a university's website. Since the university list
  (name/country/website) is a static Python dict, the website value is
  stored as an override in `data.json` (`university_overrides`) and merged
  in by `GET /api/universities`. The Universities tab now has an "Edit"
  button per row opening a small modal for the website field.
- **Why:** Requested alongside the unit-editing work, to let admins fill in
  the website links that were blank in the static university table.
- **Files:** `new_directory.py` (`UniversityUpdate`, `update_university`,
  `get_universities`), `static/index.html` (`openEditUniversityModal`).

## 2. Cleanup of `web/apps/`

Surveyed all 18 directories under `web/apps/` to find code no longer wired
into `web/app.py` or referenced anywhere else in the repo (HTML/JS included,
not just Python), since a couple of "obviously dead" folders turned out to
still be load-bearing once checked properly (see the `directory` app below).

### 2.1 Moved to `web/apps/old apps/`

- **`fonesp_lti`**, **`redaccion_lti`** — dead forks. The real, active LTI
  provider code for these tools lives in the top-level `UltiR/` package,
  which is what `web/app.py` actually imports; these `web/apps/` copies were
  never referenced anywhere.
- **`holiday_tracker`** (old) — superseded by `uma_holiday_tracker`, which is
  the one actually mounted in `web/app.py` at `/holiday-tracker`.
- **`personal_dashboard`** — no references anywhere in the repo.

### 2.2 Deleted outright

- **`event_catalogue`**, **`internships`**, **`rag_study`** — contained
  nothing but stale compiled `.pyc` files from long-deleted source; no
  tracked files, no data worth preserving. (`event_catalogue` and
  `internships` are actually external links to `uninovis.widening.eu` in the
  intranet nav, unrelated to these local folders. `rag_study` is unrelated to
  the separate, active "Transparency Study" agent system in `agents/rag_study`
  and `web/static/rag_study2*`, which was a name collision, not an overlap.)
- **`web/app.py`**: removed the dead, already-commented-out `apps.rag_study`
  mount block, since the folder it referenced no longer exists at all.

### 2.3 Explicitly left alone: `web/apps/directory`

- This one looked dead at first glance — `web/auth.py` explicitly marks its
  nav tile as retired (`"directory": []  # hidden for everyone... Agora
  Directory link retired`), and it's superseded by `new_directory` for
  day-to-day use. **However**, `web/static/intranet.html` still actively
  calls `/directory/api/auth-check`, fetches `/directory/api/data` to enrich
  user info elsewhere on the intranet, and links "Edit my profile" to
  `/directory/#my-profile`. Its backend is genuinely load-bearing even
  though its own promotional tile is hidden, so it was **not** moved or
  unmounted.
- **Why this matters:** this was caught by grepping the whole repo (HTML/JS
  included) for every reference before moving anything, not just checking
  `web/app.py`'s router wiring — a mount-level check alone would have missed
  this and broken live functionality.

## 3. Shared auth helper de-duplication

### 3.1 What was duplicated

Nine apps (`new_directory`, `directory`, `event_tracker`, `mobility_planner`,
`researcher_connect`, `research_proposals`, `unigracon`,
`collaboration_dashboard`, `uma_holiday_tracker`) each independently defined
their own copies of the same three functions:

- `_get_token(request)` — read the bearer token from the `Authorization`
  header, falling back to a `?token=` query param.
- `_require_auth(request)` — resolve the caller's session via
  `auth.get_session`, falling back to a read-only "guest" session.
- `_require_editor(session)` — require `EDITOR_ROLES` membership on top of a
  resolved session (present in 6 of the 9 apps).

`_get_token` and `_require_auth` were byte-for-byte identical in every app.
`_require_editor` was identical in 5 apps and functionally equivalent
(different calling style, same result) in a 6th (`researcher_connect`).

### 3.2 What changed

- Added `get_token()`, `require_session()`, and `require_editor()` to
  `web/auth.py` as shared, reusable FastAPI dependencies.
- In 8 apps (all except `research_proposals`), removed the local
  `_get_token`/`_require_auth`/`_require_editor` definitions and imported the
  shared versions instead, aliased to the same local names (e.g.
  `from auth import require_session as _require_auth`) so every existing
  `Depends(_require_auth)` call site kept working unchanged.
- Also removed now-unused imports left behind in the process: the `Request`
  type (no longer used once the local `_get_token`/`_require_auth` were
  removed) in 8 files, and an already-unused `ROLES` import in 5 files.

### 3.3 What was deliberately left alone

- **`research_proposals`** keeps its own local `_require_editor`. Unlike
  every other app (which gates on `EDITOR_ROLES` membership across *all* of
  a user's roles via `auth.can_edit`), this app gates on the session's
  *primary* role level vs. `"tester"` — a real, pre-existing behavioral
  difference (not just a stylistic copy) used consistently throughout that
  file. Unifying it would have silently changed who can edit there, so it
  was left as-is with a comment explaining why.
- **`web/apps/directory`** was included in this de-duplication (it's one of
  the 9), since it's still live per section 2.3 above.

### 3.4 A regression caught during this work

While removing the local auth blocks, the import for `can_edit` (used
elsewhere as `_can_edit_check` inside each app's own `/api/auth-check`
endpoint, separately from the removed functions) was accidentally dropped in
5 apps (`directory`, `event_tracker`, `mobility_planner`,
`researcher_connect`, `unigracon`). This would have caused a `NameError`
(500 response) on every call to those apps' auth-check endpoint.

This was only caught because the refactor was verified with actual FastAPI
`TestClient` requests through the real dependency-injection chain (not just
`import` checks, which don't execute function bodies). All 5 were fixed by
re-adding `can_edit as _can_edit_check` to their import lines.

### 3.5 Verification performed

For all 9 apps, via `fastapi.testclient.TestClient` against real mounted
routes:

- `/api/auth-check` returns 200 (no server errors) for guest, a generic
  editor role, a non-editor role, a UMA-domain role, and `content_manager`.
- Guest/non-privileged tokens get `403` on write endpoints; a sufficiently
  privileged token passes the auth layer (verified by reaching body
  validation instead of being rejected).
- App-specific gating still behaves identically: `new_directory`'s
  `content_manager`-only endpoints, `uma_holiday_tracker`'s and
  `collaboration_dashboard`'s `@uma.es`-email requirement, and
  `research_proposals`'s distinct role-threshold check.
- `event_tracker`'s separate query-param token path (used by its iCal feed,
  which doesn't go through `Depends`) still works, since its direct
  `get_session` import was correctly kept.
