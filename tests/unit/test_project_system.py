import uuid
import pytest

from models.db_models import (
    Building, BuildingType, DynastyDB, HistoryLogEntryDB, MilitaryUnit, PersonDB,
    Project, Region, Province, Territory, TerrainType, UnitType, User,
)
from models.project_system import (
    EFFECT_DISPATCHER,
    InsufficientResourcesError,
    PROJECT_TYPE_CATALOGUE,
    ProjectSystem,
)


def _make_user_and_dynasty(session, name='Test Dynasty', year=1300,
                           wealth=200, iron=100, timber=100):
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


@pytest.mark.unit
@pytest.mark.model
class TestProjectSystem:
    """Unit tests for the ProjectSystem subsystem (Sprint 2 — Story 2-2)."""

    # ------------------------------------------------------------------
    # start_project
    # ------------------------------------------------------------------
    def test_start_project_happy_path(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty_id=dynasty.id,
            project_type='build_farm',
            started_year=1300,
        )
        assert project.id is not None
        assert project.status == 'active'
        assert project.started_year == 1300
        assert project.completion_year == 1302  # 2-year duration from catalogue
        assert project.yearly_cost_gold == 30
        assert project.yearly_cost_timber == 20
        assert project.initiated_by_monarch_id is not None
        # No upfront deduction — only year 1 affordability was checked.
        session.refresh(dynasty)
        assert dynasty.current_wealth == 200
        assert dynasty.current_timber == 100

    def test_start_project_unknown_type_raises_value_error(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        with pytest.raises(ValueError, match="Unknown project_type"):
            ps.start_project(dynasty.id, 'build_alien_spaceship', 1300)

    def test_start_project_no_monarch_raises_value_error(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        # NB: no monarch created
        ps = ProjectSystem(session)
        with pytest.raises(ValueError, match="no living monarch"):
            ps.start_project(dynasty.id, 'build_farm', 1300)

    def test_start_project_insufficient_gold_raises(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=10)  # build_farm needs 30
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        with pytest.raises(InsufficientResourcesError):
            ps.start_project(dynasty.id, 'build_farm', 1300)

    def test_start_project_insufficient_iron_raises(self, session):
        _, dynasty = _make_user_and_dynasty(session, iron=5)  # recruit_cavalry needs 10 iron
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        with pytest.raises(InsufficientResourcesError):
            ps.start_project(dynasty.id, 'recruit_cavalry', 1300)

    def test_start_project_persists_params_kwarg(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty_id=dynasty.id, project_type='recruit_infantry',
            started_year=1300,
            params={'unit_type': 'spearman', 'count': 100},
        )
        assert project.get_params() == {'unit_type': 'spearman', 'count': 100}

    # ------------------------------------------------------------------
    # tick_projects
    # ------------------------------------------------------------------
    def test_tick_drains_yearly_cost(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=200, iron=100, timber=100)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        ps.start_project(dynasty.id, 'build_farm', 1300)
        ps.tick_projects(dynasty.id, 1300)
        session.refresh(dynasty)
        assert dynasty.current_wealth == 170  # 200 - 30
        assert dynasty.current_timber == 80   # 100 - 20
        # build_farm has no iron cost — iron must remain unchanged.
        assert dynasty.current_iron == 100

    def test_tick_stalls_project_and_emits_interrupt(self, session):
        # build_farm: 30g + 20 timber per year. Start with exactly one year's
        # worth so year 1 is affordable and year 2 stalls.
        _, dynasty = _make_user_and_dynasty(session, wealth=30, timber=20)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_farm', 1300)
        interrupts1 = ps.tick_projects(dynasty.id, 1300)
        assert interrupts1 == []
        # Now dynasty has 0g, 0 timber. Second tick stalls.
        interrupts2 = ps.tick_projects(dynasty.id, 1301)
        assert len(interrupts2) == 1
        reason, year, project_id = interrupts2[0]
        assert reason == 'project_stalled'
        assert year == 1301
        assert project_id == project.id
        session.refresh(project)
        assert project.status == 'stalled'

    def test_tick_returns_empty_when_no_active_projects(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        assert ps.tick_projects(dynasty.id, 1300) == []

    def test_tick_ignores_food_cost(self, session):
        # march_army_cross_realm has yearly_cost_food=20, but DynastyDB has no
        # food column. Tick should ignore food and not raise.
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        ps.start_project(dynasty.id, 'march_army_cross_realm', 1300)
        interrupts = ps.tick_projects(dynasty.id, 1300)
        assert interrupts == []
        session.refresh(dynasty)
        assert dynasty.current_wealth == 190  # 200 - 10 gold; food ignored

    def test_tick_skips_stalled_projects(self, session):
        # A stalled project should NOT continue to drain on subsequent ticks.
        # build_walls: 100g/yr. Fund 1 year, stall in year 2, then verify
        # no further drain.
        _, dynasty = _make_user_and_dynasty(session, wealth=100)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        ps.start_project(dynasty.id, 'build_walls', 1300)
        ps.tick_projects(dynasty.id, 1300)  # drains 100 → 0
        ps.tick_projects(dynasty.id, 1301)  # stalls (0 < 100)
        session.refresh(dynasty)
        before = dynasty.current_wealth
        ps.tick_projects(dynasty.id, 1302)  # stalled → should be no-op
        session.refresh(dynasty)
        assert dynasty.current_wealth == before

    # ------------------------------------------------------------------
    # complete_project
    # ------------------------------------------------------------------
    def test_complete_sets_status_and_invokes_dispatcher(self, session, caplog):
        # envoy_mission is still a stub effect in Story 2-3 (no gameplay
        # mechanic for diplomatic missions yet) — using it here keeps the
        # test focused on the dispatcher invocation rather than on a
        # specific real-effect's side effects.
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'envoy_mission', 1300)
        with caplog.at_level('INFO', logger='royal_succession.project_system'):
            completed = ps.complete_project(project.id)
        assert completed.status == 'completed'
        assert completed.completed_by_monarch_id is not None
        assert any('[stub]' in record.message for record in caplog.records)

    def test_complete_unknown_project_raises(self, session):
        ps = ProjectSystem(session)
        with pytest.raises(ValueError, match="Project .* not found"):
            ps.complete_project(999_999)

    def test_complete_sets_completed_by_to_current_monarch_not_initiator(self, session):
        # The chronicle hook (Story 2-4) needs distinct initiator/completer
        # when monarchs change between start and completion. Here we simulate
        # by replacing the monarch before completion.
        _, dynasty = _make_user_and_dynasty(session)
        initiator = _make_monarch(session, dynasty, name='Aldric I')
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_cathedral', 1300)
        assert project.initiated_by_monarch_id == initiator.id
        # Replace monarch.
        initiator.is_monarch = False
        initiator.death_year = 1310
        successor = _make_monarch(session, dynasty, name='Eldred II', birth_year=1290)
        session.commit()
        completed = ps.complete_project(project.id)
        assert completed.initiated_by_monarch_id == initiator.id
        assert completed.completed_by_monarch_id == successor.id

    # ------------------------------------------------------------------
    # cancel_project
    # ------------------------------------------------------------------
    def test_cancel_refunds_50_percent(self, session):
        # build_walls: 5 years × 100g/yr. After 4 years (canceled in year 1304)
        # the dynasty has spent 400g; refund = 200g.
        _, dynasty = _make_user_and_dynasty(session, wealth=600)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_walls', 1300)
        for y in range(1300, 1304):
            ps.tick_projects(dynasty.id, y)
        session.refresh(dynasty)
        assert dynasty.current_wealth == 200  # 600 - 4×100
        ps.cancel_project(project.id, current_year=1304)
        session.refresh(dynasty)
        assert dynasty.current_wealth == 400  # 200 + refund of 200
        session.refresh(project)
        assert project.status == 'cancelled'

    def test_cancel_same_year_refunds_zero(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=200)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_walls', 1300)
        before = dynasty.current_wealth
        ps.cancel_project(project.id, current_year=1300)
        session.refresh(dynasty)
        assert dynasty.current_wealth == before  # no time elapsed → 0 refund
        session.refresh(project)
        assert project.status == 'cancelled'

    def test_cancel_unknown_project_raises(self, session):
        ps = ProjectSystem(session)
        with pytest.raises(ValueError, match="Project .* not found"):
            ps.cancel_project(999_999, current_year=1300)

    # ------------------------------------------------------------------
    # get_active_projects
    # ------------------------------------------------------------------
    def test_get_active_filters_by_status(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=500)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        p1 = ps.start_project(dynasty.id, 'build_farm', 1300)
        p2 = ps.start_project(dynasty.id, 'envoy_mission', 1300)
        p3 = ps.start_project(dynasty.id, 'develop_territory', 1300)
        # Cancel one, complete one — both should drop off the active list.
        ps.cancel_project(p2.id, current_year=1300)
        ps.complete_project(p3.id)
        active = ps.get_active_projects(dynasty.id)
        assert {p.id for p in active} == {p1.id}

    def test_get_active_returns_empty_for_dynasty_with_no_projects(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        assert ps.get_active_projects(dynasty.id) == []

    # ------------------------------------------------------------------
    # Catalogue / dispatcher sanity
    # ------------------------------------------------------------------
    def test_dispatcher_covers_every_catalogue_entry(self):
        # Every project_type in the catalogue must have a registered effect
        # dispatcher (even if just a stub). complete_project now raises
        # KeyError if a dispatcher entry is missing, so a future catalogue
        # addition without a paired dispatcher entry would fail loudly.
        assert set(EFFECT_DISPATCHER) == set(PROJECT_TYPE_CATALOGUE)
        for project_type, fn in EFFECT_DISPATCHER.items():
            assert callable(fn), f"dispatcher entry {project_type!r} is not callable"

    # ------------------------------------------------------------------
    # State-machine guards (added during code review)
    # ------------------------------------------------------------------
    def test_complete_rejects_already_completed_project(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_farm', 1300)
        ps.complete_project(project.id)
        with pytest.raises(ValueError, match="cannot be completed from status"):
            ps.complete_project(project.id)

    def test_complete_rejects_cancelled_project(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_farm', 1300)
        ps.cancel_project(project.id, current_year=1300)
        with pytest.raises(ValueError, match="cannot be completed from status"):
            ps.complete_project(project.id)

    def test_complete_rejects_stalled_project(self, session):
        # A stalled project should not silently complete and grant its effect
        # without the dynasty having paid the full cost.
        _, dynasty = _make_user_and_dynasty(session, wealth=30, timber=20)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_farm', 1300)
        ps.tick_projects(dynasty.id, 1300)  # funds year 1
        ps.tick_projects(dynasty.id, 1301)  # stalls
        session.refresh(project)
        assert project.status == 'stalled'
        with pytest.raises(ValueError, match="cannot be completed from status"):
            ps.complete_project(project.id)

    def test_cancel_rejects_already_cancelled_project(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=300)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_walls', 1300)
        ps.tick_projects(dynasty.id, 1300)
        ps.cancel_project(project.id, current_year=1301)
        with pytest.raises(ValueError, match="cannot be cancelled from status"):
            ps.cancel_project(project.id, current_year=1302)

    def test_cancel_rejects_completed_project(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_farm', 1300)
        ps.complete_project(project.id)
        with pytest.raises(ValueError, match="cannot be cancelled from status"):
            ps.cancel_project(project.id, current_year=1302)

    def test_cancel_rejects_time_travel(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_walls', 1305)
        with pytest.raises(ValueError, match="precedes started_year"):
            ps.cancel_project(project.id, current_year=1300)

    # ------------------------------------------------------------------
    # Real effect dispatchers (Story 2-3)
    # ------------------------------------------------------------------
    def test_effect_recruit_infantry_creates_unit(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        territory = _make_territory(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty.id, 'recruit_infantry', 1300,
            target_territory_id=territory.id,
            params={'size': 150},
        )
        ps.tick_projects(dynasty.id, 1300)
        ps.complete_project(project.id)
        units = session.query(MilitaryUnit).filter_by(
            dynasty_id=dynasty.id, territory_id=territory.id,
        ).all()
        assert len(units) == 1
        assert units[0].unit_type == UnitType.LEVY_SPEARMEN
        assert units[0].size == 150

    def test_effect_build_farm_creates_building(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        territory = _make_territory(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty.id, 'build_farm', 1300,
            target_territory_id=territory.id,
        )
        ps.tick_projects(dynasty.id, 1300)
        ps.tick_projects(dynasty.id, 1301)
        ps.complete_project(project.id)
        farms = session.query(Building).filter_by(
            territory_id=territory.id,
            building_type=BuildingType.FARM,
        ).all()
        assert len(farms) == 1
        assert farms[0].level == 1
        assert farms[0].construction_year == 1300

    def test_effect_develop_territory_raises_dev_level(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        territory = _make_territory(session, dynasty, dev_level=2)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty.id, 'develop_territory', 1300,
            target_territory_id=territory.id,
        )
        for y in (1300, 1301, 1302):
            ps.tick_projects(dynasty.id, y)
        ps.complete_project(project.id)
        session.refresh(territory)
        assert territory.development_level == 3

    # ------------------------------------------------------------------
    # Multi-generation chronicle hook (Story 2-4)
    # ------------------------------------------------------------------
    def test_complete_same_monarch_no_multigen_entry(self, session):
        """Same-monarch completion does NOT write a multi-gen chronicle entry."""
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'envoy_mission', 1300)
        ps.complete_project(project.id)
        entries = session.query(HistoryLogEntryDB).filter_by(
            dynasty_id=dynasty.id,
            event_type='project_completed_multigen',
        ).all()
        assert entries == []

    def test_complete_multigen_writes_history_entry(self, session):
        """When initiator != completer, complete_project writes a HistoryLogEntryDB."""
        _, dynasty = _make_user_and_dynasty(session)
        initiator = _make_monarch(session, dynasty, name='Aldric I')
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'envoy_mission', 1300)
        # Replace the monarch (simulating death between start and completion).
        initiator.is_monarch = False
        initiator.death_year = 1310
        successor = _make_monarch(session, dynasty, name='Eldred II', birth_year=1290)
        session.commit()
        ps.complete_project(project.id)
        entries = session.query(HistoryLogEntryDB).filter_by(
            dynasty_id=dynasty.id,
            event_type='project_completed_multigen',
        ).all()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.person1_sim_id == initiator.id
        assert entry.person2_sim_id == successor.id
        assert entry.year == project.completion_year
        assert 'Aldric' in entry.event_string
        assert 'Eldred' in entry.event_string

    def test_complete_with_null_completer_skips_multigen(self, session):
        """Interregnum at completion (no living monarch) skips multi-gen entry."""
        _, dynasty = _make_user_and_dynasty(session)
        initiator = _make_monarch(session, dynasty, name='Aldric I')
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'envoy_mission', 1300)
        # Kill the monarch with no successor; complete_project will see no
        # living monarch and leave completed_by_monarch_id = NULL.
        initiator.is_monarch = False
        initiator.death_year = 1305
        session.commit()
        ps.complete_project(project.id)
        entries = session.query(HistoryLogEntryDB).filter_by(
            dynasty_id=dynasty.id,
            event_type='project_completed_multigen',
        ).all()
        assert entries == []
        # Project itself should still be marked completed.
        session.refresh(project)
        assert project.status == 'completed'

    def test_complete_effect_failure_rolls_back(self, session, monkeypatch):
        # If a dispatcher effect_fn raises, the session should be rolled back
        # and the project's status should NOT have been committed as 'completed'.
        from models import project_system as ps_module

        def boom(_session, _project):
            raise RuntimeError("simulated effect failure")

        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_farm', 1300)

        original = ps_module.EFFECT_DISPATCHER['build_farm']
        ps_module.EFFECT_DISPATCHER['build_farm'] = boom
        try:
            with pytest.raises(RuntimeError, match="simulated effect failure"):
                ps.complete_project(project.id)
            # session rolled back — re-load and confirm status is still 'active'
            session.expire_all()
            reloaded = session.get(Project, project.id)
            assert reloaded.status == 'active'
        finally:
            ps_module.EFFECT_DISPATCHER['build_farm'] = original
