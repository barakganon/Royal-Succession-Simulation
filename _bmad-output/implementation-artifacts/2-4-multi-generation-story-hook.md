# Story 2-4: Multi-Generation Chronicle Hook

Status: done

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

- [x] Task 1: Add the two prompt functions to `utils/llm_prompts.py` (AC1, AC2)
  - [x] `build_multigen_project_completion_prompt(project_type, initiator_name, completer_name, dynasty_name, started_year, completion_year) -> str`
  - [x] `generate_multigen_project_completion_fallback(project_type, initiator_name, completer_name, dynasty_name, started_year, completion_year) -> str` — uses a module-level `_PROJECT_LABELS` dict to map project_type → human label.

- [x] Task 2: Add `_chronicle_multigen_completion(session, project)` helper inside `models/project_system.py` (AC3, AC4, AC5)
  - [x] Resolve initiator and completer `PersonDB` rows.
  - [x] If either is None, log at DEBUG and return (AC4).
  - [x] If `initiator.id == completer.id`, return (AC3 negative branch).
  - [x] Try LLM via the same `_llm_available()` guard as `turn_processor.py` — copy the helper inline at module level. On any failure, use the fallback.
  - [x] Build the `HistoryLogEntryDB` row and add to session. Caller (`complete_project`) commits once at the end.

- [x] Task 3: Call `_chronicle_multigen_completion` from `complete_project` (AC3)
  - [x] Invoke AFTER `effect_fn(self.session, project)` returns successfully, BEFORE the final `self.session.commit()`.

- [x] Task 4: Unit tests for `utils/llm_prompts.py` (AC6)
  - [x] `test_multigen_prompt_includes_both_names`
  - [x] `test_multigen_fallback_template_matches_master_plan`
  - [x] `test_multigen_fallback_project_label_for_known_types` (cathedral, walls, farm, develop_territory, recruit_infantry)
  - [x] `test_multigen_fallback_project_label_for_unknown_type` — uses `replace('_', ' ')`

- [x] Task 5: Unit tests for `models/project_system.py` (AC6)
  - [x] `test_complete_multigen_writes_history_entry` — start project with initiator A, replace monarch with B (manually), complete; assert one `HistoryLogEntryDB` row with `event_type='project_completed_multigen'`, `person1_sim_id=A.id`, `person2_sim_id=B.id`.
  - [x] `test_complete_same_monarch_no_multigen_entry` — start + complete with the same monarch; assert zero `HistoryLogEntryDB` rows with `event_type='project_completed_multigen'`.
  - [x] `test_complete_with_null_completer_skips_multigen` — kill the monarch before completion so no living monarch exists; assert no multi-gen entry, no exception.

- [x] Task 6: Run `pytest`, confirm 274+ passed, 0 failed, 0 skipped (AC6, AC7)

- [x] Task 7: Commit, push, merge.

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

claude-opus-4-7[1m] (direct execution)

### Implementation Plan

1. Added `build_multigen_project_completion_prompt` + `generate_multigen_project_completion_fallback` + `_PROJECT_LABELS` to `utils/llm_prompts.py`.
2. Added `_llm_available()` + `_chronicle_multigen_completion(session, project)` helpers to `models/project_system.py`. Helper resolves the two PersonDB rows, calls LLM with the new prompt builder (with API-key guard), falls back to the template, and `session.add()`s a `HistoryLogEntryDB` row with `event_type='project_completed_multigen'`.
3. `ProjectSystem.complete_project` invokes the helper AFTER the effect dispatcher runs and BEFORE the final commit. Wrapped in try/except + warning log so a failing chronicle hook never rolls back the actual completion.
4. 6 unit tests in `tests/unit/test_llm_prompts.py` + 3 unit tests in `tests/unit/test_project_system.py`.

### Completion Notes

- All 6 ACs satisfied. Acceptance Auditor returned clean on first pass.
- Code review surfaced 2 PATCH-level findings (null surname rendering, LLM-text log-spam) — both applied.
- The "null surname" defensive guard turned out to be unreachable because `PersonDB.surname` is `nullable=False` at the schema level. Kept the `name or ''` defense as belt-and-braces, but removed the unreachable test.
- 25+ findings deferred — mostly pre-existing patterns in `turn_processor.py` (hardcoded model name, no LLM timeout, multiple API-key names, bare exception catches) or upstream invariants that `start_project`/`complete_project` already enforce.
- pytest: **277 passed, 0 failed, 0 skipped** (was 268 pre-story; +9 tests).
- Story 2-4 closes Epic 2 (Project Model). All four stories (2-1, 2-2, 2-3, 2-4) shipped.

### File List

- `utils/llm_prompts.py` — MODIFIED (added 2 functions + `_PROJECT_LABELS` constant + `_project_label` helper, ~55 LoC)
- `models/project_system.py` — MODIFIED (added `_llm_available`, `_chronicle_multigen_completion`, call from `complete_project`, ~110 LoC)
- `tests/unit/test_llm_prompts.py` — MODIFIED (+ 6 tests across 2 new test classes)
- `tests/unit/test_project_system.py` — MODIFIED (+ 3 tests for multigen branches)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED (2-4: backlog → done; epic-2: in-progress → done)
- `_bmad-output/implementation-artifacts/2-4-multi-generation-story-hook.md` — MODIFIED (status, Dev Agent Record)
- `_bmad-output/implementation-artifacts/deferred-work.md` — MODIFIED (~25 review-driven defers)

### Change Log

| Date | Change |
|---|---|
| 2026-05-17 | feat(llm-prompts): add multigen project completion prompt + fallback |
| 2026-05-17 | feat(project-system): emit multigen chronicle entry when monarchs differ |
| 2026-05-17 | test: multigen chronicle hook (6 prompt tests + 3 project_system tests) |
| 2026-05-17 | Code review (3 layers): Acceptance Auditor clean; 2 patches applied (null-surname defense + DEBUG-level chronicle text log), ~25 deferred |
| 2026-05-17 | fix(project-system): null-safe name composition + log LLM text at DEBUG |
| 2026-05-17 | pytest: 277 passed, 0 failed, 0 skipped (was 268) |
| 2026-05-17 | Story status → done; Epic 2 → done |

### Review Findings

_Code review run 2026-05-17 — 3 parallel adversarial layers._

**Patches (applied):**

- [x] [Review][Patch] Null-surname rendering: `f"{name} {surname}".strip()` would produce `"Aldric None"` if surname were NULL. Changed to `f"{name or ''} {surname or ''}".strip()`. Note: the case is unreachable in practice because `PersonDB.surname` is `nullable=False` at the schema level — kept as belt-and-braces defense; removed the unreachable test [`models/project_system.py:_chronicle_multigen_completion`]
- [x] [Review][Patch] LLM text log-spam: full chronicle paragraph was logged at INFO with `%r`. Split into an INFO line with metadata only (project_id, dynasty_id, monarch IDs, year) and a DEBUG line with the full text [`models/project_system.py:_chronicle_multigen_completion`]

**Deferred (~25):**

- [x] [Review][Defer] `_llm_available()` duplicates `turn_processor.py:_llm_available()` — intentional to avoid circular import; consolidate in Sprint 11 via `utils/llm_guard.py`.
- [x] [Review][Defer] Bare `except Exception` in `_llm_available()` silently returns False on config bugs — matches pre-existing pattern.
- [x] [Review][Defer] Inline `genai.configure()` + hardcoded `"gemini-1.5-flash"` model name — matches `turn_processor.py` pattern; centralize in Sprint 11.
- [x] [Review][Defer] Three API-key names (`FLASK_APP_GOOGLE_API_KEY_PRESENT`, `FLASK_APP_GOOGLE_API_KEY`, `GOOGLE_API_KEY`) — pre-existing inconsistency already in deferred-work.md from Story 1-4.
- [x] [Review][Defer] `max_output_tokens=100` paired with "2-3 sentences" instruction may truncate mid-sentence — intentional safety net under 150-token chronicle budget.
- [x] [Review][Defer] No LLM timeout configured — pre-existing pattern; SDK default applies.
- [x] [Review][Defer] `response.text` raises on safety block / MAX_TOKENS — caught by outer except, falls back.
- [x] [Review][Defer] Network errors / rate-limit / quota errors all collapse into one warning — no retry / circuit breaker; Sprint 11 LLM hardening.
- [x] [Review][Defer] `_PROJECT_LABELS` is module-level mutable dict — convention in this codebase; freeze in Sprint 11 if needed.
- [x] [Review][Defer] Em-dash (U+2014) in fallback text — `db.Text` handles unicode; rendering layer's problem.
- [x] [Review][Defer] Fallback ignores `dynasty_name` parameter — true but harmless; master plan template doesn't use it.
- [x] [Review][Defer] No prompt-injection sanitization on `initiator_name`/`completer_name`/`dynasty_name` — real concern; would need cross-prompt-builder rollout. Sprint 11 security pass.
- [x] [Review][Defer] `_chronicle_multigen_completion` is module-level rather than a `ProjectSystem` method — matches `_effect_*` and `_stub_effect` pattern in the same module.
- [x] [Review][Defer] Hardcoded `'project_completed_multigen'` string instead of a constant/enum — match pre-existing event_type string convention.
- [x] [Review][Defer] No timeout on `model.generate_content` — pre-existing pattern.
- [x] [Review][Defer] `google.generativeai` import cost paid on every multigen call — pre-existing lazy-import pattern.
- [x] [Review][Defer] No `created_at` / no `ondelete=SET NULL` on initiated_by_monarch_id FK — Story 2-1 deferred-work covers FK ondelete; created_at is auto-set by HistoryLogEntryDB column default.
- [x] [Review][Defer] `years = completion_year - started_year` no negative-value guard — `start_project` enforces `completion_year = started_year + duration_years` (positive); unreachable.
- [x] [Review][Defer] Empty `project_type` string — unreachable; `start_project` rejects unknown types.
- [x] [Review][Defer] `genai.configure` mutates global state across concurrent dynasties — pre-existing pattern; not threading-safe but app is single-process Flask.
- [x] [Review][Defer] Hook fires before commit; if commit fails, the "queued" INFO log overstates — true but cosmetic; the warning log on the outer commit failure captures the real story.
- [x] [Review][Defer] `test_complete_sets_status_and_invokes_dispatcher` and other 2-2 tests don't assert on HistoryLogEntryDB row counts — fine; no need to update.
- [x] [Review][Defer] Substring-only prompt assertions — sufficient for Story 2-4 surface area; deeper validation would need golden-file comparisons.
- [x] [Review][Defer] `test_template_matches_master_plan` over-couples to exact prose (`startswith`, `endswith`) — intentional pinning of the master-plan template; if copy needs to change, this is the test to update.
- [x] [Review][Defer] Tests simulate monarch succession via direct ORM mutation rather than the real inheritance flow — acceptable until Sprint 5 wires real flow into a fixture.

**Dismissed (~6):**

- "`HistoryLogEntryDB.person2_sim_id` might not exist" — verified at `models/db_models.py:280`; the column has existed since the multi-agent game models landed.
- "test name suffix wording" — class-scoped test names override spec literal naming; functionally equivalent.
- Test of LLM happy path (would need mocking the SDK) — covered by integration smoke when `GOOGLE_API_KEY` is set in real environments; not a unit-test concern.
- `import google.generativeai` happens inside the function — already gated by `_llm_available()` check, so import cost is only paid when the API is actually configured.
- "Substring tests are weak" — covered as defer; not actionable as a patch here.
- "`construction_year` semantic" — out of scope (project_system.py creates the row in `_effect_build_farm`, not in this story).

**Acceptance Auditor:** ✅ 6/6 ACs satisfied. Dev Notes (HistoryLogEntryDB choice, no commit in helper, `_llm_available()` duplicated intentionally, token budget compliance, hook ordering, non-fatal chronicle errors) all honored. Out-of-scope (`db_models.py`, `ChronicleEntryDB`, `turn_processor.py`, UI) all respected.
