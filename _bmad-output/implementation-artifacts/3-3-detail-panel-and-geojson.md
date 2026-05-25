# Story 3-3: Right Detail Panel + GeoJSON Upgrade

Status: done

## Story

As a player who clicks a hex (or a left-rail slot) on the world map,
I want the right slide-in detail panel to render the right thing for the context (territory card with buildings/garrison/active project, or a project card, or a monarch card, or an empty-slot placeholder),
and I want the canvas overlay buttons to include **Threats** and **Projects** views,
so the world map can drive the entire turn loop without leaving the map.

## Acceptance Criteria

1. **AC1 — GeoJSON enriched (hex_mode only).** `visualization/map_renderer.generate_geojson(dynasty_id, session, hex_mode=True)` adds three new per-feature properties:
   - `buildings`: list of `{'building_type': str, 'name': str, 'level': int}` for buildings on that territory (or `[]`).
   - `garrison_total`: integer sum of `size` over all MilitaryUnits in the territory whose dynasty_id == `controller_dynasty_id`.
   - `hostile_garrison_total`: integer sum of `size` over all MilitaryUnits in the territory whose dynasty_id != `controller_dynasty_id` (and != null).
   - `active_project_type`: string project_type if a player-owned active Project targets this territory; else `null`. (Player-owned = the `dynasty_id` param passed into `generate_geojson`.)
   - `active_project_id`: int or `null` mirroring active_project_type.

2. **AC2 — `/territory/<int:territory_id>/details.json` endpoint.** New `@login_required` route in `blueprints/map.py` returns JSON shape:
   ```json
   {
     "territory": {
       "id": 1, "name": "Old Hollow", "terrain_type": "forest",
       "population": 1200, "development_level": 2, "is_capital": false,
       "base_tax": 0, "fortification_level": 0,
       "controller": {"id": 1, "name": "House Foo"} or null,
       "is_player_owned": true
     },
     "buildings": [{"building_type": "FARM", "name": "Farm", "level": 1, "condition": 1.0}],
     "garrison": [{"unit_type": "LEVY_SPEARMEN", "size": 100, "morale": 1.0, "quality": 1.0}],
     "active_project": {"id": 5, "project_type": "build_walls", "started_year": 1300, "completion_year": 1305} or null
   }
   ```
   No ownership check on the territory itself (any logged-in player may inspect any hex); `is_player_owned` is derived against the current_user's primary dynasty. Returns 404 if territory doesn't exist.

3. **AC3 — Detail panel renders conditional content by `ctx.type`.** Replace the Story-3-1 stub body (`JSON.stringify(ctx) + " — Story 3-3 will fill this..."`) with a switch:
   - `ctx.type === 'territory'`: fetch `/territory/<id>/details.json`, render a territory card (name, terrain, population, owner, is_player_owned badge, building list, garrison summary, active project).
   - `ctx.type === 'project'`: render a project summary from `window.__activeProjectsById` (populated from server-side `active_projects` list passed via `world_map` route, indexed by id), showing project_type, years remaining, full cost-to-date estimate. If id is not in the cache, show "Project #X — not currently active".
   - `ctx.type === 'project_slot'`: render "Empty Slot · Right-click a territory and choose a project to fill this slot."
   - `ctx.type === 'monarch'`: render the existing `current_monarch` data passed from `world_map` (name, age) plus traits if available. Falls back to "No monarch" if absent.
   - `ctx.type === 'chronicle'`: render the existing `recent_events` array in a vertical list (year + text).
   - `ctx.type === 'world'`: render a simple "World overview — coming in Story 3-4" stub line (it's the next story's content).
   - `ctx.type === 'war'`: render a simple list of active wars involving the player dynasty, or "No active wars". Wars are passed via the route.

4. **AC4 — Clicking a hex (left-click) also opens the detail panel as `{type:'territory', id: territory_id}`.** The existing left-click handler still updates `selected-info` botbar text and toggles `selectedTerritoryId` for highlight, but now ALSO calls `openDetailPanel({type:'territory', id: p.territory_id})`.

5. **AC5 — Overlay buttons grow from 3 → 5: add Threats and Projects.** `templates/world_map.html` overlay buttons now include `Threats` and `Projects` next to terrain/armies/economy. JS `setOverlay(mode)` accepts the new modes and the canvas draw fills hex color based on:
   - `threats`: hex shaded red proportional to `hostile_garrison_total / max_hostile_garrison_total` across all features (white if 0).
   - `projects`: hex shaded gold if `active_project_type` is set, otherwise the terrain color subtly desaturated.

6. **AC6 — Map route passes `active_wars` to the template.** `blueprints/map.world_map` queries `War` for active wars involving the player dynasty and serializes a list of dicts: `[{'id', 'attacker_dynasty_id', 'attacker_name', 'defender_dynasty_id', 'defender_name', 'start_year'}, ...]`. Empty list if no wars or no dynasty. Used by AC3's `war` panel.

7. **AC7 — Existing tests still pass.** `pytest` must stay green (currently 291). New tests are additive. The Story 3-1 detail-panel stub assertions still pass — they check structural IDs which remain unchanged.

8. **AC8 — At least 8 new tests across two new test files.**
   - `tests/integration/test_territory_details_endpoint.py`:
     - 404 on missing territory.
     - 200 + correct shape on existing territory.
     - is_player_owned=true when current_user owns the controller dynasty.
     - is_player_owned=false when current_user does not.
   - `tests/integration/test_detail_panel_render.py`:
     - `/world/map` renders all 5 overlay buttons (terrain/armies/economy/threats/projects).
     - Detail panel JS no longer contains the Story-3-1 stub literal "Story 3-3 will fill this".
     - The new project_type/garrison/buildings fields appear in the served GeoJSON (when dynasty exists).
     - `/world/map` contains a `window.__activeProjectsById` initializer.

## Scope split (worktree agents)

This story is implemented by **two parallel worktree agents** working against this shared spec:

### Worktree A (backend) — `wt/3-3-backend`

Files: `visualization/map_renderer.py`, `blueprints/map.py`, `tests/unit/test_map_renderer.py` (or a new test file if needed), `tests/integration/test_territory_details_endpoint.py` (NEW).

Tasks:
- AC1: enrich `generate_geojson` with buildings/garrison/hostile_garrison/active_project per hex.
- AC2: implement `/territory/<id>/details.json`.
- AC6: extend `world_map` route to query active wars and pass `active_wars` to template (just the data; template wiring is Worktree B's job).
- Unit + integration tests.

### Worktree B (frontend) — `wt/3-3-frontend`

Files: `templates/world_map.html`, `static/style.css`, `tests/integration/test_detail_panel_render.py` (NEW).

Tasks:
- AC3: conditional detail panel rendering by `ctx.type`. Fetch `/territory/<id>/details.json` on type=territory. Use server-rendered `active_projects` array (already passed in 3-1), `current_monarch`, `recent_events`, and a NEW `active_wars` (assumes worktree A wires the route — frontend uses `active_wars | tojson` in the template).
- AC4: hook left-click `canvas.addEventListener('click', ...)` to also call `openDetailPanel({type:'territory', id})`.
- AC5: add Threats + Projects overlay buttons and JS support.
- CSS for the new detail-panel content blocks (territory card, project card, monarch card, war list).
- Integration tests for DOM presence + JS handler text.

## Dev Notes

### Why a separate detail endpoint (`/territory/<id>/details.json`) vs. baking into GeoJSON

The GeoJSON is fetched once per page load and shared across hundreds of hexes. Per-territory detail data (full building list with conditions, per-unit garrison breakdown, etc.) bloats the GeoJSON. Splitting keeps the GeoJSON lean (counts + flags) and lazy-loads detail on click. Same pattern as Story 3-2's `/project_catalogue.json`.

### Why no DB schema changes

All new GeoJSON fields and the new endpoint are derived from existing tables (Territory, Building, MilitaryUnit, Army, Project, War, DynastyDB, PersonDB). No Alembic / db_initialization changes needed.

### Active wars query

`War.query.filter(War.is_active == True, or_(War.attacker_dynasty_id == player_id, War.defender_dynasty_id == player_id)).all()`. Use `db.or_` from SQLAlchemy. The query is small (active wars are few) so no special caching is needed.

### Reused server-side data for the detail panel

`current_monarch`, `recent_events`, `active_projects` are already passed by `world_map` (Story 3-1). Worktree B uses them via Jinja `| tojson` to seed JS globals. Worktree A only adds `active_wars` to the template context — it does NOT change the existing data flow.

### `active_project_type` only marks player-owned projects on the GeoJSON

Reason: a player should see THEIR projects highlighted on the map, not foreign ones (which they couldn't influence anyway). Foreign projects can be added in a later story (Sprint 5+ AI dynasties get more visibility).

### Branch + commit plan

Branch: `feature/detail-panel-and-geojson` (already cut from main).
Sub-branches per worktree: `wt/3-3-backend`, `wt/3-3-frontend`.

After both worktrees report, the integrator (main session) merges both sub-branches into `feature/detail-panel-and-geojson`, runs pytest, runs 3-agent code review, applies patches, and merges to main.

Worktree-A commit plan (3 commits):
1. `feat(geojson): enrich hex_mode features with buildings + garrison + active_project`
2. `feat(map-route): new /territory/<id>/details.json endpoint`
3. `feat(map-route): pass active_wars to world_map template + tests`

Worktree-B commit plan (3 commits):
1. `feat(world-map-css): detail panel content blocks (territory / project / monarch / war)`
2. `feat(world-map): conditional detail panel rendering + Threats/Projects overlays + left-click → detail`
3. `test: world_map detail panel DOM + overlay buttons`

### References

- Story 3-1 spec: `_bmad-output/implementation-artifacts/3-1-world-map-panel-rebuild.md` (left rail + slide-in detail panel + active_projects route plumbing)
- Story 3-2 spec: `_bmad-output/implementation-artifacts/3-2-right-click-context-menu.md` (canvas contextmenu + JSON endpoint pattern)
- `visualization/map_renderer.generate_geojson`: `visualization/map_renderer.py:589-673`
- `blueprints/map.world_map`: `blueprints/map.py:72-176`
- `templates/world_map.html` IIFE: lines ~245-end
- `Project.target_territory_id` linkage: `models/db_models.py:629-680`
- `War.attacker_dynasty_id / defender_dynasty_id / is_active`: `models/db_models.py`

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (worktree-A + worktree-B sub-agents + main session integrator)

### Implementation Plan

Story 3-3 was split into two parallel **worktree sub-agents** working against the spec's JSON contract:

- **Worktree A (backend, `wt/3-3-backend`)** — 4 commits: GeoJSON enrichment (`generate_geojson` adds `buildings` / `garrison_total` / `hostile_garrison_total` / `active_project_type` / `active_project_id` for `hex_mode=True`); new `/territory/<int:id>/details.json` route in `blueprints/map.py` with `is_player_owned` derived from the current user's dynasties; `active_wars` list passed to the `world_map` route. Backend tests: 4 unit + 5 integration = 9 tests.
- **Worktree B (frontend, `wt/3-3-frontend`)** — 3 commits: conditional detail panel renderer in `templates/world_map.html` switching on `ctx.type` across all 7 spec'd branches (territory / project / project_slot / monarch / chronicle / world / war); new Threats and Projects overlay buttons + `setOverlay` / `drawAll` mode branches; left-click → detail panel; CSS for detail card / row / badge / list / empty / error / project-progress. Frontend tests: 6.

Integration: both worktree branches merged into `feature/detail-panel-and-geojson` with `--no-ff` and zero conflicts (orthogonal file sets).

### Completion Notes

- All 8 ACs satisfied (Acceptance Auditor: 8/8 PASS, 0 PARTIAL, 0 FAIL).
- Worktree-A: 291 → 300 (+9). Worktree-B: 291 → 297 (+6). Integrated: 306 (+15 net).
- 2 PATCH-level review findings applied as a single follow-up commit:
  - **`m.traits` dead-code fix**: `_renderMonarchCard` referenced `m.traits` but the route never serialized them. Wired `traits = monarch.get_traits()` into the `current_monarch` payload in `blueprints/map.py` so the panel's Traits section actually renders.
  - **AC4 UX guard**: left-click was always calling `openDetailPanel`, even when the click was being consumed by a pending-action queue (Recruit/Build/March destination). Added `consumedByAction` flag so the panel only opens when the click is informational.
- ~13 findings deferred to `deferred-work.md` (perf scans, N+1 wars, project tie-breaker, stale globals, garrison size-0, etc.).
- pytest under deterministic order: **306 passed, 0 failed, 0 skipped** (was 291; +15).
- Pre-existing intermittent flake on `test_develop_action_raises_development_level` (Story 2-3 test) reproduces under pytest-randomly ordering but not under `-p no:randomly`. Unrelated to this story; logged in deferred-work.

#### ⚠ Visual verification deferred

Session can't run the dev server. Test-verified: DOM structure, JSON shapes, JS handler text, ARIA, CSS classes. Visual aspects pending the user's `python main_flask_app.py` check at `/world/map`:

- Left-click a hex → detail panel slides in with the territory card (terrain, owner, buildings, garrison, active project if any).
- Clicking each left-rail nav button (Chronicle 📖 / World 🌍 / War ⚔) renders the right panel.
- Clicking a project slot pill shows the project card (years remaining) or empty-slot placeholder.
- Clicking the monarch portrait shows the monarch card with traits (now wired).
- Threats overlay: red-scaled hexes per `hostile_garrison_total`.
- Projects overlay: gold-tinted hexes where player has an active project.
- Pending Build/Recruit/March → click destination hex → action queues without the panel popping up.

### File List

- `visualization/map_renderer.py` — MODIFIED (~65 LoC added: aggregations + new properties)
- `blueprints/map.py` — MODIFIED (~160 LoC added: `/territory/<id>/details.json` + active_wars block + monarch traits patch)
- `templates/world_map.html` — MODIFIED (~300 LoC added: switch dispatcher + 7 `_renderXCard` helpers + 2 overlay branches + Jinja seeds + left-click guard patch)
- `static/style.css` — MODIFIED (~145 LoC added: detail card / row / badge / list family)
- `tests/unit/test_map_renderer.py` — NEW (4 unit tests for AC1)
- `tests/integration/test_territory_details_endpoint.py` — NEW (5 integration tests for AC2)
- `tests/integration/test_detail_panel_render.py` — NEW (6 integration tests for AC3 / AC5)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED (3-3: backlog → in-progress → done)
- `_bmad-output/implementation-artifacts/3-3-detail-panel-and-geojson.md` — MODIFIED
- `_bmad-output/implementation-artifacts/deferred-work.md` — MODIFIED (~13 Story 3-3 defers)

### Change Log

| Date | Change |
|---|---|
| 2026-05-25 | spec(3-3) committed (JSON contract for both worktrees) |
| 2026-05-25 | wt/3-3-backend: 4 commits (GeoJSON enrichment + /details.json + active_wars + tests) |
| 2026-05-25 | wt/3-3-frontend: 3 commits (CSS + conditional panel + overlays + tests) |
| 2026-05-25 | Merged both worktrees into feature/detail-panel-and-geojson (zero conflicts) |
| 2026-05-25 | Code review (3 layers): Acceptance Auditor 8/8 PASS; Blind + Edge Hunters surfaced 2 must-fix + ~11 defers |
| 2026-05-25 | fix(world-map): wire monarch traits into route + guard left-click panel-open on pending action |
| 2026-05-25 | pytest: 306 passed, 0 failed, 0 skipped (was 291) |
| 2026-05-25 | Story status → done |
