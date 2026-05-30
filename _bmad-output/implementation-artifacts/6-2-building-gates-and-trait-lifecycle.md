# Story 6-2: Building Gates + Sickly Lifespan + Trait Inheritance

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player, I want recruit-projects gated behind the right buildings, sickly rulers to die younger, and children to inherit their parents' traits, so that buildings, traits, and bloodlines all carry real weight. **Backend-only** — tests are the verification.

## Acceptance Criteria

1. **AC1 — Building gate in `ProjectSystem.start_project` (`models/project_system.py`).** The `PROJECT_TYPE_CATALOGUE` already carries `requires_building` (e.g. `recruit_cavalry → 'Stables'`). Enforce it: when a project's `requires_building` is set, `start_project` must verify the dynasty controls at least one `Territory` (`controller_dynasty_id == dynasty_id`) that has a `Building` of that type, BEFORE creating the Project / charging cost. If the required building is absent → reject using `start_project`'s EXISTING failure signal (mirror how it rejects unaffordable/invalid starts — same return type/exception, with a clear message like "Requires a Stables"). No required building, or `requires_building is None` → unchanged. Match `'Stables'`/`'Barracks'` against `Building.building_type` (handle enum `.value`/name and the `Building.name` string — be tolerant).

2. **AC2 — Sickly halves lifespan in `process_death_check` (`models/turn_processor.py:370`).** If the person `get_traits()` contains `'Sickly'`, halve their effective `max_age` (`max_age *= 0.5`) — so the guaranteed-death threshold drops (~85→~42) — and additionally bump `base_mortality` (e.g. `*= 2`) so they're likelier to die each year. A non-Sickly person is unaffected. Keep the function's return (bool) and the existing death-logging behavior.

3. **AC3 — Trait inheritance in `process_childbirth_check` (`models/turn_processor.py`).** When a child is created, build its traits:
   - For each trait of EACH parent (mother + the spouse/father), inherit it with ~30% probability (`random.random() < 0.30`), de-duplicated.
   - Cap inherited traits at **3** (if more roll in, keep the first 3).
   - Then add **1 random** trait from the theme's `common_traits` (`theme_config.get('common_traits', [...])`), if available and not already present.
   - Set via `child.set_traits([...])`. (Mother is the `person` being processed; the father is her `spouse_sim_id` → look up that `PersonDB` for its traits.)

4. **AC4 — No regressions.** Full suite green (baseline **387**; new tests additive). Existing project/turn tests unaffected: the building gate only triggers for `requires_building` project types (today only `recruit_cavalry`), Sickly logic is a no-op without the trait, and inheritance only changes the trait list of newly-born children (existing tests rarely assert exact child traits; if any do, the integrator adjusts).

5. **AC5 — ≥6 new tests** (`tests/integration/test_building_gates.py` + `tests/unit/` or integration for lifecycle; mock `random` for determinism):
   - Building gate: `start_project('recruit_cavalry', ...)` for a dynasty WITHOUT a Stables → rejected (no Project created, cost not charged); WITH a Stables in a controlled territory → succeeds.
   - A non-`requires_building` project (e.g. `recruit_infantry`/`build_farm`) starts regardless of buildings.
   - Sickly lifespan: a `Sickly` person at an age above the halved max_age (e.g. 50, where halved max ~42) → `process_death_check` returns True (dies); an identical non-Sickly person at 50 with `random.random` patched high → survives.
   - Trait inheritance: with `random.random` patched to `0.0` (always inherit), a child of two trait-bearing parents inherits parents' traits up to the cap of 3 (+1 themed); with `random.random` patched to `1.0` (never inherit), the child gets only the +1 random themed trait (no parent traits).
   - Inherited-trait cap is ≤ 3 parent traits (+ at most 1 themed).

## Tasks / Subtasks
- [ ] Task 1 — Building gate in `start_project` (`models/project_system.py`). [Agent A]
- [ ] Task 2 — Sickly lifespan + trait inheritance (`models/turn_processor.py`). [Agent B]
- [ ] Task 3 — Tests (`tests/integration/test_building_gates.py` + lifecycle tests). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `models/project_system.py` only (building-gate pre-check in `start_project`).
- **Agent B** — `models/turn_processor.py` only (`process_death_check` Sickly + `process_childbirth_check` inheritance).
- **Agent C** — NEW test files only.
- No shared files.

### FROZEN INTERFACE CONTRACT
- `start_project` rejects (its existing failure signal) when the project's `requires_building` is set and the dynasty controls no territory with a `Building` of that type; otherwise unchanged. Match building type tolerantly (`building_type.value`/name/`Building.name`).
- `process_death_check`: `'Sickly'` in traits → `max_age *= 0.5` and `base_mortality *= 2` (applied before the random roll). Return type unchanged (bool).
- `process_childbirth_check`: child traits = (≤3 inherited from parents at ~30%/trait, deduped) + (1 random from `common_traits` if available); `child.set_traits(...)`.

### Reuse / project rules
- Don't rewrite `ProjectSystem`/turn_processor — extend. `start_project` already returns a documented failure signal for unaffordable/invalid — reuse it (don't invent a new exception). Building lookup via `self.session` join `Territory.controller_dynasty_id == dynasty_id` + `Building.building_type`. `get_traits()`/`set_traits()` on PersonDB. `random` is already imported in turn_processor. No new deps.

### Out of scope / deferred
- Chronicle voice reflecting traits + player-facing `docs/traits.md` → **Story 6-3** (completes Epic 6). 6-2 is the three mechanics only.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool (Epic 5 + 6-1 ran clean). Agents default to plan mode → "EXECUTE NOW, pre-approved, no EnterPlanMode"; worktrees branch off `main`; contract inlined. Integrator verifies the main tree is clean before merging. `pytest` against an isolated temp DB rebuilt per run; **reset the temp DB before a run for determinism** (the shared-DB accumulation otherwise produces spurious errors). Baseline 387. Known `test_military_routes` flake.
- 6-1 added `models/trait_effects.py` + hooks; `requires_building` has sat unenforced in the catalogue since Story 2-2 (logged in `deferred-work.md`).
- Backend-only → no run-the-app visual check.

## References
- `PROJECT_TYPE_CATALOGUE` (`requires_building`) + `start_project`: `models/project_system.py:148-226`, `def start_project`.
- `process_death_check`: `models/turn_processor.py:370-393` (`max_age`/`base_mortality`).
- `process_childbirth_check` + spouse/father lookup (`spouse_sim_id`): `models/turn_processor.py` (childbirth function); founder trait sampling example `models/game_manager.py` / `blueprints/dynasty.py:947-953`.
- `Building` (`building_type`, `territory_id`), `Territory.controller_dynasty_id`: `models/db_models.py`.
- Test fixtures: `tests/integration/test_succession.py`, `tests/unit/`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool (run `wf_2f69bb64-3fb`), + main-session integrator.

### Completion Notes List

- All ACs satisfied. `pytest -p no:randomly`: **395 passed, 0 failed** (387 baseline + 8). A `wt/6-2-gate` (`2dfc2da`): `_dynasty_has_building` + `requires_building` gate in `start_project` (tolerant building-type match; reuses the existing `ValueError` invalid-start signal; ordered after affordability to keep `test_start_project_insufficient_iron_raises` green). B `wt/6-2-lifecycle` (`04ac9e9`): Sickly → `max_age *= 0.5` + `base_mortality *= 2`; child trait inheritance (≤3 parent traits at 30%/trait + 1 themed). C `wt/6-2-tests` (`6b8f8d4`): 8 tests. Clean merges, zero file overlap.
- **Integrator fix:** the new gate broke the existing `test_recruit_cavalry_maps_to_recruit_cavalry_project` (its fixture had no Stables) — added a `Building(BuildingType.STABLE, construction_year=...)` to that test's territory so it verifies the mapping with the prerequisite met. (The two other lifecycle failures under full-suite ordering were the known shared-state flakes — green in isolation.)

### File List

- `models/project_system.py` — MODIFIED (`requires_building` gate + `_dynasty_has_building`)
- `models/turn_processor.py` — MODIFIED (Sickly lifespan + child trait inheritance)
- `tests/integration/test_building_gates.py` — NEW (8 tests)
- `tests/integration/test_project_turn_lifecycle.py` — MODIFIED (integrator: Stables for the cavalry-mapping test)
- `_bmad-output/implementation-artifacts/{6-2-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED

### Change Log

| Date | Change |
|---|---|
| 2026-05-30 | spec(6-2); 3 worktree agents via Workflow; merged; integrator fixture fix; 395 passed; Story 6-2 → done |
