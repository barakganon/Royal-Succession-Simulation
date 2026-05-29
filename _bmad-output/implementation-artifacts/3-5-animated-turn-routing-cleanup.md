# Story 3-5: Animated Turn Pass + Routing + Delete action_phase

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player on the world map,
I want End Turn to play the turn's events as toasts on the map before taking me to the turn report, to land on the map straight after login, and to no longer have the obsolete action-phase screen,
so that the map is the single, self-contained play surface and turn resolution feels alive instead of an abrupt page jump.

## Acceptance Criteria

1. **AC1 — `advance_turn` content-negotiated JSON.** `dynasty.advance_turn` (currently a 302-redirect GET at `blueprints/dynasty.py:231-332`) gains a JSON mode: when the request is XHR (`request.headers.get('X-Requested-With') == 'XMLHttpRequest'`), it processes the turn EXACTLY as today (same `process_dynasty_turn` + AI turns + victory check + `is_turn_processing` lock + storing `flask_session['last_turn_summary']` and `['last_turn_dynasty_id']`), but instead of redirecting it returns:
   ```json
   {
     "ok": true,
     "redirect": "/dynasty/<id>/turn_report",   // or the victory URL, or view_dynasty on failure
     "summary": {
       "start_year": 1300, "end_year": 1305, "years_advanced": 5,
       "interrupt_reason": "quiet_period", "living_count": 7, "current_wealth": 340,
       "events": [{"year": 1302, "text": "...", "type": "death"}]
     }
   }
   ```
   - `summary` mirrors the existing turn-summary dict (keys already produced by `process_dynasty_turn`; see `turn_report.html` usage: `start_year`, `end_year`, `years_advanced`, `interrupt_reason`, `living_count`, `current_wealth`, `events[]` each `{year,text,type}`). On failure/no-summary, `ok:false`, `summary:null`, `redirect` = view_dynasty (or current map). On victory, `redirect` = victory URL (summary still stored in session is not required for victory).
   - Session state is still written so `turn_report` renders normally after the JS navigates to `redirect`.
   - **The non-XHR path is unchanged** — a plain GET still 302-redirects (no-JS fallback). Keep `@block_if_turn_processing` and the lock semantics intact.

2. **AC2 — Animated End Turn on the map.** In `templates/world_map.html`, replace the End Turn `<a href="{{ url_for('dynasty.advance_turn', ...) }}">` (lines ~33-37) with a JS-driven control (keep `id="end-turn-btn"`). On click an `endTurn()` function:
   - Disables the button + shows a brief processing state (prevent double-submit; respect that a turn may already be processing).
   - `fetch(advanceTurnUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }, credentials: 'same-origin' })`.
   - On JSON: plays `data.summary.events` as **sequential toasts** into a toast stack (`#turn-toast-stack`), ~700ms apart, each toast type-colored by `event.type` (death/birth/marriage/succession/world_event — reuse the icon/color mapping concept from `turn_report.html:88-111`). If `events` is empty (quiet turn), show a single `"N quiet years passed"` toast using `summary.years_advanced`.
   - After the toasts finish (or immediately on `ok:false`), `window.location = data.redirect`.
   - **No-JS fallback:** keep a real `href` to `advance_turn` on the element (or a `<noscript>` link) so the button still works without JS (the non-XHR 302 path).
   - CSS for the toast stack + toasts in `static/style.css` (slide-in, dismiss, type colors using existing theme vars).

3. **AC3 — Dashboard becomes secondary; login lands on the map.** `auth.dashboard` (`blueprints/auth.py:100`): if `current_user` has ≥1 dynasty AND `request.args.get('manage') != '1'`, `redirect(url_for('map.world_map'))`. Otherwise render the dashboard as today. Because login already redirects to `auth.dashboard` (`auth.py:84`), this transitively makes **login land on the map** for players with a dynasty — do NOT change the login route itself. Users with **no** dynasty still see the dashboard (unaffected). The dashboard remains reachable for switching/creating via `?manage=1`. Update `view_dynasty.html`'s back-link / any in-app "Dashboard" link that should still reach the manager to use `?manage=1` where appropriate (keep at least one path to the dashboard alive).

4. **AC4 — Delete the action_phase screen.** Remove the `action_phase` route (`blueprints/dynasty.py:382`-end of that view, ~382-503) and delete `templates/action_phase.html`. Remove the `action_phase` link in `templates/view_dynasty.html:30-32` (the "Take Actions" button). `GET /dynasty/<id>/action_phase` must return **404**. **Keep** the `submit_actions` route (`dynasty.py:521`) — it is a separate POST endpoint still referenced by tests; do NOT remove it in this story (note it as legacy in a comment). **Keep** `view_dynasty.html` as the dynasty-stats sub-page (do NOT delete it).

5. **AC5 — No regressions; existing tests updated by the backend agent.** The behavior changes break existing tests — they MUST be updated (not deleted) to match:
   - `tests/integration/test_dynasty_routes.py` — references `action_phase` (~15 assertions): repoint to the new reality (expect 404 for the action_phase URL; exercise advance_turn/submit_actions directly where the test intent was "take a turn").
   - Dashboard-page tests that expect a 200 render: `tests/integration/test_auth_routes.py` (~276-289), `test_flask_app.py` (~128,139), `test_game_loop.py` (~105) — for a user **with** a dynasty, either add `?manage=1` (to assert the dashboard renders) or assert the new redirect to `/world/map`, per each test's intent. Fresh no-dynasty users need no change.
   - Full suite stays green (**313 baseline** + new tests).

6. **AC6 — At least 5 new integration tests** in a new file `tests/integration/test_animated_turn_and_routing.py` (fixture pattern from `tests/integration/test_detail_panel_render.py`):
   - Dashboard redirects to `/world/map` (302, `Location` contains `/world/map`) for a logged-in user with a dynasty.
   - `dashboard?manage=1` renders the dashboard (200) for that same user.
   - `GET /dynasty/<id>/action_phase` returns 404.
   - `advance_turn` with header `X-Requested-With: XMLHttpRequest` returns JSON with `ok`, `redirect`, and a `summary` object (assert `Content-Type` is JSON and the keys exist). Mock the LLM per project rules.
   - `/world/map` template contains the animation wiring: `b"turn-toast-stack"`, `b"X-Requested-With"`, `b"end-turn-btn"`, and `b"endTurn"`.

## Tasks / Subtasks

- [ ] **Task 1 — Backend (AC1, AC3, AC4, AC5)** — `blueprints/dynasty.py`, `blueprints/auth.py`, `templates/view_dynasty.html`, delete `templates/action_phase.html`, + update existing tests.
  - [ ] advance_turn JSON branch (XHR) returning `{ok, redirect, summary}`; keep non-XHR 302 + lock + victory.
  - [ ] dashboard conditional redirect (`has dynasty and manage != '1'` → world_map).
  - [ ] delete action_phase route + template + view_dynasty link; keep submit_actions + view_dynasty.
  - [ ] update `test_dynasty_routes.py` (action_phase → 404 / direct turn calls) + the dashboard-page tests in `test_auth_routes.py` / `test_flask_app.py` / `test_game_loop.py`. Run full suite green.
- [ ] **Task 2 — Frontend animation (AC2)** — `templates/world_map.html`, `static/style.css`.
  - [ ] End Turn button → `endTurn()` fetch + sequential toasts + redirect; no-JS fallback href.
  - [ ] `#turn-toast-stack` container + toast CSS (type-colored).
- [ ] **Task 3 — Tests (AC6)** — new `tests/integration/test_animated_turn_and_routing.py` (≥5 tests; contract-first — will fail in isolation, green after integration).

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A (backend + existing-test maintenance)** — `blueprints/dynasty.py`, `blueprints/auth.py`, `templates/view_dynasty.html`, delete `templates/action_phase.html`, and edits to EXISTING test files (`test_dynasty_routes.py`, `test_auth_routes.py`, `test_flask_app.py`, `test_game_loop.py`). Owns AC1, AC3, AC4, AC5. Must keep its own worktree's `pytest` green (it has the backend changes, so it must fix the existing tests).
- **Agent B (frontend animation)** — `templates/world_map.html`, `static/style.css`. Owns AC2.
- **Agent C (new tests)** — ONLY the new file `tests/integration/test_animated_turn_and_routing.py`. Owns AC6. Contract-first: these tests FAIL in C's isolated worktree (A+B's changes absent) and go green after integration — do NOT weaken them.
- No two agents touch the same file. Integration merge is clean.

### FROZEN INTERFACE CONTRACT (exact tokens; C asserts them, A/B emit them)
- advance_turn XHR detection: `request.headers.get('X-Requested-With') == 'XMLHttpRequest'`; JSON shape `{ "ok": bool, "redirect": str, "summary": {…}|null }` with summary keys listed in AC1.
- Frontend: a JS function/marker named `endTurn`; the fetch sends header `X-Requested-With`; toast stack element id/class `turn-toast-stack`; End Turn button keeps `id="end-turn-btn"`.
- Dashboard escape param: `manage=1`.

### Current turn flow (read before editing)
- `advance_turn` `blueprints/dynasty.py:231-332` — sets `is_turn_processing`, calls `process_dynasty_turn(id, 5)` → 3-tuple `(success, message, turn_summary)`, runs AI turns via `GameManager`, checks victory, stores `flask_session['last_turn_summary']` + `['last_turn_dynasty_id']`, redirects to `turn_report` (or `victory`, or `view_dynasty` on failure). **Wrap the final redirect block in an XHR check** — when XHR, `jsonify` the same outcome with a `redirect` URL instead of returning the `redirect(...)`.
- `turn_report` `dynasty.py:335-379` — pops `last_turn_summary` from session and renders. Unchanged. (This is why the JS must navigate to `redirect` after the toasts: the summary is consumed there.) Note the existing `flask_session.pop` single-use behavior (deferred item, `deferred-work.md`) is acceptable for this story — the JS navigates exactly once.
- `action_phase` `dynasty.py:382-~503` — the screen being deleted.
- `auth.dashboard` `blueprints/auth.py:100-164` — renders `dashboard.html`; add the early conditional redirect at the top.
- `world_map` route `blueprints/map.py:72` — selects `DynastyDB.query.filter_by(user_id=current_user.id).first()`; passes `dynasty_id` to the template. End Turn button uses `dynasty_id` (template var) already.

### Project rules (project-context.md)
- All LLM calls guarded + mocked in tests; DB writes in try/except + rollback. `@login_required` on routes. `url_for` only. Flash categories limited. Serialize before template/JSON — for the advance_turn JSON, build a plain dict (the `turn_summary` is already a dict of primitives + list-of-dicts; safe to `jsonify`). No new dependencies.
- Match existing inline-`onclick=`/IIFE/`window.*` style in `world_map.html` (established pattern; CSP cleanup is deferred).

### Out of scope (kept to the sprint-status definition)
- **Project-start POST wiring + the `.cannot-afford` click guard** (the Story-3-2 deferral that mentioned "Story 3-5") are NOT included — 3-5's defined scope is animated turn pass + routing + action_phase deletion. Right-click still only sets `window.lastChosenAction`. These remain in `deferred-work.md` for Sprint 4 (free actions) / a follow-up.
- `view_dynasty.html` and the `submit_actions` route are KEPT (deleting them is explicitly optional in the master plan and out of scope here).

### Testing standards
- New tests in `tests/integration/`; reuse the `_register_login_and_create_dynasty` + client fixture pattern from `test_detail_panel_render.py`; `VALID_THEME_KEY='MEDIEVAL_EUROPEAN'`; mock the LLM. For the advance_turn JSON test, send the XHR header and assert JSON.
- Use `-p no:randomly` to dodge the known pre-existing `test_project_turn_lifecycle.py` isolation flake (unrelated; logged in `deferred-work.md`).

### Project Structure Notes
- No DB schema change, no new dependency, no new blueprint. Net file delta: −1 template (`action_phase.html`), +1 test file, edits to 2 blueprints + 2 templates + CSS + 4 existing test files.

## Previous Story Intelligence (Story 3-4, just merged)
- 3-4 added the canvas IIFE pan/zoom + borders + the `.overlay-tab-bar`. The End Turn button lives in the topbar (`world_map.html:33-37`), well clear of the IIFE — Agent B's animation JS can live in the same IIFE or a small module script; keep it clear of the 3-4 pan/zoom code.
- The contract-first worktree flow worked cleanly in 3-4 (3 agents, zero merge conflicts). Same approach here. 3-4 baseline test count was **312**; with this story's existing-test edits the count shifts — treat **the current `main` count (run `pytest --collect-only -q`)** as the baseline and require the new tests to be additive on top.
- 3-4 review logged perf/cleanup defers; none affect 3-5.

## Git Intelligence
Branch: `feature/animated-turn-routing-cleanup` (cut from `main`). Suggested commits (mirroring 3-4 conventions):
- A: `feat(turn): advance_turn returns JSON for XHR + animated-turn contract`, `feat(routing): dashboard→world_map for players (manage=1 escape)`, `chore(cleanup): delete action_phase route + template; update tests`.
- B: `feat(world-map): animated End Turn — fetch summary, toast events, then redirect` (+ css commit).
- C: `test: animated turn pass + dashboard routing + action_phase 404 (contract-first)`.
Merge `--no-ff` after `pytest` green; update STATUS.md + `3-5 → done`; push only when the user asks.

## References
- `advance_turn` / `turn_report` / `action_phase`: `blueprints/dynasty.py:231`, `:335`, `:382`
- `submit_actions` (keep): `blueprints/dynasty.py:521`
- `auth.dashboard` / login: `blueprints/auth.py:100`, `:64-84`
- `world_map` route + End Turn button: `blueprints/map.py:72`, `templates/world_map.html:33-37`
- turn-summary keys + event icon/color map: `templates/turn_report.html:16-69`, `:84-111`
- existing tests to update: `tests/integration/test_dynasty_routes.py` (action_phase), `test_auth_routes.py:276-289`, `test_flask_app.py:128,139`, `test_game_loop.py:105`
- fixture pattern: `tests/integration/test_detail_panel_render.py:13-39`
- deferred items: `_bmad-output/implementation-artifacts/deferred-work.md` (flask_session.pop single-use → noted acceptable; cannot-afford guard → stays deferred)

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] — 3 parallel worktree sub-agents (backend / frontend / tests) against a frozen contract, + main-session integrator.

### Implementation Plan

Contract-first 3-agent worktree split, zero file overlap:
- **Agent A** `wt/3-5-backend` @ `fd7a732` — `advance_turn` XHR→JSON (`{ok,redirect,summary}` at every return incl. victory/failure), `auth.dashboard` → `world_map` when the user has a dynasty & `manage!=1`, deleted `action_phase` route + `templates/action_phase.html` + the view_dynasty link (kept `submit_actions` + `view_dynasty`), and updated the existing tests that referenced action_phase/dashboard.
- **Agent B** `wt/3-5-frontend` @ `858b8e2` — `endTurn()` fetch (`X-Requested-With`) → sequential type-colored toasts in `#turn-toast-stack` → redirect; no-JS `href` fallback + double-submit guard; toast CSS.
- **Agent C** `wt/3-5-tests` @ `ac609b2` — `tests/integration/test_animated_turn_and_routing.py` (6 contract-first tests).
- **Integrator** — merged A→B→C clean (no overlap); fixed one C bonus-test bug (asserted a flat `year`; corrected to the contract keys `start_year`/`end_year`); reviewed all seams.

### Completion Notes List

- All 6 ACs satisfied. `pytest -p no:randomly`: **315 passed, 0 failed, 0 skipped** (was 312; net −3 from A's action_phase-test consolidation, +6 from C).
- Backend XHR branch verified at all five `advance_turn` return points; dashboard `manage=1` escape works; `GET /dynasty/<id>/action_phase` → 404; frontend correctly consumes the JSON contract with fallbacks.
- One integrator patch: corrected C's bonus assertion (`'year'` → `start_year`/`end_year`).
- Defers logged (`deferred-work.md`, 2026-05-29): advance_turn should be POST; turn_report single-use summary; project-start/cannot-afford still unwired (Sprint 4).
- **Epic 3 (Map as Main View) is now complete** (3-1…3-5 all done).
- **Visual verification deferred** (no dev server in session). Pending the user's `/world/map` check: End Turn plays event toasts then lands on the turn report; logging in goes straight to the map; `/dashboard?manage=1` still reaches the manager; old action_phase URL 404s.

### File List

- `blueprints/dynasty.py` — MODIFIED (advance_turn XHR/JSON; action_phase view removed; submit_actions kept)
- `blueprints/auth.py` — MODIFIED (dashboard → world_map redirect with manage=1 escape)
- `templates/view_dynasty.html` — MODIFIED (removed action_phase "Take Actions" link)
- `templates/action_phase.html` — DELETED
- `templates/world_map.html` — MODIFIED (End Turn button → `endTurn()`, `#turn-toast-stack`)
- `static/style.css` — MODIFIED (toast stack + toast styles)
- `tests/integration/test_animated_turn_and_routing.py` — NEW (6 tests; 1 integrator fix)
- `tests/integration/test_dynasty_routes.py` — MODIFIED (action_phase → 404 assertions)
- `tests/integration/test_game_loop.py` — MODIFIED (dashboard?manage=1)
- `_bmad-output/implementation-artifacts/{sprint-status.yaml, deferred-work.md, 3-5-...md}` — MODIFIED

### Change Log

| Date | Change |
|---|---|
| 2026-05-29 | spec(3-5) committed (frozen contract for 3 worktree agents) |
| 2026-05-29 | wt/3-5-backend / wt/3-5-frontend / wt/3-5-tests implemented in parallel |
| 2026-05-29 | merged all three into feature/animated-turn-routing-cleanup (clean) |
| 2026-05-29 | integrator fix (test contract keys); review of XHR/dashboard/endTurn seams |
| 2026-05-29 | pytest: 315 passed, 0 failed, 0 skipped (was 312) |
| 2026-05-29 | Story 3-5 → done; Epic 3 complete |
