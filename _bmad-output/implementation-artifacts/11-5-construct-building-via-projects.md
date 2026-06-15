# Story 11-5: Route Building Construction Through the Project System (fix phantom-column bug)

Status: ready-for-dev

## Story
As a **player constructing buildings**,
I want **direct building construction to go through the multi-year Project system instead of the broken instant path**,
so that **construction actually works (no silent failure), is consistent with the Story 2-3 project design, and the non-existent `Building.is_under_construction`/`completion_year` columns are no longer referenced.**

## Context (the bug — Project-Lead decision: route through Projects)
`EconomySystem.construct_building` (`models/economy_system.py` ~:774-783) constructs `Building(..., completion_year=..., is_under_construction=True)`, but `Building` (`models/db_models.py`) declares **neither** column → `TypeError` on every direct construction, swallowed by the route's try/except (`blueprints/economy.py:138-178`) → silent flash error. The same phantom columns are read in `update_dynasty_economy` (~:673) and `upgrade_building` (~:818), which also break on any real building. Story 2-3 already moved construction toward Projects: `_effect_build_farm` (`models/project_system.py:302`) creates a Building **in finished state** (no phantom flags) — that is the correct pattern to generalize. **Project-Lead decision (2026-06-15): route `construct_building` through the Project system.** Consequence (accepted): construction becomes multi-year + slot-consuming, not instant.

## Acceptance Criteria

1. **AC1 — Generic `build_building` project type.** Add a `build_building` entry to `PROJECT_TYPE_CATALOGUE` in `models/project_system.py` (baseline `duration_years`, `yearly_cost_*`, `slot: True`, `requires_building: None`). It is the generic construction project; the specific `BuildingType` rides in the project's `params_json`.

2. **AC2 — Per-building cost/duration overrides in `start_project`.** Extend `ProjectSystem.start_project(...)` to accept OPTIONAL overrides via kwargs (`duration_years`, `yearly_cost_gold`, `yearly_cost_iron`, `yearly_cost_timber`, `yearly_cost_food`) that, when provided, override the catalogue values for that project instance (affordability check + Project row use the effective values). **Backward compatible:** existing callers pass none → identical behavior (verify the existing `build_farm` tests still pass unchanged). This lets construction preserve the existing per-building costs/times from `EconomySystem.building_construction_costs` / `building_construction_time`.

3. **AC3 — `_effect_build_building` completion effect.** Add `_effect_build_building(session, project)` (mirror `_effect_build_farm`): read the target `BuildingType` from `project.params_json` (e.g. `building_type` value string → `BuildingType(...)`), and if `project.target_territory_id` is set, create the `Building` in **finished state** — `territory_id`, `building_type`, `name`, `level=1`, `condition=1.0`, `construction_year=project.started_year`, and `effects_json` from `EconomySystem.building_production_bonuses` (serialize ResourceType keys to `.value` like the old code did). **No `is_under_construction`/`completion_year` kwargs.** Register it in `EFFECT_DISPATCHER['build_building']`. Log success like the other effects. If `target_territory_id` or a valid building_type is missing, log a warning and skip (don't crash).

4. **AC4 — `construct_building` delegates to a project.** Rewrite `EconomySystem.construct_building(territory_id, building_type)` to:
   - Resolve `dynasty` from `territory.controller_dynasty_id` (as today).
   - Compute cost (`building_construction_costs`) + duration (`building_construction_time`) from the existing tables.
   - Call `ProjectSystem(self.session).start_project(dynasty.id, 'build_building', dynasty.current_simulation_year, target_territory_id=territory_id, params={'building_type': building_type.value}, duration_years=<time>, yearly_cost_gold=<cost gold>, ...)`.
   - Translate exceptions into the existing `(success, message)` contract: `InsufficientResourcesError` → `(False, "Not enough resources")`; "no living monarch" `ValueError` → `(False, "No reigning monarch to commission construction")`; success → `(True, "Commissioned construction of <Name> (completes in <n> years)")`.
   - It must NOT construct a `Building` directly anymore and must NOT reference `is_under_construction`/`completion_year`.

5. **AC5 — Purge phantom-column reads.** Remove the `is_under_construction`/`completion_year` logic from `update_dynasty_economy` (~:673 completion branch — obsolete now that buildings are created complete by the project effect) and the `is_under_construction` guard in `upgrade_building` (~:818). Confirm a repo grep for `is_under_construction` and `completion_year` over `models/economy_system.py` returns ZERO after the change. (`Project.completion_year` is a real column — do not touch Project code; scope is economy_system + the new project_system additions.)

6. **AC6 — Route messaging.** `blueprints/economy.py` `construct_building` route keeps working (it already flashes the returned message). No behavior change needed beyond the message now reflecting a commissioned project. Keep the route's existing try/except + flash categories.

7. **AC7 — Tests.** Add to `tests/unit/test_project_system.py` (or a new `tests/unit/test_construct_building.py`):
   - `start_project` override: starting `build_building` with override costs/duration produces a Project with those effective costs and `completion_year = started_year + override_duration`; affordability uses the override.
   - `_effect_build_building`: completing a `build_building` project whose params name e.g. `MARKET` creates a `Building(building_type=MARKET, level=1)` in the target territory with NO phantom attributes, and sets `effects_json`.
   - `EconomySystem.construct_building` happy path: starts a `build_building` project (assert a Project row exists; no Building yet until completion); insufficient funds → `(False, ...)`; no living monarch → `(False, ...)`.
   - Regression: existing `build_farm`/start_project tests unchanged and green.

8. **AC8 — No regressions + live check.** Full suite green (baseline **590 passed**, 0 failed, 0 skipped) + new tests. `python -c "import main_flask_app"` clean. Boot app on 8091; authenticated POST to `/dynasty/<id>/construct_building` (territory_id + a building_type) returns a success flash (commissioned), NOT the old "Error constructing building" danger flash. (Per Epic 3 retro — verify the real path, since the bug was a silent runtime failure tests didn't surface.)

## Tasks
- [ ] Task 1 — `build_building` catalogue entry (AC1).
- [ ] Task 2 — optional cost/duration overrides in `start_project`, backward-compatible (AC2).
- [ ] Task 3 — `_effect_build_building` + register in EFFECT_DISPATCHER (AC3).
- [ ] Task 4 — rewrite `construct_building` to delegate (AC4); purge phantom reads in `update_dynasty_economy` + `upgrade_building` (AC5).
- [ ] Task 5 — tests (AC7).
- [ ] Task 6 — pytest 590+new green; import clean; live construct-route check on 8091 (AC8).

## Dev Notes
- **Pattern to mirror:** `_effect_build_farm` (`models/project_system.py:302-326`) — creates the Building in finished state, NO phantom flags. Generalize it via `params_json['building_type']`.
- `start_project` signature is `(self, dynasty_id, project_type, started_year, **kwargs)` and reads `PROJECT_TYPE_CATALOGUE[project_type]` for `duration_years`/`yearly_cost_*` (`models/project_system.py:384`). Add override handling right after `meta = ...` (e.g. `meta = {**meta, **{k: kwargs[k] for k in OVERRIDE_KEYS if k in kwargs}}`) so the rest of the function is unchanged. Don't pass override keys down as `target_*`/`params`.
- `start_project` requires a living monarch and does a year-1 affordability check (raises `InsufficientResourcesError`) — `construct_building` must catch these and return the `(success, message)` tuple the route expects (the route does NOT expect exceptions to bubble for the normal "can't afford" case).
- `ProjectSystem` constructor takes `session` only (subsystem rule). Import it in economy_system (watch for circular imports — import inside the method if needed, like the blueprint does).
- BuildingType enum values: farm, mine, lumber_camp, workshop, market, port, warehouse, trade_post, barracks, stable, training_ground, fortress, roads, irrigation, guild_hall, bank. `params_json` stores the `.value` string; reconstruct with `BuildingType(value)`.
- SA 2.0 conventions (Epic 11): `session.get`, no legacy `.query.get()`. Logger `royal_succession.economy` / `royal_succession.project` as in those modules. No `print()`.
- **Self-contained backend refactor → single Sonnet subagent on live `main` (no worktree)** per Epic 11 retro policy.
- After this lands, update memory `construct-building-phantom-columns-bug` to RESOLVED.

## References
- `models/economy_system.py`: `construct_building` (~:740-801), `update_dynasty_economy` phantom branch (~:673), `upgrade_building` guard (~:818), `building_construction_costs`/`building_construction_time`/`building_production_bonuses` tables.
- `models/project_system.py`: `PROJECT_TYPE_CATALOGUE` (~:200), `start_project` (~:384), `_effect_build_farm` (~:302), `EFFECT_DISPATCHER` (~:352).
- `blueprints/economy.py:138-178` (construct_building route).
- `models/db_models.py`: `Building` (no is_under_construction/completion_year), `Project` (params_json, target_territory_id), `BuildingType`.
- Memory: `construct-building-phantom-columns-bug` (re-verified 2026-06-14).

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-15 | spec(11-5); route construct_building through Project system; purge phantom columns (ready-for-dev) |
