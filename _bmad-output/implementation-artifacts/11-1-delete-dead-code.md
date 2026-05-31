# Story 11-1: Retire the Legacy Simulation Engine + Delete Dead Code

Status: done

## Story

Pay down the largest chunk of pre-ORM technical debt: retire the standalone `simulation_engine.py` CLI simulation and the legacy in-memory `Person` / `FamilyTree` / `EconomyManager` classes (all fully superseded by the ORM models + `EconomySystem` + the SVG family-tree renderer), remove their now-dead importers/routes/tests, and clear junk files. ~1,450 lines of dead code removed. The live Flask web app depends on NONE of these (verified) — it uses `PersonDB`/`DynastyDB` + `EconomySystem` throughout.

## Approach note
The deletions are tightly coupled (each module + its importers + `models/__init__.py` re-exports + the import-smoke tests must change together atomically). So this story is implemented as a **single coordinated main-session pass** (not parallel worktree agents — there is no parallelism benefit and serial editing avoids deleting-a-module-while-another-edits-its-importer races), gated by the full test suite.

## Acceptance Criteria

1. **AC1 — Remove dead importers/routes (rewire first).**
   - `main_flask_app.py`: remove the unused `from simulation_engine import SimulationEngine` (imported, never referenced). (App-setup cleanup only — within the allowed scope for that file.)
   - `blueprints/economy.py`: delete the entire `add_holding` route (~:449-517) — it is the ONLY user of `EconomyManager` and is unreferenced (no template / `url_for` / form posts to it).
   - `blueprints/map.py`: delete the two dead placeholder redirect routes (`create_dynasty_placeholder`, `view_dynasty_placeholder`, ~:948-961) — pure back-compat shims, unreferenced.
   - `models/__init__.py`: remove the `from .person import Person` and `from .family_tree import FamilyTree` re-exports. (Leave `History` re-export if present — `models/history.py` is NOT in scope for this story.)
2. **AC2 — Delete the legacy modules + CLI.**
   - Delete `simulation_engine.py`, `models/person.py`, `models/family_tree.py`, `models/economy.py`, and `run_local_simulation.py` (the standalone CLI wrapper that imported the engine).
3. **AC3 — Delete the dead tests** (all are import-smoke/unit tests for the retired engine — they test nothing live): `tests/test_imports.py`, `tests/test_single_import.py`, `tests/test_flask.py`, `tests/unit/test_simulation_engine.py`.
4. **AC4 — Junk + gitignore.** `git rm` `simulation_engine.py.bak` and `cookies.txt` (tracked junk). Add `*.log`, `*.bak`, and `cookies.txt` to `.gitignore` (so `flask_app.log` etc. stop being candidates for tracking).
5. **AC5 — No live references remain.** After the deletions, ALL of these greps over `*.py` (excluding `.venv`/`__pycache__`) return ZERO: `from models.person import`, `import models.person`, `from models.family_tree import`, `from models.economy import`, `import simulation_engine`, `from simulation_engine`, `EconomyManager`, `SimulationEngine`. (`models/history.py` may remain and may import `Person` under `TYPE_CHECKING` — if so, that's the ONE allowed remaining reference; verify it's TYPE_CHECKING-only and doesn't break import. If `models/history.py` imports `Person` at runtime, either keep `models/person.py` or guard the import — do NOT break `history.py`.)
6. **AC6 — No regressions.** Full suite green (baseline **542 passed**, minus the 4 deleted dead-test files' tests = the suite count drops by however many those held; **0 failures**). The app imports cleanly (`python -c "import main_flask_app"`) and `/world/map`, `/dynasty/<id>/view`, the economy routes, and advance_turn still work. No new deps.

## Tasks / Subtasks
- [ ] Task 1 — Remove dead importers + the `add_holding` route + the 2 map placeholder routes + the `__init__` re-exports. [main-session]
- [ ] Task 2 — Delete the 5 modules/CLI + 4 dead tests + 2 junk files; update `.gitignore`. [main-session]
- [ ] Task 3 — Verify (greps from AC5 all zero; full suite green; app imports + key routes smoke). [main-session]

## Dev Notes

### Verified dependency map (from investigation)
- `simulation_engine.py`: imported but UNUSED in `main_flask_app.py:44`; real importer is `run_local_simulation.py:13` (standalone CLI, `if __name__=='__main__'`) + 4 import-smoke tests. Imports `models.person`, `models.family_tree`, `models.history`.
- `models/person.py` (`Person`) + `models/family_tree.py` (`FamilyTree`): used ONLY by `simulation_engine.py` + `models/__init__.py` re-exports (and a TYPE_CHECKING hint in `models/history.py`). Live app uses `PersonDB` (ORM) exclusively; `turn_processor` stopped using them in Story 8-3; `visualization/family_tree_svg.py` uses ORM.
- `models/economy.py` (`EconomyManager`): used ONLY by the dead `add_holding` route (`blueprints/economy.py:486`). All live economy code uses `EconomySystem` (`models/economy_system.py`).
- Junk: `simulation_engine.py.bak` (tracked), `cookies.txt` (tracked), `flask_app.log` (untracked, ~500KB — gitignore it).

### Reuse / project rules
- Deletions only — no new code. Keep `models/economy_system.py` (`EconomySystem`), `models/db_models.py`, `models/history.py` (out of scope). Don't touch `models/time_system.py`/`game_manager.py`/`turn_processor.py` (they already use ORM). Run `pytest` after the deletions; if any unexpected importer surfaces, fix or keep that module. Stage deletions explicitly (`git rm`); never `git add .`.

### Out of scope / deferred
- `models/history.py` (`History` class) retirement (not in the plan's list; verify it doesn't block import but leave it). Flask-Migrate/Alembic (Story 11-2). Perf indexes (11-3). Logging/warnings (11-4). The matplotlib full-removal (still needed by 5 renderers — separate) and the `Building` construction-schema bug (separate) remain deferred.

## Previous Story Intelligence
- Done as a single coordinated main-session pass (deletions are coupled). Integrator = main session: run the FULL suite after deleting; `python -c "import main_flask_app"` must succeed; spot-check `/world/map`, `/dynasty/<id>/view`, economy routes, advance_turn on the live app. This is the 4th plan-vs-code reconciliation (matplotlib, construction, now dead-code) — the plan's "delete after Sprint 8" assumptions were partly stale (the 3 modules were still imported), hence the rewire-first approach.
- Baseline **542 passed** (Epics 7-10 complete). Tests: temp DB; `python -m pytest -p no:randomly -q`. The 4 deleted test files only smoke-tested the retired engine.

## References
- `main_flask_app.py:44`; `blueprints/economy.py:449-517` (add_holding) + `:486` (EconomyManager import); `blueprints/map.py:948-961` (placeholder routes); `models/__init__.py:6,8` (Person/FamilyTree re-exports); `simulation_engine.py:13-15`; `run_local_simulation.py:13`. Dead tests: `tests/test_imports.py`, `tests/test_single_import.py`, `tests/test_flask.py`, `tests/unit/test_simulation_engine.py`.

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — single coordinated main-session pass (no sub-agents; coupled deletions).
### Completion Notes List
- Done as a single coordinated main-session pass. ~1,450 lines of dead code removed. Full suite **536 passed** (542 - 6 tests from the 4 deleted dead-test files), 0 failures; app imports clean; dashboard/create/world-map/dynasty-view/economy routes all 200 live.
- **Correction to the plan:** the two `map.py` placeholder routes were NOT dead — `templates/base.html`'s nav ("New Dynasty") and `themes/{base,dashboard}.html` linked to `map.create_dynasty_placeholder` / `view_dynasty_placeholder`. Deleting them first broke every base.html-extending page (72 failures). Fixed by repointing those template links directly to the real `dynasty.create_dynasty` / `dynasty.view_dynasty` routes, then the shims stayed deleted. (4th plan-vs-code reconciliation this session.)
- `models/history.py` left in place (out of scope); its `from .person import Person` is TYPE_CHECKING-only so it survives the `person.py` deletion at runtime.
### File List
- DELETE: `simulation_engine.py`, `simulation_engine.py.bak`, `run_local_simulation.py`, `models/person.py`, `models/family_tree.py`, `models/economy.py`, `cookies.txt`, `tests/test_imports.py`, `tests/test_single_import.py`, `tests/test_flask.py`, `tests/unit/test_simulation_engine.py`
- MODIFY: `main_flask_app.py` (drop unused import), `blueprints/economy.py` (drop add_holding), `blueprints/map.py` (drop 2 placeholder routes), `models/__init__.py` (drop re-exports), `.gitignore`
- `_bmad-output/implementation-artifacts/{11-1-...md, sprint-status.yaml}`, `STATUS.md`
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(11-1); retire legacy sim + dead code; single coordinated pass |
