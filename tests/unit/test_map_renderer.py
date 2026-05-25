# tests/unit/test_map_renderer.py
# Sprint 3 Story 3-3 AC1 — unit tests for `generate_geojson` hex-mode
# enrichment (buildings, garrison_total, hostile_garrison_total,
# active_project_type / active_project_id).

import uuid

import pytest

from models.db_models import (
    Building, BuildingType, DynastyDB, MilitaryUnit, PersonDB, Project,
    Province, Region, Territory, TerrainType, UnitType, User,
)
from visualization.map_renderer import generate_geojson


def _make_user_dynasty(session, name='House Geo', wealth=500, year=1300):
    suffix = uuid.uuid4().hex[:8]
    slug = name.lower().replace(' ', '_')
    user = User(username=f"u_{slug}_{suffix}", email=f"{slug}+{suffix}@x.test")
    user.set_password('password123')
    session.add(user)
    session.commit()
    dynasty = DynastyDB(
        user_id=user.id,
        name=name,
        theme_identifier_or_json='medieval_europe',
        start_year=year,
        current_simulation_year=year,
        current_wealth=wealth,
    )
    session.add(dynasty)
    session.commit()
    return user, dynasty


def _make_monarch(session, dynasty, birth_year=1270):
    person = PersonDB(
        dynasty_id=dynasty.id,
        name='Aldric',
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


def _make_territory(session, name='Old Hollow', controller_id=None,
                    cx=2.0, cy=3.0):
    suffix = uuid.uuid4().hex[:6]
    region = Region(name=f'Region_{suffix}', description='Test')
    session.add(region)
    session.commit()
    province = Province(
        region_id=region.id,
        name=f'Province_{suffix}',
        primary_terrain=TerrainType.PLAINS,
    )
    session.add(province)
    session.commit()
    territory = Territory(
        province_id=province.id,
        name=f'{name}_{suffix}',
        terrain_type=TerrainType.PLAINS,
        x_coordinate=cx,
        y_coordinate=cy,
        controller_dynasty_id=controller_id,
        development_level=2,
        population=1234,
    )
    session.add(territory)
    session.commit()
    return territory


@pytest.mark.unit
class TestGenerateGeoJsonHexModeEnrichment:
    """AC1 — hex_mode features expose buildings/garrison/active_project."""

    def test_hex_mode_emits_buildings_garrison_and_active_project(self, session):
        _, player = _make_user_dynasty(session, name='House Player')
        _make_monarch(session, player)
        _, foreigner = _make_user_dynasty(session, name='House Foreign')

        territory = _make_territory(session, controller_id=player.id)

        # One Building on the territory.
        building = Building(
            territory_id=territory.id,
            building_type=BuildingType.FARM,
            name='Riverside Farm',
            level=2,
            condition=0.9,
            construction_year=1300,
            maintenance_cost=1,
        )
        session.add(building)

        # Garrison: 80-strong levy unit owned by the controller dynasty.
        own_unit = MilitaryUnit(
            dynasty_id=player.id,
            unit_type=UnitType.LEVY_SPEARMEN,
            name='Levy',
            size=80,
            quality=1.0,
            morale=1.0,
            territory_id=territory.id,
            maintenance_cost=1,
            food_consumption=1.0,
            created_year=1300,
        )
        # Hostile garrison: 50-strong foreign unit physically in the territory.
        foreign_unit = MilitaryUnit(
            dynasty_id=foreigner.id,
            unit_type=UnitType.HEAVY_CAVALRY,
            name='Foreign Cav',
            size=50,
            quality=1.0,
            morale=1.0,
            territory_id=territory.id,
            maintenance_cost=2,
            food_consumption=1.5,
            created_year=1300,
        )
        session.add(own_unit)
        session.add(foreign_unit)

        # Player-owned project targeting the same territory.
        project = Project(
            dynasty_id=player.id,
            project_type='build_walls',
            target_territory_id=territory.id,
            started_year=1300,
            completion_year=1303,
            yearly_cost_gold=50,
            yearly_cost_iron=10,
            yearly_cost_timber=20,
            status='active',
            initiated_by_monarch_id=player.persons.first().id,
        )
        session.add(project)
        session.commit()

        fc = generate_geojson(player.id, session, hex_mode=True)
        assert fc['type'] == 'FeatureCollection'
        # Exactly one feature (we only made one territory).
        assert len(fc['features']) == 1
        props = fc['features'][0]['properties']

        # Buildings list — compact form per spec.
        assert isinstance(props['buildings'], list)
        assert len(props['buildings']) == 1
        b = props['buildings'][0]
        assert b['building_type'] == 'farm'
        assert b['name'] == 'Riverside Farm'
        assert b['level'] == 2

        # Garrison vs. hostile garrison sums.
        assert props['garrison_total'] == 80
        assert props['hostile_garrison_total'] == 50

        # Active player project surfaces.
        assert props['active_project_type'] == 'build_walls'
        assert props['active_project_id'] == project.id

    def test_hex_mode_skips_foreign_active_projects(self, session):
        _, player = _make_user_dynasty(session, name='House Local')
        _make_monarch(session, player)
        _, foreigner = _make_user_dynasty(session, name='House Foreign2')
        _make_monarch(session, foreigner)

        territory = _make_territory(session, controller_id=player.id)

        # Foreign dynasty has a project targeting the same territory — must
        # NOT appear in the player's GeoJSON.
        proj = Project(
            dynasty_id=foreigner.id,
            project_type='build_walls',
            target_territory_id=territory.id,
            started_year=1300,
            completion_year=1303,
            status='active',
            initiated_by_monarch_id=foreigner.persons.first().id,
        )
        session.add(proj)
        session.commit()

        fc = generate_geojson(player.id, session, hex_mode=True)
        props = fc['features'][0]['properties']
        assert props['active_project_type'] is None
        assert props['active_project_id'] is None

    def test_hex_mode_empty_when_no_buildings_or_units(self, session):
        _, player = _make_user_dynasty(session, name='House Bare')
        _make_monarch(session, player)
        _make_territory(session, controller_id=player.id)

        fc = generate_geojson(player.id, session, hex_mode=True)
        props = fc['features'][0]['properties']
        assert props['buildings'] == []
        assert props['garrison_total'] == 0
        assert props['hostile_garrison_total'] == 0
        assert props['active_project_type'] is None
        assert props['active_project_id'] is None

    def test_non_hex_mode_omits_new_fields(self, session):
        _, player = _make_user_dynasty(session, name='House Legacy')
        _make_monarch(session, player)
        _make_territory(session, controller_id=player.id)

        fc = generate_geojson(player.id, session, hex_mode=False)
        props = fc['features'][0]['properties']
        # Story 3-3 fields are only emitted in hex_mode.
        assert 'buildings' not in props
        assert 'garrison_total' not in props
        assert 'hostile_garrison_total' not in props
        assert 'active_project_type' not in props
        assert 'active_project_id' not in props
