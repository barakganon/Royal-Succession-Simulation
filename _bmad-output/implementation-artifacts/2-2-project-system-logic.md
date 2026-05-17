# Story 2-2: project_system.py Core Logic

Status: done

## Story

As a developer wiring the multi-year project mechanic into the turn loop,
I want a `ProjectSystem` subsystem that knows how to start, tick, complete, and cancel projects,
so that Story 2-3 (turn-processor wiring + `submit_actions` migration) can call into a single, fully-tested module rather than scattering project lifecycle logic across blueprints.

## Acceptance Criteria

1. **AC1 — `models/project_system.py` exists with a `ProjectSystem` class.** Constructor takes `session: Session` as its only argument (matches `MilitarySystem`, `EconomySystem`, `BankingSystem` convention). All 5 lifecycle methods are present: `start_project`, `tick_projects`, `complete_project`, `cancel_project`, `get_active_projects`.

2. **AC2 — A `PROJECT_TYPE_CATALOGUE` dict lives at module level with at least 6 representative project types** drawn from the master plan list (lines 196-211). Each entry is a dict with: `duration_years`, `yearly_cost_gold`, `yearly_cost_iron`, `yearly_cost_timber`, `yearly_cost_food` (forward-compat, see Dev Notes), `slot` (bool: occupies a project slot), and `requires_building` (str or None). The catalogue is the single source of truth for project metadata; `start_project` reads from it.

3. **AC3 — `start_project(dynasty_id, project_type, started_year, **kwargs)`** returns the new `Project` row on success. It (a) raises `ValueError` if `project_type` is unknown, (b) raises `InsufficientResourcesError` (new exception class in this module) if the dynasty cannot afford year 1's yearly cost (per-resource check against `dynasty.current_wealth / current_iron / current_timber`), (c) creates the `Project` row with `status='active'`, `started_year` and `completion_year = started_year + duration_years`, all four `yearly_cost_*` columns populated from the catalogue, `params_json` set from `kwargs.get('params', {})`, and `initiated_by_monarch_id` derived from the dynasty's current monarch (queried inside the method). Does NOT pre-deduct upfront resources — `tick_projects` is the sole drainer.

4. **AC4 — `tick_projects(dynasty_id, year)`** iterates over all active projects for the dynasty, deducts the yearly cost from the dynasty's stockpiles (`current_wealth -= yearly_cost_gold`, `current_iron -= yearly_cost_iron`, `current_timber -= yearly_cost_timber`; food is skipped per Dev Notes), and if any deduction would push a resource below zero, sets the project's `status` to `'stalled'` AND emits an interrupt tuple `('project_stalled', year, project_id)`. Returns a list of interrupt tuples (may be empty). Projects whose `completion_year == year` after a successful tick are NOT auto-completed here — the caller (Story 2-3 turn processor) is responsible for invoking `complete_project` separately. `tick_projects` only handles draining.

5. **AC5 — `complete_project(project_id)`** sets `status='completed'`, sets `completed_by_monarch_id` to the dynasty's current monarch, and invokes the registered effect function for the project's type (via an `EFFECT_DISPATCHER` registry at module level). For Story 2-2 every effect function is a NO-OP stub that just `logger.info`s the completion — Story 2-3 wires the real effects (spawn unit, build building, etc.). Returns the updated `Project` row.

6. **AC6 — `cancel_project(project_id)`** sets `status='cancelled'` and refunds 50% of the resources already spent on the project to the dynasty. "Resources spent" = `(year_of_cancellation - started_year) × yearly_cost_*` for each of gold / iron / timber. The current year is passed as a kwarg `current_year` to make the math deterministic and testable. Returns the updated `Project` row. Cancelling in `current_year == started_year` refunds 0 (no time elapsed).

7. **AC7 — `get_active_projects(dynasty_id)`** returns a list of all `Project` rows for the given dynasty whose status is `'active'`. Wraps the existing `dynasty.projects.filter_by(status='active').all()` pattern but accepts a dynasty_id (not a dynasty object) so callers don't need to load the dynasty first.

8. **AC8 — Comprehensive unit tests in `tests/unit/test_project_system.py` (new file).** At minimum: start happy path, start unknown project_type → `ValueError`, start insufficient resources → `InsufficientResourcesError`, tick drains correctly, tick stalls project on insufficient resource AND emits interrupt, tick returns `[]` when no active projects, complete sets status + calls effect dispatcher, complete sets `completed_by_monarch_id`, cancel refunds 50% correctly, cancel in same year refunds 0, `get_active_projects` filters by status (not by completion_year). pytest must report **241+ passed, 0 failed, 0 skipped** (was 231 pre-story; +10 expected).

## Tasks / Subtasks

- [x] Task 1: Create `models/project_system.py` skeleton (AC1)
  - [x] Module-level logger `royal_succession.project_system`
  - [x] `InsufficientResourcesError(Exception)` class
  - [x] `class ProjectSystem` with `__init__(self, session)` only

- [x] Task 2: `PROJECT_TYPE_CATALOGUE` constant (AC2)
  - [x] At least 6 entries: e.g., `recruit_infantry` (1 yr), `recruit_cavalry` (2 yr, needs Stables), `build_farm` (2 yr), `build_walls` (5 yr), `build_cathedral` (15 yr), `develop_territory` (3 yr), `envoy_mission` (1 yr)
  - [x] Each entry has keys: `duration_years`, `yearly_cost_gold`, `yearly_cost_iron`, `yearly_cost_timber`, `yearly_cost_food`, `slot`, `requires_building`

- [x] Task 3: `EFFECT_DISPATCHER` registry (AC5)
  - [x] Module-level `EFFECT_DISPATCHER: Dict[str, Callable[[Session, Project], None]]`
  - [x] One NO-OP stub per `PROJECT_TYPE_CATALOGUE` key — each just logs `logger.info(f"[stub] {project_type} completed for project {project.id}")`. Real effects are Story 2-3.
  - [x] `complete_project` calls `EFFECT_DISPATCHER[project.project_type](self.session, project)` if the key exists; raises `KeyError` if not (covered by AC5 catalogue completeness).

- [x] Task 4: `start_project(dynasty_id, project_type, started_year, **kwargs)` (AC3)
  - [x] Lookup `meta = PROJECT_TYPE_CATALOGUE[project_type]` — raise `ValueError` if missing.
  - [x] Load dynasty by id; query current monarch (`PersonDB.filter_by(dynasty_id=..., is_monarch=True, death_year=None).first()`); raise `ValueError` if no monarch (the AC2 schema now requires `initiated_by_monarch_id` NOT NULL).
  - [x] Check `dynasty.current_wealth >= meta['yearly_cost_gold']` AND `dynasty.current_iron >= meta['yearly_cost_iron']` AND `dynasty.current_timber >= meta['yearly_cost_timber']`. If any fails → `InsufficientResourcesError(f"Dynasty {dynasty_id} cannot afford year 1 of {project_type}")`.
  - [x] Create `Project` row, add to session, commit. Use `kwargs.get('target_territory_id')`, `kwargs.get('target_dynasty_id')`, `kwargs.get('target_person_id')`, `kwargs.get('params', {})`.

- [x] Task 5: `tick_projects(dynasty_id, year)` (AC4)
  - [x] `active = self.get_active_projects(dynasty_id)`
  - [x] `dynasty = DynastyDB.query.get(dynasty_id)`
  - [x] For each project: check `dynasty.current_wealth >= project.yearly_cost_gold and dynasty.current_iron >= project.yearly_cost_iron and dynasty.current_timber >= project.yearly_cost_timber`. If yes → deduct. If no → set `project.status = 'stalled'` and append `('project_stalled', year, project.id)` to interrupts list.
  - [x] Commit. Return interrupts list.

- [x] Task 6: `complete_project(project_id)` (AC5)
  - [x] Load project; raise `ValueError` if not found.
  - [x] Set `status='completed'`. Find current monarch of `project.dynasty_id`; set `completed_by_monarch_id`.
  - [x] Call `EFFECT_DISPATCHER[project.project_type](self.session, project)`. Commit. Return project.

- [x] Task 7: `cancel_project(project_id, current_year)` (AC6)
  - [x] Load project; raise `ValueError` if not found.
  - [x] Compute `years_elapsed = max(0, current_year - project.started_year)`.
  - [x] Compute refund: `dynasty.current_wealth += int(0.5 * years_elapsed * project.yearly_cost_gold)`; same for iron, timber. Use `int()` to avoid floats persisting.
  - [x] Set `status='cancelled'`. Commit. Return project.

- [x] Task 8: `get_active_projects(dynasty_id)` (AC7)
  - [x] `return self.session.query(Project).filter_by(dynasty_id=dynasty_id, status='active').all()`

- [x] Task 9: Unit tests in `tests/unit/test_project_system.py` (AC8)
  - [x] Reuse `_make_user_and_dynasty` + `_make_monarch` helpers (consider promoting to `tests/conftest.py` if duplication starts to bite — but for Story 2-2, importing from `tests.unit.test_db_models` is acceptable). Easiest path: duplicate the 2 helpers in the new test file (the existing TDD pattern in this repo keeps tests file-local).
  - [x] Cover all 10 cases listed in AC8.

- [x] Task 10: Run `pytest`, confirm 241+ passed, 0 failed, 0 skipped (AC8)

- [x] Task 11: Commit per Dev Notes plan, push branch.

## Dev Notes

### Files to change

| File | Change type | Description |
|---|---|---|
| `models/project_system.py` | NEW | ~150-180 LoC: catalogue + dispatcher + ProjectSystem class with 5 methods |
| `tests/unit/test_project_system.py` | NEW | ~250 LoC: 10+ tests across single TestProjectSystem class |

### Why `yearly_cost_food` exists but is not drained

`DynastyDB` has 3 resource columns: `current_wealth` (gold), `current_iron`, `current_timber`. There is no `current_food` column. The `yearly_cost_food` column on `Project` is forward-compatible schema for Sprint 6 (when food becomes a real stockpiled resource); for Story 2-2, `tick_projects` simply ignores food cost. This is documented in the catalogue with a comment, and `march_army_cross_realm` is the canonical example (master plan line 206 shows `-20 food/yr`) — its `yearly_cost_food=20` in the catalogue, but `tick_projects` doesn't deduct it. When food is wired up (Sprint 6), update `tick_projects` to add the food check; the catalogue entries don't need to change.

### Why no upfront cost deduction in `start_project`

Master plan line 178-179: "Yearly drain (validated at project start; if treasury runs out, project goes into 'stalled' status and reports a turn interrupt)". Two readings:
1. **Pre-deduct year 1's cost at start** — but this conflicts with the `tick_projects` model (would the first tick deduct again? do we skip year 1's tick?).
2. **Validate dynasty CAN pay year 1, then let `tick_projects` do all draining uniformly.**

Reading (2) is cleaner. Story 2-2 implements (2): `start_project` checks affordability of year 1 (rejects if insufficient), then `tick_projects` is the only place that mutates `current_*` stockpiles. This is simpler to reason about and easier to test.

### Effect dispatcher = stubs in this story, real in 2-3

Master plan line 218 says "On completion: apply the project's effect (spawn the unit, mark the building built, transfer the army, register the marriage)". Wiring real effects requires calling into `MilitarySystem.recruit_unit`, `EconomySystem.construct_building`, etc. — and that's tangled with the `submit_actions` migration in Story 2-3.

Story 2-2 introduces the `EFFECT_DISPATCHER` registry skeleton with NO-OP stubs (each logs `logger.info(f"[stub] {project_type} completed for project {project.id}")`). Story 2-3 replaces those stubs with real subsystem calls. The dispatcher signature `Callable[[Session, Project], None]` is final — Story 2-3 only swaps the function bodies.

### Why `tick_projects` does NOT auto-complete on `completion_year`

Master plan line 219: "Wire into `process_dynasty_turn` — projects tick before lifecycle each year". The natural ordering is:
1. `tick_projects(dynasty_id, current_year)` — drain costs, may set stalled
2. Lifecycle (births/deaths/etc.)
3. Check `if project.completion_year <= current_year: complete_project(project_id)` — separate call

Bundling completion into `tick_projects` mixes two responsibilities and makes the interrupt emission semantics unclear (does completion emit an interrupt? if so, alongside stalls?). Story 2-3 owns the orchestration order. Story 2-2 keeps `tick_projects` strictly to draining; completion is a separate caller-driven step.

### Why `cancel_project` takes `current_year` as a parameter

The class has no concept of "current year" — `DynastyDB.current_simulation_year` is the source of truth, but injecting it as a parameter makes the refund math deterministic and unit-testable (no need to set up dynasty state for every cancel test). The Story 2-3 caller will pass `dynasty.current_simulation_year`.

### Resource-deduction pattern (mirror existing code)

`models/economy_system.py:735` shows the existing pattern: `dynasty.current_wealth -= costs.get("gold", 0)`. Mirror exactly: `dynasty.current_wealth -= project.yearly_cost_gold` (etc.). Wrap in try/except + `db.session.rollback()` per CLAUDE.md / project-context.md rules.

### `InsufficientResourcesError` location

Define at module level in `project_system.py`. Don't put it in a separate `exceptions.py` — none exists, and the project-context rules discourage premature abstractions. Story 2-3 can re-import as `from models.project_system import InsufficientResourcesError`.

### Interrupt tuple shape

For consistency with `turn_processor.py:134` (`interrupt = ('monarch_death', current_year)`), the stalled interrupt is `('project_stalled', year, project_id)` — a 3-tuple to carry the project ID for the UI to display "Project X stalled because dynasty is out of iron". Other interrupts in `INTERRUPT_REASONS` are 2-tuples; the extra element doesn't break anything because callers index `interrupt[0]` for the reason. Story 2-3 will likely normalize to 2-tuples or expand the schema; for now, the 3-tuple is the path of least resistance and `tick_projects` returns a LIST of them (multiple stalls in one tick possible).

### What this story does NOT touch

- `models/db_models.py` — no schema changes. Project model from Story 2-1 is complete.
- `models/turn_processor.py` — Story 2-3.
- `blueprints/dynasty.py` `submit_actions` — Story 2-3.
- Real effect implementations — Story 2-3.
- Chronicle hook for multi-monarch completion — Story 2-4.
- UI / templates — Sprint 3 (Epic 3).

### Snake-pit: don't auto-load `Project` in `models/__init__.py`

Some existing code does `from models import db_models` and expects everything to be available. Story 2-2 doesn't change imports; just `from models.db_models import Project, DynastyDB, PersonDB, db` inside `project_system.py`. Don't add `project_system` to `models/__init__.py`.

### Branch name

`feature/project-system-logic` (already created in this session).

### Commit plan

- Commit 1: `feat(project-system): add ProjectSystem class with start_project + get_active_projects`
- Commit 2: `feat(project-system): add tick_projects with stall interrupt and EFFECT_DISPATCHER stubs`
- Commit 3: `feat(project-system): add complete_project and cancel_project with 50% refund`
- Commit 4: `test(project-system): unit tests for lifecycle methods, stall interrupt, refund math`

(Combining 1+2 or 2+3 is fine if the chronology doesn't naturally split.)

### Scope boundaries

- **In scope:** `models/project_system.py` (new), `tests/unit/test_project_system.py` (new).
- **Out of scope:** real effect implementations, turn-processor wiring, submit_actions migration, chronicle hooks, UI.

### References

- Master plan: `review_documents/8_master_plan_2026.md` lines 153-232 (Sprint 2 — Project model)
- Project type catalogue (master): lines 194-211
- Project schema (Story 2-1, now done): `models/db_models.py:624-665`
- DynastyDB resource columns: `models/db_models.py:54,71-72` (`current_wealth`, `current_iron`, `current_timber`)
- Existing resource deduction pattern: `models/economy_system.py:735`
- Subsystem constructor convention: `models/banking_system.py:__init__` (takes `session: Session` only)
- Interrupt tuple pattern: `models/turn_processor.py:134,156` (`('reason', year)` 2-tuple)
- `INTERRUPT_REASONS` list: `models/turn_processor.py:38-47` (includes `'project_complete'`; `'project_stalled'` is NOT yet listed — Story 2-3 will add it)
- Project rules (logging, error handling, no print): `_bmad-output/project-context.md` lines 34-44

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (direct execution)

### Implementation Plan

1. Created `models/project_system.py`: module logger, `InsufficientResourcesError`, `PROJECT_TYPE_CATALOGUE` (8 entries — added `march_army_cross_realm` to test the food-skip path), `EFFECT_DISPATCHER` (auto-built dict mapping every catalogue key → `_stub_effect`).
2. `ProjectSystem.__init__(session)`, plus 5 lifecycle methods exactly matching the spec.
3. Created `tests/unit/test_project_system.py` with 20 tests across one `TestProjectSystem` class.
4. Two test-setup fixes during run: had to give the dynasty exactly one year's worth of resources for stall tests (the spec's "start_project checks year-1 affordability" means dynasty must afford year 1 OR the project can't start).

### Completion Notes

- All 8 ACs satisfied; all 11 tasks (+ subtasks) checked.
- pytest: **251 passed, 0 failed, 0 skipped** (was 231 pre-story; +20 tests).
- Added one project type beyond the 6 ACs required (`march_army_cross_realm`) specifically to test the food-skip path documented in Dev Notes.
- Decision recorded inline: `start_project` validates year-1 affordability AND does not pre-deduct; `tick_projects` is the sole drainer (Dev Notes rationale honored).
- Decision recorded inline: `tick_projects` does NOT auto-complete on `completion_year`; Story 2-3 owns orchestration.
- Decision recorded inline: stalled projects are skipped on subsequent ticks (`get_active_projects` filters by `status='active'`).
- Effect dispatcher uses NO-OP stubs per spec; Story 2-3 swaps function bodies.
- Out-of-scope honored: no `db_models.py` changes, no `turn_processor.py` wiring, no `submit_actions` migration, no chronicle hook, no UI.

### File List

- `models/project_system.py` — NEW (~230 LoC: catalogue, dispatcher, ProjectSystem class with 5 methods)
- `tests/unit/test_project_system.py` — NEW (~250 LoC: 20 tests across TestProjectSystem class + 2 fixture helpers)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED (status: backlog → in-progress → review)
- `_bmad-output/implementation-artifacts/2-2-project-system-logic.md` — MODIFIED (status updates, Dev Agent Record sections populated)

### Change Log

| Date | Change |
|---|---|
| 2026-05-17 | feat(project-system): add ProjectSystem class + PROJECT_TYPE_CATALOGUE + EFFECT_DISPATCHER stubs |
| 2026-05-17 | feat(project-system): start_project / tick_projects / complete_project / cancel_project / get_active_projects |
| 2026-05-17 | test(project-system): 20 unit tests for lifecycle, stall interrupt, refund math, dispatcher coverage |
| 2026-05-17 | pytest: 251 passed, 0 failed, 0 skipped |
| 2026-05-17 | Story status → review |
| 2026-05-17 | Code review (3 layers): Acceptance Auditor clean; 7 patches applied (3 state-machine bugs + 1 contract drift + 1 effect-fn rollback + 2 cosmetic), ~30 deferred, ~6 dismissed |

### Review Findings

_Code review run 2026-05-17 — 3 parallel adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor)._

**Patches (applied):**

- [x] [Review][Patch] AC5/Task 3 contract drift: `complete_project` was `EFFECT_DISPATCHER.get(...)` + warning; spec said strict `KeyError`. Now uses `[]` indexing so a future catalogue addition without a paired dispatcher entry fails loudly [`models/project_system.py:complete_project`]
- [x] [Review][Patch] State guard: `complete_project` now raises `ValueError` if project status is not `'active'` — prevents double-completion / completing a stalled or cancelled project [`models/project_system.py:complete_project`]
- [x] [Review][Patch] State guard: `cancel_project` now raises `ValueError` if project is already `'completed'` or `'cancelled'` — prevents double-refund [`models/project_system.py:cancel_project`]
- [x] [Review][Patch] Time-travel guard: `cancel_project` raises if `current_year < project.started_year` — prior code silently clamped to 0 [`models/project_system.py:cancel_project`]
- [x] [Review][Patch] `complete_project` wraps `effect_fn` invocation in try/except + rollback so a failing effect doesn't leave the session in a partially-committed state [`models/project_system.py:complete_project`]
- [x] [Review][Patch] Dead imports cleanup: removed unused `Optional`, `db` (only used via models internally); tightened `List[Tuple]` to `List[Tuple[str, int, int]]` on tick_projects return type [`models/project_system.py:imports,tick_projects`]
- [x] [Review][Patch] Tests strengthened: `test_tick_drains_yearly_cost` now also asserts iron unchanged (regression guard); `test_dispatcher_covers_every_catalogue_entry` now also asserts every dispatcher entry is callable; **7 new state-guard tests** added [`tests/unit/test_project_system.py`]

**Deferred (Story 2-3 / Sprint 11 / cosmetic):**

- [x] [Review][Defer] `requires_building` field in catalogue is decorative — not enforced by `start_project`. Story 2-3 wires the building check.
- [x] [Review][Defer] `slot` field in catalogue is decorative — not consumed. Sprint 3 (UI) will surface the 3-slot constraint.
- [x] [Review][Defer] `start_project` doesn't validate that `target_*` IDs reference existing rows — DB FK will reject on commit (caught at commit time, not pre-validated). Story 2-3 may add eager validation if UX wants nicer errors.
- [x] [Review][Defer] `start_project` accepts arbitrary kwargs (typos like `target_territoy_id` silently swallowed) — Sprint 11 type-strict kwargs cleanup.
- [x] [Review][Defer] No history-log entries written by tick/complete/cancel — Story 2-4 (chronicle hook) and Story 2-3 (turn-processor wiring) own the chronicle integration.
- [x] [Review][Defer] No `resume_project` method — stalled is currently permanent. Sprint 5 succession drama might add resume; for now intentional.
- [x] [Review][Defer] Single commit at end of `tick_projects` is intentionally atomic per-dynasty per-tick; per-project savepoints rejected as over-engineering.
- [x] [Review][Defer] `_make_monarch` always sets `gender='MALE'` — extend when Sprint 5 succession drama needs female-monarch coverage.
- [x] [Review][Defer] `caplog`-based dispatcher test is fragile to log format — replace with mock dispatcher in Sprint 11 test cleanup.
- [x] [Review][Defer] Monarch-succession test simulates inheritance manually rather than via real flow — acceptable until Sprint 5 wires the real flow into a fixture.
- [x] [Review][Defer] `cancel_project` doesn't invoke a dispatcher (no chronicle entry for cancellation) — Story 2-4 chronicle hook will add a cancel-line variant.
- [x] [Review][Defer] No fractional-year refund tests (e.g. cancel after 3 ticks of a 100g/yr project = 150g refund) — add when Story 2-3 wires cancel into the UI.
- [x] [Review][Defer] `tick_projects` per-project iteration order is DB-insertion order (non-deterministic across backends) — Story 2-3 may add `ORDER BY started_year` for fairness.
- [x] [Review][Defer] Multi-dynasty isolation not explicitly tested (only one dynasty per test) — partially covered by `get_active_projects` filter test; full multi-dynasty test added in Story 2-3 integration tests.
- [x] [Review][Defer] No `ProjectSystemError` base class — premature; revisit when 2nd exception type is needed.
- [x] [Review][Defer] No method-level docstrings — Sprint 11 documentation pass.
- [x] [Review][Defer] `PROJECT_TYPE_CATALOGUE` returns mutable dict by reference (no `MappingProxyType` / freeze) — caller responsibility; constants in this codebase aren't frozen by convention.
- [x] [Review][Defer] All-or-nothing affordability (not partial-pay) is deliberate game design — Sprint 11 retro if telemetry shows it's frustrating.
- [x] [Review][Defer] Affordability check uses `<` (not `<=`); a dynasty with exactly year-1 cost can start a project that immediately drains to zero — no buffer policy. Sprint 11 if economy balance needs it.
- [x] [Review][Defer] `build_walls` / `build_cathedral` have only gold cost (no iron/timber) — placeholder balance; tweak when Sprint 6 wires stone resource.
- [x] [Review][Defer] No `pytest.xfail` on `test_tick_ignores_food_cost` — this is a documented design choice (food is forward-compat schema), not a known bug. Sprint 6 will replace this test with real food-drain assertions.
- [x] [Review][Defer] `completion_year = started_year + duration_years` (1-year project completes in `started_year + 1`, not the same year) — semantic convention pinned by tests and not changed.

**Dismissed (paranoid / out-of-context):**

- 6 items: dynasty deleted between fetch and tick (single-process Flask), race conditions on affordability check (no concurrent writers), non-JSON-serializable params (caller responsibility), uuid4 collisions in test helper (cosmically improbable), negative catalogue values (constant is module-private), `models/__init__.py` auto-load (was never proposed).

**Acceptance Auditor:** ✅ All 8 ACs satisfied. Out-of-scope boundaries honored (no `db_models.py`, `turn_processor.py`, blueprint, real-effect, chronicle, or UI changes). One contract drift on dispatcher-miss behavior was patched.
