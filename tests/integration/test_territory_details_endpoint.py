# tests/integration/test_territory_details_endpoint.py
# Sprint 3 Story 3-3 AC2 + AC8 — integration tests for the new
# `/territory/<id>/details.json` endpoint.

import pytest

from models.db_models import (
    Building, BuildingType, DynastyDB, MilitaryUnit, PersonDB, Project,
    Province, Region, Territory, TerrainType, UnitType, User,
)

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_and_login(app, db, client, username='td_user'):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': 'password123'})


def _create_dynasty(client, name='House Detail'):
    client.post('/dynasty/create', data={
        'dynasty_name': name,
        'theme_type': 'predefined',
        'theme_key': VALID_THEME_KEY,
        'start_year': '1300',
        'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
    }, follow_redirects=True)


def _make_territory(app, db, name='Old Hollow', controller_id=None):
    """Direct-DB-write helper: a Province/Region scaffolding + one Territory."""
    import uuid
    suffix = uuid.uuid4().hex[:6]
    with app.app_context():
        region = Region(name=f'Region_{suffix}', description='td-test')
        db.session.add(region)
        db.session.commit()
        province = Province(
            region_id=region.id,
            name=f'Province_{suffix}',
            primary_terrain=TerrainType.PLAINS,
        )
        db.session.add(province)
        db.session.commit()
        territory = Territory(
            province_id=province.id,
            name=f'{name}_{suffix}',
            terrain_type=TerrainType.PLAINS,
            x_coordinate=2.0,
            y_coordinate=3.0,
            controller_dynasty_id=controller_id,
            development_level=2,
            population=1234,
            base_tax=5,
            fortification_level=1,
            is_capital=False,
        )
        db.session.add(territory)
        db.session.commit()
        return territory.id


@pytest.fixture
def td_client(app, db, session):
    with app.test_client() as c:
        _register_and_login(app, db, c, username='td_user')
        _create_dynasty(c)
        yield c


class TestTerritoryDetailsEndpoint:
    def test_returns_404_for_missing_territory(self, td_client):
        response = td_client.get('/territory/99999/details.json')
        assert response.status_code == 404

    def test_returns_200_with_expected_top_level_keys(self, app, db, td_client):
        # Create a territory NOT owned by the player.
        territory_id = _make_territory(app, db, controller_id=None)
        response = td_client.get(f'/territory/{territory_id}/details.json')
        assert response.status_code == 200
        payload = response.get_json()
        assert set(payload.keys()) >= {'territory', 'buildings', 'garrison', 'active_project'}
        terr = payload['territory']
        for key in (
            'id', 'name', 'terrain_type', 'population', 'development_level',
            'is_capital', 'base_tax', 'fortification_level',
            'controller', 'is_player_owned',
        ):
            assert key in terr, f"missing key {key!r} in territory payload"
        assert terr['id'] == territory_id
        assert terr['terrain_type'] == 'plains'
        assert terr['population'] == 1234
        assert terr['development_level'] == 2
        assert terr['base_tax'] == 5
        assert terr['fortification_level'] == 1
        assert terr['controller'] is None
        assert terr['is_player_owned'] is False
        # No buildings / garrison / project were created → empty collections.
        assert payload['buildings'] == []
        assert payload['garrison'] == []
        assert payload['active_project'] is None

    def test_is_player_owned_true_when_user_owns_controller(self, app, db, td_client):
        # Find the player dynasty and create a territory it controls.
        with app.app_context():
            player_dynasty = DynastyDB.query.filter_by(name='House Detail').first()
            assert player_dynasty is not None
            controller_id = player_dynasty.id
        territory_id = _make_territory(app, db, controller_id=controller_id)
        response = td_client.get(f'/territory/{territory_id}/details.json')
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['territory']['is_player_owned'] is True
        assert payload['territory']['controller'] == {
            'id': controller_id,
            'name': 'House Detail',
        }

    def test_is_player_owned_false_when_other_user_owns(self, app, db, td_client):
        # Create a second user + dynasty via direct DB writes (same pattern
        # as test_world_map_context_menu.py).
        with app.app_context():
            other = User(username='td_other', email='td_other@x.test')
            other.set_password('password123')
            db.session.add(other)
            db.session.commit()
            other_dynasty = DynastyDB(
                user_id=other.id,
                name='House Foreign',
                theme_identifier_or_json='MEDIEVAL_EUROPEAN',
                current_wealth=100,
                start_year=1300,
                current_simulation_year=1300,
            )
            db.session.add(other_dynasty)
            db.session.commit()
            other_dynasty_id = other_dynasty.id

        territory_id = _make_territory(app, db, controller_id=other_dynasty_id)
        response = td_client.get(f'/territory/{territory_id}/details.json')
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['territory']['is_player_owned'] is False
        assert payload['territory']['controller'] == {
            'id': other_dynasty_id,
            'name': 'House Foreign',
        }

    def test_payload_includes_buildings_garrison_and_active_project(self, app, db, td_client):
        with app.app_context():
            player_dynasty = DynastyDB.query.filter_by(name='House Detail').first()
            controller_id = player_dynasty.id

        territory_id = _make_territory(app, db, controller_id=controller_id)

        with app.app_context():
            # Building
            db.session.add(Building(
                territory_id=territory_id,
                building_type=BuildingType.FARM,
                name='Riverside Farm',
                level=1,
                condition=0.85,
                construction_year=1300,
                maintenance_cost=1,
            ))
            # Garrison unit owned by player dynasty
            db.session.add(MilitaryUnit(
                dynasty_id=controller_id,
                unit_type=UnitType.LEVY_SPEARMEN,
                name='Levy',
                size=120,
                quality=1.0,
                morale=1.0,
                territory_id=territory_id,
                maintenance_cost=1,
                food_consumption=1.0,
                created_year=1300,
            ))
            # Active project targeting the territory
            monarch = PersonDB.query.filter_by(
                dynasty_id=controller_id, is_monarch=True
            ).first()
            assert monarch is not None
            db.session.add(Project(
                dynasty_id=controller_id,
                project_type='build_walls',
                target_territory_id=territory_id,
                started_year=1300,
                completion_year=1303,
                yearly_cost_gold=50,
                status='active',
                initiated_by_monarch_id=monarch.id,
            ))
            db.session.commit()

        response = td_client.get(f'/territory/{territory_id}/details.json')
        assert response.status_code == 200
        payload = response.get_json()

        # Buildings include condition (per spec).
        assert len(payload['buildings']) == 1
        b = payload['buildings'][0]
        assert b['building_type'] == 'farm'
        assert b['name'] == 'Riverside Farm'
        assert b['level'] == 1
        assert b['condition'] == pytest.approx(0.85)

        # Garrison entry
        assert len(payload['garrison']) == 1
        g = payload['garrison'][0]
        assert g['unit_type'] == 'levy_spearmen'
        assert g['size'] == 120
        assert g['morale'] == pytest.approx(1.0)
        assert g['quality'] == pytest.approx(1.0)

        # Active project block
        assert payload['active_project'] is not None
        ap = payload['active_project']
        assert ap['project_type'] == 'build_walls'
        assert ap['started_year'] == 1300
        assert ap['completion_year'] == 1303
        assert isinstance(ap['id'], int)
