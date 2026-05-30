# Story 9-2: Wire Event-Flavor into Lifecycle Events

Status: done (construction descoped — see notes)

## Story

Make every mechanical event read as narrated history: at each lifecycle log site (birth, death, battle, construction completion), build the relevant Story 9-1 flavor prompt and run it through a single guarded LLM helper that returns the narrated line — or the deterministic fallback when the LLM is unavailable/errors/times out (>3s). Store the result as the `event_string` on the `HistoryLogEntryDB`. **Synchronous** (mirrors the existing chronicle/wedding guarded-`genai` pattern); async/world-news is Story 9-3.

## Acceptance Criteria

1. **AC1 — Shared narration helper (NEW `utils/llm_narration.py`).** `narrate_event(prompt: str, fallback: str, max_tokens: int = 100, timeout_s: int = 3) -> str`. Self-contained, mirroring the existing guarded block (turn_processor.py:302-326): if no Flask app / `current_app.config.get('FLASK_APP_GOOGLE_API_KEY_PRESENT', False)` is falsy / no API key → return `fallback`; else lazy-`import google.generativeai as genai`, configure with `current_app.config.get("FLASK_APP_GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")`, `GenerativeModel("gemini-1.5-flash")`, `generate_content(prompt, generation_config={"max_output_tokens": max_tokens, "temperature": 0.85}, request_options={"timeout": timeout_s})`, return `response.text.strip()` or `fallback` if empty. **Never raises** — any exception (incl. timeout) → log at debug + return `fallback`. `logger = logging.getLogger('royal_succession.llm_narration')`. No top-level genai/flask import (all lazy) so the module stays importable in pure unit tests.

2. **AC2 — Birth + Death flavor (`models/turn_processor.py`).** Lazy-import `narrate_event` (and the 9-1 builders) where used.
   - **Birth** (`process_childbirth_check`, ~line 750, the surviving-child `birth_log`): set `event_string = narrate_event(build_birth_flavor_prompt(child_name, child.get_traits(), woman.name, spouse.name, dynasty.name, current_year), generate_birth_flavor_fallback(child_name, woman.name, spouse.name, dynasty.name, current_year), max_tokens=80)`. (Use the child's full display name as elsewhere.)
   - **Death** (`process_death_check`-driven `death_log`, ~line 404): `event_string = narrate_event(build_death_flavor_prompt(f"{person.name} {person.surname}", person.get_traits(), dynasty.name, age, current_year, person.is_monarch), generate_death_flavor_fallback(f"{person.name} {person.surname}", dynasty.name, age, current_year, person.is_monarch), max_tokens=90)`.
   - Leave the infant-death and other logs as-is. No change to event_type values. The mechanical outcome (who is born/dies) is unchanged — only the `event_string` text.

3. **AC3 — Battle flavor (`models/military_system.py`, `initiate_battle`, ~line 581-584).** Replace the static battle `event_string` with `narrate_event(build_battle_flavor_prompt(<attacker dynasty name>, <defender dynasty name>, territory.name, winner_name, attacker_casualties + defender_casualties, <year>), generate_battle_flavor_fallback(<attacker dynasty name>, <defender dynasty name>, winner_name, <year>), max_tokens=100)`. Lazy-import the helper + builder. Use the dynasty names already resolvable from the armies; `<year>` = the attacker dynasty's `current_simulation_year` (or the value already used in that log). Keep `event_type` and all casualty/winner mechanics unchanged.

4. **AC4 — Construction-completion flavor + log (`models/economy_system.py`, ~line 673).** When a building finishes (`is_under_construction` flips False because `current_simulation_year >= completion_year`), append a `HistoryLogEntryDB(dynasty_id=dynasty.id, year=dynasty.current_simulation_year, event_type='construction', event_string=narrate_event(build_construction_complete_prompt(building.name, <territory name>, dynasty.name, dynasty.current_simulation_year), generate_construction_complete_fallback(building.name, <territory name>, dynasty.name, dynasty.current_simulation_year), max_tokens=70))` to the session. Resolve the territory name via `building.territory_id` (Territory). Lazy-import helper + builder. Do not change the existing completion mechanics (level-up etc.); just ADD the log entry. Guard the territory lookup (fallback to "" / a generic name if missing).

5. **AC5 — No regressions.** Full suite green vs baseline **468 passed**. **Any test asserting the OLD static birth/death/battle strings must be updated** to assert the new flavored-fallback text (search `tests/` for `passed away at the age of`, `was born to`, `Battle of`, `defeated`). With the LLM off (tests), every `event_string` comes from the deterministic 9-1 fallback — so assertions should match the fallback wording (which names the subject). No new pip deps.

6. **AC6 — Tests (NEW `tests/integration/test_lifecycle_flavor.py`) — ≥5.** LLM is off in tests, so these assert the deterministic fallback path:
   - A birth (drive `process_childbirth_check` with a surviving child) logs a `birth` entry whose `event_string` equals/contains `generate_birth_flavor_fallback(...)` (i.e. the flavored fallback, naming the child + year), not the old static string.
   - A death (drive `process_death_check` to kill someone, or `process_dynasty_turn` with a forced death) logs a `death` entry whose `event_string` is the death fallback (names the person + age + year; monarch variant differs).
   - A battle via `MilitarySystem.initiate_battle` logs a battle entry whose `event_string` is the battle fallback (names the combatants + year).
   - A building finishing construction (drive the economy update past `completion_year`) creates a `construction` log whose `event_string` is the construction fallback (names the building + year).
   - `narrate_event` unit: with the LLM unavailable (no app config flag) returns the `fallback` verbatim and never raises; passing a bogus prompt still returns the fallback.

## Tasks / Subtasks
- [ ] Task 1 — `narrate_event` helper + birth/death wiring. [Agent A]
- [ ] Task 2 — Battle + construction wiring. [Agent B]
- [ ] Task 3 — Tests + update any old-string assertions. [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — NEW `utils/llm_narration.py` (`narrate_event`) + `models/turn_processor.py` (birth + death event_string only).
- **Agent B** — `models/military_system.py` (battle event_string) + `models/economy_system.py` (construction completion log). LAZY-import `narrate_event` from `utils.llm_narration` inside the functions (A's module is absent in B's worktree → lazy import keeps B importable).
- **Agent C** — NEW `tests/integration/test_lifecycle_flavor.py` + update any EXISTING test that asserts the old static birth/death/battle strings (search tests/ for the phrases in AC5; comment each change).
- No shared files. (A owns turn_processor.py; B owns military_system.py + economy_system.py; only C touches tests.)

### FROZEN INTERFACE CONTRACT (authoritative)
- `utils/llm_narration.py :: narrate_event(prompt: str, fallback: str, max_tokens: int = 100, timeout_s: int = 3) -> str` — returns the LLM text or, on unavailable/empty/error/timeout, the `fallback`; never raises; all genai/flask imports lazy.
- 9-1 builders/fallbacks (already in `utils/llm_prompts.py`, verbatim signatures): `build_birth_flavor_prompt(child_name, child_traits, mother_name, father_name, house, year)` + `generate_birth_flavor_fallback(child_name, mother_name, father_name, house, year)`; `build_death_flavor_prompt(person_name, person_traits, house, age, year, was_monarch=False)` + `generate_death_flavor_fallback(person_name, house, age, year, was_monarch=False)`; `build_battle_flavor_prompt(attacker_name, defender_name, location, victor_name, casualties, year)` + `generate_battle_flavor_fallback(attacker_name, defender_name, victor_name, year)`; `build_construction_complete_prompt(building_name, territory_name, house, year)` + `generate_construction_complete_fallback(building_name, territory_name, house, year)`.
- Each wired site: `event_string = narrate_event(build_X(...), generate_X_fallback(...), max_tokens=<budget>)`. event_type values unchanged; mechanical outcomes unchanged.

### Reuse / project rules
- Mirror the guarded-genai block at `turn_processor.py:302-326` (chronicle) / `:530-560` (wedding). `_llm_available` semantics: `current_app.config['FLASK_APP_GOOGLE_API_KEY_PRESENT']`; api key `FLASK_APP_GOOGLE_API_KEY` or `os.environ['GOOGLE_API_KEY']`. Token budgets per 9-1 (birth 80, death 90, battle 100, construction 70). DB writes via the existing session; never abort the turn/battle/economy update on a narration failure (the helper already swallows errors). No `print()`; module loggers. No new deps.
- Log sites: birth `turn_processor.py:750`, death `:404`, battle `military_system.py:581-584` (`initiate_battle`, has `winner_name`/`loser_name`/`territory`/casualties), construction `economy_system.py:673` (building completion loop; resolve Territory by `building.territory_id`).

### Out of scope / deferred
- "Letter from afar" world-news entries when an AI dynasty does something significant (`build_world_news_prompt`, already defined in 9-1) + **async background LLM** for turns with 5+ calls (so per-event calls never block) → **Story 9-3**. 9-2 stays synchronous.
- Succession/coronation already narrated (Story 5-2). Free-action flavor already wired (4-2).

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool; "EXECUTE NOW, no plan mode"; write only inside the worktree root (verify `git rev-parse --show-toplevel`); contract inlined. Integrator: verify where each agent's edits landed; **run the full suite before merge — this story changes birth/death/battle event_string TEXT, so existing assertions on the old strings WILL break and must be updated** (Agent C handles known ones; integrator fixes any stragglers). Signature drift bit 7-1/7-2 — frozen signatures above are authoritative.
- Baseline **468 passed**. Tests run LLM-off (no `FLASK_APP_GOOGLE_API_KEY_PRESENT`) → deterministic fallback path. `python -m pytest -p no:randomly -q`, temp DB at `/tmp/rss_pytest.db`. Backend-only → no run-the-app visual check required (optional: set GOOGLE_API_KEY and eyeball one narrated line).
- 9-1 (just merged, 25a0bdc) defined the builders/fallbacks; this story consumes them.

## References
- Guarded-genai pattern: `models/turn_processor.py:69` (`_llm_available`), `:302-326`, `:530-560`. Lifecycle logs: birth `:750`, death `:404`. Battle: `models/military_system.py:509` (`initiate_battle`), `:581-584` (log). Construction: `models/economy_system.py:668-676`. Builders: `utils/llm_prompts.py` (9-1 additions).

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool + main-session integrator.
### Completion Notes List
- birth/death/battle flavor delivered + tested; full suite **474 passed** (468 + 6 new). 3 worktree agents (run wf_dc2be0f2-f95) + integrator.
- **Construction flavor DESCOPED** (AC4/construction test removed): the `Building` model has no `is_under_construction`/`completion_year` columns, yet `EconomySystem.construct_building` + the completion branch reference them — a **pre-existing latent bug** (construct_building raises TypeError; completion branch is dead code; suite stays green because the route swallows it). Wiring construction flavor needs that schema fixed first — deferred to a dedicated story. Reverted Agent B's economy_system change; `build_construction_complete_prompt` (9-1) remains ready to wire.
- Integrator test fixes: removed a bogus `assert "was born to" not in event_string` (the 9-1 birth fallback legitimately uses that phrase; the `== fallback` assertion is the real check); removed the construction test class with a documented explanation.
- Agent A death-site note: `process_death_check` has no `dynasty` in scope → house resolved via `DynastyDB.query.get(person.dynasty_id)` (guarded), passing the same value the contract intended.
### File List
- `utils/llm_narration.py` — NEW (`narrate_event`)
- `models/turn_processor.py` — MODIFIED (birth + death event_string)
- `models/military_system.py` — MODIFIED (battle event_string)
- `models/economy_system.py` — MODIFIED (construction completion log)
- `tests/integration/test_lifecycle_flavor.py` — NEW; plus any existing test updated for new strings
- `_bmad-output/implementation-artifacts/{9-2-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(9-2); ready-for-dev; 3 worktree agents via Workflow; synchronous guarded narration (async deferred to 9-3) |
