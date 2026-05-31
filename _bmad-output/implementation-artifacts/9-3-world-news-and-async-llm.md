# Story 9-3: World News + Async AI-Turn LLM

Status: ready-for-dev

## Story

Two things: (1) **World news** — when an AI dynasty does something significant (declares war), a narrated "letter from afar" appears on the **player's** chronicle/history (using the 9-1 `build_world_news_prompt`). (2) **Async AI turns** — the bulk of a turn's LLM latency comes from AI decision-making in `process_ai_turns` (up to ~4–5 calls per AI dynasty). When the LLM is enabled and a turn projects **5+ LLM calls**, run `process_ai_turns` on a **background thread** so the player's own turn returns immediately and AI consequences (incl. world-news) land shortly after. The player's own `process_dynasty_turn` stays synchronous (its result must be correct/complete on return).

## Design decision (chosen approach)
Async is applied at **one clean boundary — `process_ai_turns`** — not by refactoring every per-event narration call. This keeps game-state mutations off the request thread only for the AI (whose results the player reads moments later as "news"), avoids a risky per-call-site rewrite of `turn_processor`, and keeps the synchronous path (and all existing tests, which run LLM-off) unchanged. Tradeoff: the immediate `turn_report` may not yet show that turn's async AI news; it surfaces on the next view/refresh — acceptable and on-theme for "letters from afar". Documented in code.

## Acceptance Criteria

1. **AC1 — Async infra (NEW `utils/async_narration.py`).**
   - `run_in_background(app, fn, *args, **kwargs) -> threading.Thread` — spawns a **daemon** thread that runs `with app.app_context(): fn(*args, **kwargs)` inside try/except (log any error via `logging.getLogger('royal_succession.async_narration')`, never propagate) and **always** calls `db.session.remove()` in a finally (fresh thread-local scoped session is cleaned up). Returns the started thread (callers may ignore it; tests may `.join()`). `app` is the real app object (`current_app._get_current_object()`).
   - `should_offload_ai_turns(session, user_id, threshold: int = 5) -> bool` — returns True only when `_llm_available()` (LLM configured) AND the projected AI LLM-call count ≥ `threshold`. Projected count = (number of AI-controlled dynasties owned by `user_id`) × `AI_LLM_CALLS_PER_DYNASTY` (a module constant = 4, matching decide_diplomacy/military/economy/character). When LLM is off → always False (so tests + no-key installs keep the synchronous path).
   - All flask/db imports lazy where needed so the module imports cleanly in pure unit tests. Never raises.

2. **AC2 — World-news on significant AI action (`models/game_manager.py`).** Add a helper `_record_world_news(self, actor_dynasty, action_desc: str, year: int) -> None`: find the **player** dynasty/dynasties of `actor_dynasty.user_id` (i.e. `is_ai_controlled == False`), and for each append a `HistoryLogEntryDB(dynasty_id=<player dynasty id>, year=year, event_type='world_news', event_string=narrate_event(build_world_news_prompt(actor_dynasty.name, action_desc, <player dynasty name>, year), generate_world_news_fallback(actor_dynasty.name, action_desc, year), max_tokens=120))` to the session. Guard everything in try/except (never abort the AI turn). Lazy-import `narrate_event` + the prompt builders. **Call it when an AI declares war** — in `_consider_war` right after `declare_war()` succeeds (~game_manager.py:1197-1202), with `action_desc` like `f"declared war on House {target.name}"`. (War is the chosen "significant action" for 9-3; other triggers can be added later.)

3. **AC3 — Offload AI turns when heavy (`blueprints/dynasty.py`, `advance_turn` ~line 388-392).** Where it currently calls `GameManager(...).process_ai_turns(current_user.id)` synchronously: if `should_offload_ai_turns(db.session, current_user.id)` → `run_in_background(current_app._get_current_object(), _ai_turns_job, current_user.id)` and continue (don't block); else call synchronously as today. `_ai_turns_job(user_id)` (a small module-level function in the blueprint or a lazy-imported helper) does `GameManager(db.session).process_ai_turns(user_id)` (inside the background thread's app context, `db.session` is a fresh thread-local session). Lazy-import `run_in_background`/`should_offload_ai_turns`. The player-facing redirect/flow is otherwise unchanged. Add a brief flash/log noting AI turns are resolving in the background when offloaded (optional, info category).

4. **AC4 — `world_news` surfaced.** The dynasty view / turn_report already query `HistoryLogEntryDB` for recent events; ensure `event_type='world_news'` entries on the player's dynasty are included in what the player sees (if the existing `recent_events`/chronicle query filters by type, add `world_news`; if it shows all types, no change needed — verify and note). No new template required; a one-line inclusion at most.

5. **AC5 — No regressions / safety.** Full suite green vs baseline **474 passed**. With LLM **off** (all tests): `should_offload_ai_turns` → False → `process_ai_turns` runs **synchronously exactly as today** → existing advance_turn / game-flow tests unchanged. World-news writes use the deterministic fallback. No new pip deps (stdlib `threading` only). The background thread must use its own app context + thread-local session and `db.session.remove()` in finally — never touch the request session from the thread. `process_dynasty_turn` (the player's own turn) stays fully synchronous.

6. **AC6 — Tests (NEW files only) — ≥6.**
   - `tests/unit/test_async_narration.py`: `run_in_background(app, fn)` actually runs `fn` within an app context (use a fn that writes a row / sets a flag; `.join()` the returned thread; assert the effect) and never raises if `fn` throws (pass a throwing fn → no exception escapes, thread ends). `should_offload_ai_turns`: with LLM off → False regardless of AI count; with `_llm_available` monkeypatched True and N AI dynasties such that N×4 ≥ 5 → True, and below threshold → False.
   - `tests/integration/test_world_news.py`: drive an AI war declaration (call `GameManager._consider_war` on an aggressive AI dynasty vs a target, or directly call `_record_world_news`) and assert a `HistoryLogEntryDB` with `event_type='world_news'` and `dynasty_id == player dynasty id` exists, whose `event_string` equals/contains `generate_world_news_fallback(actor_name, action_desc, year)` (LLM off). Also assert no world_news is written to the AI's own dynasty. Mirror the player+AI fixture pattern (two dynasties, one `is_ai_controlled=True`).
   - At least one test that `advance_turn` still works synchronously with LLM off (offload predicate False) — i.e. existing behavior; can be a focused assertion that `should_offload_ai_turns` is False in the test app so the sync path is taken.

## Tasks / Subtasks
- [ ] Task 1 — `utils/async_narration.py` (`run_in_background` + `should_offload_ai_turns`). [Agent A]
- [ ] Task 2 — `_record_world_news` + war trigger (game_manager) + offload dispatch (advance_turn) + world_news surfacing. [Agent B]
- [ ] Task 3 — Tests. [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — NEW `utils/async_narration.py` ONLY.
- **Agent B** — `models/game_manager.py` (`_record_world_news` + call in `_consider_war`) + `blueprints/dynasty.py` (offload dispatch in `advance_turn` + `_ai_turns_job` + world_news surfacing in the view/turn_report query if needed). LAZY-import `run_in_background`/`should_offload_ai_turns` (A's module absent in B's worktree) and `narrate_event`/prompt builders.
- **Agent C** — NEW `tests/unit/test_async_narration.py` + `tests/integration/test_world_news.py` ONLY.
- No shared files.

### FROZEN INTERFACE CONTRACT (authoritative)
- `utils/async_narration.py`: `run_in_background(app, fn, *args, **kwargs) -> threading.Thread` (daemon; runs fn in app_context; swallows + logs errors; `db.session.remove()` in finally). `should_offload_ai_turns(session, user_id, threshold: int = 5) -> bool` (True only if `_llm_available()` and `ai_dynasty_count * AI_LLM_CALLS_PER_DYNASTY >= threshold`; LLM off → False). Module const `AI_LLM_CALLS_PER_DYNASTY = 4`.
- `GameManager._record_world_news(self, actor_dynasty, action_desc: str, year: int) -> None` — writes a `world_news` `HistoryLogEntryDB` (event_type exactly `'world_news'`) to each player (non-AI) dynasty of `actor_dynasty.user_id`, narrated via `build_world_news_prompt(actor_dynasty.name, action_desc, player_name, year)` / `generate_world_news_fallback(actor_dynasty.name, action_desc, year)` through `narrate_event(..., max_tokens=120)`. Never raises.
- 9-1 builders (in utils/llm_prompts.py, verbatim): `build_world_news_prompt(actor_dynasty, action_desc, player_dynasty, year)`, `generate_world_news_fallback(actor_dynasty, action_desc, year)`. 9-2 helper: `utils/llm_narration.py::narrate_event(prompt, fallback, max_tokens=100, timeout_s=3)`.
- `advance_turn`: when `should_offload_ai_turns(db.session, current_user.id)` → `run_in_background(current_app._get_current_object(), _ai_turns_job, current_user.id)`; else synchronous `process_ai_turns` (unchanged). Player flow/redirect unchanged.

### Reuse / project rules
- `_llm_available()`: `models/turn_processor.py:69` (config `FLASK_APP_GOOGLE_API_KEY_PRESENT`). It can be imported (`from models.turn_processor import _llm_available`) or re-checked via current_app config directly — pick one and keep it importable in unit tests (lazy `current_app`).
- `process_ai_turns(user_id) -> (bool, str)`: `models/game_manager.py:870`. War: `_consider_war` ~`:1152-1210` (`declare_war()` ~1197). `HistoryLogEntryDB` cols: `models/db_models.py:288` (dynasty_id, year, event_string, event_type). `advance_turn`: `blueprints/dynasty.py:311` (AI-turn call ~`:388-392`). recent_events/turn_report AI news: `blueprints/dynasty.py:466-488`.
- Flask-SQLAlchemy 3.x: `db.session` is a thread-local scoped session; inside a NEW thread's `app.app_context()` it is a fresh session — safe to use, then `db.session.remove()`. Do NOT pass ORM objects across threads — pass ids (`user_id`) and re-query inside the thread. App ref via `current_app._get_current_object()`. SocketIO uses `async_mode='threading'` (main_flask_app.py:77) — plain `threading.Thread(daemon=True)` is consistent.
- DB writes try/except + rollback; `@login_required` preserved; flash categories success/danger/info/warning; no `print()`; no new deps.

### Out of scope / deferred
- Per-event async narration upgrade of birth/death/battle/turn-story (write fallback now, backfill LLM text later) — heavier refactor; 9-3 offloads at the `process_ai_turns` boundary instead. Additional world-news triggers beyond war (battles won, conquests, successions). A websocket push when async AI news arrives (currently surfaces on next view).

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool; "EXECUTE NOW, no plan mode"; write only inside the worktree root (verify `git rev-parse --show-toplevel`); contract inlined. Integrator: verify where edits landed; **run the full suite before merge**; this touches the core `advance_turn` route + `process_ai_turns` — confirm the SYNC path (LLM off) is byte-for-byte behaviourally unchanged so game-flow tests stay green. Signature drift bit 7-1/7-2 — frozen signatures above authoritative.
- Baseline **474 passed** (Epics 7+8 done; 9-1+9-2 done). Tests run LLM-OFF → `should_offload_ai_turns` False → synchronous AI turns. Async machinery is unit-tested in isolation (the LLM-on path isn't exercised by the normal suite — note that explicitly; do not fake LLM-on in the integration turn tests).
- 9-1 built the prompts; 9-2 built `narrate_event` + birth/death/battle wiring; 9-3 adds world-news + the async boundary. After 9-3, **Epic 9 complete**.
- Known pre-existing issues to avoid tripping: `Building` schema gap (construction non-functional — see 9-2 notes); don't touch economy/construction here.

## References
- AI turns: `models/game_manager.py:870` (`process_ai_turns`), `:1152-1210` (`_consider_war`/`declare_war`). advance_turn: `blueprints/dynasty.py:311`, AI call ~`:388-392`, turn_report AI news `:466-488`. `_llm_available`: `models/turn_processor.py:69`. `narrate_event`: `utils/llm_narration.py`. world-news prompts: `utils/llm_prompts.py` (9-1). HistoryLogEntryDB: `models/db_models.py:288`. Flask/SocketIO/db setup: `main_flask_app.py:58-126`. Tests: `tests/functional/test_game_flow.py`, `tests/integration/` (player+AI fixtures), `tests/conftest.py:64-108`.

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool + main-session integrator.
### Completion Notes List
- _pending_
### File List
- `utils/async_narration.py` — NEW (`run_in_background`, `should_offload_ai_turns`)
- `models/game_manager.py` — MODIFIED (`_record_world_news` + war trigger)
- `blueprints/dynasty.py` — MODIFIED (offload dispatch in advance_turn + world_news surfacing)
- `tests/unit/test_async_narration.py` — NEW
- `tests/integration/test_world_news.py` — NEW
- `_bmad-output/implementation-artifacts/{9-3-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(9-3); ready-for-dev; full scope (world-news + async AI-turn offload) per user decision; 3 worktree agents |
