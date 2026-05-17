# Story 2-3: Wire Projects into Turn Processor + Migrate Actions

Status: in-progress

## Story

As a player who has just started a multi-year project,
I want the turn loop to drain my project's resources each year, stall it if I run out, and apply its effect when complete,
so that the project mechanic from Story 2-2 actually affects the game world instead of just sitting in the DB.

## Acceptance Criteria

1. **AC1 — `tick_projects` runs before lifecycle each year.** In `process_dynasty_turn`'s per-year loop (before the per-person death/marriage/childbirth checks), `ProjectSystem(db.session).tick_projects(dynasty_id, current_year)` is called. If it returns a non-empty interrupt list, the turn loop breaks immediately with `interrupt = ('project_stalled', current_year)` (matching the existing 2-tuple shape used by `monarch_death`/`quiet_period`); the project IDs from the stall events are stored on `turn_summary['stalled_project_ids']`.

2. **AC2 — Projects auto-complete when `completion_year <= current_year`.** After lifecycle for the year runs (before incrementing `years_advanced`), iterate over active projects for the dynasty whose `completion_year <= current_year` and call `ProjectSystem.complete_project(project.id)` for each. Completion does NOT emit an interrupt — completion is a "good news" event surfaced via the chronicle / turn report, not a turn-halting one.

3. **AC3 — `INTERRUPT_REASONS` includes `'project_stalled'` and `'project_complete'`** (the latter already existed; verify present). Add `'project_stalled'` if missing. No other entries change.

4. **AC4 — `submit_actions` migrates `recruit`, `build`, `develop` to project starters.** For each of the 3 action types, instead of calling `MilitarySystem.recruit_unit` / `EconomySystem.construct_building` / `EconomySystem.develop_territory` directly, call `ProjectSystem(db.session).start_project(...)` with the appropriate `project_type`. The result row's `id` is recorded in the result dict alongside `'success': True`. On `InsufficientResourcesError` or `ValueError` from `start_project`, the action result is `{'type': action_type, 'success': False, 'error': str(e)}` (matches existing failure shape).

5. **AC5 — `march`, `trade`, `war` actions remain instant.** Master plan Sprint 4 explicitly carves these out as free actions (lines 422-442). Story 2-3 does NOT migrate them; they keep their existing direct-subsystem call paths. A comment in `submit_actions` near each one cites Sprint 4 ownership.

6. **AC6 — `EFFECT_DISPATCHER` entries for `recruit_infantry`, `build_farm`, `develop_territory` are real (not NO-OP).** Each one mutates game state without re-charging resources (since `tick_projects` already drained the full cost over the project's duration). Specifically:
   - `recruit_infantry`: creates a `MilitaryUnit` row in the project's `target_territory_id`, owned by the project's `dynasty_id`. Default `size=100` unless `params['size']` overrides.
   - `build_farm`: creates a `Building` row with `building_type=BuildingType.FARM`, `level=1`, `is_under_construction=False` (project already paid for it), in the project's `target_territory_id`.
   - `develop_territory`: increments `Territory.development_level` by 1 for the project's `target_territory_id`.
   - The other 5 catalogue entries (`recruit_cavalry`, `build_walls`, `build_cathedral`, `envoy_mission`, `march_army_cross_realm`) stay as NO-OP stubs — wiring those needs gameplay decisions about cavalry/wall/cathedral mechanics that belong to later sprints.

7. **AC7 — `Building.is_under_construction` flag is NOT removed.** The flag stays on `Building` rows; the project-completed `build_farm` effect creates rows with `is_under_construction=False`. The legacy `EconomySystem.construct_building` code path (still used as a fallback / for non-project builds in older tests) is untouched. Removing the flag is a separate Sprint 11 refactor.

8. **AC8 — Tests cover the full lifecycle and the migrated action paths.** New tests in `tests/unit/test_project_system.py` (extending the existing file) for the 3 real effects. A new integration test in `tests/integration/test_project_turn_lifecycle.py` (NEW) covers:
   - Player submits `build` action → `Project` row exists with `status='active'`, no Building yet.
   - Advance turn 5 years (2-year `build_farm` project) → `Project.status='completed'` AND `Building` row exists.
   - Stall path: submit `build` with dynasty wealth equal to just year 1's cost → next turn stalls → `turn_summary['interrupt'][0] == 'project_stalled'`.
   - `march`/`trade`/`war` still work as instant actions (regression guard).
   - **pytest must report 264+ passed, 0 failed, 0 skipped** (was 258; +6 expected: 3 effect unit tests + 3 integration tests).

## Tasks / Subtasks

- [ ] Task 1: Wire `tick_projects` + completion into `process_dynasty_turn` (AC1, AC2, AC3)
  - [ ] Import `ProjectSystem` from `models.project_system` at top of `models/turn_processor.py`.
  - [ ] Inside the per-year `while` loop, BEFORE the `try`/`process_world_events` block: instantiate `ps = ProjectSystem(db.session)`; call `stall_interrupts = ps.tick_projects(dynasty_id, current_year)`; if any, set `interrupt = ('project_stalled', current_year)`, store `stalled_ids = [t[2] for t in stall_interrupts]` for later, `break`.
  - [ ] AFTER the per-person lifecycle (line 147 in current code), iterate `due_projects = [p for p in ps.get_active_projects(dynasty_id) if p.completion_year <= current_year]` and call `ps.complete_project(p.id)` for each.
  - [ ] Add `'project_stalled'` to `INTERRUPT_REASONS` if missing. Verify `'project_complete'` is present.
  - [ ] When building `turn_summary`, add `'stalled_project_ids'` (list, may be empty) so the UI in Sprint 3 can surface them.

- [ ] Task 2: Migrate 3 action types in `submit_actions` (AC4, AC5)
  - [ ] In `blueprints/dynasty.py:submit_actions`, replace the `recruit` branch body with `ps = ProjectSystem(db.session); project = ps.start_project(dynasty_id, 'recruit_infantry', dynasty.current_simulation_year, target_territory_id=params.get('territory_id'), params={'size': int(params.get('size', 100))})`. On `InsufficientResourcesError`/`ValueError`, return the failure shape.
  - [ ] Same for `build`: project_type derived from `params.get('building_type')` mapped via a small dict: `{'farm': 'build_farm', 'market': 'build_farm', 'walls': 'build_walls', 'cathedral': 'build_cathedral'}`. (Default `farm` → `build_farm`. `market` collapsed to `build_farm` because the catalogue doesn't have `build_market` yet — log a warning and use `build_farm`; deferred work item for adding `build_market` to the catalogue.)
  - [ ] Same for `develop`: `start_project(..., 'develop_territory', ...)`.
  - [ ] Add inline comment `# Sprint 4 free-action split owns this — leaving instant` above each of `march`, `trade`, `war` (do NOT migrate them).

- [ ] Task 3: Replace 3 NO-OP dispatchers with real effects (AC6, AC7)
  - [ ] In `models/project_system.py`, define `_effect_recruit_infantry(session, project)` that creates a `MilitaryUnit` row.
  - [ ] Define `_effect_build_farm(session, project)` that creates a `Building` row with `is_under_construction=False`.
  - [ ] Define `_effect_develop_territory(session, project)` that increments `territory.development_level`.
  - [ ] Replace the dictionary-comprehension that maps every catalogue key → `_stub_effect` with an explicit dict that uses the real effect for the 3 wired types and `_stub_effect` for the rest. Imports: add `MilitaryUnit, UnitType, Building, BuildingType, Territory` to the `models.db_models` import line.

- [ ] Task 4: Unit tests for the 3 new effects (AC6, AC8)
  - [ ] `test_effect_recruit_infantry_creates_unit` — start + tick + complete a `recruit_infantry` project, assert a `MilitaryUnit` row exists with the right dynasty_id and territory_id.
  - [ ] `test_effect_build_farm_creates_building` — similar, assert a `Building` row with `building_type=BuildingType.FARM`, `is_under_construction=False`.
  - [ ] `test_effect_develop_territory_raises_dev_level` — set a territory's `development_level=1`, run the project, assert level==2.
  - [ ] Add to `tests/unit/test_project_system.py`.

- [ ] Task 5: Integration tests in `tests/integration/test_project_turn_lifecycle.py` (NEW) (AC8)
  - [ ] `test_build_project_completes_via_turn_loop` — POST to `submit_actions` with a `build` action → assert Project row created → advance 5 years → assert Project status=='completed' AND Building row exists.
  - [ ] `test_stalled_project_halts_turn_loop` — dynasty has just year-1 funds → submit `build` → advance turn → assert response indicates project_stalled interrupt.
  - [ ] `test_march_action_still_instant` — submit `march` action → assert army.territory_id updated immediately, no Project row created (regression guard for AC5).

- [ ] Task 6: Run `pytest`, confirm 264+ passed, 0 failed, 0 skipped (AC8)

- [ ] Task 7: Commit per Dev Notes plan, push branch.

## Dev Notes

### Files to change

| File | Change type | Description |
|---|---|---|
| `models/turn_processor.py` | UPDATE | Wire ProjectSystem.tick + completion into year loop; add `'project_stalled'` to INTERRUPT_REASONS; add `stalled_project_ids` to turn_summary |
| `blueprints/dynasty.py` | UPDATE | Migrate `recruit`/`build`/`develop` to ProjectSystem.start_project; add comments noting `march`/`trade`/`war` deferred to Sprint 4 |
| `models/project_system.py` | UPDATE | Replace 3 NO-OP stubs with real effect handlers; explicit dict instead of comprehension |
| `tests/unit/test_project_system.py` | UPDATE | 3 new tests for the wired effects |
| `tests/integration/test_project_turn_lifecycle.py` | NEW | 3 integration tests for the full submit→tick→complete flow |

### Why tick BEFORE lifecycle each year

Master plan line 219: "Wire into `process_dynasty_turn` — projects tick before lifecycle each year". Reasoning: a stalled project should halt the turn at the year of stalling, BEFORE any deaths/marriages/births happen — otherwise the player sees a confusing "5 children were born; ALSO your cathedral stalled in year 3" report when the right framing is "the cathedral stalled in year 3 and the turn ended there".

### Why completion check is AFTER lifecycle

If a monarch dies in year N AND a cathedral completes in year N, the death halts the loop first (`monarch_death` interrupt). The cathedral remains active and is completed on the NEXT turn. This preserves the master plan invariant that interrupts halt the loop immediately. If completion were checked BEFORE the death, we'd risk completing projects "after" the player saw the death modal — confusing UX.

### Why `complete_project` does NOT emit an interrupt

Completion is good news. It generates a chronicle entry (Story 2-4) and shows in turn_summary, but doesn't halt the loop. Master plan only lists `project_complete` in INTERRUPT_REASONS to support OPTIONAL completion modals in the future (e.g. "select what to build on this new estate" workflow). For now it's a string label only — no code path sets it.

### Why `recruit`/`build`/`develop` but not the others

`march`/`trade`/`war` are decisions the player makes once (the actual march/trade-route/war declaration is instant in-fiction). Sprint 4 (Story 4-1) introduces a dedicated `free_action` endpoint for these. Migrating them to projects now would require either:
- Adding stub catalogue entries (`establish_trade_route`, `declare_war`) that take 0 years — but a 0-year project is just an instant action; we'd have the project_system handle two paradigms
- Or doing meaningful design work (e.g. `declare_war` becomes a 1-year `marshal_army_for_war` project per master plan line 422) that Sprint 4 owns

Cleaner to leave them as instant in Story 2-3 and let Story 4-1 redesign them.

### `params` carries the per-project state

`MilitaryUnit` recruitment needs `size`, building creation needs `building_type` to be set on the row (vs. inferred from `project_type`). The `params_json` column carries this. The dispatcher reads `project.get_params()` and uses the values.

Convention for this story:
- `recruit_infantry`: `params = {'size': int}` (default 100 if absent)
- `build_farm`: no params needed (building_type is implied by project_type)
- `develop_territory`: no params needed

### Affordability check on `start_project` (existing from 2-2)

`start_project` already validates year-1 affordability. If a player tries to submit a `build_farm` with insufficient gold/timber, the action returns failure. The UI in Sprint 3 will show the cost preview BEFORE submission to avoid this.

### Existing `is_under_construction` behavior is preserved

The legacy `EconomySystem.construct_building` (used in Sprint 1-pre-existing tests and the `build_farm` action BEFORE this story migrates it) still creates rows with `is_under_construction=True`. After this story, the `submit_actions` path no longer calls it — but Sprint 1 tests / integration tests that call `construct_building` directly still work. The flag remains on Building rows for backward compatibility. Sprint 11 (`11-1-delete-dead-code`) is the natural place to either:
- Remove the flag entirely (and the legacy code path)
- Or repurpose it as a denormalized "has active build_* project" flag

For Story 2-3, we just DON'T set it to `True` from the project flow.

### Build-type mapping in `submit_actions`

The legacy `build` action accepts `params['building_type']` as a free-form string (`'farm'`, `'market'`, etc.). The catalogue only has `build_farm`, `build_walls`, `build_cathedral` (no `build_market` — Sprint 2-2 deferred). For Story 2-3:
- `'farm'` → `'build_farm'`
- `'walls'` → `'build_walls'`
- `'cathedral'` → `'build_cathedral'`
- `'market'` → falls back to `'build_farm'` (log a warning); proper `build_market` entry added in Sprint 4 or Story 11-3
- Anything else → action returns failure with `'Unknown building type for project mapping'`

This means existing test data passing `building_type='market'` will create a `build_farm` project, which is wrong behavior — but those tests are integration tests that probably bypass `submit_actions` anyway. If any of them break, fix them as part of this story.

### Interrupt tuple shape for `project_stalled` at the turn level

`tick_projects` returns 3-tuples `('project_stalled', year, project_id)`. At the `turn_processor` level, the existing `interrupt` variable is a 2-tuple `('reason', year)`. To stay consistent without changing the interrupt schema:
- Set `interrupt = ('project_stalled', current_year)` (2-tuple, matches existing pattern).
- Store the stalled project IDs separately as `stalled_project_ids` in turn_summary (a list).
- Story 1-3's turn_report UI already handles `interrupt.reason`; adding the project IDs is a forward-compat hook for Sprint 3 UI.

### What this story does NOT touch (scope boundaries)

- `models/db_models.py` — no schema changes.
- `Building.is_under_construction` — flag stays; no removal.
- Chronicle hooks for multi-monarch project completion — Story 2-4.
- `march`/`trade`/`war` action types — Sprint 4 free-action split.
- Add `build_market` to catalogue — deferred-work.md (Sprint 4 or 11-3).
- UI / templates / world_map.html — Sprint 3 (Epic 3).

### Branch name

`feature/wire-projects-and-migrate-actions` (already created).

### Commit plan

- Commit 1: `feat(turn-processor): wire ProjectSystem.tick + completion into year loop`
- Commit 2: `feat(submit-actions): migrate recruit/build/develop to project starters`
- Commit 3: `feat(project-system): real effect dispatchers for recruit_infantry/build_farm/develop_territory`
- Commit 4: `test: full project lifecycle through submit_actions + turn loop`

### References

- Master plan: `review_documents/8_master_plan_2026.md` lines 213-232 (Sprint 2 tasks)
- Sprint 4 free-action split: master plan lines 416-442
- Current submit_actions: `blueprints/dynasty.py:515-589`
- Current process_dynasty_turn year loop: `models/turn_processor.py:117-156`
- INTERRUPT_REASONS: `models/turn_processor.py:38-47`
- Legacy construct_building: `models/economy_system.py:700-767`
- Story 2-2 ProjectSystem: `models/project_system.py`
- Story 2-1 Project schema: `models/db_models.py:624-665`

## Dev Agent Record

### Agent Model Used

(to be filled by dev agent)

### Implementation Plan

(to be filled by dev agent)

### Completion Notes

(to be filled by dev agent)

### File List

(to be filled by dev agent)

### Change Log

(to be filled by dev agent)
