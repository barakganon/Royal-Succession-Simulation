# Story 2-4: Multi-Generation Chronicle Hook

Status: in-progress

## Story

As a player whose grandfather laid the foundation stone of a 15-year cathedral,
I want a chronicle entry when my current monarch finishes it,
so that "What Aldric I began, Eldred III finished — the Cathedral of the Saints stood at last" appears in my saga and rewards the multi-generational commitment the project system makes possible.

## Acceptance Criteria

1. **AC1 — `build_multigen_project_completion_prompt(...)` lives in `utils/llm_prompts.py`.** Takes `project_type: str`, `initiator_name: str`, `completer_name: str`, `dynasty_name: str`, `started_year: int`, `completion_year: int`. Returns a prompt string that asks for a single 2-3 sentence dramatic chronicle line in medieval-chronicler voice. Uses `max_tokens=100` budget (LLM token table in project-context.md: chronicle narration ≤150; this is one short line so 100 is the ceiling).

2. **AC2 — `generate_multigen_project_completion_fallback(...)` lives in `utils/llm_prompts.py`.** Same signature as the prompt builder. Returns the master-plan template line: `"What {initiator_name} began, {completer_name} finished — the {project_label} stands."` where `project_label` is a human-readable rendering of `project_type` (e.g. `'build_cathedral'` → `'Cathedral'`, `'build_walls'` → `'Walls'`, `'build_farm'` → `'Farm'`, `'develop_territory'` → `'territory development'`, `'recruit_infantry'` → `'levy'`, etc.). Unknown project types fall back to `project_type.replace('_', ' ')`.

3. **AC3 — `ProjectSystem.complete_project` writes a `HistoryLogEntryDB` row when monarchs differ.** AFTER the effect dispatcher runs (so the chronicle reflects the completed state) and BEFORE the final commit: if `project.initiated_by_monarch_id != project.completed_by_monarch_id` AND both are non-NULL, generate the chronicle line (LLM-with-fallback) and create a `HistoryLogEntryDB(dynasty_id=project.dynasty_id, year=completion_year, event_string=<line>, event_type='project_completed_multigen', person1_sim_id=initiator_id, person2_sim_id=completer_id)`. Single-monarch completions do NOT create this entry.

4. **AC4 — `completed_by_monarch_id` may be NULL** (interregnum case from Story 2-2 review). When NULL, skip the multi-gen chronicle entirely (no initiator/completer pair to compare). Log at DEBUG level so the absence is traceable.

5. **AC5 — LLM unavailable → fallback fires.** Full playability without `GOOGLE_API_KEY` is preserved. The LLM call uses the same `_llm_available()` guard pattern as `turn_processor.py`. If the LLM call raises or returns empty text, the fallback string is used instead.

6. **AC6 — Tests cover prompt builder + fallback + the two `complete_project` branches.** In `tests/unit/test_llm_prompts.py` (existing): add tests for the new prompt builder and fallback (singular/plural year handling, project_label rendering, both names appear). In `tests/unit/test_project_system.py` (existing): add `test_complete_multigen_writes_history_entry` AND `test_complete_same_monarch_no_multigen_entry` AND `test_complete_with_null_completer_skips_multigen`. **pytest must report 274+ passed, 0 failed, 0 skipped** (was 268; +6 expected).

## Tasks / Subtasks

- [ ] Task 1: Add the two prompt functions to `utils/llm_prompts.py` (AC1, AC2)
  - [ ] `build_multigen_project_completion_prompt(project_type, initiator_name, completer_name, dynasty_name, started_year, completion_year) -> str`
  - [ ] `generate_multigen_project_completion_fallback(project_type, initiator_name, completer_name, dynasty_name, started_year, completion_year) -> str` — uses a module-level `_PROJECT_LABELS` dict to map project_type → human label.

- [ ] Task 2: Add `_chronicle_multigen_completion(session, project)` helper inside `models/project_system.py` (AC3, AC4, AC5)
  - [ ] Resolve initiator and completer `PersonDB` rows.
  - [ ] If either is None, log at DEBUG and return (AC4).
  - [ ] If `initiator.id == completer.id`, return (AC3 negative branch).
  - [ ] Try LLM via the same `_llm_available()` guard as `turn_processor.py` — copy the helper inline at module level. On any failure, use the fallback.
  - [ ] Build the `HistoryLogEntryDB` row and add to session. Caller (`complete_project`) commits once at the end.

- [ ] Task 3: Call `_chronicle_multigen_completion` from `complete_project` (AC3)
  - [ ] Invoke AFTER `effect_fn(self.session, project)` returns successfully, BEFORE the final `self.session.commit()`.

- [ ] Task 4: Unit tests for `utils/llm_prompts.py` (AC6)
  - [ ] `test_multigen_prompt_includes_both_names`
  - [ ] `test_multigen_fallback_template_matches_master_plan`
  - [ ] `test_multigen_fallback_project_label_for_known_types` (cathedral, walls, farm, develop_territory, recruit_infantry)
  - [ ] `test_multigen_fallback_project_label_for_unknown_type` — uses `replace('_', ' ')`

- [ ] Task 5: Unit tests for `models/project_system.py` (AC6)
  - [ ] `test_complete_multigen_writes_history_entry` — start project with initiator A, replace monarch with B (manually), complete; assert one `HistoryLogEntryDB` row with `event_type='project_completed_multigen'`, `person1_sim_id=A.id`, `person2_sim_id=B.id`.
  - [ ] `test_complete_same_monarch_no_multigen_entry` — start + complete with the same monarch; assert zero `HistoryLogEntryDB` rows with `event_type='project_completed_multigen'`.
  - [ ] `test_complete_with_null_completer_skips_multigen` — kill the monarch before completion so no living monarch exists; assert no multi-gen entry, no exception.

- [ ] Task 6: Run `pytest`, confirm 274+ passed, 0 failed, 0 skipped (AC6, AC7)

- [ ] Task 7: Commit, push, merge.

## Dev Notes

### Files to change

| File | Change type | Description |
|---|---|---|
| `utils/llm_prompts.py` | UPDATE | Add 2 functions (~30 LoC); module-level `_PROJECT_LABELS` dict |
| `models/project_system.py` | UPDATE | Add `_llm_available()` helper + `_chronicle_multigen_completion()` helper; call from `complete_project` |
| `tests/unit/test_llm_prompts.py` | UPDATE | 4 new tests |
| `tests/unit/test_project_system.py` | UPDATE | 3 new tests |

### Why the entry goes through `HistoryLogEntryDB` not `ChronicleEntryDB`

`HistoryLogEntryDB` is the per-event log that powers `turn_summary['events']` (the per-year breakdown shown in turn_report.html and Story 1-4's `build_turn_story_prompt` event input). It's the right home for individual milestone events that should flow into the next turn's narrative paragraph. `ChronicleEntryDB` (Sprint 9-era cumulative chronicle) is for the longer-form saga text and is appended to by `turn_processor.py`'s epic-story generation — not the right hook point.

A future Sprint 12 (Chronicle Compiler) may dual-write to both. For Story 2-4, single-write to `HistoryLogEntryDB` matches existing event semantics.

### Why the helper is private + module-level

Same pattern as `_effect_*` in `project_system.py` — internal-only helper, not exposed via `ProjectSystem` public API. `complete_project` calls it directly.

### `_llm_available()` duplication is fine for now

`turn_processor.py` defines `_llm_available()` at module level. Story 2-4 will define an identical helper in `project_system.py` rather than importing it (avoids a circular import: project_system already imported by turn_processor). Sprint 11 cleanup can consolidate both into a shared `utils/llm_guard.py`.

### LLM call inline pattern (mirrors `turn_processor.py:185-216`)

```python
def _llm_available() -> bool:
    try:
        from flask import current_app
        return current_app.config.get('FLASK_APP_GOOGLE_API_KEY_PRESENT', False)
    except Exception:
        return False


# inside _chronicle_multigen_completion:
text = ""
if _llm_available():
    try:
        import google.generativeai as genai
        from flask import current_app
        import os
        api_key = current_app.config.get("FLASK_APP_GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = build_multigen_project_completion_prompt(...)
            response = model.generate_content(prompt, generation_config={"max_output_tokens": 100, "temperature": 0.8})
            text = response.text.strip() if response.text else ""
    except Exception:
        text = ""
if not text:
    text = generate_multigen_project_completion_fallback(...)
```

### Project label rendering

Initial mapping:
```python
_PROJECT_LABELS = {
    'build_farm': 'Farm',
    'build_walls': 'Walls',
    'build_cathedral': 'Cathedral',
    'develop_territory': 'territory development',
    'recruit_infantry': 'levy',
    'recruit_cavalry': 'cavalry',
    'envoy_mission': 'envoy mission',
    'march_army_cross_realm': 'cross-realm march',
}
```

Unknown project_types fall back to `project_type.replace('_', ' ')`. This is forward-compatible: as the catalogue grows, only the labels need updating.

### Why we don't commit inside the helper

The helper only `session.add()`s the row. `complete_project` already has a commit + rollback wrapper around the effect call. Single commit point keeps the project state and the chronicle entry atomic — either both land or neither does.

### Token budget compliance

Project-context.md / CLAUDE.md mandates ≤150 tokens for chronicle narration. Story 2-4 sets `max_output_tokens=100` because the line is a single sentence (or two short sentences) — leaves headroom under the 150 ceiling.

### What this story does NOT touch

- `models/db_models.py` — no schema changes. `HistoryLogEntryDB` already has `event_string`, `event_type`, `person1_sim_id`, `person2_sim_id` — all the fields we need.
- `ChronicleEntryDB` — out of scope (per "Why HistoryLogEntryDB not ChronicleEntryDB" above).
- `models/turn_processor.py` — no changes; the multigen hook fires inside `complete_project`, which is already called from the turn loop.
- UI / templates — Sprint 3 (Epic 3) can surface the entry; for Story 2-4 it's just data in the DB.

### Snake-pit: `_chronicle_multigen_completion` is called even when `complete_project` is invoked directly (outside the turn loop)

Story 2-2 tests call `ps.complete_project(project.id)` directly. After Story 2-4, those tests will also fire the multigen hook — which means tests for completed-by/initiator semantics need to be aware of the new HistoryLogEntryDB rows in their DB. If a 2-2 test asserts on a row count, it may now see +1. Quick scan of `tests/unit/test_project_system.py` shows no such assertions, but verify when implementing.

### Branch name

`feature/multigen-chronicle-hook` (already created).

### Commit plan

- Commit 1: `feat(llm-prompts): add multigen project completion prompt + fallback`
- Commit 2: `feat(project-system): emit multigen chronicle entry when monarchs differ`
- Commit 3: `test: multigen chronicle hook for cross-monarch project completion`

### References

- Master plan: `review_documents/8_master_plan_2026.md` lines 220-228 (Sprint 2 tasks + AC #3 "shows both names in the completion chronicle entry")
- `HistoryLogEntryDB` schema: `models/db_models.py:268-316`
- Existing prompt+fallback pattern: `utils/llm_prompts.py:47-67` (chronicle), `utils/llm_prompts.py:128-180` (turn story)
- `_llm_available()` pattern: `models/turn_processor.py:56-66`
- LLM call inline pattern: `models/turn_processor.py:185-216` (epic story generation)
- ProjectSystem.complete_project: `models/project_system.py` (Story 2-2)

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
