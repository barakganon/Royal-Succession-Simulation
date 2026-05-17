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
from typing import Callable, Dict, List, Tuple

from sqlalchemy.orm import Session

from models.db_models import DynastyDB, PersonDB, Project

logger = logging.getLogger('royal_succession.project_system')


class InsufficientResourcesError(Exception):
    """Raised by start_project when a dynasty cannot afford year 1's yearly cost."""


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
# Effect dispatcher — invoked by complete_project. Story 2-3 replaces the
# stub bodies with real subsystem calls (MilitarySystem.recruit_unit,
# EconomySystem.construct_building, etc.).
# ---------------------------------------------------------------------------
def _stub_effect(session: Session, project: Project) -> None:
    logger.info(
        "[stub] %s completed for project %s (dynasty %s)",
        project.project_type, project.id, project.dynasty_id,
    )


EFFECT_DISPATCHER: Dict[str, Callable[[Session, Project], None]] = {
    project_type: _stub_effect for project_type in PROJECT_TYPE_CATALOGUE
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
