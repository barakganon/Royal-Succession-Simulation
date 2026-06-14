# Story 12-2: Foreword & Epilogue Prompts

Status: ready-for-dev

## Story
As a **player compiling my dynasty's Chronicle into a book**,
I want **an LLM-written foreword and epilogue (with deterministic fallbacks when the LLM is off)**,
so that **the compiled book opens with a framing introduction and closes with a reflective ending — and still reads well with no API key.**

## Context
Story 12-1 produced `ChronicleBook` with `foreword=""` / `epilogue=""` placeholders. This story adds the prompt builders + fallbacks to `utils/llm_prompts.py` only (pure string functions; no LLM call, no DB, no ORM objects). The actual LLM invocation + setting `book.foreword`/`book.epilogue` happens in Story 12-3's route (with the standard `if model is None: use fallback` guard). Follow the existing `build_<name>_prompt` / `generate_<name>_fallback` conventions already in the file (see `build_turn_story_prompt`/`generate_turn_story_fallback`, `build_coronation_prompt`/`generate_coronation_fallback`).

## Acceptance Criteria

1. **AC1 — `build_foreword_prompt`.** Add to `utils/llm_prompts.py`:
   `build_foreword_prompt(dynasty_name: str, founding_year: int, first_paragraphs: list[str], first_monarch_name: str = "") -> str`.
   Returns a prompt instructing the model to write a short framing **foreword** (in the voice of a medieval chronicler/archivist) introducing the saga, using the opening paragraphs as context. Docstring must state **max_tokens<=200** and style (third-person, 2-4 sentences, sets the stage, does not spoil the ending). Primitives only — never an ORM object.

2. **AC2 — `generate_foreword_fallback`.** `generate_foreword_fallback(dynasty_name: str, founding_year: int, first_monarch_name: str = "") -> str` — deterministic prose (no LLM), e.g. a 2-3 sentence foreword naming the house and founding year. Must be non-empty and readable with zero LLM access.

3. **AC3 — `build_epilogue_prompt`.** `build_epilogue_prompt(dynasty_name: str, current_year: int, last_paragraphs: list[str], current_state: dict | None = None) -> str`. Returns a prompt for a reflective **epilogue** closing the chronicle, using the most recent paragraphs (and optional `current_state` summary — e.g. {'prestige':..,'territories':..,'is_extinct':..}) as context. Docstring: **max_tokens<=200**, style (third-person, 2-4 sentences, reflective, reflects where the dynasty stands now). Primitives only.

4. **AC4 — `generate_epilogue_fallback`.** `generate_epilogue_fallback(dynasty_name: str, current_year: int, current_state: dict | None = None) -> str` — deterministic closing prose naming the house and current year; if `current_state` indicates extinction, phrase it as an ending; otherwise as an ongoing legacy. Non-empty, LLM-free.

5. **AC5 — Robustness.** All four functions handle empty `first_paragraphs`/`last_paragraphs` lists and `current_state=None` without error (a brand-new or eventless dynasty still gets a sensible foreword/epilogue). Builders truncate/cap the paragraph context they embed (e.g. first 3 / last 5 paragraphs, and don't dump huge text) to respect the token budget.

6. **AC6 — Tests.** Add `tests/unit/test_chronicle_prompts.py` (or extend an existing llm_prompts test file if one exists): assert each builder returns a non-empty `str` containing the dynasty name; assert each fallback returns non-empty readable prose for (a) normal input, (b) empty paragraph list, (c) `current_state=None`, and (d) extinct-dynasty state for the epilogue fallback. No LLM, no HTTP.

7. **AC7 — No regressions.** Full suite green (baseline **547 passed**, 0 failed, 0 skipped) + new tests. `python -c "import main_flask_app"` clean. No new deps, no schema change.

## Tasks
- [ ] Task 1 — `build_foreword_prompt` + `generate_foreword_fallback` (AC1, AC2).
- [ ] Task 2 — `build_epilogue_prompt` + `generate_epilogue_fallback` (AC3, AC4).
- [ ] Task 3 — empty/None robustness + paragraph-context capping (AC5).
- [ ] Task 4 — unit tests (AC6).
- [ ] Task 5 — pytest 547+new green; import clean (AC7).

## Dev Notes
- **Prompt strings live ONLY in `utils/llm_prompts.py`** (project rule) — do not inline elsewhere. Co-locate the fallbacks in the same file, matching the existing naming (`build_<name>_prompt` / `generate_<name>_fallback`).
- **No LLM call in this story.** These are pure string functions. The caller (Story 12-3 route) will do `model = _get_llm(); foreword = (model.generate_content(build_foreword_prompt(...)).text if model else generate_foreword_fallback(...))`. Mirror the guard pattern in `models/turn_processor.py:402-421`.
- Token budget table (CLAUDE.md): keep both prompts within a ~200-token response; say so in the docstring. Style: medieval chronicler, third-person.
- Primitives only (no ORM objects passed in) — consistent with every other builder in the file.
- This is a self-contained pure-Python story → **single Sonnet subagent on live `main` (no worktree)** per Epic 11 retro policy.

## References
- `utils/llm_prompts.py` — existing `build_turn_story_prompt`/`generate_turn_story_fallback` (:140/:176), `build_coronation_prompt`/`generate_coronation_fallback` (:465/:483) as the closest templates.
- LLM-guard call site pattern: `models/turn_processor.py:402-421`.
- `ChronicleBook.foreword/epilogue` fields (Story 12-1, `models/chronicle_compiler.py`).
- Design: `_bmad-output/implementation-artifacts/epic-12-design.md`.

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-14 | spec(12-2); foreword/epilogue prompts + deterministic fallbacks (ready-for-dev) |
