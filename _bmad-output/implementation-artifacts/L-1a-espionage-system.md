# Story L-1a: Espionage System (backend) + Project wiring + Diplomacy consolidation

Status: ready-for-dev

## Story
As a **scheming dynasty**,
I want **to dispatch a court member as a spy on a multi-turn mission (assassinate / sabotage / intel) that resolves through the Project system**,
so that **`espionage_skill` finally matters, assassination actually kills, and there is one assassination implementation.**

This is the **backend half** of Epic L-1 (design: `_bmad-output/implementation-artifacts/epic-L-1-espionage-design.md`). The blueprint/template/UI is Story **L-1b**. **No schema change** — missions ride on the `Project` table; intel reports ride on `HistoryLogEntryDB`.

## Acceptance Criteria

1. **AC1 — `EspionageSystem(session)`** in new `models/espionage_system.py`. Subsystem class taking `session: Session` only. Logger `royal_succession.espionage`. Constant `MISSION_TYPES` mapping the three mission keys to defaults:
   | key | duration_years | gold_cost | base_success |
   |---|---|---|---|
   | `espionage_intel` | 1 | 50 | 0.55 |
   | `espionage_sabotage` | 2 | 120 | 0.40 |
   | `espionage_assassinate` | 3 | 250 | 0.30 |

2. **AC2 — `dispatch_mission(...)`.** `dispatch_mission(actor_dynasty_id, mission_type, agent_person_id, target_dynasty_id, *, target_person_id=None, target_territory_id=None, building_id=None) -> (ok: bool, msg: str)`:
   - Validate: `mission_type in MISSION_TYPES`; agent is a **living** `PersonDB` of `actor_dynasty_id`; `target_dynasty_id` exists and != actor; the mission's required target is present — assassinate→`target_person_id` (a living person of the target dynasty), sabotage→`building_id` (a Building in a territory the target controls), intel→just `target_dynasty_id`.
   - Affordability handled by `start_project` (gold). On failure return `(False, <reason>)` — do NOT raise to the caller.
   - Start a **Project** via `ProjectSystem(self.session).start_project(actor_dynasty_id, mission_type, <current year of actor dynasty>, target_dynasty_id=target_dynasty_id, target_person_id=target_person_id, target_territory_id=target_territory_id, params={'agent_person_id': agent_person_id, 'building_id': building_id}, duration_years=MISSION_TYPES[mission_type]['duration_years'], yearly_cost_gold=MISSION_TYPES[mission_type]['gold_cost'])`. Catch `InsufficientResourcesError`→`(False, "Cannot afford this mission")`, `ValueError` (no living monarch / bad dynasty)→`(False, <message>)`.
   - The success roll happens at **resolution (completion)**, NOT now. Return `(True, "Dispatched <mission> against <target dynasty> (resolves in <n> years)")`.

3. **AC3 — `resolve_mission(project) -> (success: bool, detected: bool)`.** Called from the completion effects (AC4). Logic:
   - Load agent from `params_json['agent_person_id']` (may be dead/missing → effective skill 0). `agent_skill = agent.espionage_skill if agent and agent.death_year is None else 0`.
   - `target_defense = 0.03 * max(espionage_skill of target dynasty's LIVING members, default 0)`; for sabotage also `+ 0.05 * <fortification_level of the target territory>` if available.
   - `success_chance = clamp(base_success + 0.04*agent_skill − target_defense, 0.05, 0.95)`; `success = random.random() < success_chance`.
   - **Assassinate:** success → set `target_person.death_year = <current year>`; log `successful_assassination` for the actor only (target doesn't learn it was murder); actor `infamy += 10`. Failure → actor `infamy += 20`, `honor -= 10`, relation −50 (use the existing relation update path), log `failed_assassination` for BOTH dynasties; on a detection sub-roll, the **agent is caught**: set `agent.death_year = <current year>`.
   - **Sabotage:** success → halve the target `Building.condition` (or remove the building if condition would drop below a threshold); log `sabotage` for the actor. Failure → actor `infamy += 10`, relation −20, log `sabotage` (discovered) for both.
   - **Intel:** success → assemble a report of the target dynasty's hidden state (current_wealth/iron/timber, count + sizes of living armies, active project types, top relations, current monarch + heir) and write a `HistoryLogEntryDB(dynasty_id=actor, year=<current>, event_type='intel_report', event_string=<report text>)`. Failure → relation −10, no report.
   - Wrap mutations in try/except + `self.session.rollback()` on error; never raise out of resolution (a failed effect must not crash turn processing). Return `(success, detected)`.

4. **AC4 — Project wiring** (`models/project_system.py`): add `espionage_intel`/`espionage_sabotage`/`espionage_assassinate` to `PROJECT_TYPE_CATALOGUE` (baseline duration/cost — overridden at dispatch; `slot: True`, `requires_building: None`). Add three thin completion effects `_effect_espionage_intel/_sabotage/_assassinate(session, project)` that **delegate to `EspionageSystem(session).resolve_mission(project)`** (keep all logic in EspionageSystem; the effect is an adapter — match the existing `def _effect_x(session, project) -> None` signature). Register all three in `EFFECT_DISPATCHER`.

5. **AC5 — Diplomacy consolidation** (`models/diplomacy_system.py`): remove the shallow `elif action_type == "assassinate":` branch (~:300-356) and the `"assassinate"` entries in the action tables (~:42, :162, :184). Add an explicit early guard in `perform_diplomatic_action`: if `action_type == "assassinate"` → `return (False, "Assassination is handled by the Espionage system.")` (so the generic `/diplomatic_action` route can't silently treat it as a normal relation action). Verify no other caller depends on the old behavior (grep `assassinate` over `models/`, `blueprints/`, `templates/`).

6. **AC6 — Chronicle weights** (`models/chronicle_compiler.py`): add `'sabotage'` and `'intel_report'` to `EVENT_WEIGHTS` (e.g. sabotage=8, intel_report=4). `successful_assassination`/`failed_assassination` already weighted.

7. **AC7 — Tests** `tests/unit/test_espionage_system.py`:
   - `dispatch_mission` validation: bad mission type, dead/foreign agent, missing required target, self-target → `(False, ...)`; happy path creates a `Project` of the right type with the agent in `params_json` and override cost/duration applied (no resolution yet).
   - `resolve_mission` per mission, **patching `random.random`** to force success then failure:
     - assassinate success → `target_person.death_year` set + actor infamy up; failure → infamy/honor/relation penalties + both-side logs (+ agent death on forced detection).
     - sabotage success → building condition reduced/removed; failure → penalty + log.
     - intel success → an `intel_report` `HistoryLogEntryDB` row exists for the actor with the target's data; failure → no report + relation penalty.
   - skill effect: higher `agent.espionage_skill` raises `success_chance` (assert the computed chance, or that a borderline roll flips) ; dead/missing agent → skill treated as 0.
   - Diplomacy guard: `perform_diplomatic_action(a, b, "assassinate")` → `(False, ...)` mentioning espionage.
   - Use existing unit fixtures (see `tests/unit/test_project_system.py` for `_make_user_and_dynasty`, monarch creation — `start_project` needs a living monarch). No HTTP.

8. **AC8 — No regressions.** Full suite green (baseline **599 passed**, 0 failed, 0 skipped) + new tests. `python -c "import main_flask_app"` clean. No new deps, no schema change, no Alembic.

## Tasks
- [ ] Task 1 — `EspionageSystem`: `MISSION_TYPES`, `dispatch_mission` (AC1, AC2).
- [ ] Task 2 — `resolve_mission` + per-mission resolution (assassinate/sabotage/intel) (AC3).
- [ ] Task 3 — project catalogue entries + 3 delegating effects + EFFECT_DISPATCHER (AC4).
- [ ] Task 4 — diplomacy consolidation: remove branch + table entries, add guard (AC5); chronicle weights (AC6).
- [ ] Task 5 — unit tests, patching random (AC7).
- [ ] Task 6 — pytest 599+new green; import clean (AC8).

## Dev Notes
- **Reuse `start_project`'s override hook** (added in Story 11-5): `start_project(..., duration_years=, yearly_cost_gold=, ...)` overrides the catalogue per instance. The catalogue still needs a baseline entry per AC4.
- **Resolution roll is at COMPLETION** (in the effect), giving suspense — not at dispatch.
- **Effect = thin adapter.** `_effect_espionage_*` just calls `EspionageSystem(session).resolve_mission(project)`; all logic stays in EspionageSystem (cohesion + testability). complete_project invokes `EFFECT_DISPATCHER[project.project_type]` (`models/project_system.py:586`).
- **Never raise out of `resolve_mission`** — a throwing completion effect would break `tick_projects`/turn processing. Catch, rollback, log, return.
- **Relations:** mirror how the old assassinate applied penalties (it used a relation object's `update_relation(...)` and adjusted `infamy`/`honor` on the dynasty). Reuse the same relation lookup the diplomacy system uses.
- **Agent reuse not locked** in v1 (an agent can run multiple missions) — design-deferred; don't add a lock.
- SA 2.0 conventions: `session.get(Model, id)`, `Model.query.filter(...)`, no legacy `.query.get()`. DB writes try/except + rollback. No `print()`. `params_json` is JSON text — `json.dumps`/`json.loads`.
- **Self-contained backend → single Sonnet subagent on live `main` (no worktree)** per Epic 11 retro policy.
- Out of scope (→ L-1b): `blueprints/espionage.py`, `templates/espionage.html`, `main_flask_app` registration, integration tests, live UI check, optional LLM flavor line.

## References
- Design: `_bmad-output/implementation-artifacts/epic-L-1-espionage-design.md`.
- `models/project_system.py`: `start_project` + override block (~:384-400), `_effect_build_building` (~:358, the delegate/Building pattern), `EFFECT_DISPATCHER` (~:428), `complete_project` (~:564-586), `PROJECT_TYPE_CATALOGUE`.
- `models/diplomacy_system.py`: assassinate branch (~:300-356), action tables (~:42/:162/:184), `perform_diplomatic_action` (~:219), relation `update_relation`.
- `models/db_models.py`: `PersonDB.espionage_skill`/`death_year`, `Project` (target_person_id/target_territory_id/target_dynasty_id/params_json), `Building.condition`, `Territory.fortification_level`, `HistoryLogEntryDB`, `MilitaryUnit`/`Army`.
- `models/chronicle_compiler.py`: `EVENT_WEIGHTS`.
- `tests/unit/test_project_system.py`: fixtures + monarch creation patterns.

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-15 | spec(L-1a); EspionageSystem + project wiring + diplomacy consolidation (ready-for-dev) |
