# Story 1-4: Chronicle Prompt Update

Status: review

## Story

As a player,
I want the epic chronicle paragraph generated each turn to reflect how long the turn lasted and why it ended,
so that "five quiet years of governance" reads differently from "a single crisis year in which the king died" — and the narrative feels grounded in what actually happened.

## Acceptance Criteria

1. **AC1 — `build_turn_story_prompt` accepts `years_advanced` and `interrupt_reason`.** The function signature adds two new required parameters. The rendered prompt string includes both values so the LLM knows the turn's duration and cause.

2. **AC2 — `generate_turn_story_fallback` accepts the same two new parameters and produces distinct output per interrupt class.** At minimum:
   - `quiet_period`: existing peaceful-governance tone, mentions the span of years
   - `monarch_death`: a crisis-shadowed tone, mentions brevity ("in the single year that followed" or "in the three years before the king's passing")

3. **AC3 — Call sites in `turn_processor.py` pass `years_advanced` and `interrupt[0]` to both functions.** No other call sites exist; no other file changes are needed to propagate the new parameters.

4. **AC4 — Fallback fires correctly when LLM is unavailable.** Full playability without `GOOGLE_API_KEY` is maintained. Fallback produces grammatically correct sentences for any combination of valid `years_advanced` (1–5) and any `INTERRUPT_REASONS` value.

5. **AC5 — No regression on existing 212 tests.** `pytest` must report 212 passed, 0 failed, 0 skipped after all changes.

6. **AC6 — New unit tests for both updated functions.** At least one test per function verifying the new parameters appear in / affect the output. Test file: `tests/unit/test_llm_prompts.py` (new file, since none exists).

## Tasks / Subtasks

- [x] Task 1: Update `build_turn_story_prompt` signature and body in `utils/llm_prompts.py` (AC1)
  - [x] Add `years_advanced: int` and `interrupt_reason: str` as required parameters after `existing_story`
  - [x] Insert a pacing instruction line into the prompt body, e.g.:
    `f'This turn spanned {years_advanced} year{"s" if years_advanced != 1 else ""}. It ended because: {interrupt_reason.replace("_", " ")}.\n'`
  - [x] Keep all existing parameters and their behaviour unchanged

- [x] Task 2: Update `generate_turn_story_fallback` signature and body (AC2)
  - [x] Add `years_advanced: int` and `interrupt_reason: str` as required parameters after `monarch_name`
  - [x] Add a branch for `interrupt_reason == 'monarch_death'` that returns a crisis-toned sentence using `years_advanced`
  - [x] Keep the existing `quiet_period` / generic branch as the default, updated to use `years_advanced` for better grammar ("1 year" vs "N years")

- [x] Task 3: Update both call sites in `models/turn_processor.py` (AC3)
  - [x] `build_turn_story_prompt` call (around line 204): add `years_advanced=years_advanced, interrupt_reason=interrupt[0]`
  - [x] `generate_turn_story_fallback` call (around line 220): add `years_advanced=years_advanced, interrupt_reason=interrupt[0]`

- [x] Task 4: Create `tests/unit/test_llm_prompts.py` with unit tests (AC6)
  - [x] Test `build_turn_story_prompt` includes `years_advanced` value in returned string
  - [x] Test `build_turn_story_prompt` includes `interrupt_reason` (or its human-readable form) in returned string
  - [x] Test `generate_turn_story_fallback` returns different strings for `quiet_period` vs `monarch_death`
  - [x] Test `generate_turn_story_fallback` for `years_advanced=1` produces singular "year" not "years"

- [x] Task 5: Run `pytest`, confirm 212+ passed, 0 failed (AC5)

- [x] Task 6: Create branch, commit, push, update STATUS.md

## Dev Notes

### Files to change

| File | Change type | Description |
|---|---|---|
| `utils/llm_prompts.py` | UPDATE | Add 2 params to 2 functions |
| `models/turn_processor.py` | UPDATE | Pass new params at 2 call sites |
| `tests/unit/test_llm_prompts.py` | NEW | Unit tests for updated functions |

### Current state of `build_turn_story_prompt` (lines 128–145)

```python
def build_turn_story_prompt(dynasty_name, start_year, end_year, events, monarch_name, existing_story):
    events_str = '; '.join(events[:8]) if events else 'quiet seasons of governance'
    continuation_hint = (
        'Continue the saga naturally from where it left off.'
        if existing_story.strip()
        else 'Begin the saga of this dynasty.'
    )
    prev = existing_story[-800:] if existing_story else '(none yet)'
    return (
        f'You are the immortal chronicler of a great dynasty, writing their epic saga.\n'
        f'Dynasty: {dynasty_name}\n'
        f'Current ruler: {monarch_name}\n'
        f'Years {start_year} to {end_year} the following transpired: {events_str}\n\n'
        f'Previous chronicle:\n{prev}\n\n'
        f'{continuation_hint} Write exactly ONE paragraph (4-6 sentences) of vivid, '
        f'high-fantasy prose that weaves these events into the living legend of {dynasty_name}. '
        f'Use dramatic third-person narration. No bullet points, no headings, pure flowing prose only.'
    )
```

**Target signature:**
```python
def build_turn_story_prompt(dynasty_name, start_year, end_year, events, monarch_name, existing_story,
                             years_advanced: int = 5, interrupt_reason: str = 'quiet_period'):
```

**Insertion point for pacing line** — add immediately after the `events_str` and `continuation_hint` assignments, before the `return`:
```python
    year_span = f'{years_advanced} year{"s" if years_advanced != 1 else ""}'
    reason_human = interrupt_reason.replace('_', ' ')
    pacing_hint = f'This turn spanned {year_span}. It ended because: {reason_human}. '
    if interrupt_reason == 'monarch_death':
        pacing_hint += 'The shadow of the ruler\'s death defines this passage — write it accordingly. '
    elif interrupt_reason == 'quiet_period':
        pacing_hint += 'These were peaceful, uneventful seasons. '
```

Then add `pacing_hint` to the prompt body after `{continuation_hint}`:
```python
    f'{continuation_hint} {pacing_hint}Write exactly ONE paragraph ...'
```

### Current state of `generate_turn_story_fallback` (lines 148–160)

```python
def generate_turn_story_fallback(dynasty_name, start_year, end_year, events, monarch_name):
    if events:
        key_event = events[0]
        return (
            f'In the years {start_year} through {end_year}, the annals of {dynasty_name} record '
            f'the reign of {monarch_name}, under whose stewardship {key_event.lower()} '
            f'The scribes of the realm set down these deeds in ink and candlelight, '
            f'that the glory and the grief of this age might endure beyond the lives of those who lived it.'
        )
    return (
        f'The years {start_year} to {end_year} passed like quiet water beneath the banner of {dynasty_name}. '
        f'{monarch_name} ruled with measured hand, and the realm held its breath.'
    )
```

**Target signature:**
```python
def generate_turn_story_fallback(dynasty_name, start_year, end_year, events, monarch_name,
                                  years_advanced: int = 5, interrupt_reason: str = 'quiet_period'):
```

**New branch for `monarch_death`:**
```python
    year_word = 'year' if years_advanced == 1 else 'years'
    if interrupt_reason == 'monarch_death':
        key_event = events[0].lower() if events else 'the realm fell into mourning'
        return (
            f'In the {years_advanced} {year_word} before the passing of {monarch_name}, '
            f'{dynasty_name} was marked by {key_event} '
            f'When the end came, the realm fell silent, and the scribes set down their quills '
            f'to mourn before returning to record what followed.'
        )
```

**Existing branches become the default.** Update the quiet-period return to use `years_advanced` for a natural sentence: `f'The {years_advanced} {year_word} from {start_year} to {end_year} passed like quiet water...'`

### Call sites in `turn_processor.py`

**Site 1 — `build_turn_story_prompt` call (around line 204):**

Current:
```python
prompt = build_turn_story_prompt(
    dynasty_name=dynasty.name,
    start_year=start_year,
    end_year=dynasty.current_simulation_year - 1,
    events=event_texts,
    monarch_name=monarch_display,
    existing_story=existing_story,
)
```

Target:
```python
prompt = build_turn_story_prompt(
    dynasty_name=dynasty.name,
    start_year=start_year,
    end_year=dynasty.current_simulation_year - 1,
    events=event_texts,
    monarch_name=monarch_display,
    existing_story=existing_story,
    years_advanced=years_advanced,
    interrupt_reason=interrupt[0],
)
```

**Site 2 — `generate_turn_story_fallback` call (around line 220):**

Current:
```python
new_paragraph = generate_turn_story_fallback(
    dynasty.name, start_year, dynasty.current_simulation_year - 1, event_texts, monarch_display
)
```

Target:
```python
new_paragraph = generate_turn_story_fallback(
    dynasty.name, start_year, dynasty.current_simulation_year - 1, event_texts, monarch_display,
    years_advanced=years_advanced,
    interrupt_reason=interrupt[0],
)
```

Both variables (`years_advanced` and `interrupt`) are in scope at both call sites — confirmed by reading `turn_processor.py` lines 115–252.

### Why default parameter values

Both functions use `years_advanced: int = 5` and `interrupt_reason: str = 'quiet_period'` as defaults. This preserves backward compatibility with any test that calls these functions without the new parameters — no existing callers need updating except the two in `turn_processor.py`.

### Token budget note

`max_output_tokens: 300` in the LLM call violates the CLAUDE.md 150-token budget for chronicle narration. This is a pre-existing deferred issue (`deferred-work.md`, Sprint 9). **Do NOT change it in this story** — changing the token budget is Sprint 9 scope. This story only adds the two new parameters.

### `FLASK_APP_GOOGLE_API_KEY` config key note

The LLM call at `turn_processor.py:200` uses `current_app.config.get("FLASK_APP_GOOGLE_API_KEY")` which always returns `None` (the app only stores the bool flag). The env var fallback makes it work. This is a pre-existing deferred issue — **do NOT fix it in this story**.

### New test file: `tests/unit/test_llm_prompts.py`

No Flask app context needed — both functions are pure Python (no DB, no Flask). Tests import directly from `utils.llm_prompts`.

Minimal structure:
```python
# tests/unit/test_llm_prompts.py
import pytest
from utils.llm_prompts import build_turn_story_prompt, generate_turn_story_fallback


class TestBuildTurnStoryPrompt:
    def _call(self, **overrides):
        kwargs = dict(
            dynasty_name='Anjou',
            start_year=1300,
            end_year=1304,
            events=['A harvest festival was held'],
            monarch_name='Aldric I',
            existing_story='',
            years_advanced=5,
            interrupt_reason='quiet_period',
        )
        kwargs.update(overrides)
        return build_turn_story_prompt(**kwargs)

    def test_years_advanced_appears_in_prompt(self):
        result = self._call(years_advanced=3)
        assert '3' in result

    def test_interrupt_reason_appears_in_prompt(self):
        result = self._call(interrupt_reason='monarch_death')
        assert 'monarch' in result.lower() or 'death' in result.lower()

    def test_quiet_period_pacing_hint(self):
        result = self._call(interrupt_reason='quiet_period')
        assert 'peaceful' in result.lower() or 'uneventful' in result.lower() or 'quiet' in result.lower()


class TestGenerateTurnStoryFallback:
    def _call(self, **overrides):
        kwargs = dict(
            dynasty_name='Anjou',
            start_year=1300,
            end_year=1304,
            events=['Walls were completed at Riverlands'],
            monarch_name='Aldric I',
            years_advanced=5,
            interrupt_reason='quiet_period',
        )
        kwargs.update(overrides)
        return generate_turn_story_fallback(**kwargs)

    def test_monarch_death_differs_from_quiet_period(self):
        quiet = self._call(interrupt_reason='quiet_period')
        death = self._call(interrupt_reason='monarch_death')
        assert quiet != death

    def test_singular_year_grammar(self):
        result = self._call(years_advanced=1, interrupt_reason='quiet_period')
        assert 'years' not in result.lower().split('1')[0] or '1 year' in result.lower()

    def test_monarch_death_mentions_passing(self):
        result = self._call(interrupt_reason='monarch_death')
        assert 'passing' in result.lower() or 'mourning' in result.lower() or 'death' in result.lower()

    def test_returns_non_empty_for_no_events(self):
        result = self._call(events=[], interrupt_reason='quiet_period')
        assert len(result) > 20
```

### Branch name

`feature/chronicle-prompt-interrupt-pacing`

### Commit plan

- Commit 1: `feat(llm-prompts): add years_advanced + interrupt_reason to build_turn_story_prompt`
- Commit 2: `feat(llm-prompts): add years_advanced + interrupt_reason to generate_turn_story_fallback`
- Commit 3: `feat(turn-processor): pass years_advanced + interrupt_reason to chronicle prompt builders`
- Commit 4: `test(llm-prompts): add unit tests for updated chronicle prompt functions`

### Scope boundaries

- **In scope:** `utils/llm_prompts.py` (2 functions), `models/turn_processor.py` (2 call sites), `tests/unit/test_llm_prompts.py` (new)
- **Out of scope:** `max_output_tokens` budget (Sprint 9), `FLASK_APP_GOOGLE_API_KEY` fix (Sprint 11), any template changes, any DB changes
- **Out of scope:** Any other prompt builder functions — only `build_turn_story_prompt` and `generate_turn_story_fallback` change in this story

### References

- Prompt functions: `utils/llm_prompts.py` lines 128–160
- Call sites: `models/turn_processor.py` lines 204–222
- `interrupt[0]` values: `models/turn_processor.py` lines 40–49 (`INTERRUPT_REASONS` list)
- `years_advanced` variable: in scope at call sites — `models/turn_processor.py` lines 115, 152, 237
- Master plan LLM hook table: `review_documents/8_master_plan_2026.md` line 1031 — "Sprint 1: Chronicle prompt receives `years_advanced` + `interrupt_reason`"
- Previous story: `_bmad-output/implementation-artifacts/1-3-turn-report-interrupt-ui.md`
- Token budget rule: `_bmad-output/project-context.md` lines 45–52

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (bmad-dev-story workflow)

### Implementation Plan

Followed story-prescribed red-green-refactor cycle:

1. **RED:** Wrote 10 unit tests in `tests/unit/test_llm_prompts.py` covering both updated functions (5 tests per function). Confirmed all 10 fail with `TypeError: unexpected keyword argument 'years_advanced'`.
2. **GREEN:** Added `years_advanced` and `interrupt_reason` params to `build_turn_story_prompt` with `pacing_hint` derived from interrupt class; added matching params to `generate_turn_story_fallback` with new `monarch_death` branch and `years_advanced`-aware grammar.
3. **WIRE:** Updated both call sites in `models/turn_processor.py` to pass `years_advanced=years_advanced, interrupt_reason=interrupt[0]`.
4. **REGRESSION:** `pytest` → 222 passed, 0 failed, 0 skipped (project now has 222 tests; story baseline was 212).

### Completion Notes

- All 6 acceptance criteria satisfied; all 6 tasks (+ 14 subtasks) marked complete.
- New test file follows the exact structure prescribed in Dev Notes; minor expansions: added explicit singular-year-grammar test for `build_turn_story_prompt`, added empty-events test for the `monarch_death` branch (covers AC4 "any combination" requirement).
- Default param values (`years_advanced=5`, `interrupt_reason='quiet_period'`) preserve backward compatibility — no other callers in the repo besides the two in `turn_processor.py`.
- Out-of-scope items left untouched per story: `max_output_tokens=300` (Sprint 9), `FLASK_APP_GOOGLE_API_KEY` config key bug (Sprint 11).
- Pre-existing atexit logging errors visible at end of pytest output are unrelated (Sprint 11 deferred work).

### File List

- `utils/llm_prompts.py` — MODIFIED (both `build_turn_story_prompt` and `generate_turn_story_fallback` extended)
- `models/turn_processor.py` — MODIFIED (both call sites pass new params)
- `tests/unit/test_llm_prompts.py` — NEW (10 unit tests across 2 test classes)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED (status: backlog → in-progress → review; last_updated bumped)
- `_bmad-output/implementation-artifacts/1-4-chronicle-prompt-years-and-interrupt.md` — MODIFIED (status, tasks, Dev Agent Record, Change Log)

### Change Log

| Date | Change |
|---|---|
| 2026-05-13 | Story status: ready-for-dev → in-progress; sprint-status.yaml synced |
| 2026-05-13 | feat(llm-prompts): add `years_advanced` + `interrupt_reason` to `build_turn_story_prompt` |
| 2026-05-13 | feat(llm-prompts): add `years_advanced` + `interrupt_reason` to `generate_turn_story_fallback` with monarch_death branch |
| 2026-05-13 | feat(turn-processor): pass `years_advanced` + `interrupt[0]` at both chronicle call sites |
| 2026-05-13 | test(llm-prompts): add 10 unit tests across 2 test classes |
| 2026-05-13 | pytest: 222 passed, 0 failed, 0 skipped |
| 2026-05-13 | Story status → review |
