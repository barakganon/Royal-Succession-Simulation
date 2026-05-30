# Story 7-2: AI Marriage Acceptance + Wedding Chronicle

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

When a cross-dynasty match (Story 7-1) targets an AI-controlled house, that house should DECIDE whether to accept (by relations, prestige, piety, traits); an accepted union bumps relations and pulls toward alliance, and writes an LLM-narrated wedding line into the chronicle. **Backend-only** — tests are the verification.

## Acceptance Criteria

1. **AC1 — `AIController.decide_marriage_response` (`models/ai_controller.py`).** New method `decide_marriage_response(self, context: dict) -> bool` (mirror the existing `decide_*` rule-based + optional-LLM pattern). Deterministic rule baseline (LLM optional, must fall back cleanly): accept when the existing relation score with the proposing dynasty is not hostile (e.g. `relations >= -20`) AND the match is not strongly unfavorable; lean toward acceptance when relations are high or the proposer's prestige ≥ own. `context` carries at least: `proposer_dynasty_id`, `relation_score`, `proposer_prestige`, `own_prestige` (religion/piety + traits may factor in but keep the core rule simple and testable). Returns `True` (accept) / `False` (reject). Never raises; LLM-off → rule path.

2. **AC2 — `build_wedding_chronicle_prompt` + fallback (`utils/llm_prompts.py`).** `build_wedding_chronicle_prompt(spouse1_name, spouse1_traits, spouse2_name, spouse2_traits, house1, house2, year) -> str` (medieval wedding announcement, ≤150 tokens, names both spouses + houses, references traits) and `generate_wedding_fallback(spouse1_name, spouse2_name, house1, house2, year) -> str` (deterministic, non-empty, e.g. "In {year}, {s1} of House {h1} wed {s2} of House {h2}, binding the two houses.").

3. **AC3 — Wire acceptance + relations + chronicle into the cross-dynasty match (`models/turn_processor.py`).** Where 7-1 found a cross-dynasty `partner` (~:460-465), BEFORE linking:
   - If the partner's dynasty `is_ai_controlled`: build `AIController(session, partner.dynasty_id, <partner dynasty ai_personality or ''>)` and call `decide_marriage_response(context)` with the seeker's dynasty as proposer. If it returns **False** → do NOT link this partner; fall through to the stranger fallback (or no marriage this tick). If the partner dynasty is NOT AI (human/player) → accept (no gate in 7-2).
   - On **acceptance** (link both `spouse_sim_id` as in 7-1): bump the diplomatic relation between the two dynasties by **+30** (via `DiplomacySystem(session).get_diplomatic_relation(a, b)` then `update_relation('marriage_alliance', 30)`, clamped to ±100 by the model), and append a **wedding chronicle** `HistoryLogEntryDB` (event_type `marriage`) using `build_wedding_chronicle_prompt` when `_llm_available()` (guarded inline `genai`, ≤150 tok, error→fallback) else `generate_wedding_fallback`, naming both spouses' traits/houses.
   - LLM-off (tests) → deterministic wedding fallback; relations still +30.

4. **AC4 — No regressions.** Full suite green vs current baseline (**408** + the known isolation flake; new tests additive). Single-dynasty setups (no cross-dynasty partner) → unchanged. Human/player-target matches auto-accept (7-1 behavior preserved); only AI-target matches gain the decision gate.

5. **AC5 — ≥5 new tests** (`tests/integration/test_ai_marriage.py` + unit for the prompt):
   - `decide_marriage_response`: accepts when `relation_score` is high/neutral; rejects when hostile (e.g. `relation_score = -80`). Deterministic (LLM off).
   - Accepted cross-dynasty match to an AI dynasty (relations neutral) → the two are linked AND the diplomatic relation between the dynasties increased by 30 AND a `marriage` wedding chronicle entry exists.
   - Rejected match (AI dynasty, hostile relations) → the seeker is NOT linked to that partner (falls back to stranger or stays single), and no +30 relation bump to that partner's dynasty.
   - `build_wedding_chronicle_prompt(['Brave'], ['Pious'], ...)` contains both spouse names + a trait; `generate_wedding_fallback` is non-empty and names both houses.
   - A match to a NON-AI (player) dynasty still links without a decision gate (7-1 preserved).

## Tasks / Subtasks
- [ ] Task 1 — `decide_marriage_response` + wedding prompt/fallback (`models/ai_controller.py`, `utils/llm_prompts.py`). [Agent A]
- [ ] Task 2 — Wire AI gate + relations +30 + wedding chronicle into the match (`models/turn_processor.py`). [Agent B]
- [ ] Task 3 — Tests (`tests/integration/test_ai_marriage.py` + prompt unit tests). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `models/ai_controller.py` (`decide_marriage_response`) + `utils/llm_prompts.py` (wedding prompt + fallback).
- **Agent B** — `models/turn_processor.py` only (gate the 7-1 cross-dynasty link on AI acceptance + relations +30 + wedding chronicle). LAZY-import `AIController` / `DiplomacySystem` / the wedding prompt inside the function if a top-level import risks a cycle; A's symbols are absent in B's worktree, so a lazy import keeps B's module importable (mirrors prior stories).
- **Agent C** — NEW test files only.
- No shared files.

### FROZEN INTERFACE CONTRACT
- `AIController.decide_marriage_response(context: dict) -> bool` (rule baseline: accept unless `relation_score < -20`/hostile; LLM optional, fallback clean). `context` keys: `proposer_dynasty_id`, `relation_score`, `proposer_prestige`, `own_prestige` (+ optional piety/traits).
- `build_wedding_chronicle_prompt(spouse1_name, spouse1_traits, spouse2_name, spouse2_traits, house1, house2, year)` + `generate_wedding_fallback(spouse1_name, spouse2_name, house1, house2, year)`.
- `turn_processor` cross-dynasty match: AI-target partner gated by `decide_marriage_response`; on acceptance → link (7-1) + relation +30 between the dynasties + a `marriage` wedding chronicle (LLM-guarded else fallback). Non-AI target → accept without gate.

### Reuse / project rules
- Mirror `AIController.decide_*` rule/LLM pattern; LLM calls guarded (`_llm_available()` else fallback); prompt strings in `utils/llm_prompts.py` only; ≤150-token chronicle budget. Relations via `DiplomacySystem.get_diplomatic_relation` + `DiplomaticRelation.update_relation` (clamps ±100). `DynastyDB.is_ai_controlled` / `ai_personality`. Don't rewrite AIController/turn_processor — extend. No new deps. Lazy imports in turn_processor to avoid cycles (B's worktree lacks A's new symbols → lazy import keeps it importable).

### Out of scope / deferred
- Children-with-claims (cross-dynasty child → `Claim`) + "Propose marriage to my son/daughter" right-click UI → **Story 7-3**. Full alliance treaty creation beyond the relation bump → later. 7-2 is the AI decision + relation bump + wedding chronicle.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool. Agents default to plan mode → "EXECUTE NOW, pre-approved, no EnterPlanMode"; worktrees branch off `main`; contract inlined. **Integrator caution:** agents have repeatedly leaked edits into the MAIN working tree — verify `git status` clean before each merge; if a merge fails on a dirty tree, discard the leaked copies and merge the branch. Also watch for **helper-signature drift** between the impl agent and the tests agent (bit us in 7-1) — the contract signatures above are authoritative.
- `pytest` against an isolated temp DB; reset it before a run; run sandbox-disabled if "readonly database" appears. Shared-state isolation flake intermittently dings the full-suite gate (passes in isolation). Baseline 408.
- 7-1 delivered `_find_cross_dynasty_spouse` + the cross-dynasty link in `process_marriage_check`, and `MarriageOfferDB`.
- Backend-only → no run-the-app visual check.

## References
- `AIController` + `decide_*` pattern + `_llm_available`/LLM guard: `models/ai_controller.py:67,94,128,160,193`.
- 7-1 cross-dynasty match point: `models/turn_processor.py:417` (`_find_cross_dynasty_spouse`), `:460-465` (link).
- Relations: `models/diplomacy_system.py:68` (`get_diplomatic_relation`), `models/db_models.py:882` (`update_relation`, clamps ±100).
- Wedding-prompt pattern to mirror: `utils/llm_prompts.py` (e.g. `build_multigen_project_completion_prompt`/`generate_*_fallback`); guarded call `models/free_action_system.py:184-220`.
- `DynastyDB.is_ai_controlled` / `ai_personality`: `models/db_models.py:68-69`.
- Test fixtures: `tests/integration/test_cross_dynasty_marriage.py`, `test_succession.py`.

## Dev Agent Record

### Agent Model Used

(to be filled by dev/integration)

### Debug Log References

### Completion Notes List

### File List
