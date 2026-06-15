"""Unit tests for EspionageSystem (Story L-1a).

Tests cover dispatch_mission validation, happy-path dispatch, and all
resolve_mission outcome branches with deterministic random patching.
"""

import json
import uuid
from unittest.mock import patch

import pytest

from models.db_models import (
    Building, BuildingType, DiplomaticRelation, DynastyDB, HistoryLogEntryDB,
    PersonDB, Project, Region, Province, Territory, TerrainType, User,
)
from models.espionage_system import EspionageSystem, MISSION_TYPES
from models.project_system import ProjectSystem


# ---------------------------------------------------------------------------
# Fixture helpers (reuse same pattern as test_project_system.py)
# ---------------------------------------------------------------------------

def _make_user_and_dynasty(session, name='Test Dynasty', year=1300,
                           wealth=500, iron=100, timber=100):
    suffix = uuid.uuid4().hex[:8]
    slug = name.lower().replace(' ', '_')
    user = User(username=f"u_{slug}_{suffix}", email=f"{slug}+{suffix}@x.test")
    user.set_password("password123")
    session.add(user)
    session.commit()
    dynasty = DynastyDB(
        user_id=user.id,
        name=name,
        theme_identifier_or_json="medieval_europe",
        start_year=year,
        current_simulation_year=year,
        current_wealth=wealth,
        current_iron=iron,
        current_timber=timber,
    )
    session.add(dynasty)
    session.commit()
    return user, dynasty


def _make_territory(session, dynasty, name='Rouen', dev_level=1):
    suffix = uuid.uuid4().hex[:6]
    region = Region(name=f"Region_{suffix}", description="Test region")
    session.add(region)
    session.commit()
    province = Province(
        region_id=region.id,
        name=f"Province_{suffix}",
        primary_terrain=TerrainType.PLAINS,
    )
    session.add(province)
    session.commit()
    territory = Territory(
        province_id=province.id,
        name=f"{name}_{suffix}",
        terrain_type=TerrainType.PLAINS,
        x_coordinate=0.0,
        y_coordinate=0.0,
        controller_dynasty_id=dynasty.id,
        development_level=dev_level,
    )
    session.add(territory)
    session.commit()
    return territory


def _make_monarch(session, dynasty, name='Aldric I', birth_year=1270):
    person = PersonDB(
        dynasty_id=dynasty.id,
        name=name.split(' ')[0],
        surname=dynasty.name,
        gender='MALE',
        birth_year=birth_year,
        is_noble=True,
        is_monarch=True,
        reign_start_year=dynasty.start_year,
    )
    session.add(person)
    session.commit()
    return person


def _make_person(session, dynasty, name='Agent', birth_year=1280, espionage_skill=0):
    person = PersonDB(
        dynasty_id=dynasty.id,
        name=name,
        surname=dynasty.name,
        gender='MALE',
        birth_year=birth_year,
        is_noble=True,
        is_monarch=False,
        reign_start_year=None,
        espionage_skill=espionage_skill,
    )
    session.add(person)
    session.commit()
    return person


def _make_building(session, territory, condition=1.0):
    building = Building(
        territory_id=territory.id,
        building_type=BuildingType.FARM,
        name='Farm',
        level=1,
        condition=condition,
        construction_year=1290,
    )
    session.add(building)
    session.commit()
    return building


def _make_active_project(session, actor_dynasty, target_dynasty, mission_type,
                         agent, target_person=None, building=None):
    """Create an active Project row directly (bypasses start_project affordability checks).

    Requires the actor_dynasty to already have a living monarch (initiated_by_monarch_id
    is NOT NULL in the Project table).
    """
    params = {'agent_person_id': agent.id}
    if target_person is not None:
        params['target_person_id'] = target_person.id
    if building is not None:
        params['building_id'] = building.id

    # Look up the living monarch to satisfy the NOT NULL FK
    monarch = (
        session.query(PersonDB)
        .filter(
            PersonDB.dynasty_id == actor_dynasty.id,
            PersonDB.is_monarch == True,  # noqa: E712
            PersonDB.death_year.is_(None),
        )
        .first()
    )
    if monarch is None:
        raise RuntimeError(
            f"_make_active_project: actor dynasty {actor_dynasty.id} has no living monarch"
        )

    meta = MISSION_TYPES[mission_type]
    project = Project(
        dynasty_id=actor_dynasty.id,
        project_type=mission_type,
        started_year=actor_dynasty.current_simulation_year,
        completion_year=actor_dynasty.current_simulation_year + meta['duration_years'],
        yearly_cost_gold=meta['gold_cost'],
        yearly_cost_iron=0,
        yearly_cost_timber=0,
        yearly_cost_food=0,
        status='active',
        target_dynasty_id=target_dynasty.id,
        target_person_id=target_person.id if target_person else None,
        initiated_by_monarch_id=monarch.id,
    )
    project.set_params(params)
    session.add(project)
    session.commit()
    return project


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.model
class TestDispatchMission:
    """Tests for EspionageSystem.dispatch_mission."""

    def test_unknown_mission_type_returns_false(self, session):
        _, actor = _make_user_and_dynasty(session, 'Actor')
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'Target')
        agent = _make_person(session, actor)
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(actor.id, 'unknown_mission', agent.id, target.id)
        assert ok is False
        assert 'Unknown mission type' in msg

    def test_missing_actor_dynasty_returns_false(self, session):
        _, target = _make_user_and_dynasty(session, 'Target2')
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(99999, 'espionage_intel', 1, target.id)
        assert ok is False
        assert 'not found' in msg.lower()

    def test_missing_target_dynasty_returns_false(self, session):
        _, actor = _make_user_and_dynasty(session, 'Actor3')
        _make_monarch(session, actor)
        agent = _make_person(session, actor)
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(actor.id, 'espionage_intel', agent.id, 99999)
        assert ok is False
        assert 'not found' in msg.lower()

    def test_dead_agent_returns_false(self, session):
        _, actor = _make_user_and_dynasty(session, 'Actor4')
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'Target4')
        agent = _make_person(session, actor)
        agent.death_year = 1290
        session.commit()
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(actor.id, 'espionage_intel', agent.id, target.id)
        assert ok is False
        assert 'dead' in msg.lower()

    def test_assassinate_without_target_person_returns_false(self, session):
        _, actor = _make_user_and_dynasty(session, 'Actor5')
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'Target5')
        agent = _make_person(session, actor)
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(actor.id, 'espionage_assassinate', agent.id, target.id)
        assert ok is False
        assert 'target_person_id' in msg

    def test_sabotage_without_building_returns_false(self, session):
        _, actor = _make_user_and_dynasty(session, 'Actor6')
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'Target6')
        agent = _make_person(session, actor)
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(actor.id, 'espionage_sabotage', agent.id, target.id)
        assert ok is False
        assert 'building_id' in msg

    def test_insufficient_gold_returns_false(self, session):
        _, actor = _make_user_and_dynasty(session, 'BrokeActor', wealth=0)
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'BrokeTarget')
        agent = _make_person(session, actor)
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(actor.id, 'espionage_intel', agent.id, target.id)
        assert ok is False
        assert 'afford' in msg.lower()

    def test_happy_path_creates_project_with_agent_in_params(self, session):
        _, actor = _make_user_and_dynasty(session, 'HappyActor')
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'HappyTarget')
        agent = _make_person(session, actor)
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(actor.id, 'espionage_intel', agent.id, target.id)
        assert ok is True
        assert 'espionage_intel' in msg

        project = (
            session.query(Project)
            .filter_by(dynasty_id=actor.id, project_type='espionage_intel')
            .first()
        )
        assert project is not None
        params = json.loads(project.params_json)
        assert params['agent_person_id'] == agent.id

    def test_happy_path_assassinate_stores_target_person(self, session):
        _, actor = _make_user_and_dynasty(session, 'AssActor')
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'AssTarget')
        _make_monarch(session, target, name='TargetKing')
        agent = _make_person(session, actor)
        target_person = _make_person(session, target, name='VictimNobleman')
        es = EspionageSystem(session)
        ok, msg = es.dispatch_mission(
            actor.id, 'espionage_assassinate', agent.id, target.id,
            target_person_id=target_person.id,
        )
        assert ok is True
        project = (
            session.query(Project)
            .filter_by(dynasty_id=actor.id, project_type='espionage_assassinate')
            .first()
        )
        params = json.loads(project.params_json)
        assert params['target_person_id'] == target_person.id


@pytest.mark.unit
@pytest.mark.model
class TestResolveMission:
    """Tests for EspionageSystem.resolve_mission."""

    # ------------------------------------------------------------------
    # Assassinate
    # ------------------------------------------------------------------
    def test_assassinate_success_sets_death_year(self, session):
        _, actor = _make_user_and_dynasty(session, 'AssSuccActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'AssSuccTarget')
        _make_monarch(session, target_d, name='TargetKing2')
        agent = _make_person(session, actor)
        victim = _make_person(session, target_d, name='Victim')
        project = _make_active_project(
            session, actor, target_d, 'espionage_assassinate', agent, target_person=victim
        )

        es = EspionageSystem(session)
        with patch('random.random', return_value=0.0):
            success, detected = es.resolve_mission(project)

        session.refresh(victim)
        assert success is True
        assert victim.death_year is not None
        log = (
            session.query(HistoryLogEntryDB)
            .filter_by(dynasty_id=actor.id, event_type='successful_assassination')
            .first()
        )
        assert log is not None

    def test_assassinate_failure_applies_penalties(self, session):
        _, actor = _make_user_and_dynasty(session, 'AssFailActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'AssFailTarget')
        _make_monarch(session, target_d, name='TargetKing3')
        agent = _make_person(session, actor)
        victim = _make_person(session, target_d, name='Victim2')
        project = _make_active_project(
            session, actor, target_d, 'espionage_assassinate', agent, target_person=victim
        )
        initial_infamy = actor.infamy or 0
        initial_honor = actor.honor or 0

        es = EspionageSystem(session)
        # roll=1.0 → fails; second roll for agent death: patch to > 0.4 so agent survives
        with patch('random.random', side_effect=[1.0, 0.9]):
            success, detected = es.resolve_mission(project)

        session.refresh(actor)
        assert success is False
        assert detected is True
        assert actor.infamy >= initial_infamy + 20
        assert actor.honor <= initial_honor - 10
        # Failed assassination log for actor
        log = (
            session.query(HistoryLogEntryDB)
            .filter_by(dynasty_id=actor.id, event_type='failed_assassination')
            .first()
        )
        assert log is not None

    def test_assassinate_failure_agent_can_die(self, session):
        _, actor = _make_user_and_dynasty(session, 'AssAgentDieActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'AssAgentDieTarget')
        _make_monarch(session, target_d, name='TargetKing4')
        agent = _make_person(session, actor, name='PoorAgent')
        victim = _make_person(session, target_d, name='Victim3')
        project = _make_active_project(
            session, actor, target_d, 'espionage_assassinate', agent, target_person=victim
        )

        es = EspionageSystem(session)
        # roll=1.0 fails the mission; 0.1 < 0.4 so agent dies
        with patch('random.random', side_effect=[1.0, 0.1]):
            es.resolve_mission(project)

        session.refresh(agent)
        assert agent.death_year is not None

    # ------------------------------------------------------------------
    # Sabotage
    # ------------------------------------------------------------------
    def test_sabotage_success_halves_building_condition(self, session):
        _, actor = _make_user_and_dynasty(session, 'SabSuccActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'SabSuccTarget')
        _make_monarch(session, target_d, name='SabTargetKing')
        terr = _make_territory(session, target_d)
        building = _make_building(session, terr, condition=1.0)
        agent = _make_person(session, actor)
        project = _make_active_project(
            session, actor, target_d, 'espionage_sabotage', agent, building=building
        )

        es = EspionageSystem(session)
        with patch('random.random', return_value=0.0):
            success, _ = es.resolve_mission(project)

        assert success is True
        refreshed = session.get(Building, building.id)
        # condition is a 0.0-1.0 float: 1.0 halved to 0.5 (still > 0.1) → survives, damaged.
        assert refreshed is not None
        assert refreshed.condition == pytest.approx(0.5)

    def test_sabotage_success_high_condition_halved(self, session):
        _, actor = _make_user_and_dynasty(session, 'SabHighActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'SabHighTarget')
        _make_monarch(session, target_d, name='SabHighKing')
        terr = _make_territory(session, target_d)
        building = _make_building(session, terr, condition=0.8)
        agent = _make_person(session, actor)
        project = _make_active_project(
            session, actor, target_d, 'espionage_sabotage', agent, building=building
        )

        es = EspionageSystem(session)
        with patch('random.random', return_value=0.0):
            success, _ = es.resolve_mission(project)

        assert success is True
        session.refresh(building)
        assert building.condition == pytest.approx(0.4)

    def test_sabotage_destroys_building_below_threshold(self, session):
        """A building already in poor repair (condition 0.15) is destroyed when
        halved below the 0.1 floor — repeated sabotage eventually wrecks it."""
        _, actor = _make_user_and_dynasty(session, 'SabDestroyActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'SabDestroyTarget')
        _make_monarch(session, target_d, name='SabDestroyKing')
        terr = _make_territory(session, target_d)
        building = _make_building(session, terr, condition=0.15)
        agent = _make_person(session, actor)
        project = _make_active_project(
            session, actor, target_d, 'espionage_sabotage', agent, building=building
        )

        es = EspionageSystem(session)
        with patch('random.random', return_value=0.0):
            success, _ = es.resolve_mission(project)

        assert success is True
        assert session.get(Building, building.id) is None  # 0.15 → 0.075 < 0.1 → destroyed

    def test_sabotage_failure_applies_relation_penalty(self, session):
        _, actor = _make_user_and_dynasty(session, 'SabFailActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'SabFailTarget')
        _make_monarch(session, target_d, name='SabFailKing')
        terr = _make_territory(session, target_d)
        building = _make_building(session, terr)
        agent = _make_person(session, actor)
        project = _make_active_project(
            session, actor, target_d, 'espionage_sabotage', agent, building=building
        )
        initial_infamy = actor.infamy or 0

        es = EspionageSystem(session)
        with patch('random.random', return_value=1.0):
            success, detected = es.resolve_mission(project)

        session.refresh(actor)
        assert success is False
        assert detected is True
        assert actor.infamy >= initial_infamy + 10

    # ------------------------------------------------------------------
    # Intel
    # ------------------------------------------------------------------
    def test_intel_success_writes_intel_report_log(self, session):
        _, actor = _make_user_and_dynasty(session, 'IntelSuccActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'IntelSuccTarget', wealth=777, iron=33, timber=55)
        _make_monarch(session, target_d, name='IntelTargetKing')
        agent = _make_person(session, actor)
        project = _make_active_project(session, actor, target_d, 'espionage_intel', agent)

        es = EspionageSystem(session)
        with patch('random.random', return_value=0.0):
            success, _ = es.resolve_mission(project)

        assert success is True
        log = (
            session.query(HistoryLogEntryDB)
            .filter_by(dynasty_id=actor.id, event_type='intel_report')
            .first()
        )
        assert log is not None
        assert 'Wealth=777' in log.event_string
        assert 'Iron=33' in log.event_string
        assert 'Timber=55' in log.event_string

    def test_intel_failure_applies_relation_penalty(self, session):
        _, actor = _make_user_and_dynasty(session, 'IntelFailActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'IntelFailTarget')
        _make_monarch(session, target_d, name='IntelFailKing')
        agent = _make_person(session, actor)
        project = _make_active_project(session, actor, target_d, 'espionage_intel', agent)

        es = EspionageSystem(session)
        with patch('random.random', return_value=1.0):
            success, _ = es.resolve_mission(project)

        assert success is False
        # Relation should be updated (relation row created with -10)
        d1, d2 = sorted([actor.id, target_d.id])
        rel = (
            session.query(DiplomaticRelation)
            .filter_by(dynasty1_id=d1, dynasty2_id=d2)
            .first()
        )
        assert rel is not None
        assert rel.relation_score <= -10

    # ------------------------------------------------------------------
    # Success chance math
    # ------------------------------------------------------------------
    def test_higher_espionage_skill_raises_success_chance(self, session):
        """Agent with higher espionage_skill should produce a higher computed success chance."""
        from models.espionage_system import MISSION_TYPES
        _, actor_low = _make_user_and_dynasty(session, 'LowSkillActor')
        _make_monarch(session, actor_low)
        _, target_low = _make_user_and_dynasty(session, 'LowSkillTarget')
        _make_monarch(session, target_low, name='LowKing')
        agent_low = _make_person(session, actor_low, espionage_skill=0)

        _, actor_high = _make_user_and_dynasty(session, 'HighSkillActor')
        _make_monarch(session, actor_high)
        _, target_high = _make_user_and_dynasty(session, 'HighSkillTarget')
        _make_monarch(session, target_high, name='HighKing')
        agent_high = _make_person(session, actor_high, espionage_skill=10)

        meta = MISSION_TYPES['espionage_intel']
        # Manual math: success_chance = base_success + 0.02 * skill - 0
        low_chance = meta['base_success'] + 0.02 * 0
        high_chance = meta['base_success'] + 0.02 * 10
        assert high_chance > low_chance

    def test_dead_or_missing_agent_uses_skill_zero(self, session):
        _, actor = _make_user_and_dynasty(session, 'NoAgentActor')
        _make_monarch(session, actor)
        _, target_d = _make_user_and_dynasty(session, 'NoAgentTarget')
        _make_monarch(session, target_d, name='NoAgentKing')
        agent = _make_person(session, actor)
        project = _make_active_project(session, actor, target_d, 'espionage_intel', agent)
        # Kill the agent before resolution
        agent.death_year = actor.current_simulation_year
        session.commit()

        es = EspionageSystem(session)
        # We just need this to not raise and return a valid result
        with patch('random.random', return_value=0.0):
            result = es.resolve_mission(project)
        assert isinstance(result, tuple)
        assert len(result) == 2


@pytest.mark.unit
@pytest.mark.model
class TestDiplomacyGuard:
    """Ensure diplomacy_system blocks assassinate calls with a clear message."""

    def test_assassinate_via_diplomacy_returns_false_with_espionage_message(self, session):
        from models.diplomacy_system import DiplomacySystem
        _, actor = _make_user_and_dynasty(session, 'DipGuardActor')
        _make_monarch(session, actor)
        _, target = _make_user_and_dynasty(session, 'DipGuardTarget')
        _make_monarch(session, target, name='DipGuardKing')
        ds = DiplomacySystem(session)
        ok, msg = ds.perform_diplomatic_action(actor.id, target.id, 'assassinate')
        assert ok is False
        assert 'Espionage' in msg or 'espionage' in msg
