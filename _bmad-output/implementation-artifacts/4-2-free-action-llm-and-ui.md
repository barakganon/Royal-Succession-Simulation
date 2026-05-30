# Story 4-2: Free Action LLM Flavor + Right-Click Menu Integration + Undo

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player issuing free actions from the map,
I want each free action to read as a chronicle sentence (LLM-narrated, with a deterministic fallback), to pick free actions from the right-click menu (visually separated from multi-year project actions), and to undo the last reversible free action before I click End Turn,
so that instant decisions feel narrated and in-context, and a misclick isn't permanent.

Builds on Story 4-1 (`FreeActionSystem` + `POST /free_action`). LLM-off must remain fully functional (deterministic fallback), per project rules.

## Acceptance Criteria

1. **AC1 — LLM flavor lines (with fallback).** Add to `utils/llm_prompts.py`:
   - `build_free_action_flavor_prompt(action_type, dynasty_name, monarch_name, year, target_name=None) -> str` — medieval-chronicler, 1–2 sentences, third-person; **max_tokens ≤ 150** (chronicle budget).
   - `generate_free_action_flavor_fallback(action_type, dynasty_name, monarch_name, year, target_name=None) -> str` — deterministic per-action sentence (this replaces/augments 4-1's plain message as the fallback).
   `FreeActionSystem` uses the flavor for the chronicle `event_string`: if `_llm_available()` call the model (guarded, inline `genai` pattern from `models/project_system.py:81-102`, `max_output_tokens<=150`, on any error → fallback); else use the fallback. The `HistoryLogEntryDB.event_type` stays `'free_action'`; year stays current (no tick). LLM-off (test env) → deterministic fallback text, non-empty.

2. **AC2 — Free-action catalogue endpoint.** New `GET /dynasty/<int:dynasty_id>/free_action_catalogue.json` (`blueprints/dynasty.py`, `@login_required`, ownership → 403 else). Returns:
   ```json
   {"actions": [
     {"action_type":"declare_war","label":"Declare War","category":"diplomacy","needs_target":true,"undoable":false},
     {"action_type":"hold_feast","label":"Hold Feast","category":"court","needs_target":false,"undoable":true},
     ... all 9 from VALID_FREE_ACTIONS ...
   ]}
   ```
   - `category` ∈ `diplomacy` (declare_war, propose_treaty, send_envoy, issue_ultimatum) / `succession` (name_heir, adopt_succession_law) / `court` (hold_feast, hold_tournament, pardon_vassal).
   - `needs_target`: true for the 4 diplomacy actions (require `target_dynasty_id`).
   - `undoable`: true for the 5 field-mutation actions, false for the 4 diplomacy actions.

3. **AC3 — Undo (reversible-only, server session stack).**
   - `FreeActionSystem`: keep `perform_free_action(...) -> (ok, message)` **unchanged** (don't break 4-1). After a successful **reversible** action, set instance attr `self.last_undo_token` to a dict `{"action_type", "dynasty_id", "snapshot": {<field>: <prior_value>, ...}, "history_entry_id": <int>}`; for non-reversible actions set `self.last_undo_token = None`. Initialize `self.last_undo_token = None` in `__init__`. Capture the `HistoryLogEntryDB` id so undo can delete that chronicle line.
   - New method `undo_free_action(self, dynasty_id, undo_token) -> (ok, message)`: validates the token's `dynasty_id` matches; restores each snapshot field on the `DynastyDB`; deletes the captured `HistoryLogEntryDB`; returns `(True, "Undid <action>.")`. Invalid/foreign token → `(False, ...)`. Does NOT commit (route commits).
   - Reversible field maps: `name_heir`→`designated_heir_id`; `adopt_succession_law`→`succession_law`; `hold_feast`/`hold_tournament`→`current_wealth`+`prestige`; `pardon_vassal`→`honor`.
   - **Route plumbing** (`blueprints/dynasty.py`): in `/free_action`, after a successful perform, if `system.last_undo_token` is not None, push it onto `flask_session['free_action_undo_stack']` (create list if absent). New route `POST /dynasty/<int:dynasty_id>/free_action/undo` (`@login_required`, `@block_if_turn_processing`, ownership→403): pop the last token from the session stack; empty → JSON `{"ok":false,"message":"Nothing to undo"}` (200); else call `undo_free_action`, commit on ok / rollback on error, return `{"ok":bool,"message":str}`. Non-reversible actions never get pushed, so they're inherently non-undoable; an explicit undo attempt with an empty stack returns the "Nothing to undo" message.

4. **AC4 — Right-click menu integration.** `templates/world_map.html` context menu (Story 3-2 lives at `#ctx-rows`, `_populateMenu`, `_renderRow`, fetched from `project_catalogue.json`) gains a **free-actions section** below the project actions, **visually separated** (a labeled divider / distinct container class, e.g. `ctx-free-actions` with a "Decisions" header vs the "Projects" rows). Fetch from `free_action_catalogue.json` (cache like the project catalogue). Clicking a free action POSTs to `/dynasty/<id>/free_action` (XHR, `X-Requested-With`) with `action_type` (+ for `needs_target`, a minimal target prompt/selection — a simple `window.prompt` for `target_dynasty_id` is acceptable in this story; richer targeting is later). On success, show a small toast (reuse the Story 3-5 `turn-toast-stack` if convenient) with the returned `message`, and surface an **"Undo last"** control that POSTs `/free_action/undo` and toasts the result. Keep all Story 3-2 project-row behavior intact.

5. **AC5 — No regressions; tests green.** Full suite stays green (baseline **327**; new tests additive). 4-1's tests still pass — the chronicle still has `event_type='free_action'`, and `perform_free_action` still returns `(ok, message)`.

6. **AC6 — At least 6 new integration tests** in NEW `tests/integration/test_free_action_ui_and_undo.py` (fixture pattern from `test_detail_panel_render.py`; LLM is unavailable in tests → flavor uses fallback):
   - `free_action_catalogue.json` returns 9 actions with `category`/`needs_target`/`undoable`; 403 for non-owner.
   - Flavor fallback: a free action's `HistoryLogEntryDB.event_string` is the deterministic fallback (non-empty, action-appropriate) when LLM is off.
   - Undo reversible: `hold_feast` then `POST /free_action/undo` → `current_wealth`/`prestige` restored AND the `free_action` chronicle entry count returns to its prior value.
   - Undo with empty stack → `{"ok":false,"message":"Nothing to undo"}`.
   - A non-reversible action (`declare_war`) does NOT become undoable (stack not pushed → next undo says "Nothing to undo", and the War row persists).
   - `/world/map` HTML contains the free-actions menu markers (e.g. `free_action_catalogue` fetch + the `ctx-free-actions` container) and an undo control.

7. **AC7 — Visual verification (Epic 3 retro lesson).** This story has a UI surface, so it is NOT "done" on tests alone. The integrator runs the app and confirms via headless-Chrome screenshot: right-click a hex → the menu shows project actions AND a separated "Decisions"/free-actions section; choosing one toasts a narrated line; the Undo control reverses a reversible action.

## Tasks / Subtasks
- [ ] Task 1 — Backend: flavor prompt+fallback (`utils/llm_prompts.py`), flavor wiring + undo (`models/free_action_system.py`), catalogue + undo route + session-stack plumbing (`blueprints/dynasty.py`). [Agent A]
- [ ] Task 2 — Frontend: free-actions menu section + undo control + toasts (`templates/world_map.html`, `static/style.css`). [Agent B]
- [ ] Task 3 — Tests (NEW `tests/integration/test_free_action_ui_and_undo.py`). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A (all backend)** — `models/free_action_system.py`, `utils/llm_prompts.py`, `blueprints/dynasty.py`. Owns flavor + undo + catalogue endpoint + undo route + session-stack. (One owner for all backend so the FreeActionSystem/route changes don't split across agents.)
- **Agent B (frontend)** — `templates/world_map.html`, `static/style.css` only. Consumes A's endpoints via the frozen contract.
- **Agent C (tests)** — ONLY `tests/integration/test_free_action_ui_and_undo.py`. Contract-first: tests fail in isolation (endpoints/markers absent), green on integration — do NOT weaken.
- No two agents share a file.

### FROZEN INTERFACE CONTRACT
- llm_prompts: `build_free_action_flavor_prompt(action_type, dynasty_name, monarch_name, year, target_name=None)` + `generate_free_action_flavor_fallback(action_type, dynasty_name, monarch_name, year, target_name=None)`.
- `FreeActionSystem`: `perform_free_action(...) -> (ok, message)` UNCHANGED; new attr `last_undo_token` (dict|None, init None); new `undo_free_action(dynasty_id, undo_token) -> (ok, message)`. Neither commits; neither ticks.
- Endpoints: `GET /dynasty/<id>/free_action_catalogue.json` → `{"actions":[{action_type,label,category,needs_target,undoable}...]}`; `POST /dynasty/<id>/free_action/undo` → `{"ok":bool,"message":str}` (pops `flask_session['free_action_undo_stack']`); `/free_action` pushes `last_undo_token` when present.
- Frontend markers (tests assert): `free_action_catalogue` (in the fetch URL) and a `ctx-free-actions` container in `/world/map`, plus an undo control.
- Reversible = {name_heir, adopt_succession_law, hold_feast, hold_tournament, pardon_vassal}; non-reversible/undoable=false = {declare_war, propose_treaty, send_envoy, issue_ultimatum}.

### Reuse / project rules
- LLM guard: mirror `models/project_system.py:35,81-102` (`_llm_available()` + inline `genai` + `max_output_tokens<=150`, temperature ~0.8, any error → fallback). All prompt strings in `utils/llm_prompts.py` (never inline). DB writes guarded; route owns commit/rollback. `@login_required` (+ `@block_if_turn_processing` on undo). `url_for` in templates. Match the Story 3-2 context-menu JS style and the Story 3-5 toast/`X-Requested-With` fetch pattern already in `world_map.html`.
- Do NOT change `perform_free_action`'s return shape (4-1 route + tests depend on `(ok, message)`); expose the undo token via the `last_undo_token` attribute read by the route after the call.

### Out of scope / deferred
- Rich target selection UI (a `window.prompt` for `target_dynasty_id` is fine here); full undo for war/treaty (non-reversible by design — logged); map-driven *project* starts (still the separate 3-2 deferral). 4-2 is flavor + menu + reversible-undo only.

## Previous Story Intelligence
- Same worktree contract-first flow as 4-1/Epic 3 (zero conflicts). **Spawned agents default to plan mode** → each prompt says "EXECUTE NOW, pre-approved, no EnterPlanMode". Worktrees branch off `main`; contract is inlined per prompt.
- `pytest` runs against an isolated temp DB that is now rebuilt fresh each run (schema changes picked up) — safe to run freely. Baseline 327.
- 4-1 delivered `FreeActionSystem`/`VALID_FREE_ACTIONS`/`VALID_SUCCESSION_LAWS`, the `/free_action` route, and `DynastyDB.designated_heir_id`/`succession_law`. 4-1 chronicle is deterministic; 4-2 makes it flavored (fallback == old behavior).
- **This story has a visual surface → run-the-app screenshot check before done (AC7).**

## References
- FreeActionSystem (4-1): `models/free_action_system.py` (`_append_chronicle` ~103, handlers ~120+); `VALID_FREE_ACTIONS` ~33.
- `/free_action` route (4-1): `blueprints/dynasty.py:593`.
- LLM flavor pattern: `utils/llm_prompts.py:223` (build_multigen prompt + fallback); guarded call `models/project_system.py:81-102`.
- Context menu (Story 3-2): `templates/world_map.html` `_populateMenu`/`_renderRow`/`#ctx-rows` (~1159-1240); project catalogue endpoint `blueprints/map.py:219`.
- Toast/XHR pattern (Story 3-5): `templates/world_map.html` `turn-toast-stack` + `X-Requested-With` fetch.
- Test fixture: `tests/integration/test_detail_panel_render.py:13-39`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] — 3 parallel worktree sub-agents (backend / frontend / tests) against a frozen contract, + main-session integrator.

### Completion Notes List

- All 7 ACs satisfied. `pytest -p no:randomly`: **334 passed, 0 failed, 0 skipped** (327 baseline + 7). Contract-first: C's 7 tests failed in isolation (404 + missing markers), green on integration (19 free-action tests total).
- Agents: A `wt/4-2-backend` (`abdebb2`) — `build_free_action_flavor_prompt`/`generate_free_action_flavor_fallback` in llm_prompts; `_build_flavor` in FreeActionSystem (guarded LLM, ≤150 tok, error→fallback); `last_undo_token` capture (flush for history id) + `undo_free_action`; `free_action_catalogue.json` + `free_action/undo` routes + session-stack push. B `wt/4-2-frontend` (`713d3b1`) — `.ctx-free-actions` "Decisions" menu section + `#free-action-undo-btn`, XHR POSTs, toasts. C `wt/4-2-tests` (`268ddcc`) — 7 tests. Clean merges, zero file overlap.
- `perform_free_action` return kept `(ok, message)`; undo token exposed via `last_undo_token` attr → 4-1 contract + tests intact.
- **AC7 visual + live verification (Epic 3 retro lesson):** ran the app (headless Chrome) — right-click menu shows PROJECTS + a separated DECISIONS section with all 9 free actions (diplomacy ones marked `→`). Live undo round-trip confirmed: `hold_feast` 100→70 gold/+5 prestige, then `/free_action/undo` restored 70→... wait 40→70/−5 — i.e. fully reversed via the session stack. (An initial curl-only undo "failure" was a test-harness cookie bug on my side, not the app.)
- **Integration note (git):** the three `wt/4-2-*` merges landed directly on `main` (rather than the `feature/free-action-llm-ui` branch, which held only the spec commit); main carries the full tested 4-2 work. The spec doc was consolidated onto main during finalization; the stale feature branch was deleted.

### File List

- `utils/llm_prompts.py` — MODIFIED (free-action flavor prompt + fallback)
- `models/free_action_system.py` — MODIFIED (flavor wiring + last_undo_token + undo_free_action)
- `blueprints/dynasty.py` — MODIFIED (free_action_catalogue.json + free_action/undo routes + session-stack push)
- `templates/world_map.html` — MODIFIED (Decisions menu section + undo control + toasts)
- `static/style.css` — MODIFIED (free-actions section + undo control styles)
- `tests/integration/test_free_action_ui_and_undo.py` — NEW (7 tests)
- `_bmad-output/implementation-artifacts/{4-2-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED

### Change Log

| Date | Change |
|---|---|
| 2026-05-30 | spec(4-2) committed; 3 worktree agents built backend/frontend/tests in parallel |
| 2026-05-30 | merged all three (clean); 334 passed |
| 2026-05-30 | AC7 visual check (menu screenshot) + live undo round-trip verified |
| 2026-05-30 | Story 4-2 → done; Epic 4 complete |
