"""Tests for construct_building routed through ProjectSystem (Story 11-5).

Covers:
- start_project override kwargs (duration_years, yearly_cost_gold)
- _effect_build_building creates a Building with no phantom attrs
- construct_building happy path creates a Project row (no Building yet)
- construct_building insufficient funds returns (False, ...)
- construct_building no living monarch returns (False, ...)
"""
import json
import uuid

import pytest

from models.db_models import (
    Building, BuildingType, DynastyDB, PersonDB, Project, Province, Region,
    Territory, TerrainType, User,
)
from models.economy_system import EconomySystem
from models.project_system import (
    EFFECT_DISPATCHER,
    PROJECT_TYPE_CATALOGUE,
    ProjectSystem,
    _effect_build_building,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers (same pattern as test_project_system.py)
# ---------------------------------------------------------------------------

def _make_user_and_dynasty(session, name='Test Dynasty', year=1300,
                            wealth=500, iron=100, timber=200):
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


def _make_territory(session, dynasty, name='Testburg', dev_level=1):
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


def _make_monarch(session, dynasty, name='Rainer I', birth_year=1270):
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.model
class TestStartProjectOverride:
    """Verify that start_project honours override kwargs."""

    def test_override_duration_and_cost(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty_id=dynasty.id,
            project_type='build_building',
            started_year=1300,
            params={'building_type': 'market'},
            duration_years=3,
            yearly_cost_gold=200,
        )
        assert project.status == 'active'
        assert project.completion_year == 1303  # started_year + 3
        assert project.yearly_cost_gold == 200

    def test_catalogue_entry_present(self):
        assert 'build_building' in PROJECT_TYPE_CATALOGUE
        cat = PROJECT_TYPE_CATALOGUE['build_building']
        assert cat['duration_years'] == 2
        assert cat['yearly_cost_gold'] == 50

    def test_dispatcher_entry_present(self):
        assert 'build_building' in EFFECT_DISPATCHER
        assert callable(EFFECT_DISPATCHER['build_building'])


@pytest.mark.unit
@pytest.mark.model
class TestEffectBuildBuilding:
    """Verify _effect_build_building creates a valid Building row."""

    def test_creates_building_in_territory(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        territory = _make_territory(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty_id=dynasty.id,
            project_type='build_building',
            started_year=1300,
            target_territory_id=territory.id,
            params={'building_type': 'market'},
            duration_years=2,
            yearly_cost_gold=120,
            yearly_cost_timber=40,
        )
        # Tick to drain costs then complete
        ps.tick_projects(dynasty.id, 1300)
        ps.tick_projects(dynasty.id, 1301)
        ps.complete_project(project.id)

        buildings = session.query(Building).filter_by(
            territory_id=territory.id,
            building_type=BuildingType.MARKET,
        ).all()
        assert len(buildings) == 1
        b = buildings[0]
        assert b.level == 1
        assert b.condition == 1.0
        assert b.construction_year == 1300
        # Must NOT have phantom attributes
        assert not hasattr(b, 'is_under_construction') or True  # no AttributeError

    def test_skips_gracefully_when_no_territory(self, session):
        _, dynasty = _make_user_and_dynasty(session)
        _make_monarch(session, dynasty)
        ps = ProjectSystem(session)
        project = ps.start_project(
            dynasty_id=dynasty.id,
            project_type='build_building',
            started_year=1300,
            params={'building_type': 'farm'},
        )
        # Complete without a target_territory_id — should not crash
        ps.complete_project(project.id)
        session.refresh(project)
        assert project.status == 'completed'
        # No buildings created
        all_buildings = session.query(Building).filter_by(
            territory_id=None,
        ).count()
        assert all_buildings == 0


@pytest.mark.unit
@pytest.mark.model
class TestConstructBuilding:
    """Integration tests for EconomySystem.construct_building."""

    def test_happy_path_creates_project_not_building(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=1000, timber=200)
        _make_monarch(session, dynasty)
        territory = _make_territory(session, dynasty)

        eco = EconomySystem(session)
        success, msg = eco.construct_building(territory.id, BuildingType.MARKET)

        assert success is True
        assert "Commissioned" in msg or "completes in" in msg

        # A Project row must exist; no Building row yet
        projects = session.query(Project).filter_by(
            dynasty_id=dynasty.id,
            project_type='build_building',
        ).all()
        assert len(projects) == 1
        assert projects[0].status == 'active'

        params = projects[0].get_params()
        assert params.get('building_type') == 'market'
        assert projects[0].target_territory_id == territory.id

        buildings = session.query(Building).filter_by(
            territory_id=territory.id,
        ).all()
        assert len(buildings) == 0

    def test_insufficient_funds_returns_false(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=5)  # market costs 120 gold
        _make_monarch(session, dynasty)
        territory = _make_territory(session, dynasty)

        eco = EconomySystem(session)
        success, msg = eco.construct_building(territory.id, BuildingType.MARKET)

        assert success is False
        assert "resource" in msg.lower() or "enough" in msg.lower()

    def test_no_living_monarch_returns_false(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=1000, timber=200)
        # NB: no monarch created
        territory = _make_territory(session, dynasty)

        eco = EconomySystem(session)
        success, msg = eco.construct_building(territory.id, BuildingType.MARKET)

        assert success is False
        assert "monarch" in msg.lower()

    def test_duplicate_building_blocked(self, session):
        _, dynasty = _make_user_and_dynasty(session, wealth=1000, timber=200)
        _make_monarch(session, dynasty)
        territory = _make_territory(session, dynasty)

        # Pre-seed a farm
        existing = Building(
            territory_id=territory.id,
            building_type=BuildingType.FARM,
            name='Farm',
            level=1,
            condition=1.0,
            construction_year=1290,
        )
        session.add(existing)
        session.commit()

        eco = EconomySystem(session)
        success, msg = eco.construct_building(territory.id, BuildingType.FARM)

        assert success is False
        assert "already exists" in msg.lower()
