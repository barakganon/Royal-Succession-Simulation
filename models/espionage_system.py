"""EspionageSystem — spy missions dispatched as Projects that resolve on completion.

Story L-1a: backend-only espionage (no blueprints/templates this story).

Three mission types:
  espionage_intel        — gather intelligence on a target dynasty
  espionage_sabotage     — damage a target Building
  espionage_assassinate  — kill a target PersonDB

Missions ride the existing Project table; outcomes are applied by effect adapter
functions wired into project_system.EFFECT_DISPATCHER.
"""

import json
import logging
import random
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from models.db_models import (
    Building, DynastyDB, HistoryLogEntryDB, PersonDB, Territory,
)

logger = logging.getLogger('royal_succession.espionage')

MISSION_TYPES = {
    'espionage_intel': {
        'duration_years': 1,
        'gold_cost': 50,
        'base_success': 0.55,
    },
    'espionage_sabotage': {
        'duration_years': 2,
        'gold_cost': 120,
        'base_success': 0.40,
    },
    'espionage_assassinate': {
        'duration_years': 3,
        'gold_cost': 250,
        'base_success': 0.30,
    },
}


class EspionageSystem:
    """Manages spy mission dispatch and resolution."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # dispatch_mission
    # ------------------------------------------------------------------
    def dispatch_mission(
        self,
        actor_dynasty_id: int,
        mission_type: str,
        agent_person_id: int,
        target_dynasty_id: int,
        *,
        target_person_id: Optional[int] = None,
        target_territory_id: Optional[int] = None,
        building_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Validate inputs and start a Project for the mission.

        Returns (True, message) on success or (False, reason) on any failure.
        Never raises.
        """
        try:
            return self._dispatch_mission_inner(
                actor_dynasty_id=actor_dynasty_id,
                mission_type=mission_type,
                agent_person_id=agent_person_id,
                target_dynasty_id=target_dynasty_id,
                target_person_id=target_person_id,
                target_territory_id=target_territory_id,
                building_id=building_id,
            )
        except Exception as exc:
            logger.error(
                "Unexpected error in dispatch_mission for dynasty %s mission %s: %s",
                actor_dynasty_id, mission_type, exc,
            )
            return False, str(exc)

    def _dispatch_mission_inner(
        self,
        actor_dynasty_id: int,
        mission_type: str,
        agent_person_id: int,
        target_dynasty_id: int,
        *,
        target_person_id: Optional[int],
        target_territory_id: Optional[int],
        building_id: Optional[int],
    ) -> Tuple[bool, str]:
        if mission_type not in MISSION_TYPES:
            return False, f"Unknown mission type: {mission_type!r}"

        actor = self.session.get(DynastyDB, actor_dynasty_id)
        if actor is None:
            return False, f"Actor dynasty {actor_dynasty_id} not found"

        target = self.session.get(DynastyDB, target_dynasty_id)
        if target is None:
            return False, f"Target dynasty {target_dynasty_id} not found"

        agent = self.session.get(PersonDB, agent_person_id)
        if agent is None:
            return False, f"Agent person {agent_person_id} not found"
        if agent.death_year is not None:
            return False, "Cannot dispatch a dead agent"

        if mission_type == 'espionage_assassinate':
            if target_person_id is None:
                return False, "espionage_assassinate requires target_person_id"
            target_person = self.session.get(PersonDB, target_person_id)
            if target_person is None:
                return False, f"Target person {target_person_id} not found"
            if target_person.death_year is not None:
                return False, "Target person is already dead"

        if mission_type == 'espionage_sabotage':
            if building_id is None:
                return False, "espionage_sabotage requires building_id"
            building = self.session.get(Building, building_id)
            if building is None:
                return False, f"Building {building_id} not found"

        meta = MISSION_TYPES[mission_type]
        params = {
            'agent_person_id': agent_person_id,
        }
        if target_person_id is not None:
            params['target_person_id'] = target_person_id
        if building_id is not None:
            params['building_id'] = building_id

        # Import here to avoid module-level circular import
        from models.project_system import InsufficientResourcesError, ProjectSystem
        ps = ProjectSystem(self.session)
        try:
            project = ps.start_project(
                dynasty_id=actor_dynasty_id,
                project_type=mission_type,
                started_year=actor.current_simulation_year,
                target_dynasty_id=target_dynasty_id,
                target_person_id=target_person_id,
                target_territory_id=target_territory_id,
                params=params,
                duration_years=meta['duration_years'],
                yearly_cost_gold=meta['gold_cost'],
                yearly_cost_iron=0,
                yearly_cost_timber=0,
                yearly_cost_food=0,
            )
        except InsufficientResourcesError:
            return False, "Cannot afford this mission"
        except ValueError as exc:
            return False, str(exc)

        duration = meta['duration_years']
        return True, (
            f"Dispatched {mission_type} mission (project {project.id}); "
            f"resolves in {duration} year{'s' if duration != 1 else ''}."
        )

    # ------------------------------------------------------------------
    # resolve_mission
    # ------------------------------------------------------------------
    def resolve_mission(self, project) -> Tuple[bool, bool]:
        """Apply outcome of a completed espionage project.

        Returns (success, detected). Never raises.
        """
        try:
            return self._resolve_mission_inner(project)
        except Exception as exc:
            logger.error(
                "Unexpected error resolving mission project %s: %s",
                project.id if project else None, exc,
            )
            try:
                self.session.rollback()
            except Exception:
                pass
            return False, False

    def _resolve_mission_inner(self, project) -> Tuple[bool, bool]:
        params = {}
        if project.params_json:
            try:
                params = json.loads(project.params_json)
            except Exception:
                params = {}

        actor_dynasty_id = project.dynasty_id
        target_dynasty_id = project.target_dynasty_id
        current_year = project.completion_year or project.started_year

        actor = self.session.get(DynastyDB, actor_dynasty_id)
        if actor is None:
            logger.warning("resolve_mission: actor dynasty %s not found", actor_dynasty_id)
            return False, False

        # Agent skill (0 if missing/dead)
        agent_id = params.get('agent_person_id')
        agent = self.session.get(PersonDB, int(agent_id)) if agent_id is not None else None
        if agent is None or agent.death_year is not None:
            agent_skill = 0
        else:
            agent_skill = agent.espionage_skill or 0

        # Target defence: max espionage_skill among living target-dynasty members
        target_defense = 0.0
        if target_dynasty_id:
            living_members = (
                self.session.query(PersonDB)
                .filter(
                    PersonDB.dynasty_id == target_dynasty_id,
                    PersonDB.death_year.is_(None),
                )
                .all()
            )
            if living_members:
                max_skill = max((m.espionage_skill or 0) for m in living_members)
                target_defense += 0.03 * max_skill

        # For sabotage, also add fortification bonus from target territories
        if project.project_type == 'espionage_sabotage' and target_dynasty_id:
            territories = (
                self.session.query(Territory)
                .filter(Territory.controller_dynasty_id == target_dynasty_id)
                .all()
            )
            if territories:
                avg_fort = sum(t.fortification_level or 0 for t in territories) / len(territories)
                target_defense += 0.05 * avg_fort

        meta = MISSION_TYPES.get(project.project_type, {})
        base_success = meta.get('base_success', 0.30)
        success_chance = base_success + 0.02 * agent_skill - target_defense
        success_chance = max(0.05, min(0.95, success_chance))

        roll = random.random()
        success = roll < success_chance
        detected = False

        logger.info(
            "resolve_mission: project %s type=%s success_chance=%.3f roll=%.3f success=%s",
            project.id, project.project_type, success_chance, roll, success,
        )

        try:
            if project.project_type == 'espionage_assassinate':
                success, detected = self._apply_assassinate(
                    project, params, actor, current_year, success
                )
            elif project.project_type == 'espionage_sabotage':
                success, detected = self._apply_sabotage(
                    project, params, actor, target_dynasty_id, current_year, success
                )
            elif project.project_type == 'espionage_intel':
                success, detected = self._apply_intel(
                    project, actor, target_dynasty_id, current_year, success
                )
            self.session.commit()
        except Exception as exc:
            logger.error(
                "Error applying mission effects for project %s: %s", project.id, exc
            )
            self.session.rollback()
            return False, False

        return success, detected

    # ------------------------------------------------------------------
    # Effect helpers
    # ------------------------------------------------------------------
    def _apply_assassinate(self, project, params, actor, current_year, success):
        detected = False
        target_person_id = params.get('target_person_id') or project.target_person_id
        target_person = (
            self.session.get(PersonDB, int(target_person_id))
            if target_person_id is not None else None
        )
        actor_dynasty_id = project.dynasty_id
        target_dynasty_id = project.target_dynasty_id

        if success and target_person and target_person.death_year is None:
            target_person.death_year = current_year
            actor.infamy = (actor.infamy or 0) + 10
            log = HistoryLogEntryDB(
                dynasty_id=actor_dynasty_id,
                year=current_year,
                event_type='successful_assassination',
                event_string=(
                    f"Our agent successfully assassinated "
                    f"{target_person.name} {target_person.surname or ''}".strip()
                    + "."
                ),
                person1_sim_id=target_person.id,
            )
            self.session.add(log)
            logger.info(
                "Assassination project %s: killed person %s for dynasty %s",
                project.id, target_person.id, actor_dynasty_id,
            )
        else:
            # Failed assassination
            actor.infamy = (actor.infamy or 0) + 20
            actor.honor = (actor.honor or 0) - 10
            self._update_relation(actor_dynasty_id, target_dynasty_id, -50)
            target = self.session.get(DynastyDB, target_dynasty_id)
            actor_log = HistoryLogEntryDB(
                dynasty_id=actor_dynasty_id,
                year=current_year,
                event_type='failed_assassination',
                event_string=(
                    f"Our assassination attempt against "
                    f"{(target.name if target else 'the target dynasty')} was discovered!"
                ),
            )
            self.session.add(actor_log)
            if target_dynasty_id:
                target_log = HistoryLogEntryDB(
                    dynasty_id=target_dynasty_id,
                    year=current_year,
                    event_type='failed_assassination',
                    event_string=(
                        f"We uncovered an assassination plot by {actor.name}!"
                    ),
                )
                self.session.add(target_log)
            detected = True
            # Detection sub-roll: agent may die
            if random.random() < 0.4:
                agent_id = params.get('agent_person_id')
                if agent_id is not None:
                    agent = self.session.get(PersonDB, int(agent_id))
                    if agent and agent.death_year is None:
                        agent.death_year = current_year
                        logger.info(
                            "Assassinate project %s: agent %s captured/killed",
                            project.id, agent.id,
                        )
        return success, detected

    def _apply_sabotage(self, project, params, actor, target_dynasty_id, current_year, success):
        detected = False
        building_id = params.get('building_id')
        building = (
            self.session.get(Building, int(building_id))
            if building_id is not None else None
        )
        actor_dynasty_id = project.dynasty_id

        if success and building:
            # Building.condition is a 0.0-1.0 float. Halve it; if it falls below
            # 10% the building is wrecked beyond use and removed (so repeated
            # sabotage eventually destroys it: 1.0 → 0.5 → 0.25 → 0.125 → 0.06 → gone).
            old_condition = building.condition or 0
            building.condition = old_condition / 2.0
            if building.condition < 0.1:
                self.session.delete(building)
                logger.info(
                    "Sabotage project %s: building %s destroyed (condition < 0.1)",
                    project.id, building_id,
                )
            log = HistoryLogEntryDB(
                dynasty_id=actor_dynasty_id,
                year=current_year,
                event_type='sabotage',
                event_string=(
                    f"Our agents successfully sabotaged a building in "
                    f"the enemy territory."
                ),
            )
            self.session.add(log)
        else:
            actor.infamy = (actor.infamy or 0) + 10
            self._update_relation(actor_dynasty_id, target_dynasty_id, -20)
            target = self.session.get(DynastyDB, target_dynasty_id)
            actor_log = HistoryLogEntryDB(
                dynasty_id=actor_dynasty_id,
                year=current_year,
                event_type='sabotage',
                event_string=(
                    f"Our sabotage mission against "
                    f"{(target.name if target else 'the enemy')} was discovered!"
                ),
            )
            self.session.add(actor_log)
            if target_dynasty_id:
                target_log = HistoryLogEntryDB(
                    dynasty_id=target_dynasty_id,
                    year=current_year,
                    event_type='sabotage',
                    event_string=(
                        f"We discovered a sabotage plot by {actor.name}!"
                    ),
                )
                self.session.add(target_log)
            detected = True
        return success, detected

    def _apply_intel(self, project, actor, target_dynasty_id, current_year, success):
        detected = False
        actor_dynasty_id = project.dynasty_id

        if success:
            target = self.session.get(DynastyDB, target_dynasty_id) if target_dynasty_id else None
            if target:
                # Gather intel
                living_members = (
                    self.session.query(PersonDB)
                    .filter(
                        PersonDB.dynasty_id == target_dynasty_id,
                        PersonDB.death_year.is_(None),
                    )
                    .all()
                )
                monarch = next(
                    (m for m in living_members if m.is_monarch), None
                )
                heir = next(
                    (
                        m for m in living_members
                        if not m.is_monarch and m.is_noble
                    ),
                    None,
                )

                from models.db_models import Army, MilitaryUnit
                active_armies = (
                    self.session.query(Army)
                    .filter(
                        Army.dynasty_id == target_dynasty_id,
                        Army.is_active == True,  # noqa: E712
                    )
                    .all()
                )

                from models.db_models import Project as ProjectModel
                active_projects = (
                    self.session.query(ProjectModel)
                    .filter(
                        ProjectModel.dynasty_id == target_dynasty_id,
                        ProjectModel.status == 'active',
                    )
                    .all()
                )

                from models.db_models import DiplomaticRelation
                relations = (
                    self.session.query(DiplomaticRelation)
                    .filter(
                        (DiplomaticRelation.dynasty1_id == target_dynasty_id)
                        | (DiplomaticRelation.dynasty2_id == target_dynasty_id)
                    )
                    .order_by(DiplomaticRelation.relation_score.desc())
                    .limit(3)
                    .all()
                )
                top_relations = []
                for rel in relations:
                    other_id = (
                        rel.dynasty2_id
                        if rel.dynasty1_id == target_dynasty_id
                        else rel.dynasty1_id
                    )
                    other = self.session.get(DynastyDB, other_id)
                    if other:
                        top_relations.append(
                            f"{other.name} ({rel.relation_score:+d})"
                        )

                monarch_name = (
                    f"{monarch.name} {monarch.surname or ''}".strip()
                    if monarch else "Unknown"
                )
                heir_name = (
                    f"{heir.name} {heir.surname or ''}".strip()
                    if heir else "None known"
                )
                army_summary = (
                    f"{len(active_armies)} active armies"
                    if active_armies else "No active armies"
                )
                project_types = (
                    ", ".join(set(p.project_type for p in active_projects))
                    if active_projects else "none"
                )
                relations_str = (
                    "; ".join(top_relations) if top_relations else "none"
                )

                report = (
                    f"Intel report on {target.name}: "
                    f"Wealth={target.current_wealth}, "
                    f"Iron={target.current_iron}, "
                    f"Timber={target.current_timber}. "
                    f"{army_summary}. "
                    f"Active projects: {project_types}. "
                    f"Top relations: {relations_str}. "
                    f"Monarch: {monarch_name}; Heir: {heir_name}."
                )
                log = HistoryLogEntryDB(
                    dynasty_id=actor_dynasty_id,
                    year=current_year,
                    event_type='intel_report',
                    event_string=report,
                )
                self.session.add(log)
                logger.info(
                    "Intel project %s: report written for dynasty %s about %s",
                    project.id, actor_dynasty_id, target_dynasty_id,
                )
        else:
            self._update_relation(actor_dynasty_id, target_dynasty_id, -10)
        return success, detected

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_relation(
        self,
        dynasty1_id: Optional[int],
        dynasty2_id: Optional[int],
        delta: int,
    ) -> None:
        """Adjust diplomatic relation score between two dynasties."""
        if not dynasty1_id or not dynasty2_id:
            return
        from models.db_models import DiplomaticRelation
        d1, d2 = (dynasty1_id, dynasty2_id) if dynasty1_id < dynasty2_id else (dynasty2_id, dynasty1_id)
        rel = (
            self.session.query(DiplomaticRelation)
            .filter_by(dynasty1_id=d1, dynasty2_id=d2)
            .first()
        )
        if rel is None:
            rel = DiplomaticRelation(dynasty1_id=d1, dynasty2_id=d2, relation_score=0)
            self.session.add(rel)
        rel.relation_score = (rel.relation_score or 0) + delta
        logger.debug(
            "_update_relation: dynasties %s/%s delta=%+d → %s",
            d1, d2, delta, rel.relation_score,
        )
