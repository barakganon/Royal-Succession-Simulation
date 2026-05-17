"""ProjectSystem — multi-year project lifecycle for a dynasty.

Sprint 2 of the master plan replaces instant actions with multi-year projects.
This module owns the lifecycle (start, tick, complete, cancel, query) but does
NOT wire into the turn processor — that's Story 2-3.

For Story 2-2 the effect dispatcher (run on completion) is a registry of
no-op stubs; Story 2-3 will replace the bodies with calls into MilitarySystem,
EconomySystem, etc. The dispatcher signature `Callable[[Session, Project], None]`
is final.
"""

import logging
import os
from typing import Callable, Dict, List, Tuple

from sqlalchemy.orm import Session

from models.db_models import (
    Building, BuildingType, DynastyDB, HistoryLogEntryDB, MilitaryUnit, PersonDB,
    Project, Territory, UnitType,
)
from utils.llm_prompts import (
    build_multigen_project_completion_prompt,
    generate_multigen_project_completion_fallback,
)

logger = logging.getLogger('royal_succession.project_system')


class InsufficientResourcesError(Exception):
    """Raised by start_project when a dynasty cannot afford year 1's yearly cost."""


def _llm_available() -> bool:
    """Return True if the LLM API key is present in the running Flask app.

    Duplicates models/turn_processor.py:_llm_available() rather than importing
    it (would create a circular import — turn_processor already imports this
    module). Sprint 11 cleanup can lift both into utils/llm_guard.py.
    """
    try:
        from flask import current_app
        return current_app.config.get('FLASK_APP_GOOGLE_API_KEY_PRESENT', False)
    except Exception:
        return False


def _chronicle_multigen_completion(session: Session, project: Project) -> None:
    """Emit a HistoryLogEntryDB if the project's initiator and completer differ.

    Called from complete_project after the effect dispatcher runs and before
    the final commit. No-op when:
      - completed_by_monarch_id is None (interregnum at completion)
      - initiator == completer (same-monarch completion is not multi-gen)
    """
    if project.initiated_by_monarch_id is None or project.completed_by_monarch_id is None:
        logger.debug(
            "Skipping multi-gen chronicle for project %s: initiator=%s completer=%s",
            project.id, project.initiated_by_monarch_id, project.completed_by_monarch_id,
        )
        return
    if project.initiated_by_monarch_id == project.completed_by_monarch_id:
        return

    dynasty = session.get(DynastyDB, project.dynasty_id)
    initiator = session.get(PersonDB, project.initiated_by_monarch_id)
    completer = session.get(PersonDB, project.completed_by_monarch_id)
    if dynasty is None or initiator is None or completer is None:
        logger.debug(
            "Skipping multi-gen chronicle for project %s: missing dynasty/initiator/completer rows",
            project.id,
        )
        return

    # Surnames can be NULL for early-game founders; collapse double-spaces.
    initiator_name = f"{initiator.name or ''} {initiator.surname or ''}".strip()
    completer_name = f"{completer.name or ''} {completer.surname or ''}".strip()

    text = ""
    if _llm_available():
        try:
            import google.generativeai as genai
            from flask import current_app
            api_key = (
                current_app.config.get("FLASK_APP_GOOGLE_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
            )
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = build_multigen_project_completion_prompt(
                    project_type=project.project_type,
                    initiator_name=initiator_name,
                    completer_name=completer_name,
                    dynasty_name=dynasty.name,
                    started_year=project.started_year,
                    completion_year=project.completion_year,
                )
                response = model.generate_content(
                    prompt,
                    generation_config={"max_output_tokens": 100, "temperature": 0.8},
                )
                text = response.text.strip() if response.text else ""
        except Exception as llm_exc:
            logger.warning(
                "LLM call for multi-gen chronicle failed (project %s): %s",
                project.id, llm_exc,
            )
            text = ""
    if not text:
        text = generate_multigen_project_completion_fallback(
            project_type=project.project_type,
            initiator_name=initiator_name,
            completer_name=completer_name,
            dynasty_name=dynasty.name,
            started_year=project.started_year,
            completion_year=project.completion_year,
        )

    entry = HistoryLogEntryDB(
        dynasty_id=project.dynasty_id,
        year=project.completion_year,
        event_string=text,
        event_type='project_completed_multigen',
        person1_sim_id=initiator.id,
        person2_sim_id=completer.id,
    )
    session.add(entry)
    # INFO carries the metadata; the full chronicle text only at DEBUG so
    # production logs don't get spammed with LLM-generated paragraphs.
    logger.info(
        "Multi-gen chronicle entry queued for project %s (dynasty %s) — initiator=%s completer=%s year=%s",
        project.id, project.dynasty_id, initiator.id, completer.id, project.completion_year,
    )
    logger.debug("Multi-gen chronicle text for project %s: %r", project.id, text)


# ---------------------------------------------------------------------------
# Project type catalogue — single source of truth for project metadata.
# Story 2-2 ships 7 representative entries; Story 2-3 / Sprint 4 may expand.
#
# NOTE on `yearly_cost_food`: DynastyDB does not yet have a `current_food`
# column, so tick_projects skips food when draining. The catalogue records
# the food cost for forward-compatibility with Sprint 6 (when food becomes a
# stockpiled resource); see story spec Dev Notes.
# ---------------------------------------------------------------------------
PROJECT_TYPE_CATALOGUE: Dict[str, Dict] = {
    'recruit_infantry': {
        'duration_years': 1,
        'yearly_cost_gold': 50,
        'yearly_cost_iron': 0,
        'yearly_cost_timber': 0,
        'yearly_cost_food': 0,
        'slot': True,
        'requires_building': None,
    },
    'recruit_cavalry': {
        'duration_years': 2,
        'yearly_cost_gold': 80,
        'yearly_cost_iron': 10,
        'yearly_cost_timber': 0,
        'yearly_cost_food': 0,
        'slot': True,
        'requires_building': 'Stables',
    },
    'build_farm': {
        'duration_years': 2,
        'yearly_cost_gold': 30,
        'yearly_cost_iron': 0,
        'yearly_cost_timber': 20,
        'yearly_cost_food': 0,
        'slot': True,
        'requires_building': None,
    },
    'build_walls': {
        'duration_years': 5,
        'yearly_cost_gold': 100,
        'yearly_cost_iron': 0,
        'yearly_cost_timber': 0,
        'yearly_cost_food': 0,
        'slot': True,
        'requires_building': None,
    },
    'build_cathedral': {
        'duration_years': 15,
        'yearly_cost_gold': 100,
        'yearly_cost_iron': 0,
        'yearly_cost_timber': 0,
        'yearly_cost_food': 0,
        'slot': True,
        'requires_building': None,
    },
    'develop_territory': {
        'duration_years': 3,
        'yearly_cost_gold': 40,
        'yearly_cost_iron': 0,
        'yearly_cost_timber': 0,
        'yearly_cost_food': 0,
        'slot': True,
        'requires_building': None,
    },
    'envoy_mission': {
        'duration_years': 1,
        'yearly_cost_gold': 10,
        'yearly_cost_iron': 0,
        'yearly_cost_timber': 0,
        'yearly_cost_food': 0,
        'slot': True,
        'requires_building': None,
    },
    'march_army_cross_realm': {
        'duration_years': 1,
        'yearly_cost_gold': 10,
        'yearly_cost_iron': 0,
        'yearly_cost_timber': 0,
        'yearly_cost_food': 20,  # not drained until Sprint 6
        'slot': True,
        'requires_building': None,
    },
}


# ---------------------------------------------------------------------------
# Effect dispatcher — invoked by complete_project.
#
# Story 2-3 wires three real effects (recruit_infantry, build_farm,
# develop_territory) that mutate game state without re-charging resources
# (tick_projects already drained the full cost over the project's duration).
# The other catalogue entries remain NO-OP stubs until later sprints decide
# their gameplay mechanics.
# ---------------------------------------------------------------------------
def _stub_effect(session: Session, project: Project) -> None:
    logger.info(
        "[stub] %s completed for project %s (dynasty %s)",
        project.project_type, project.id, project.dynasty_id,
    )


def _effect_recruit_infantry(session: Session, project: Project) -> None:
    params = project.get_params()
    size = int(params.get('size', 100))
    unit = MilitaryUnit(
        dynasty_id=project.dynasty_id,
        unit_type=UnitType.LEVY_SPEARMEN,
        size=size,
        territory_id=project.target_territory_id,
        quality=1.0,
        morale=1.0,
        maintenance_cost=1,
        food_consumption=1,
        created_year=project.completion_year,
    )
    session.add(unit)
    logger.info(
        "Project %s completed: recruited %s LEVY_SPEARMEN at territory %s for dynasty %s",
        project.id, size, project.target_territory_id, project.dynasty_id,
    )


def _effect_build_farm(session: Session, project: Project) -> None:
    if project.target_territory_id is None:
        logger.warning(
            "build_farm project %s has no target_territory_id — skipping building creation",
            project.id,
        )
        return
    # NB: Building model does not declare `is_under_construction` — though
    # `economy_system.py` references it. That inconsistency is pre-existing
    # and logged in deferred-work.md; the project-completion path simply
    # creates the row in its finished state without touching that flag.
    building = Building(
        territory_id=project.target_territory_id,
        building_type=BuildingType.FARM,
        name='Farm',
        level=1,
        condition=1.0,
        construction_year=project.started_year,
    )
    session.add(building)
    logger.info(
        "Project %s completed: built FARM in territory %s for dynasty %s",
        project.id, project.target_territory_id, project.dynasty_id,
    )


def _effect_develop_territory(session: Session, project: Project) -> None:
    if project.target_territory_id is None:
        logger.warning(
            "develop_territory project %s has no target_territory_id — skipping",
            project.id,
        )
        return
    territory = session.get(Territory, project.target_territory_id)
    if territory is None:
        logger.warning(
            "develop_territory project %s targets missing territory %s",
            project.id, project.target_territory_id,
        )
        return
    territory.development_level = (territory.development_level or 1) + 1
    logger.info(
        "Project %s completed: territory %s development_level → %s",
        project.id, territory.id, territory.development_level,
    )


EFFECT_DISPATCHER: Dict[str, Callable[[Session, Project], None]] = {
    'recruit_infantry': _effect_recruit_infantry,
    'recruit_cavalry': _stub_effect,
    'build_farm': _effect_build_farm,
    'build_walls': _stub_effect,
    'build_cathedral': _stub_effect,
    'develop_territory': _effect_develop_territory,
    'envoy_mission': _stub_effect,
    'march_army_cross_realm': _stub_effect,
}


# ===========================================================================
# ProjectSystem
# ===========================================================================

class ProjectSystem:
    """Multi-year project lifecycle for a dynasty."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_active_projects(self, dynasty_id: int) -> List[Project]:
        return (
            self.session.query(Project)
            .filter_by(dynasty_id=dynasty_id, status='active')
            .all()
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start_project(self, dynasty_id: int, project_type: str, started_year: int,
                      **kwargs) -> Project:
        if project_type not in PROJECT_TYPE_CATALOGUE:
            raise ValueError(f"Unknown project_type: {project_type!r}")
        meta = PROJECT_TYPE_CATALOGUE[project_type]

        dynasty = self.session.get(DynastyDB, dynasty_id)
        if dynasty is None:
            raise ValueError(f"Dynasty {dynasty_id} not found")

        monarch = (
            self.session.query(PersonDB)
            .filter_by(dynasty_id=dynasty_id, is_monarch=True, death_year=None)
            .first()
        )
        if monarch is None:
            raise ValueError(
                f"Dynasty {dynasty_id} has no living monarch; cannot start project"
            )

        # Affordability check for year 1 (food not yet enforced).
        if (dynasty.current_wealth < meta['yearly_cost_gold']
                or dynasty.current_iron < meta['yearly_cost_iron']
                or dynasty.current_timber < meta['yearly_cost_timber']):
            raise InsufficientResourcesError(
                f"Dynasty {dynasty_id} cannot afford year 1 of {project_type}"
            )

        project = Project(
            dynasty_id=dynasty_id,
            project_type=project_type,
            started_year=started_year,
            completion_year=started_year + meta['duration_years'],
            yearly_cost_gold=meta['yearly_cost_gold'],
            yearly_cost_iron=meta['yearly_cost_iron'],
            yearly_cost_timber=meta['yearly_cost_timber'],
            yearly_cost_food=meta['yearly_cost_food'],
            status='active',
            initiated_by_monarch_id=monarch.id,
            target_territory_id=kwargs.get('target_territory_id'),
            target_dynasty_id=kwargs.get('target_dynasty_id'),
            target_person_id=kwargs.get('target_person_id'),
        )
        params = kwargs.get('params')
        if params is not None:
            project.set_params(params)

        self.session.add(project)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return project

    def tick_projects(self, dynasty_id: int, year: int) -> List[Tuple[str, int, int]]:
        active = self.get_active_projects(dynasty_id)
        if not active:
            return []
        dynasty = self.session.get(DynastyDB, dynasty_id)
        interrupts: List[Tuple] = []
        for project in active:
            if (dynasty.current_wealth >= project.yearly_cost_gold
                    and dynasty.current_iron >= project.yearly_cost_iron
                    and dynasty.current_timber >= project.yearly_cost_timber):
                dynasty.current_wealth -= project.yearly_cost_gold
                dynasty.current_iron -= project.yearly_cost_iron
                dynasty.current_timber -= project.yearly_cost_timber
            else:
                project.status = 'stalled'
                interrupts.append(('project_stalled', year, project.id))
                logger.info(
                    "Project %s (%s) stalled for dynasty %s in year %s",
                    project.id, project.project_type, dynasty_id, year,
                )
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return interrupts

    def complete_project(self, project_id: int) -> Project:
        project = self.session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        if project.status != 'active':
            raise ValueError(
                f"Project {project_id} cannot be completed from status {project.status!r}"
            )

        project.status = 'completed'
        monarch = (
            self.session.query(PersonDB)
            .filter_by(dynasty_id=project.dynasty_id, is_monarch=True, death_year=None)
            .first()
        )
        if monarch is not None:
            project.completed_by_monarch_id = monarch.id

        # Strict dispatcher lookup — a missing entry is a contract violation
        # (the catalogue and dispatcher are constructed in lockstep) and must
        # fail loudly rather than silently complete with no effect.
        try:
            effect_fn = EFFECT_DISPATCHER[project.project_type]
            effect_fn(self.session, project)
        except Exception:
            self.session.rollback()
            raise

        # Multi-generation chronicle hook (Story 2-4). Runs AFTER the effect so
        # the chronicle reflects the completed state. Errors here MUST NOT
        # roll back the completion — chronicle is supplementary narrative.
        try:
            _chronicle_multigen_completion(self.session, project)
        except Exception as chron_exc:
            logger.warning(
                "Multi-gen chronicle hook failed for project %s (non-fatal): %s",
                project.id, chron_exc,
            )

        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return project

    def cancel_project(self, project_id: int, current_year: int) -> Project:
        project = self.session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        if project.status in ('completed', 'cancelled'):
            raise ValueError(
                f"Project {project_id} cannot be cancelled from status {project.status!r}"
            )
        if current_year < project.started_year:
            raise ValueError(
                f"current_year ({current_year}) precedes started_year "
                f"({project.started_year}) for project {project_id}"
            )

        years_elapsed = current_year - project.started_year
        dynasty = self.session.get(DynastyDB, project.dynasty_id)
        dynasty.current_wealth += int(0.5 * years_elapsed * project.yearly_cost_gold)
        dynasty.current_iron += int(0.5 * years_elapsed * project.yearly_cost_iron)
        dynasty.current_timber += int(0.5 * years_elapsed * project.yearly_cost_timber)

        project.status = 'cancelled'
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return project
