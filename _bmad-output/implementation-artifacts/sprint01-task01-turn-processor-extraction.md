# Sprint 1 Task 1: Turn-Processor Extraction

**Status:** complete
**Branch:** feature/turn-processor-extraction
**Sprint:** 1 (Master Plan 2026)

## Story

As a developer, I want the dynasty lifecycle logic (death, marriage, childbirth, succession, world events, family-tree snapshot) to live in `models/turn_processor.py` rather than `blueprints/dynasty.py`, so that subsequent sprints (variable turn length, project model, succession drama) can extend the turn engine without touching the route file.

## Acceptance Criteria

- [x] AC1: `models/turn_processor.py` exists and owns `process_dynasty_turn`, `process_death_check`, `process_marriage_check`, `process_childbirth_check`, `process_succession`, `process_world_events`, `generate_family_tree_visualization`
- [x] AC2: `blueprints/dynasty.py` imports `process_dynasty_turn` from `models.turn_processor` and contains no duplicate definitions of the lifecycle functions
- [x] AC3: Unused imports (`BankingSystem`, `build_turn_story_prompt`, `generate_turn_story_fallback`) removed from `blueprints/dynasty.py`
- [x] AC4: Integration test patch path updated from `blueprints.dynasty.process_death_check` → `models.turn_processor.process_death_check`
- [x] AC5: 211 tests pass, 0 fail, 0 skip — identical count to pre-refactor main

## Tasks/Subtasks

- [x] Task 1: Create `models/turn_processor.py` (verbatim copy of lifecycle functions from blueprint)
- [x] Task 2: Add `from models.turn_processor import process_dynasty_turn` import to `blueprints/dynasty.py`
- [x] Task 3: Remove now-unused imports from `blueprints/dynasty.py`: `BankingSystem`, `build_turn_story_prompt`, `generate_turn_story_fallback`
- [x] Task 4: Delete duplicate function bodies from `blueprints/dynasty.py`: `process_dynasty_turn`, `process_death_check`, `process_marriage_check`, `process_childbirth_check`, `process_succession`, `process_world_events`, `generate_family_tree_visualization`
- [x] Task 5: Update `tests/integration/test_game_loop.py` — patch path `blueprints.dynasty.process_death_check` → `models.turn_processor.process_death_check`
- [x] Task 6: Run `pytest` — confirm 211 passed, 0 failed
- [x] Task 7: Commit, push, update STATUS.md

## Dev Notes

- `generate_family_tree_visualization` uses lazy imports inside the function body (`from visualization.plotter import ...`), so no module-level import issues in `turn_processor.py`.
- `_llm_available()` is duplicated in both modules by design: `dynasty.py` needs it for non-turn routes; `turn_processor.py` needs it to be importable outside a Flask request context (unit tests). This duplication is intentional and safe.
- The `block_if_turn_processing` decorator and `initialize_dynasty_founder` function remain in `blueprints/dynasty.py` — they are route-level concerns.
- `BankingSystem`, `build_turn_story_prompt`, and `generate_turn_story_fallback` are all used only inside `process_dynasty_turn` in dynasty.py; once that function is deleted, these imports have no remaining callers.
- `os`, `random`, `json`, `datetime` are retained in dynasty.py — `initialize_dynasty_founder` and several route handlers use them.

## Deferred / Observed

- `generate_family_tree_visualization` is kept in `turn_processor.py` as-is. Sprint 8 of the master plan will replace it with `visualization/family_tree_svg.py` (SVG-based, dark-themed, interactive). Do not modify this function until Sprint 8.
- `blueprints/dynasty.py` still imports `DiplomaticRelation`, `War`, `TradeRoute`, `Army` from `db_models` — these are used by route handlers below the deleted functions. No change needed.
- Two dead placeholder routes in `blueprints/map.py` (`create_dynasty_placeholder`, `view_dynasty_placeholder`) noted in STATUS.md — deferred to Sprint 11 cleanup.
- `blueprints/dynasty.py` still has `from models.game_manager import GameManager` and `from models.economy_system import EconomySystem` etc. — verified in use by route handlers, not affected.
- The `advance_turn` route handler calls `process_dynasty_turn` via a 3-tuple unpack; this contract is preserved identically in `turn_processor.py`.

## File List

- `models/turn_processor.py` (new)
- `blueprints/dynasty.py` (modified — import added, 3 imports removed, 7 function bodies deleted)
- `tests/integration/test_game_loop.py` (modified — patch path corrected)
- `STATUS.md` (modified)

### Review Findings

_Code review run 2026-05-02 — 3 layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor. Result: 0 patch, 9 defer, 5 dismissed._

- [x] [Review][Defer] `process_dynasty_turn` early exits return 2-tuple, docstring promises 3-tuple [`models/turn_processor.py:72,85`] — deferred, pre-existing in dynasty.py; callers already guard with `len(result)==3`
- [x] [Review][Defer] `FLASK_APP_GOOGLE_API_KEY` config key never set in `app.config` [`models/turn_processor.py:182`] — deferred, pre-existing; `os.environ` fallback works
- [x] [Review][Defer] `max_output_tokens: 300` violates CLAUDE.md 150-token chronicle budget [`models/turn_processor.py:196`] — deferred, pre-existing in dynasty.py; fix in Sprint 9 (LLM storytelling)
- [x] [Review][Defer] `current_simulation_year` advances outside per-year `try/except` — silent year skip on exception [`models/turn_processor.py:138`] — deferred, pre-existing in dynasty.py
- [x] [Review][Defer] Sibling NULL FK query: `father_sim_id == None` compares incorrectly in SQL [`models/turn_processor.py:510`] — deferred, pre-existing in dynasty.py; succession fallback still triggers
- [x] [Review][Defer] `_llm_available()` try/except asymmetry between `dynasty.py` and `turn_processor.py` — dynasty.py version raises outside app context [`blueprints/dynasty.py:37`] — deferred, intentional design (turn_processor needs to be importable outside Flask)
- [x] [Review][Defer] Double `DynastyDB.query.get` after commit — extra round-trip [`models/turn_processor.py:213`] — deferred, pre-existing; address in Sprint 11 N+1 fix
- [x] [Review][Defer] `monarch_title` NameError if `titles` is empty list in `process_succession` [`models/turn_processor.py:566`] — deferred, pre-existing bug in dynasty.py; mitigated by default `["Leader"]`
- [x] [Review][Defer] `BankingSystem.accrue_interest` called after `db.session.commit()` with no rollback on failure [`models/turn_processor.py:153`] — deferred, pre-existing from Sprint 10B banking addition

## Change Log

- 2026-05-02: Story created; Task 1 complete (turn_processor.py committed); Tasks 2-7 complete (dynasty.py refactored, tests green, branch pushed)
- 2026-05-02: Code review complete — 0 patch, 9 deferred (all pre-existing), 5 dismissed. Status: done