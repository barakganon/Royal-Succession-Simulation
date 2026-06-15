# Epic L-1 — Espionage System: Design Note

Date: 2026-06-15 · Author: Opus (design pass with Barakganon)
Status: design locked — ready to spec L-1

## Goal
A dynasty espionage system: dispatch a court member as a spy on a multi-turn mission — **assassinate** (actually kill a target person), **sabotage** (damage an enemy building), or **intel** (reveal hidden enemy info) — with success driven by the agent's `espionage_skill` vs. the target's defense, and infamy/honor/relation consequences on detection.

## Locked decisions (Project Lead, 2026-06-15)
1. **Resolution model:** dispatched **multi-turn missions** — reuse the **Project system** (slot-consuming, resolves on completion). NOT instant.
2. **Operative:** a **court member** (living `PersonDB` of the actor dynasty) is the agent; their `espionage_skill` (0–20, currently unused) drives odds. Risked on failure.
3. **Sabotage target:** an enemy **Building** (condition damage / destruction).
4. **Consolidation:** the new `EspionageSystem` **owns assassination** (real death + skill); the existing shallow `DiplomacySystem.perform_diplomatic_action("assassinate")` is removed/redirected so there's one implementation.

## Why no schema change
- **Missions = Project rows** (existing `project` table): new project types + completion effects. Targets use existing `Project` columns (`target_person_id`, `target_territory_id`, `target_dynasty_id`) + `params_json` (agent id, building id).
- **Assassination** sets `PersonDB.death_year` (column exists).
- **Intel reports** = `HistoryLogEntryDB` rows (`event_type='intel_report'`, the report text in `event_string`) — no new table.
- (A richer `EspionageReportDB` could come later via Alembic if needed — explicitly deferred.)

## Existing state being consolidated
- `PersonDB.espionage_skill` (0–20) — exists, **currently unused** → this design activates it.
- `DiplomacySystem.perform_diplomatic_action(actor, target, "assassinate")` (`models/diplomacy_system.py:300-356`): flat 30% chance, **no skill**, and on "success" only logs — a code comment admits it never kills anyone. Infamy/honor/relation handled on failure. **To be replaced.** Also the `"assassinate"` entries in the action tables (`:42`, `:162`, `:184`) and any caller/template (diplomacy blueprint/template) must be repointed to the espionage dispatch.
- Chronicle already weights `successful_assassination` (10) / `failed_assassination` (6); add `intel_report`/`sabotage` weights to `chronicle_compiler.EVENT_WEIGHTS`.

## Architecture

### `models/espionage_system.py` (new) — `EspionageSystem(session)`
- `MISSION_TYPES`: `espionage_assassinate`, `espionage_sabotage`, `espionage_intel` — each with `duration_years`, `gold_cost`, and base success.
- `dispatch_mission(actor_dynasty_id, mission_type, agent_person_id, target_dynasty_id, *, target_person_id=None, target_territory_id=None, building_id=None) -> (ok, msg)`:
  - Validate: agent is a living member of the actor dynasty; target is a valid enemy; gold affordable; required target present for the mission type.
  - Start a **Project** via `ProjectSystem.start_project(actor_dynasty_id, '<mission_type>', current_year, target_dynasty_id=..., target_person_id=..., target_territory_id=..., params={'agent_person_id':..., 'building_id':...}, duration_years=..., yearly_cost_gold=...)`. (Reuses the 11-5 override hook.)
  - The **roll happens at completion**, not dispatch (suspense).
- `resolve_mission(project) -> (success, detected)` called from the project completion effect:
  - `success_chance = base[mission] + agent.espionage_skill*0.04 − target_defense` where `target_defense = max espionage_skill among target dynasty's living members * 0.03` (+ fortification level for sabotage). Clamp [0.05, 0.95]. Agent may be dead/missing by completion → low/zero skill.
  - **Assassinate:** success → `target_person.death_year = current_year`; emit `successful_assassination` (actor only — target doesn't learn it was murder); actor `infamy += 10`. Failure → actor `infamy += 20`, `honor -= 10`, relation −50, both sides logged `failed_assassination`; **agent may be captured/killed** (set agent `death_year` on a detection sub-roll).
  - **Sabotage building:** success → drop `building.condition` sharply or remove the building; emit `sabotage` event. Failure → infamy/relation penalty + detection log.
  - **Intel:** success → build a report of the target's hidden state (gold/iron/timber, living army count + sizes, active projects, key relations, heir) → write a `HistoryLogEntryDB(event_type='intel_report', event_string=<report>)` for the actor; flash/link it. Failure → minor relation penalty, no info.
- All DB writes in try/except + rollback; logger `royal_succession.espionage`.

### `models/project_system.py` (extend)
- Add the three `espionage_*` entries to `PROJECT_TYPE_CATALOGUE` (slot: True; baseline duration/cost overridden at dispatch).
- Add completion effects `_effect_espionage_assassinate/_sabotage/_intel` that **delegate to `EspionageSystem(session).resolve_mission(project)`** (keep resolution logic in EspionageSystem; the effect is a thin adapter). Register in `EFFECT_DISPATCHER`.

### `blueprints/espionage.py` (new) — `espionage_bp`
- `GET /dynasty/<id>/espionage` (`@login_required`, authz): show active espionage missions + a dispatch form (mission type, target dynasty, target person/territory/building as applicable, choose agent from living court members with their espionage_skill), and recent intel reports.
- `POST /dynasty/<id>/espionage/dispatch`: validate + `EspionageSystem(db.session).dispatch_mission(...)`; flash result.
- Register the blueprint in `main_flask_app.py` (the ONE allowed edit type there).
- Entry point: a link from the diplomacy page and/or a left-rail button.

### `templates/espionage.html`
- Extends `base.html`. Dispatch form + active-missions list (mission, target, turns remaining) + intel-report cards. Serialize data (no raw ORM to template).

### LLM flavor (optional, guarded)
- Optional `build_espionage_flavor_prompt` + `generate_espionage_fallback` in `utils/llm_prompts.py` for the resolution chronicle line (mirrors free-action flavor); deterministic fallback so LLM-off works. Can be deferred to a follow-up if scope is tight.

## Suggested defaults (tune freely)
| Mission | duration | gold | base success |
|---|---|---|---|
| intel | 1 yr | 50 | 0.55 |
| sabotage | 2 yr | 120 | 0.40 |
| assassinate | 3 yr | 250 | 0.30 |
- `espionage_skill` adds +0.04/point (max +0.80 at 20); target's best counter-spy subtracts ~0.03/point; sabotage also subtracts fortification.

## Scope / sequencing
L-1 is large (system + project wiring + blueprint + template + diplomacy consolidation + tests). **Recommend splitting into two stories when we spec it:**
- **L-1a — EspionageSystem + project wiring + diplomacy consolidation + unit tests** (pure backend, fully testable; the risk-heavy core).
- **L-1b — blueprint + template + main_flask_app registration + integration tests + live run-the-app check** (the UI).
Both single Sonnet subagents on live `main` (no worktree), sequential, per the Epic 11 retro policy. No schema change → no Alembic.

## Out of scope (deferred)
- Agent "busy/locked" while on a mission (v1 allows reuse); counter-espionage missions; spy networks/levels; an `EspionageReportDB` table (intel rides on HistoryLogEntryDB for now); espionage buildings.

## References
- `models/diplomacy_system.py:300-356` (assassinate to replace) + action tables `:42/:162/:184`.
- `models/project_system.py` (PROJECT_TYPE_CATALOGUE, start_project + 11-5 override hook, EFFECT_DISPATCHER, `_effect_build_building` as the delegate pattern).
- `models/db_models.py`: `PersonDB.espionage_skill`/`death_year`, `Project` (target_*/params_json), `Building.condition`, `HistoryLogEntryDB`.
- `models/chronicle_compiler.py` EVENT_WEIGHTS (add sabotage/intel_report).
- Free-action flavor pattern: `utils/llm_prompts.py` `build_free_action_flavor_prompt`.

## Next step
`create story L-1a` (EspionageSystem + project wiring + diplomacy consolidation) from this design, then L-1b (UI). Epic L is already in-progress.
