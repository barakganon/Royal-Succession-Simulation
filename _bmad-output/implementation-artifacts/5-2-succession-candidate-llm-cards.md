# Story 5-2: LLM Succession Candidate Cards + Coronation Chronicle

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player choosing the next monarch,
I want each candidate in the succession modal to carry a short narrated character sketch (LLM-flavored, with a deterministic trait-based fallback), and the act of crowning to write a coronation line into the chronicle,
so that the succession choice feels like weighing real people, and the dynasty's saga records who took the throne and why.

Builds on Story 5-1 (`succession_candidates_json` + `succession_choice` + the modal). LLM-off must stay fully functional (deterministic fallback).

## Acceptance Criteria

1. **AC1 — Flavor + coronation prompt builders (`utils/llm_prompts.py`).**
   - `build_succession_card_prompt(candidate_name, candidate_traits, relation, age, monarch_name, dynasty_name, recent_events) -> str` — medieval-chronicler character sketch, **exactly 3 sentences**, third-person; max_tokens ≤ 120.
   - `generate_succession_card_fallback(candidate_name, candidate_traits, relation, age) -> str` — deterministic, non-empty trait-based sketch (e.g. "{name}, {age}-year-old {relation} of the late ruler, is known for being {traits}. …"). Used when LLM is unavailable.
   - `build_coronation_prompt(heir_name, dynasty_name, year, heir_traits) -> str` — coronation chronicle line, 1–2 sentences, max_tokens ≤ 150.
   - `generate_coronation_fallback(heir_name, dynasty_name, year) -> str` — deterministic (e.g. "In {year}, {heir} was crowned to lead House {dynasty}.").

2. **AC2 — Candidates carry `flavor` (`blueprints/dynasty.py` `succession_candidates_json`).** Each serialized candidate gains a `"flavor": <str>` field. Generate it via a guarded LLM call (mirror `models/free_action_system.py:184-220` `_build_flavor`: `_llm_available()` → inline `genai` `gemini-1.5-flash` `generate_content(..., max_output_tokens<=120, temperature~0.8)`, ANY error → fallback) using `build_succession_card_prompt`; otherwise `generate_succession_card_fallback`. `recent_events` = the dynasty's last ~5 `HistoryLogEntryDB.event_string` (most recent). Add a module-level helper (e.g. `_succession_llm_flavor(prompt, fallback) -> str`) in the blueprint for the guarded call. **In tests LLM is off → fallback; flavor is always non-empty.** No new dependency.

3. **AC3 — Coronation chronicle entry (`succession_choice`).** After `crown_heir(...)` succeeds and before/with the commit, append ONE `HistoryLogEntryDB(dynasty_id=dynasty_id, year=deceased.death_year, event_string=<coronation flavor>, event_type='coronation', person1_sim_id=heir.id)`. The text is LLM-flavored via `build_coronation_prompt` (guarded) else `generate_coronation_fallback`. This is distinct from (and in addition to) the `succession_end` log that `crown_heir` already writes in 5-1. Commit once; keep the existing try/except + rollback.

4. **AC4 — Modal shows the flavor (`templates/world_map.html`).** The Story-5-1 succession modal candidate card now renders `candidate.flavor` as a short descriptive line (a `.succession-candidate-flavor` element) between the meta line and the traits/crown button. Style it in `static/style.css` (muted, italic, readable). All other 5-1 modal behavior (default badge, crown button, End-Turn block) stays intact.

5. **AC5 — No regressions.** Full suite green (baseline **342**; new tests additive). 5-1's succession tests still pass — the candidate shape only GAINS `flavor`; `succession_choice` still returns `{ok, message}` and crowns/unsets as before, now ALSO writing a `coronation` entry.

6. **AC6 — ≥5 new integration tests** (`tests/integration/test_succession_flavor.py`, fixture pattern from `test_detail_panel_render.py`; LLM off in tests → fallback path):
   - Every candidate in `succession_candidates.json` has a non-empty `flavor` string (deterministic fallback), and the fallback references the candidate's traits/relation.
   - `flavor` is present for all candidates (count matches `candidates`).
   - After `succession_choice` crowns an heir, a `HistoryLogEntryDB` with `event_type='coronation'` exists for the dynasty (in addition to the `succession_end` from 5-1).
   - `succession_choice` still returns `{ok:true}` and crowns the heir / unsets the deceased (5-1 behavior preserved).
   - `/world/map` HTML contains the flavor marker (`succession-candidate-flavor`) so the modal renders it.

7. **AC7 — Visual verification (retro lesson).** UI surface → run the app: craft a pending succession, open the modal, confirm each candidate card shows its narrated flavor line; crown one and confirm a coronation line lands in the chronicle feed.

## Tasks / Subtasks
- [ ] Task 1 — Backend: prompt builders + candidate `flavor` + coronation entry (`utils/llm_prompts.py`, `blueprints/dynasty.py`). [Agent A]
- [ ] Task 2 — Frontend: render `flavor` on candidate cards (`templates/world_map.html`, `static/style.css`). [Agent B]
- [ ] Task 3 — Tests (`tests/integration/test_succession_flavor.py`). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A (backend)** — `utils/llm_prompts.py` + `blueprints/dynasty.py` (candidate `flavor` in `succession_candidates_json`; coronation entry in `succession_choice`; guarded-LLM helper).
- **Agent B (frontend)** — `templates/world_map.html` + `static/style.css` (render `candidate.flavor`).
- **Agent C (tests)** — ONLY `tests/integration/test_succession_flavor.py`. Contract-first: fails in isolation, green on integration.
- No shared files. (A owns dynasty.py + llm_prompts; B owns world_map + css; C the new test.)

### FROZEN INTERFACE CONTRACT
- llm_prompts: `build_succession_card_prompt(candidate_name, candidate_traits, relation, age, monarch_name, dynasty_name, recent_events)` + `generate_succession_card_fallback(candidate_name, candidate_traits, relation, age)`; `build_coronation_prompt(heir_name, dynasty_name, year, heir_traits)` + `generate_coronation_fallback(heir_name, dynasty_name, year)`.
- `succession_candidates_json`: each candidate dict gains `"flavor": <non-empty str>`.
- `succession_choice`: on success appends `HistoryLogEntryDB(..., event_type='coronation', person1_sim_id=heir.id)` (in addition to 5-1's `succession_end`).
- Frontend: candidate card renders `candidate.flavor` inside a `.succession-candidate-flavor` element.

### Insertion points (exact, from 5-1 code)
- `succession_candidates_json` serialization loop: `blueprints/dynasty.py:1118-1136` (add `"flavor"` to the per-candidate dict).
- `succession_choice` after `crown_heir`: `blueprints/dynasty.py:1183-1191` (append coronation entry before the final commit/return).
- Guarded-LLM pattern to mirror: `models/free_action_system.py:184-220` (`_build_flavor`), `_llm_available()` at `:50`. Token budgets per CLAUDE.md (chronicle 150).
- 5-1 endpoints/modal: `succession_candidates_json` `:1090`, `succession_choice` `:1150`, modal `.succession-candidate-card` in `templates/world_map.html`.

### Reuse / project rules
- All prompt strings in `utils/llm_prompts.py` (never inline). LLM calls guarded (`if not _llm_available(): fallback`); every path works LLM-off. DB writes guarded; route owns commit/rollback. `recent_events` via `HistoryLogEntryDB.query.filter_by(dynasty_id=...).order_by(year.desc(), id.desc()).limit(5)`. Serialize before jsonify. No new deps.
- Don't change the candidate/`{ok,message}` shapes beyond ADDING `flavor` / the coronation entry (5-1 tests depend on the rest).

### Out of scope / deferred
- Pretender mechanics → Story 5-3. Civil war / heir-majority → 5-4. 5-2 is: per-candidate flavor + coronation chronicle line only. (The shared duplicated guarded-LLM helper across modules remains a Sprint 11 consolidation item.)

## Previous Story Intelligence
- Worktree contract-first flow (Epics 3–5 → zero conflicts). **Run this one via the Workflow tool** (user opted in) for the parallel fan-out; integrate (merge onto a feature branch → main, run pytest, visual check) in the main session. **Agents default to plan mode** → "EXECUTE NOW, pre-approved, no EnterPlanMode" in each prompt; worktrees branch off `main`; contract inlined.
- `pytest` runs against an isolated temp DB rebuilt per run. Baseline 342.
- 5-1 delivered `succession_candidates_json`/`succession_choice`/`crown_heir` + the modal; 4-2 established the guarded-LLM flavor + fallback pattern in `free_action_system`/`llm_prompts`.
- **UI surface → run-the-app check before done (AC7).** Known: `test_military_routes` ordering flake (unrelated); portrait fallback glyph for trait-less persons.

## References
- `succession_candidates_json` / `succession_choice`: `blueprints/dynasty.py:1090`, `:1150` (insertion points `:1118-1136`, `:1183-1191`).
- Guarded-LLM flavor pattern: `models/free_action_system.py:184-220`, `_llm_available()` `:50`.
- Free-action flavor prompt+fallback (shape to mirror): `utils/llm_prompts.py:279-298`.
- 5-1 modal `.succession-candidate-card`: `templates/world_map.html`.
- Test fixture: `tests/integration/test_detail_panel_render.py:13-39`; succession fixtures: `tests/integration/test_succession.py`.

## Dev Agent Record

### Agent Model Used

(to be filled by dev/integration)

### Debug Log References

### Completion Notes List

### File List
