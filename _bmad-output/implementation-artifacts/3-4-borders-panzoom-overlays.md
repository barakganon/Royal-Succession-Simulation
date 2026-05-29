# Story 3-4: Borders + Pan/Zoom + Overlay Tabs

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player exploring the world map,
I want realm borders drawn between territories of different owners, full pan/zoom control of the canvas, and the overlay modes presented as a clean bottom tab switcher,
so that the map reads like a real grand-strategy realm map and I can navigate dynasties of any size.

## Acceptance Criteria

1. **AC1 — Realm borders.** After the hex fill pass in `drawAll()`, a border pass draws a **thick ink-style stroke** on every hex edge that separates two territories with **different `owner_dynasty_id`** (treat `null`/unclaimed as its own "owner" — i.e. a claimed hex bordering an unclaimed hex gets a border). Internal edges (same owner on both sides) get no thick stroke. Border stroke is visually distinct from the existing thin per-hex outline (e.g. width ≥ 2.5 in world units, color `var(--dark-border)` ink tone `#2b2114` or similar dark ink). Borders render correctly under **every** overlay mode (terrain/armies/economy/threats/projects), not just terrain.

2. **AC2 — Scroll-wheel zoom.** Scrolling the wheel over the canvas zooms in/out, **centered on the cursor position** (the world point under the cursor stays under the cursor). Zoom is clamped to a sane range (e.g. `MIN_SCALE = 0.3`, `MAX_SCALE = 3.0`). `e.preventDefault()` is called so the page doesn't scroll.

3. **AC3 — Middle-drag pan.** Holding the **middle mouse button** (`e.button === 1`) and dragging pans the map. Pan does not start on left-click (reserved for select/detail) or right-click (reserved for context menu). A grab/grabbing cursor affordance is applied during pan. Pan ends on `mouseup`/`mouseleave`.

4. **AC4 — Double-click recenter.** Double-clicking a hex recenters the view on that territory (and may keep the current zoom). Double-click must **not** also fire the single-click select/detail flow in a way that opens the panel for the recenter gesture (debounce or suppress the trailing click, or accept the documented minor overlap and note it).

5. **AC5 — Hit-testing respects the transform.** All existing pointer interactions — hover tooltip (`mousemove`), left-click select + detail panel, right-click context menu — continue to target the correct hex at **any** zoom/pan. This means `nearestHex(mx, my)` (or its callers) must convert screen coordinates back to world coordinates using the inverse of the current pan/zoom transform before comparing distances. **This is the highest-risk requirement: drawing the zoom but not inverting it in hit-testing silently breaks every click.** See Dev Notes "Pan/zoom math".

6. **AC6 — Overlay tab switcher.** The overlay mode controls are presented as a **bottom tab bar** (matching the master-plan layout: tabs along the bottom of the map area), not the current top button cluster. All **five** existing modes remain functional — `terrain`, `armies`, `economy`, `threats`, `projects` — and `setOverlay(mode)` keeps working unchanged. The active tab is visually highlighted. Do **not** remove any overlay mode (removing `economy` would break `test_world_map_renders_five_overlay_buttons`).

7. **AC7 — `_renderWorldCard` stub text updated.** The detail-panel world card currently reads `"World overview — coming in Story 3-4 (border drawing + pan/zoom)."` (line ~440). Since this is Story 3-4, update it to a non-self-referential placeholder (e.g. `"World overview — other dynasties' news arrives in a later chronicle update."`). World-news *content* is **out of scope** here (it belongs to Epic 9); only fix the now-stale forward-reference text. Update the corresponding assertion if any test pins that literal.

8. **AC8 — No regressions; tests stay green.** `pytest` must remain at **306 passed, 0 failed, 0 skipped** (new tests are additive). All existing world-map tests still pass: `test_world_map_panels.py`, `test_world_map_context_menu.py`, `test_detail_panel_render.py`.

9. **AC9 — At least 4 new integration tests** in a new file `tests/integration/test_world_map_panzoom_borders.py` (template/JS substring pattern, consistent with `test_detail_panel_render.py`):
   - Pan/zoom handlers present: JS contains a `wheel` listener AND a transform reference (`setTransform` or `scale`).
   - Middle-drag pan present: JS references `button === 1` (or `e.button == 1`) / `mousedown` pan branch.
   - Double-click recenter present: JS contains a `dblclick` listener.
   - Border pass present: JS contains the border-drawing routine (assert on a stable marker — a function name like `drawBorders` or a `BORDER` comment/const you introduce; pick one and keep it stable for the test).
   - Overlay tab bar present: `/world/map` HTML contains the bottom tab container (assert on a class you introduce, e.g. `overlay-tab-bar`, plus all five `btn-<mode>` ids still present).

## Tasks / Subtasks

- [ ] **Task 1 — Pan/zoom transform core (AC2, AC3, AC4, AC5)**
  - [ ] Add module-scoped state in the IIFE: `var scale = 1, panX = 0, panY = 0;`
  - [ ] In `drawAll()`, apply the transform once before the feature loop. Recommended: `ctx.setTransform(scale, 0, 0, scale, panX, panY)` at the top, draw all hexes/markers in **world coordinates** (`c.x + offsetX`, `c.y + offsetY` — unchanged), then `ctx.setTransform(1,0,0,1,0,0)` before drawing any screen-fixed text/empty-state. (Keep the `clearRect`/background fill in identity transform.)
  - [ ] Add `screenToWorld(mx, my)` helper: `{ x: (mx - panX) / scale, y: (my - panY) / scale }`.
  - [ ] Rewrite `nearestHex(mx, my)` to first convert to world coords via `screenToWorld`, then compare against `c.x + offsetX` / `c.y + offsetY` with threshold `R` (threshold stays in world units). Fix the dead `if (dist < best)` line (best starts `null`) while you're in there — see Dev Notes.
  - [ ] `wheel` listener: compute world point under cursor, adjust `scale` (clamp), then recompute `panX/panY` so that world point stays under the cursor. `e.preventDefault()`. `drawAll()`.
  - [ ] `mousedown`/`mousemove`/`mouseup`/`mouseleave` middle-button pan: on `button===1` start, accumulate `panX/panY` by mouse delta, `drawAll()` each move; restore cursor on end.
  - [ ] `dblclick` listener: `nearestHex` → set `panX/panY` so that hex center maps to canvas center; `drawAll()`.
- [ ] **Task 2 — Realm border pass (AC1)**
  - [ ] Build a `Map`/lookup of `(col,row) → feature` once per `drawAll` (or cache on load) for neighbor lookup.
  - [ ] Add `drawBorders()` called after the fill loop, inside the same transform. For each hex, for each of its 6 edges, find the neighbor across that edge; if neighbor missing OR `neighbor.owner_dynasty_id !== this.owner_dynasty_id`, stroke that edge thick. See Dev Notes "Border geometry" for the robust center-based neighbor match (do NOT assume a textbook axial formula — the orientation/offset layout in this file is non-standard).
- [ ] **Task 3 — Overlay tab bar (AC6)**
  - [ ] Move the `.map-overlay-btns` markup (lines ~130-136) into a bottom tab bar element (new class e.g. `overlay-tab-bar`) positioned along the bottom of the map area / in the botbar. Keep all five buttons + their `id="btn-<mode>"` + `onclick="setOverlay('<mode>')"`.
  - [ ] CSS in `static/style.css` for the tab bar + active-tab highlight + (optional) `cursor: grab/grabbing` on the canvas during pan.
- [ ] **Task 4 — Stub text fix (AC7)**
  - [ ] Update `_renderWorldCard` literal; update any test that pins the old string.
- [ ] **Task 5 — Tests (AC8, AC9)**
  - [ ] New `tests/integration/test_world_map_panzoom_borders.py` (≥ 4 tests, see AC9).
  - [ ] Run full `pytest` — confirm 306 + new, 0 failed, 0 skipped.

## Dev Notes

### Scope is FRONTEND-ONLY — no backend, no DB, no new GeoJSON fields
Story 3-3 already enriched the GeoJSON (`hex=true`) with everything needed. `owner_dynasty_id`, `col`, `row`, `owner_dynasty_hue`, `terrain_type`, `is_capital`, `army_count`, `population`, `hostile_garrison_total`, `active_project_type` are all present per feature. **Do not touch `visualization/map_renderer.py`, `blueprints/map.py`, or `models/`.** No Alembic / `db_initialization.py` changes.

### Files to modify
- `templates/world_map.html` — the canvas IIFE (`(function(){ 'use strict'; ... })()`, lines **545–1098**). All pan/zoom + border logic lives here. Overlay markup at lines ~130-136. `_renderWorldCard` at line ~436-441.
- `static/style.css` — overlay tab bar styles + pan cursor.
- `tests/integration/test_world_map_panzoom_borders.py` — NEW.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — set by the dev/CR cycle (`3-4`: ready-for-dev → in-progress → done).

### Current rendering model (READ THIS before editing — `templates/world_map.html`)
- `R = 28` fixed hex radius (`world_map.html:549`).
- `hexCenter(col,row)` → world coords: `x = R*sqrt3*col + (row%2)*R*sqrt3/2; y = R*1.5*row` (line 576).
- `hexPath(cx,cy)` → 6 vertices at `angle = PI/3 * i` (vertex at 0°=East). **This is a non-standard combo:** vertex orientation reads flat-top while the `hexCenter` odd-row horizontal offset is the pointy-top-style layout. Tessellation is approximate. **Implication for borders:** do not assume the standard 6 axial neighbor offsets line up cleanly — match neighbors by geometry (below).
- `computeOffset()` (line 646) sets `offsetX/offsetY` once on load to bring the map into view. **Keep this.** It is the *base layout*; pan/zoom layers on top via `scale/panX/panY`. World coord of a hex = `hexCenter(col,row) + offset`.
- `drawAll()` (line 663): clears, fills bg, then per-feature computes `cx = c.x + offsetX; cy = c.y + offsetY` and draws. Overlay fill logic (terrain/armies/economy/threats/projects) is lines 695-721 — **leave it intact**, your transform wraps around it.
- `nearestHex(mx,my)` (line 763): currently compares raw screen `mx,my` to `c.x+offsetX`. **Must be updated to invert the transform.** Note the latent bug at line 774 (`if (dist < best)` with `best=null` → always false); the real work is the next line. Clean it up: init `bestDist=Infinity, best=null`, keep only the `dist < bestDist` branch.
- Pointer handlers: `mousemove` tooltip (780), `contextmenu` (963), left-`click` (990), all call `nearestHex` with screen coords from `getBoundingClientRect()`. Once `nearestHex` inverts the transform internally, these callers need **no change**.
- `setOverlay(mode)` (line 1028) iterates `['terrain','armies','economy','threats','projects']` toggling `btn-<mode>.active`. Keep this list intact.
- GeoJSON loaded at line 1073 via `/game/<id>/map.geojson?hex=true`; `computeOffset(); resizeCanvas();` then drawn.

### Pan/zoom math (the critical part — AC5)
Screen point `(sx,sy)` ↔ world point `(wx,wy)`:
```
sx = wx * scale + panX        wx = (sx - panX) / scale
sy = wy * scale + panY        wy = (sy - panY) / scale
```
**Cursor-anchored zoom** (AC2): before changing scale, capture `wx,wy = screenToWorld(mx,my)`. After setting the new clamped `scale`, set `panX = mx - wx*scale; panY = my - wy*scale`. That keeps the point under the cursor fixed.
**Recenter on hex** (AC4): given hex world center `(wx,wy)` (= `hexCenter + offset`), set `panX = canvas.width/2 - wx*scale; panY = canvas.height/2 - wy*scale`.
Two equivalent implementation styles — pick one and be consistent:
1. **`ctx.setTransform(scale,0,0,scale,panX,panY)`** and draw in world coords (recommended — minimal change to the draw loop). Reset to identity (`setTransform(1,0,0,1,0,0)`) before the `clearRect`/bg-fill and before any screen-fixed text (the "No territory data" / "Create a dynasty" messages at 668-673, 1088-1091).
2. Manually map every coord (`sx = (c.x+offsetX)*scale + panX`). More error-prone; avoid.

### Border geometry (AC1) — robust neighbor match
The orientation/offset combo is non-standard, so derive neighbors empirically rather than from a formula:
- Build `byColRow = {}` keyed `col + ',' + row` → feature, once.
- For a hex at world center `C`, its 6 edges are between consecutive `hexPath` vertices. The neighbor across an edge sits at center `C + 2*(edgeMidpoint - C)` ≈ `C` reflected through the edge midpoint (for a regular hex, neighbor center = `C + 2*apothem` along the edge normal). Practically: compute each edge's midpoint `M`, then the candidate neighbor center is `C + 2*(M - C)`. Find the feature whose world center is nearest that candidate (within a small epsilon, e.g. `R*0.6`). If none → unclaimed edge of the map → draw border. If found and its `owner_dynasty_id !== current` → draw border.
- Stroke the edge segment (the two vertices) thick. Because adjacent hexes share the edge, it will be drawn twice (once from each side) — harmless; or de-dupe by only drawing when `current.territory_id < neighbor.territory_id || neighbor missing`.
- **This is visual-only.** No unit test can assert pixels; AC9 asserts the routine *exists* by a stable name/marker. Visual correctness is verified manually (see Verification).

### Overlay tabs (AC6) — light touch
The five overlay buttons already work. This task is mostly **markup relocation + CSS** to present them as a bottom tab bar per the master-plan layout (`review_documents/8_master_plan_2026.md:261`). Do not change `setOverlay` semantics or the mode list. Keep `id="btn-<mode>"` so existing tests (`test_world_map_renders_five_overlay_buttons`, `test_set_overlay_supports_threats_and_projects`) keep passing.

### Why double-click needs care (AC4)
A `dblclick` is preceded by two `click` events. The existing left-`click` handler (990) selects the hex and opens the detail panel. If you bind `dblclick` to recenter, the user also gets the panel opened from the preceding clicks. Acceptable mitigations: (a) accept it and document, (b) small timer to suppress the single-click action if a dblclick follows, or (c) only open the detail panel on click if no dblclick fired within ~250ms. Keep it simple; note your choice in Completion Notes.

### Project anti-patterns to honor (from project-context.md)
- Templates must `{% extends 'base.html' %}` (already does). No inline prompt strings, no backend changes.
- This codebase already uses inline `onclick=` and `window.*` globals in this template (flagged CSP-hostile in `deferred-work.md` but it's the established pattern). **Match the existing style** — keep pan/zoom logic inside the existing IIFE; expose to `onclick=` only if a control needs it (the tab buttons already call the global `setOverlay`). Do not introduce a build step or new JS dependency.
- No `print()`; this is JS/CSS/template work so logging rules don't apply, but keep `console.error` only for genuine failures (matches existing `catch` blocks).

### Testing standards
- Tests live in `tests/integration/`. Use the established fixture pattern from `tests/integration/test_detail_panel_render.py`: `_register_login_and_create_dynasty(...)` + a `dpr_client` fixture (`username` unique per file), `VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'`, then `client.get('/world/map')` and assert substrings in `response.data`. This is the codebase-sanctioned way to test canvas/JS features (no JS test runner exists).
- These are JS/template **presence** assertions — pick stable markers (function names / class names / consts you introduce) and assert on those, not on volatile inline text.
- Run `pytest -p no:randomly` if you hit the known intermittent `test_develop_action_raises_development_level` flake (pre-existing, logged in `deferred-work.md`, unrelated to this story).

### Project Structure Notes
- All changes confined to `templates/world_map.html`, `static/style.css`, one new test file. No conflict with the project layout. No new modules, no schema change, no route change.

## Previous Story Intelligence (Story 3-3)

- 3-3 added the GeoJSON enrichment + detail panel + Threats/Projects overlays + left-click→detail, and the monarch-traits route wiring. It established `window.__activeProjectsById / __monarchData / __recentEvents / __activeWars / currentSimYear` seeds and the `_renderXCard` family in the same template. **Do not disturb those** — your work is purely additive to the canvas IIFE + overlay markup.
- 3-3 review deferred several map items now relevant to read (in `deferred-work.md`, "Story 3-3" section): unscoped table scans in `generate_geojson` (perf — NOT this story), unclaimed-hex hostile classification, Projects-overlay no-op when zero projects. None are in 3-4 scope; do not fix here.
- 3-3 worktree-split approach is overkill for 3-4 (single template + css + one test file). **Recommend a single branch, no worktrees.**
- Visual verification was deferred in 3-3 ("Session can't run the dev server"). 3-4 is heavily visual (borders, zoom, pan) — flag the same: test-verify code presence, then the user runs `python main_flask_app.py` and checks `/world/map`.

## Git Intelligence

Recent commits (Story 3-3, merged `6ec9fd7`) touched exactly the files 3-4 extends: `templates/world_map.html` (+310), `static/style.css` (+145), `visualization/map_renderer.py`, `blueprints/map.py`. The 3-3 frontend commits used the message style `feat(world-map): ...` / `feat(world-map-css): ...` / `test: world_map ...`. Follow the same convention.

Suggested branch + commits (per project Git Workflow):
- Branch: `feature/borders-panzoom-overlays` (cut from `main`).
1. `feat(world-map): canvas transform pan/zoom + transform-aware hit-testing`
2. `feat(world-map): realm border pass between differing owner_dynasty_id`
3. `feat(world-map-css): bottom overlay tab bar + pan cursor` (markup + css)
4. `fix(world-map): update _renderWorldCard stale Story-3-4 forward reference`
5. `test: world_map pan/zoom + borders + overlay tabs`
- Merge `--no-ff` after `pytest` is green; update `STATUS.md`.

## Project Context Reference

Full agent rules: `_bmad-output/project-context.md` (technology stack, template rules, testing fixtures, git workflow). Master-plan source of truth for this sprint: `review_documents/8_master_plan_2026.md` (Sprint 3 section, lines ~240-411; pan/zoom + borders tasks at 397-398, layout at 261). Sprint tracker: `_bmad-output/implementation-artifacts/sprint-status.yaml` (Epic 3, story `3-4-borders-panzoom-overlays`).

## References

- Canvas IIFE: `templates/world_map.html:545-1098`
- `drawAll`: `templates/world_map.html:663-758`
- `nearestHex` (hit-testing + latent bug): `templates/world_map.html:763-778`
- `setOverlay` + overlay button markup: `templates/world_map.html:1028-1035` and `:130-136`
- `_renderWorldCard` stale stub: `templates/world_map.html:436-441`
- GeoJSON property emission (`owner_dynasty_id`, `col`, `row`, `owner_dynasty_hue`): `visualization/map_renderer.py:generate_geojson` (`:665-735` region, hex_mode block)
- Master plan tasks: `review_documents/8_master_plan_2026.md:319` (borders), `:333` (pan/zoom), `:321-326` (overlay tabs), `:397-398` (task checklist)
- Test fixture pattern: `tests/integration/test_detail_panel_render.py:13-39`
- Prior story: `_bmad-output/implementation-artifacts/3-3-detail-panel-and-geojson.md`
- Deferred items log: `_bmad-output/implementation-artifacts/deferred-work.md`

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] — 3 parallel worktree sub-agents (canvas JS / tabs+CSS / tests) against a frozen interface contract, + main-session integrator.

### Implementation Plan

Implemented via a contract-first 3-agent worktree split (the master plan / user-requested multi-agent flow):
- **Agent A** `wt/3-4-canvas` @ `7e95f57` — all canvas-IIFE JS: `screenToWorld` + transform-aware `nearestHex`, `ctx.setTransform` pan/zoom in `drawAll`, cursor-anchored `wheel` zoom, middle-drag pan (`e.button === 1`, toggling `is-panning`), `dblclick` recenter (with `e.detail >= 2` + 350ms `suppressClickUntil` guards), `drawBorders()` (centre-based neighbour match), and the `_renderWorldCard` text fix.
- **Agent B** `wt/3-4-tabs-css` @ `f8c85c2` — overlay markup relocated into `.overlay-tab-bar` (five ids + `setOverlay` preserved) + `static/style.css` tab strip, active highlight, and `cursor: grab`/`.is-panning{grabbing}`.
- **Agent C** `wt/3-4-tests` @ `bf9da32` — `tests/integration/test_world_map_panzoom_borders.py` (6 contract-first tests; failed in isolation by design, green after integration).
- **Integrator** — merged A→B→C into `feature/borders-panzoom-overlays` (clean `ort` merges; A's script vs B's markup regions of `world_map.html` did not overlap), ran full suite, reviewed the seams + transform math.

### Completion Notes List

- All 9 ACs satisfied. Frozen contract honoured by all three agents (tokens verified present in merged template/CSS).
- `pytest -p no:randomly`: **312 passed, 0 failed, 0 skipped** (306 baseline + 6 new). The pre-existing `test_project_turn_lifecycle.py` isolation flake does not fire under `-p no:randomly`.
- Integration-review findings (all non-blocking, logged to `deferred-work.md` under 2026-05-29): drawBorders O(N²)-per-frame perf; dead `byColRow`; approximate border neighbour geometry under the non-standard hex layout.
- **Visual verification deferred** (session can't run the dev server). Pending the user's `python main_flask_app.py` → `/world/map` check: realm borders on owner boundaries; scroll-wheel zoom anchored to cursor; middle-drag pan with grab cursor; double-click recenter (no panel pop); overlay tabs along the bottom switch recolor; hover/left-click/right-click still hit the correct hex at any zoom/pan.

### File List

- `templates/world_map.html` — MODIFIED (canvas IIFE: pan/zoom + hit-testing + `drawBorders`; `_renderWorldCard` text; overlay markup → `.overlay-tab-bar`)
- `static/style.css` — MODIFIED (`.overlay-tab-bar` tab strip + active highlight; canvas `grab`/`.is-panning` cursor)
- `tests/integration/test_world_map_panzoom_borders.py` — NEW (6 contract-first integration tests)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED (3-4: backlog → ready-for-dev → done)
- `_bmad-output/implementation-artifacts/deferred-work.md` — MODIFIED (3 Story 3-4 defers)
- `_bmad-output/implementation-artifacts/3-4-borders-panzoom-overlays.md` — MODIFIED (this record)

### Change Log

| Date | Change |
|---|---|
| 2026-05-29 | spec(3-4) committed (frozen interface contract for 3 worktree agents) |
| 2026-05-29 | wt/3-4-canvas / wt/3-4-tabs-css / wt/3-4-tests implemented in parallel worktrees |
| 2026-05-29 | merged all three into feature/borders-panzoom-overlays (clean) |
| 2026-05-29 | integration review (transform math + A↔B seams); 3 non-blocking defers logged |
| 2026-05-29 | pytest: 312 passed, 0 failed, 0 skipped (was 306) |
| 2026-05-29 | Story status → done |