# Story 1.2: Interrupt-driven turn loop

Status: review

## Story

As a developer,
I want `process_dynasty_turn` to stop advancing years the moment a monarch dies,
so that subsequent sprints (succession UI, project completion, heir-majority) can pause the world at the exact year the interrupting event occurs, rather than letting 5-year turns roll over a monarch's death silently.

## Acceptance Criteria

1. **AC1 — INTERRUPT_REASONS constant exists** in `models/turn_processor.py` as a module-level list of 8 strings: `monarch_death`, `heir_majority`, `project_complete`, `war_declared`, `attack_received`, `major_world_event`, `story_moment`, `quiet_period`.

2. **AC2 — While loop replaces for loop** in `process_dynasty_turn`. The loop body executes year-by-year and exits early when `interrupt` is set. A `quiet_period` interrupt is assigned when all `max_years` complete without a more specific interrupt.

3. **AC3 — Monarch death stops the loop.** When `process_death_check` returns `True` for the current monarch, `process_succession` fires (existing behavior preserved), the interrupt is set to `('monarch_death', current_year)`, and no further years are processed in this turn.

4. **AC4 — `turn_summary` includes `interrupt_reason` and actual `years_advanced`.** `turn_summary['interrupt_reason']` is always a string from `INTERRUPT_REASONS`. `turn_summary['years_advanced']` reflects actual years processed (1–5), not the parameter. `turn_summary['end_year']` equals `dynasty.current_simulation_year` after the loop.

5. **AC5 — Quiet-period turn still advances exactly `max_years` (default 5) when no interrupt fires.** A dynasty with a young, healthy monarch advances the full 5 years.

6. **AC6 — 211 tests pass, 0 fail.** Year-increment integration and functional tests updated to mock `process_death_check` returning `False`, making them deterministic (monarch guaranteed to survive, so full 5 years advance, preserving current exact-year assertions).

7. **AC7 — Story 1-3 scope not touched.** `templates/turn_report.html` and `utils/llm_prompts.py` are unchanged. The `interrupt_reason` key is present in `turn_summary` but not yet displayed (that is Story 1-3 and 1-4's job).

## Tasks / Subtasks

- [x] Task 1: Add `INTERRUPT_REASONS` constant to `models/turn_processor.py` (AC1)
  - [x] Place it after the logger line, before `_llm_available()`
  - [x] 8-element list matching master plan exactly

- [x] Task 2: Refactor `process_dynasty_turn` while loop (AC2, AC3, AC4, AC5)
  - [x] Remove `end_year = start_year + years_to_advance` pre-computation
  - [x] Replace `for current_year in range(start_year, end_year)` with `while years_advanced < years_to_advance and interrupt is None`
  - [x] Inside loop: derive `current_year = start_year + years_advanced`
  - [x] After monarch death in the person loop: call `process_succession` then set `interrupt = ('monarch_death', current_year)`
  - [x] After the while loop: `if interrupt is None: interrupt = ('quiet_period', years_advanced)`
  - [x] Update HistoryLogEntryDB events query to use `dynasty.current_simulation_year` as upper bound
  - [x] Update epic story prompt `end_year` argument to `dynasty.current_simulation_year - 1`
  - [x] Update `turn_summary` dict: `end_year=dynasty.current_simulation_year`, `years_advanced=years_advanced`, add `interrupt_reason=interrupt[0]`

- [x] Task 3: Update year-increment tests to mock death check (AC6)
  - [x] `tests/integration/test_game_loop.py` — `test_advance_turn_increments_year`
  - [x] `tests/integration/test_game_loop.py` — `test_three_turns_year_correct`
  - [x] `tests/functional/test_game_flow.py` — line 112–114 (advance 1 turn, assert == 1405)
  - [x] `tests/functional/test_game_flow.py` — line 134–141 (advance 3 more turns, assert == 1420)
  - [x] `tests/functional/test_game_flow.py` — line 181–194 (multi-dynasty, assert == 1405)

- [x] Task 4: Run `pytest` — confirm 211 passed, 0 failed (AC6)

- [x] Task 5: Create feature branch, commit, push, update STATUS.md

## Dev Notes

### Primary file: `models/turn_processor.py`

**Current state (lines 101–138):**

```python
start_year = dynasty.current_simulation_year
end_year = start_year + years_to_advance

for current_year in range(start_year, end_year):
    try:
        process_world_events(dynasty, current_year, theme_config)
        for person in living_persons:
            if person.death_year is not None:
                continue
            if process_death_check(person, current_year, theme_config):
                if person.is_monarch:
                    process_succession(dynasty, person, current_year, theme_config)
                continue
            if person.is_noble and person.spouse_sim_id is None:
                process_marriage_check(dynasty, person, current_year, theme_config)
            if person.gender == "FEMALE" and person.spouse_sim_id is not None:
                process_childbirth_check(dynasty, person, current_year, theme_config)
        living_persons = [p for p in living_persons if p.death_year is None]
    except Exception as year_exc:
        logger.error(...)

    dynasty.current_simulation_year = current_year + 1
```

**Target state (replace lines 101–138):**

```python
interrupt = None
years_advanced = 0

while years_advanced < years_to_advance and interrupt is None:
    current_year = start_year + years_advanced
    try:
        process_world_events(dynasty, current_year, theme_config)
        for person in living_persons:
            if person.death_year is not None:
                continue
            if process_death_check(person, current_year, theme_config):
                if person.is_monarch:
                    process_succession(dynasty, person, current_year, theme_config)
                    interrupt = ('monarch_death', current_year)
                continue
            if person.is_noble and person.spouse_sim_id is None:
                process_marriage_check(dynasty, person, current_year, theme_config)
            if person.gender == "FEMALE" and person.spouse_sim_id is not None:
                process_childbirth_check(dynasty, person, current_year, theme_config)
        living_persons = [p for p in living_persons if p.death_year is None]
    except Exception as year_exc:
        logger.error(f"Error processing year {current_year} for dynasty {dynasty_id}: {year_exc}", exc_info=True)

    years_advanced += 1
    dynasty.current_simulation_year = current_year + 1

if interrupt is None:
    interrupt = ('quiet_period', years_advanced)
```

**What must be preserved:**
- `process_succession` is still called immediately after monarch death — this does NOT change.
- Non-monarch deaths do NOT set `interrupt`. The loop continues if a spouse or child dies.
- The `try/except` per year is preserved; exceptions continue to the next year.
- `dynasty.current_simulation_year` is updated at the END of each year (inside the loop), so it is always `current_year + 1` after a completed year.

### `turn_summary` dict update (lines 216–233 in current file)

**Current:**
```python
turn_summary = {
    'start_year': start_year,
    'end_year': end_year,                  # = start_year + years_to_advance (always 5)
    'years_advanced': years_to_advance,    # always 5
    ...
}
```

**Target:**
```python
turn_summary = {
    'start_year': start_year,
    'end_year': dynasty.current_simulation_year,   # actual end year
    'years_advanced': years_advanced,              # actual (1–5)
    'interrupt_reason': interrupt[0],              # 'monarch_death' or 'quiet_period'
    ...
    # all other existing keys unchanged
}
```

Also update the epic story prompt call (around line 189):
```python
# BEFORE:
prompt = build_turn_story_prompt(
    start_year=start_year,
    end_year=end_year - 1,
    ...
)

# AFTER:
prompt = build_turn_story_prompt(
    start_year=start_year,
    end_year=dynasty.current_simulation_year - 1,
    ...
)
```

And the HistoryLogEntryDB query (around line 161):
```python
# BEFORE:
HistoryLogEntryDB.year < end_year

# AFTER:
HistoryLogEntryDB.year < dynasty.current_simulation_year
```

**Rationale:** `end_year` no longer exists as a variable after this refactor. All post-loop code must use `dynasty.current_simulation_year` (which equals `start_year + years_advanced`).

### `INTERRUPT_REASONS` placement (add after logger line ~36)

```python
logger = logging.getLogger('royal_succession.turn_processor')

INTERRUPT_REASONS = [
    'monarch_death',
    'heir_majority',
    'project_complete',
    'war_declared',
    'attack_received',
    'major_world_event',
    'story_moment',
    'quiet_period',
]
```

Stubs `heir_majority`, `project_complete`, `war_declared`, `attack_received`, `major_world_event`, `story_moment` are for future sprints. They exist in the constant but no detection logic is wired for them yet.

### Test updates required

**Why tests break without mocking:** With the interrupt loop, if the monarch dies in year 1 of the turn, `current_simulation_year` advances only 1 year instead of 5. Existing tests assert exact year values (e.g., `== 1305`). These become non-deterministic — they pass ~95% of the time for a young founder with 1% annual mortality, but fail when the monarch dies early.

**Fix pattern:** Patch `process_death_check` to return `False` in tests that assert exact year values.

#### `tests/integration/test_game_loop.py`

**`test_advance_turn_increments_year` (line 140–147):**

```python
def test_advance_turn_increments_year(self, dynasty_client, app, db):
    dynasty_id = _get_dynasty_id(app, db, 'loop_user')
    with patch('models.turn_processor.process_death_check', return_value=False):
        dynasty_client.get(
            f'/dynasty/{dynasty_id}/advance_turn', follow_redirects=True
        )
    with app.app_context():
        dynasty = db.session.query(DynastyDB).get(dynasty_id)
        assert dynasty.current_simulation_year == 1305
```

Add `from unittest.mock import patch` at the top of the file (it's already imported there for the succession test, so no new import needed).

**`test_three_turns_year_correct` (line 163–172):**

```python
def test_three_turns_year_correct(self, dynasty_client, app, db):
    dynasty_id = _get_dynasty_id(app, db, 'loop_user')
    with patch('models.turn_processor.process_death_check', return_value=False):
        for _ in range(3):
            dynasty_client.get(
                f'/dynasty/{dynasty_id}/advance_turn', follow_redirects=True
            )
    with app.app_context():
        dynasty = db.session.query(DynastyDB).get(dynasty_id)
        assert dynasty.current_simulation_year == 1315
```

#### `tests/functional/test_game_flow.py`

This file uses `from unittest.mock import patch`. Add the import at the top if not present, then wrap the `advance_turn` calls in the affected tests.

**Around line 105–114** (single advance_turn, asserts `== 1405`):

```python
with patch('models.turn_processor.process_death_check', return_value=False):
    response = client.get(f'/dynasty/{dynasty_id}/advance_turn', follow_redirects=True)
assert response.status_code == 200
...
with app.app_context():
    dynasty = db.session.query(DynastyDB).get(dynasty_id)
    assert dynasty.current_simulation_year == 1405
```

**Around line 134–141** (3 more turns, asserts `== 1420`):

```python
with patch('models.turn_processor.process_death_check', return_value=False):
    for _ in range(3):
        client.get(f'/dynasty/{dynasty_id}/advance_turn', follow_redirects=True)
with app.app_context():
    dynasty = db.session.query(DynastyDB).get(dynasty_id)
    assert dynasty.current_simulation_year == 1420
```

**Around line 181–194** (multi-dynasty, asserts both `== 1405`):

```python
for dynasty_id in (dynasty_a_id, dynasty_b_id):
    with patch('models.turn_processor.process_death_check', return_value=False):
        response = client.get(f'/dynasty/{dynasty_id}/advance_turn', follow_redirects=True)
    assert response.status_code == 200
...
assert dynasty_a.current_simulation_year == 1405
assert dynasty_b.current_simulation_year == 1405
```

### Tests that do NOT need changes

- `test_advance_turn_returns_200` — checks status 200 only
- `test_advance_turn_shows_flash` — checks for 'Chronicles'/'Error'/'Turn Report' text
- `test_three_turns_history_not_empty` — checks `len(events) > 0` (still true even with 1 year)
- `test_three_turns_timeline_accessible` — checks 200 + 'Timeline' text
- `test_succession_fires_when_monarch_dies` — patches death check to force death, checks `death_year is not None` ✓ still works
- `test_unauthenticated_advance_turn_redirects_to_login` — checks redirect to login
- `test_other_user_cannot_advance_turn` — checks year stays at 1300 (unauthorized, no advance)

### Route contract: no changes to `blueprints/dynasty.py`

The `advance_turn` route (line 228) already unpacks the 3-tuple safely:
```python
if len(result) == 3:
    success, message, turn_summary = result
```

Adding `interrupt_reason` to `turn_summary` is backward-compatible — the template ignores unknown keys. No route changes needed.

The `submit_actions` route (line 582) also calls `process_dynasty_turn(dynasty_id, years_to_advance=5)` with the same safe unpacking — no changes needed there either.

### Scope boundaries for this story

- **In scope:** `models/turn_processor.py`, `tests/integration/test_game_loop.py`, `tests/functional/test_game_flow.py`, `STATUS.md`
- **Out of scope (Story 1-3):** `templates/turn_report.html` — interrupt reason display
- **Out of scope (Story 1-4):** `utils/llm_prompts.py` — chronicle prompt update to receive `years_advanced` + `interrupt_reason`
- **Out of scope (Sprint 2):** `tick_projects` — `project_complete` interrupt
- **Out of scope (Sprint 5):** `heir_majority`, `civil_war` interrupts

### Deferred items from Story 1-1 that are still deferred

The `deferred-work.md` item about `current_simulation_year` advancing outside `try/except` is fixed by this story — `dynasty.current_simulation_year = current_year + 1` now sits after the `try/except` block in each loop iteration, so an exception in a year no longer silently skips that year's clock advancement.

### Project Structure Notes

- `models/turn_processor.py` — primary file, ~720 lines currently, refactor changes ~35 lines
- `tests/integration/test_game_loop.py` — 309 lines, 2 test methods updated
- `tests/functional/test_game_flow.py` — ~200 lines, 3 test regions updated
- Branch name: `feature/interrupt-driven-turn-loop`
- Commit 1: `feat(turn-processor): add INTERRUPT_REASONS and interrupt-driven while loop`
- Commit 2: `test(game-loop): mock death check in year-increment tests for determinism`

### References

- Master plan Sprint 1 loop pseudocode: `review_documents/8_master_plan_2026.md` lines 100–128
- Current turn processor: `models/turn_processor.py` lines 62–233
- Route caller (advance_turn): `blueprints/dynasty.py` lines 228–329
- Route caller (submit_actions): `blueprints/dynasty.py` lines 570–615
- Year-increment integration tests: `tests/integration/test_game_loop.py` lines 140–195
- Year-increment functional tests: `tests/functional/test_game_flow.py` lines 105–194
- Previous story artifact: `_bmad-output/implementation-artifacts/sprint01-task01-turn-processor-extraction.md`
- Deferred work log: `_bmad-output/implementation-artifacts/deferred-work.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation matched the story spec exactly on first attempt.

### Completion Notes List

- AC1: `INTERRUPT_REASONS` list (8 items) added after logger declaration at `models/turn_processor.py:38`
- AC2: `for` loop replaced with `while years_advanced < years_to_advance and interrupt is None` loop
- AC3: Monarch death sets `interrupt = ('monarch_death', current_year)` after `process_succession` fires; non-monarch deaths do not interrupt
- AC4: `turn_summary` now has `end_year=dynasty.current_simulation_year`, `years_advanced=years_advanced` (actual), `interrupt_reason=interrupt[0]`; events query and story prompt both updated to use `dynasty.current_simulation_year` instead of pre-computed `end_year`
- AC5: Quiet-period turns (no interrupt) still advance exactly `years_to_advance` years; `interrupt = ('quiet_period', years_advanced)` assigned after loop exits naturally
- AC6: 5 year-assertion tests wrapped with `patch('models.turn_processor.process_death_check', return_value=False)`; `unittest.mock.patch` import added to `test_game_flow.py`; 211 tests pass, 0 fail
- AC7: `templates/turn_report.html` and `utils/llm_prompts.py` unchanged

### File List

- `models/turn_processor.py` — INTERRUPT_REASONS constant + while loop refactor
- `tests/integration/test_game_loop.py` — year-increment tests mock death check
- `tests/functional/test_game_flow.py` — year-assertion tests mock death check; added `from unittest.mock import patch`
- `STATUS.md` — Task 1-2 marked done
- `_bmad-output/implementation-artifacts/1-2-interrupt-driven-turn-loop.md` — story marked review
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status → review
