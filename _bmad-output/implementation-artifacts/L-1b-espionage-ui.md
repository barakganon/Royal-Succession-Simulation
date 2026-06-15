# Story L-1b: Espionage UI (blueprint + template + registration)

Status: ready-for-dev

## Story
As a **player**,
I want **an espionage page where I pick a court agent and dispatch assassinate / sabotage / intel missions against rivals, and see my active missions and intel reports**,
so that **the L-1a espionage backend is actually playable.**

This is the **UI half** of Epic L-1 (backend = Story L-1a, done). Design: `_bmad-output/implementation-artifacts/epic-L-1-espionage-design.md`. No schema change.

## Backend already available (L-1a — do not reimplement)
- `models/espionage_system.py`: `EspionageSystem(session).dispatch_mission(actor_dynasty_id, mission_type, agent_person_id, target_dynasty_id, *, target_person_id=None, target_territory_id=None, building_id=None) -> (ok: bool, msg: str)` — validates everything, never raises, returns `(False, reason)` on any problem. `mission_type ∈ {'espionage_intel','espionage_sabotage','espionage_assassinate'}`.
- Active missions are `Project` rows with `project_type` starting `espionage_` — get them via `ProjectSystem(session).get_active_projects(dynasty_id)` and filter. Intel reports are `HistoryLogEntryDB` rows with `event_type='intel_report'`.

## Acceptance Criteria

1. **AC1 — Blueprint.** New `blueprints/espionage.py` defining `espionage_bp = Blueprint('espionage', __name__)`. Mirror the structure/conventions of `blueprints/diplomacy.py`.

2. **AC2 — Espionage page route.** `GET /dynasty/<int:dynasty_id>/espionage` (`@login_required`; authz: if `dynasty.user_id != current_user.id` → flash `"warning"` + redirect `auth.dashboard`). Assemble **serialized** data (dicts/lists, never raw ORM to the template):
   - `agents`: living members of THIS dynasty (`PersonDB.dynasty_id==id, death_year is None`) → `{id, name, espionage_skill}` (so the player picks a spy and sees their skill).
   - `enemy_dynasties`: other dynasties → `{id, name}`.
   - `enemy_targets`: per enemy dynasty, its living nobles (for assassinate) → `{dynasty_id, persons:[{id,name}]}`; and its buildings (for sabotage) → `{dynasty_id, buildings:[{id, name, territory_name}]}` (Building via territories the dynasty controls).
   - `active_missions`: this dynasty's active `espionage_*` projects → `{mission_type, target_dynasty_name, completion_year, years_remaining}`.
   - `intel_reports`: this dynasty's `intel_report` HistoryLogEntryDB rows (most recent first) → `{year, text}`.
   - `mission_costs`: from `EspionageSystem.MISSION_TYPES` (label, duration, gold) for display.
   - `render_template('espionage.html', dynasty=<serialized minimal>, ...)`.

3. **AC3 — Dispatch route.** `POST /dynasty/<int:dynasty_id>/espionage/dispatch` (`@login_required` + same authz + `@block_if_turn_processing` if that decorator is used by sibling mutating routes). Read `mission_type`, `agent_person_id`, `target_dynasty_id`, and the optional `target_person_id`/`building_id` from the form; call `EspionageSystem(db.session).dispatch_mission(...)`; flash the returned message (`"success"` if ok else `"warning"`); wrap in try/except → `db.session.rollback()` + flash `"danger"` on unexpected error; redirect back to `espionage.espionage_view`.

4. **AC4 — Template.** `templates/espionage.html` extends `base.html`. Sections:
   - **Dispatch** — three mission forms (Assassinate / Sabotage / Intel), each POSTing to the dispatch route with the right hidden `mission_type` and the appropriate selectors: an **agent** `<select>` (showing each agent's name + espionage_skill) on all three; a **target dynasty** `<select>` on all; a **target person** `<select>` for assassinate; a **building** `<select>` for sabotage. Show each mission's cost/duration from `mission_costs`. Must work **server-rendered without requiring JS** (it's fine if all enemy persons/buildings are rendered and the player picks a matching dynasty+target; keep it simple — no AJAX dependency).
   - **Active Missions** — list `active_missions` (mission, target, years remaining).
   - **Intel Reports** — cards/list of `intel_reports` (year + text).
   - Use `url_for(...)`, flash via base.html, medieval theme (extend base, don't override fonts/vars).

5. **AC5 — Registration + entry point.** Register `espionage_bp` in `main_flask_app.py` (the one allowed edit type there — mirror lines ~87-96). Add an entry link to the espionage page from the **diplomacy page** (`templates/diplomacy*.html`) and/or the world-map left rail — a "🗡️ Espionage" link via `url_for('espionage.espionage_view', dynasty_id=...)`.

6. **AC6 — Integration tests.** `tests/integration/test_espionage_routes.py`:
   - Espionage page: 200 for owner; contains the dispatch form + an agent option; non-owner → 302/denied.
   - Dispatch POST (owner) with valid intel mission (target = another dynasty) → redirect + success flash + an `espionage_intel` Project now exists for the dynasty. (Ensure the dynasty has a living monarch + funds in the fixture — `start_project` needs them.)
   - Dispatch POST with an invalid mission (e.g. missing required target for assassinate) → redirect + warning flash, no Project created.
   - Unauthenticated → redirect to login.
   Use existing integration fixtures (`tests/integration/conftest.py`, `dynasty_client`/`plain_client` per `test_dynasty_routes.py`); set up a second dynasty as the target.

7. **AC7 — No regressions + live check.** Full suite green (baseline **620 passed**, 0 failed, 0 skipped) + new tests. `python -c "import main_flask_app"` clean. Boot on 8091; authenticated GET `/dynasty/<id>/espionage` renders 200 with the dispatch forms, and a dispatch POST flashes success (per Epic 3 retro — real run-the-app check for a UI feature). No new deps, no schema change.

## Tasks
- [ ] Task 1 — `blueprints/espionage.py`: page route (serialized data) + dispatch route (AC2, AC3).
- [ ] Task 2 — `templates/espionage.html` (three dispatch forms + active missions + intel reports) (AC4).
- [ ] Task 3 — register blueprint + entry link (AC5).
- [ ] Task 4 — integration tests (AC6).
- [ ] Task 5 — pytest 620+new green; import clean; live espionage page + dispatch on 8091 (AC7).

## Dev Notes
- **Do NOT touch espionage resolution logic** — L-1a owns `dispatch_mission`/`resolve_mission`. This story only calls `dispatch_mission` and reads Projects/HistoryLog for display.
- **Serialize before template** (project rule): build plain dicts/lists; never pass raw ORM objects. Mirror how `blueprints/economy.py`/`diplomacy.py` prep data.
- **`@login_required` on both routes**; flash categories `success|danger|info|warning` only; `url_for('espionage.func')` everywhere; `db.get_or_404`/`db.session.get` (SA 2.0), no legacy `.query.get()`. Check whether sibling mutating routes use `@block_if_turn_processing` (from `blueprints/dynasty.py`) and apply it to the dispatch route for consistency.
- **Blueprint registration ONLY in `main_flask_app.py`** (keep it ≤ ~300 lines; app-setup region). Logger `royal_succession.espionage` or a UI-specific one.
- `ProjectSystem(session).get_active_projects(dynasty_id)` (`models/project_system.py:502`) → filter `project_type.startswith('espionage_')`; `years_remaining = completion_year - dynasty.current_simulation_year`.
- **Self-contained UI story → single Sonnet subagent on live `main` (no worktree)** per Epic 11 retro policy.
- Out of scope: optional LLM flavor on resolution; richer JS target-filtering; an intel-report detail page. v1 keeps it server-rendered.

## References
- Backend: `models/espionage_system.py` (`dispatch_mission`, `MISSION_TYPES`), `models/project_system.py` (`get_active_projects` :502, `espionage_*` types).
- Blueprint pattern: `blueprints/diplomacy.py` (Blueprint, system import, render). Registration: `main_flask_app.py:87-96`.
- `templates/diplomacy*.html` / `economy*.html` for the action-page + form idiom; `base.html` for theme.
- Authz/turn-lock: `blueprints/dynasty.py` (`@block_if_turn_processing`).
- `models/db_models.py`: PersonDB, DynastyDB, Building/Territory, HistoryLogEntryDB, Project.
- Design: `_bmad-output/implementation-artifacts/epic-L-1-espionage-design.md`.

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-15 | spec(L-1b); espionage blueprint + template + registration + integration (ready-for-dev) |
