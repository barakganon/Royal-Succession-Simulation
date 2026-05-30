# Story 4-1: Free Action Endpoint + Dispatcher

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player on the world map,
I want instant "free actions" (declare war, propose treaty, send envoy, issue ultimatum, name heir, adopt succession law, hold feast, hold tournament, pardon vassal) that apply immediately and append a chronicle line **without** ending my turn,
so that decisions are distinguished from slot-consuming multi-year project commitments (the Epic 4 goal).

## Acceptance Criteria

1. **AC1 — New `FreeActionSystem` (`models/free_action_system.py`).** Class `FreeActionSystem` with constructor `__init__(self, session: Session)` (session is the ONLY arg, per project rule). Public method:
   `perform_free_action(self, dynasty_id: int, action_type: str, params: dict) -> tuple[bool, str]` → `(ok, message)`.
   - Module constant `VALID_FREE_ACTIONS` = the 9 exact strings: `declare_war`, `propose_treaty`, `send_envoy`, `issue_ultimatum`, `name_heir`, `adopt_succession_law`, `hold_feast`, `hold_tournament`, `pardon_vassal`.
   - Unknown `action_type` → `(False, "Unknown free action: <type>")`, no state change.
   - **Never ticks the turn** — must NOT modify `dynasty.current_simulation_year` or call any turn/lifecycle processing.
   - On success, appends exactly one chronicle line (AC4) and commits via the route (the system mutates the session; the route owns commit/rollback — see AC5). Actually the system performs its writes on the session and returns; the route commits. Do not commit inside the system (keeps it testable and lets the route roll back atomically).

2. **AC2 — Diplomatic actions delegate to the existing `DiplomacySystem`** (do NOT reimplement):
   - `declare_war` → `DiplomacySystem(session).declare_war(attacker_dynasty_id=dynasty_id, defender_dynasty_id=params['target_dynasty_id'], ...)`.
   - `propose_treaty` → `DiplomacySystem.create_treaty(dynasty1_id=dynasty_id, dynasty2_id=params['target_dynasty_id'], treaty_type=<from params, default a sensible TreatyType>, ...)`.
   - `send_envoy` / `issue_ultimatum` → `DiplomacySystem.perform_diplomatic_action(actor_dynasty_id=dynasty_id, target_dynasty_id=params['target_dynasty_id'], action_type=action_type, ...)`.
   - Normalize each system's return (`(ok,msg)` or `(ok,msg,obj)`) to `(ok, msg)`. Signatures: `models/diplomacy_system.py:198` (perform_diplomatic_action), `:321` (create_treaty), `:506` (declare_war). Missing/invalid `target_dynasty_id` → `(False, "...")`.

3. **AC3 — Five new instant actions** (reuse existing `DynastyDB` fields where possible; minimal schema for the two that need persistence):
   - `name_heir` (params: `heir_person_id`): set `dynasty.designated_heir_id` after validating the person exists, belongs to this dynasty, and is alive (`death_year is None`). Invalid → `(False, ...)`.
   - `adopt_succession_law` (params: `law`): set `dynasty.succession_law` to one of an allowed set (define `VALID_SUCCESSION_LAWS`, e.g. `PRIMOGENITURE_MALE_PREFERENCE`, `PRIMOGENITURE_ABSOLUTE`, `ELECTIVE`, `SENIORITY`); reject others.
   - `hold_feast`: cost a fixed gold amount (e.g. 30) from `dynasty.current_wealth` (reject if unaffordable), `dynasty.prestige += <small>`.
   - `hold_tournament`: cost gold (e.g. 50, reject if unaffordable), larger `prestige` bump than a feast.
   - `pardon_vassal`: `dynasty.honor += <small>` (cap at 100). No cost.
   - Each returns `(True, "<human message>")` on success.

4. **AC4 — Every successful free action appends one chronicle line** via `HistoryLogEntryDB(dynasty_id=dynasty_id, year=dynasty.current_simulation_year, event_string=<deterministic text>, event_type='free_action')` added to the session (same pattern as `models/project_system.py:121`). Deterministic text only (no LLM — LLM flavor is Story 4-2). The `year` is the CURRENT sim year (unchanged — no tick).

5. **AC5 — Route `POST /dynasty/<int:dynasty_id>/free_action` (`blueprints/dynasty.py`).** `@login_required`, `@block_if_turn_processing`. Reads `action_type` + params from `request.form`/`request.get_json()`. Ownership check (`dynasty.owner_user == current_user`) else 403. Calls `FreeActionSystem(db.session).perform_free_action(...)` inside `try/except` with `db.session.rollback()` on error; on `ok` → `db.session.commit()`. Returns JSON `{"ok": bool, "message": str}` (200 on ok, 400 on validation failure / unknown action, 403 non-owner, 409 if turn processing — the decorator handles 409/redirect). The turn's sim year MUST be unchanged after the call.

6. **AC6 — Schema additions + migration.** Add to `DynastyDB` (`models/db_models.py`):
   - `designated_heir_id = db.Column(db.Integer, db.ForeignKey('person_db.id', use_alter=True, name='fk_dynasty_designated_heir'), nullable=True)`
   - `succession_law = db.Column(db.String(40), nullable=True)`
   Add an idempotent migration in `models/db_initialization.py` mirroring the existing `epic_story_text` pattern (`db_initialization.py:144-148`): inspect `dynasty` columns, `ALTER TABLE dynasty ADD COLUMN ...` for each missing column. (Tests get the columns via `db.create_all()`; the migration is for the existing dev DB.)

7. **AC7 — No regressions; tests stay green.** Full suite remains green (current baseline **315**; the new test file is additive). Existing diplomacy/turn tests unaffected. Confirm a free action does NOT advance the sim year.

8. **AC8 — At least 6 new integration tests** in a new file `tests/integration/test_free_action_endpoint.py` (fixture pattern from `tests/integration/test_detail_panel_render.py`; mock LLM if any path touches it — though 4-1 is deterministic):
   - `name_heir` succeeds and sets `designated_heir_id`; invalid heir (not in dynasty / dead) → ok:false.
   - `adopt_succession_law` with a valid law succeeds; invalid law → ok:false.
   - `hold_feast` succeeds, deducts gold, bumps prestige; unaffordable → ok:false.
   - A diplomatic action (e.g. `send_envoy` or `declare_war` against a second dynasty) returns ok:true and delegates (assert via effect / war or relation change).
   - Unknown `action_type` → ok:false / 400.
   - **No-tick invariant:** capture `current_simulation_year` before and after any free action → unchanged; and a `HistoryLogEntryDB` with `event_type='free_action'` was created.
   - Non-owner POST → 403.

## Tasks / Subtasks

- [ ] **Task 1 — `models/free_action_system.py` + schema (AC1–AC4, AC6)** — Agent A.
- [ ] **Task 2 — `POST /free_action` route (AC5)** — Agent B (`blueprints/dynasty.py`).
- [ ] **Task 3 — integration tests (AC8)** — Agent C (new file).

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A (system + schema)** — NEW `models/free_action_system.py`; `models/db_models.py` (+2 DynastyDB columns); `models/db_initialization.py` (idempotent migration). Owns all dispatcher + handler logic + schema. Must keep its own `pytest` green (it has the columns via create_all; the new test file from C is absent in its tree, so its count is the existing total).
- **Agent B (route)** — `blueprints/dynasty.py` only: the `free_action` route calling A's `FreeActionSystem`. Consumes the frozen contract.
- **Agent C (tests)** — ONLY new `tests/integration/test_free_action_endpoint.py`. Contract-first: several tests FAIL in C's isolated worktree (A's system + columns + B's route absent) and go green after integration — do NOT weaken them.
- No two agents touch the same file. (A owns models/* + db_initialization; B owns the blueprint; C owns the new test.)

### FROZEN INTERFACE CONTRACT (exact; C asserts it, A/B emit it)
- System: `from models.free_action_system import FreeActionSystem, VALID_FREE_ACTIONS`; `FreeActionSystem(session).perform_free_action(dynasty_id, action_type, params) -> (ok: bool, message: str)`. Does NOT commit and does NOT tick (`current_simulation_year` untouched). Appends `HistoryLogEntryDB(..., event_type='free_action')` on success.
- Route: `POST /dynasty/<int:dynasty_id>/free_action` → JSON `{"ok": bool, "message": str}`; 403 non-owner; 400 unknown/invalid; commit on ok, rollback on error.
- Params keys: `target_dynasty_id` (diplomatic), `heir_person_id` (name_heir), `law` (adopt_succession_law).
- Schema: `DynastyDB.designated_heir_id` (FK person_db.id, use_alter, name `fk_dynasty_designated_heir`), `DynastyDB.succession_law` (String(40)).
- `VALID_FREE_ACTIONS` = `['declare_war','propose_treaty','send_envoy','issue_ultimatum','name_heir','adopt_succession_law','hold_feast','hold_tournament','pardon_vassal']`.

### Reuse / project rules (project-context.md)
- Subsystem classes take `session: Session` only. DB writes guarded; route owns commit/rollback. `@login_required` + `@block_if_turn_processing` on the route. `current_app.config.get(...)` for any config. DB models suffixed `DB`. Circular FK to PersonDB uses `use_alter=True` (see existing `founder_person_db_id` at `db_models.py:60`). Migration via the `ALTER TABLE` idempotent pattern (`db_initialization.py:144-148`), NOT `create_all` for schema evolution.
- **Do NOT reimplement diplomacy** — delegate to `DiplomacySystem` (`models/diplomacy_system.py`). Don't rewrite working subsystems.
- Effects use EXISTING `DynastyDB` fields: `current_wealth`, `prestige`, `honor`, `infamy`, `piety` (`db_models.py:54,64-67`). Only `designated_heir_id` + `succession_law` are new.

### Out of scope (later stories / deferred)
- **LLM flavor lines, right-click-menu integration, and undo are Story 4-2** — 4-1 is deterministic text + the endpoint only.
- **Map-driven project starts + `.cannot-afford` guard** (deferred since 3-2) are a *separate* concern (projects, not free actions) — NOT in 4-1. Still tracked in `deferred-work.md`.

### Project Structure Notes
- One new model module, one new route, +2 columns + migration, one new test file. No removal of existing routes/systems.

## Previous Story Intelligence (Epic 3 + retro)
- Epic 3 shipped via the worktree contract-first flow with zero merge conflicts — same approach here. **Spawned worktree agents default to plan mode**: each prompt MUST say "EXECUTE NOW — do not enter plan mode, pre-approved." Worktrees branch off `main`, so the story file may be absent in agents' trees — the contract is inlined in each prompt.
- Epic 3 retro lesson: this is backend/endpoint work (no visual surface), so tests are the verification; no run-the-app screenshot needed for 4-1 (4-2 adds UI → that one will need the visual check).
- `pytest` now runs against an isolated temp DB (fixed) — safe to run freely.
- Baseline: run `pytest --collect-only -q` for the current count; require new tests additive (was 315 at Epic 3 close).

## References
- DiplomacySystem: `models/diplomacy_system.py:198` (perform_diplomatic_action), `:321` (create_treaty), `:506` (declare_war)
- Chronicle/history append pattern: `models/project_system.py:121` (`HistoryLogEntryDB(...)`)
- DynastyDB fields (wealth/prestige/honor/...): `models/db_models.py:54,64-67`; circular-FK example: `:60`
- Migration pattern: `models/db_initialization.py:144-148` (epic_story_text ALTER TABLE)
- `@block_if_turn_processing` + advance_turn JSON style: `blueprints/dynasty.py` (Story 3-5 added the XHR/JSON convention)
- Test fixture: `tests/integration/test_detail_panel_render.py:13-39`

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] — 3 parallel worktree sub-agents (system+schema / route / tests) against a frozen contract, + main-session integrator.

### Completion Notes List

- All 8 ACs satisfied. `pytest -p no:randomly`: **327 passed, 0 failed, 0 skipped** (315 baseline + 12). Contract-first: C's 12 tests failed in isolation (404 + missing columns) and went green on integration.
- Agents: A `wt/4-1-system` @ `2ad3f87` (FreeActionSystem dispatcher; delegates declare_war/propose_treaty/send_envoy/issue_ultimatum to DiplomacySystem; new name_heir/adopt_succession_law/hold_feast/hold_tournament/pardon_vassal; +2 DynastyDB columns + idempotent migration). B `wt/4-1-route` @ `1350cea` (POST /free_action, lazy FreeActionSystem import, JSON {ok,message}, 403/400). C `wt/4-1-tests` @ `1ad2f5e` (12 tests). Clean merges, zero file overlap.
- Invariants verified by review + test: FreeActionSystem never commits (route owns it) and never mutates `current_simulation_year` (no tick); each success appends `HistoryLogEntryDB(event_type='free_action')`.
- A's defaults where the contract didn't pin them: `declare_war` → `WarGoal.HUMILIATE`, `propose_treaty` → `TreatyType.NON_AGGRESSION` (overridable via `params['treaty_type']`).
- **Test-infra hardening (integrator):** the persistent temp test DB (`rss_pytest.db`) is now unlinked at the start of each run in the root conftest — SQLite `create_all()` doesn't ALTER existing tables, so a stale temp DB would miss newly-added columns. This generalizes the dev-DB-isolation fix for all future schema changes.
- No regressions; no visual surface (4-1 is backend/endpoint), so per the Epic 3 retro lesson no run-the-app check is needed — Story 4-2 (right-click UI) will need one.

### File List

- `models/free_action_system.py` — NEW (FreeActionSystem dispatcher + VALID_FREE_ACTIONS/VALID_SUCCESSION_LAWS)
- `models/db_models.py` — MODIFIED (DynastyDB.designated_heir_id + succession_law)
- `models/db_initialization.py` — MODIFIED (idempotent ALTER TABLE migration for the 2 columns)
- `blueprints/dynasty.py` — MODIFIED (POST /dynasty/<id>/free_action route)
- `tests/integration/test_free_action_endpoint.py` — NEW (12 tests)
- `tests/conftest.py` — MODIFIED (unlink stale temp test DB per run)
- `_bmad-output/implementation-artifacts/{4-1-...md, sprint-status.yaml}` — MODIFIED

### Change Log

| Date | Change |
|---|---|
| 2026-05-30 | spec(4-1) committed; Epic 4 in-progress |
| 2026-05-30 | wt/4-1-system / wt/4-1-route / wt/4-1-tests built in parallel worktrees |
| 2026-05-30 | merged all three into feature/free-action-endpoint (clean); conftest temp-DB hardening |
| 2026-05-30 | pytest: 327 passed, 0 failed, 0 skipped (was 315) |
| 2026-05-30 | Story 4-1 → done |
