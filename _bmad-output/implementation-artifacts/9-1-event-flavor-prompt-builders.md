# Story 9-1: Event-Flavor Prompt Builders

Status: done

## Story

Add the prompt builders (each with a deterministic fallback) that Story 9-2 will wire into lifecycle events so every mechanical event (birth, death, battle, construction) and AI-world-event reads as a narrated medieval line instead of a bare string. **9-1 only adds the builders + fallbacks to `utils/llm_prompts.py` (+ tests)** — no lifecycle wiring (that's 9-2), no LLM calls executed here.

## Scope note (overlap with Story 5-2)
The Epic-9 plan lists 7 builders, but `build_succession_card_prompt` (+ `generate_succession_card_fallback`) and `build_coronation_prompt` (+ `generate_coronation_fallback`) **already exist** in `utils/llm_prompts.py` (added by Story 5-2, lines 416-489). **Do NOT re-add or modify those.** 9-1 adds the **5 remaining** builders + fallbacks. (There is also a pre-existing `build_battle_commentary_prompt` at line 102 — distinct from the new `build_battle_flavor_prompt`; leave it alone.)

## Acceptance Criteria

1. **AC1 — 5 new builders + 5 deterministic fallbacks (`utils/llm_prompts.py`).** Mirror the existing house style (raw f-string prompt that instructs a ≤N-token medieval line; `logger` not required in this pure module; fallbacks return a deterministic, non-empty string naming the subject + house + year). Frozen signatures (authoritative — 9-2 + tests depend on these EXACTLY):
   - `build_birth_flavor_prompt(child_name, child_traits, mother_name, father_name, house, year) -> str` (≤80 tok) + `generate_birth_flavor_fallback(child_name, mother_name, father_name, house, year) -> str`
   - `build_death_flavor_prompt(person_name, person_traits, house, age, year, was_monarch=False) -> str` (≤90 tok) + `generate_death_flavor_fallback(person_name, house, age, year, was_monarch=False) -> str`
   - `build_battle_flavor_prompt(attacker_name, defender_name, location, victor_name, casualties, year) -> str` (≤100 tok) + `generate_battle_flavor_fallback(attacker_name, defender_name, victor_name, year) -> str`
   - `build_world_news_prompt(actor_dynasty, action_desc, player_dynasty, year) -> str` (≤120 tok, framed as a "letter from afar" reaching the player's court) + `generate_world_news_fallback(actor_dynasty, action_desc, year) -> str`
   - `build_construction_complete_prompt(building_name, territory_name, house, year) -> str` (≤70 tok) + `generate_construction_complete_fallback(building_name, territory_name, house, year) -> str`
   - `*_traits` params accept a list (or None); builders should gracefully handle empty/None traits. Each prompt string must mention the subject name(s); each builder embeds the token budget hint in the instruction (mirror existing builders). Each fallback is non-empty, deterministic for the same args, and references the subject name + year (and house where applicable).

2. **AC2 — No regressions / purity.** `utils/llm_prompts.py` stays a pure prompt module (no `genai`/network/Flask imports added; no `print()`). Existing builders/fallbacks unchanged. Full suite green vs baseline **455 passed** (new tests additive).

3. **AC3 — Tests (NEW `tests/unit/test_event_flavor_prompts.py`) — ≥10.** For EACH of the 5 builders: the returned prompt is a non-empty `str` that contains the key subject name(s) passed in. For EACH of the 5 fallbacks: non-empty `str`, deterministic (two identical calls equal), and contains the subject name + the year. Plus: builders handle `None`/empty traits without error; `build_death_flavor_prompt(..., was_monarch=True)` differs from the non-monarch variant in some way (e.g. references the crown/reign). Mirror the existing prompt-test style if any (else establish it; pure unit tests, no app context needed).

## Tasks / Subtasks
- [ ] Task 1 — 5 builders + 5 fallbacks in `utils/llm_prompts.py`. [Agent A]
- [ ] Task 2 — `tests/unit/test_event_flavor_prompts.py`. [Agent B]

## Dev Notes

### Multi-agent split (2 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `utils/llm_prompts.py` ONLY (append the 5 builders + 5 fallbacks; do not touch existing functions).
- **Agent B** — NEW `tests/unit/test_event_flavor_prompts.py` ONLY (the CONTRACT signatures are authoritative since A's code isn't in B's worktree).
- No shared files.

### FROZEN INTERFACE CONTRACT (authoritative — prevents drift)
The 5 builder + 5 fallback signatures listed in AC1, verbatim. `*_traits` accept list|None. Builders return a prompt `str`; fallbacks return a deterministic non-empty `str` naming the subject + year. Do NOT touch `build_succession_card_prompt`/`build_coronation_prompt`/`build_battle_commentary_prompt` (already exist).

### Reuse / project rules
- Mirror existing builders/fallbacks: `build_wedding_chronicle_prompt`/`generate_wedding_fallback` (llm_prompts.py:302-357), `build_free_action_flavor_prompt`/`generate_free_action_flavor_fallback` (:359-414), `build_succession_card_prompt`/`generate_succession_card_fallback` (:416-463), `build_coronation_prompt`/`generate_coronation_fallback` (:465-489). Same f-string + token-budget-hint style. Token budgets per CLAUDE.md (chronicle 150, advisor 200, decision 100, battle commentary 60) — keep these flavor lines small (50-120). Pure module, no new deps.

### Out of scope / deferred
- Wiring these into `turn_processor.py` lifecycle functions (store as `event_string` on `HistoryLogEntryDB`, fallback on LLM unavailable/timeout >3s) → **Story 9-2**. World-news chronicle entries for AI actions + async LLM for 5+ call turns → **Story 9-3**.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool; "EXECUTE NOW, no plan mode"; write only inside the worktree root; contract inlined. Integrator: verify where edits landed, run the full suite before merge. **Signature drift** between the impl agent and the tests agent bit 7-1/7-2 — the frozen signatures above are authoritative.
- Baseline **455 passed** (Epics 7 + 8 complete). Tests: isolated temp DB; `python -m pytest -p no:randomly -q`. Backend-only (pure prompts) → no run-the-app check needed; the unit tests are the contract.
- `utils/llm_prompts.py` already holds all prompt strings (project rule: no inline prompts in routes/models). LLM calls are always guarded by `_llm_available()` at the call site (9-2's concern), so these builders never call the network themselves.

## References
- Prompt module + existing builders to mirror: `utils/llm_prompts.py:302-489`. Existing battle commentary (leave alone): `:102`. Token budgets: CLAUDE.md "LLM token budgets".
- 9-2 will consume these in `models/turn_processor.py` lifecycle functions; 9-1 just defines them.

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 2 worktree sub-agents via the Workflow tool + main-session integrator.
### Completion Notes List
- _pending_
### File List
- `utils/llm_prompts.py` — MODIFIED (5 builders + 5 fallbacks)
- `tests/unit/test_event_flavor_prompts.py` — NEW
- `_bmad-output/implementation-artifacts/{9-1-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(9-1); ready-for-dev; 2 worktree agents via Workflow; 5 new builders (succession_card/coronation already exist from 5-2) |
