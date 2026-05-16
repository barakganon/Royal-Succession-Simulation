import uuid
import pytest

from models.db_models import DynastyDB, PersonDB, Project, User
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
        _, dynasty = _make_user_and_dynasty(session, wealth=200, timber=100)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        ps.start_project(dynasty.id, 'build_farm', 1300)
        ps.tick_projects(dynasty.id, 1300)
        session.refresh(dynasty)
        assert dynasty.current_wealth == 170  # 200 - 30
        assert dynasty.current_timber == 80   # 100 - 20

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
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(dynasty.id, 'build_farm', 1300)
        with caplog.at_level('INFO', logger='royal_succession.project_system'):
            completed = ps.complete_project(project.id)
        assert completed.status == 'completed'
        assert completed.completed_by_monarch_id is not None
        # Stub effect should have logged a [stub] line.
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
        # dispatcher (even if just a stub) — otherwise complete_project would
        # log a warning rather than apply an effect.
        assert set(EFFECT_DISPATCHER) == set(PROJECT_TYPE_CATALOGUE)
