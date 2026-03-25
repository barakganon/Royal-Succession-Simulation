# tests/integration/test_economy_routes.py
# Integration tests for economy management routes.
#
# Routes covered:
#   GET  /dynasty/<id>/economy
#   GET  /world/economy
#   POST /dynasty/<id>/construct_building
#   POST /dynasty/<id>/upgrade_building/<building_id>
#   POST /dynasty/<id>/repair_building/<building_id>

import pytest
from models.db_models import User, DynastyDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_user_and_dynasty(app, db, username="econ_user"):
    """Create user + dynasty; return (username, dynasty_id)."""
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password("econpass123")
        db.session.add(user)
        db.session.commit()
        dynasty = DynastyDB(
            user_id=user.id,
            name="House Merchant",
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=1000,
            start_year=1300,
            current_simulation_year=1300,
        )
        db.session.add(dynasty)
        db.session.commit()
        return username, dynasty.id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plain_client(app, db, session):
    with app.test_client() as c:
        yield c


@pytest.fixture
def econ_client(app, db, session):
    username, dynasty_id = _setup_user_and_dynasty(app, db)
    with app.test_client() as c:
        c.post('/login', data={'username': username, 'password': 'econpass123'})
        yield c, dynasty_id


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestEconomyAuthGuards:
    def test_dynasty_economy_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/economy', follow_redirects=False)
        assert response.status_code == 302

    def test_dynasty_economy_unauthenticated_goes_to_login(self, plain_client):
        response = plain_client.get('/dynasty/1/economy', follow_redirects=True)
        assert b'Enter the Realm' in response.data

    def test_world_economy_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/world/economy', follow_redirects=False)
        assert response.status_code == 302

    def test_world_economy_unauthenticated_goes_to_login(self, plain_client):
        response = plain_client.get('/world/economy', follow_redirects=True)
        assert b'Enter the Realm' in response.data


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/economy
# ---------------------------------------------------------------------------

class TestDynastyEconomy:
    def test_dynasty_economy_returns_200(self, econ_client):
        client, dynasty_id = econ_client
        response = client.get(f'/dynasty/{dynasty_id}/economy')
        assert response.status_code == 200

    def test_dynasty_economy_shows_dynasty_name(self, econ_client):
        client, dynasty_id = econ_client
        response = client.get(f'/dynasty/{dynasty_id}/economy')
        assert b'House Merchant' in response.data

    def test_dynasty_economy_nonexistent_returns_404(self, econ_client):
        client, _ = econ_client
        response = client.get('/dynasty/99999/economy')
        assert response.status_code == 404

    def test_dynasty_economy_other_user_forbidden(self, app, db, session):
        """User A cannot view User B's economy."""
        with app.app_context():
            ua = User(username="econ_a_user", email="ea@ex.com")
            ua.set_password("passA")
            ub = User(username="econ_b_user", email="eb@ex.com")
            ub.set_password("passB")
            db.session.add_all([ua, ub])
            db.session.commit()
            dyn = DynastyDB(
                user_id=ub.id,
                name="House B Economy",
                theme_identifier_or_json=VALID_THEME_KEY,
                current_wealth=100,
                start_year=1000,
                current_simulation_year=1000,
            )
            db.session.add(dyn)
            db.session.commit()
            dyn_id = dyn.id

        with app.test_client() as c:
            c.post('/login', data={'username': 'econ_a_user', 'password': 'passA'})
            response = c.get(f'/dynasty/{dyn_id}/economy', follow_redirects=True)
            assert b'Not authorized' in response.data


# ---------------------------------------------------------------------------
# GET /world/economy
# ---------------------------------------------------------------------------

class TestWorldEconomy:
    def test_world_economy_returns_200(self, econ_client):
        client, _ = econ_client
        response = client.get('/world/economy')
        assert response.status_code == 200

    def test_world_economy_contains_economy_content(self, econ_client):
        client, _ = econ_client
        response = client.get('/world/economy')
        # The world economy template is world_economy.html
        assert b'Economy' in response.data or b'economy' in response.data


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/construct_building
# ---------------------------------------------------------------------------

class TestConstructBuilding:
    def test_construct_building_missing_params(self, econ_client):
        client, dynasty_id = econ_client
        response = client.post(
            f'/dynasty/{dynasty_id}/construct_building',
            data={},  # missing territory_id and building_type
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Missing required parameters' in response.data

    def test_construct_building_invalid_type(self, econ_client):
        client, dynasty_id = econ_client
        response = client.post(
            f'/dynasty/{dynasty_id}/construct_building',
            data={'territory_id': '1', 'building_type': 'INVALID_BUILDING_XYZ'},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Error' in response.data

    def test_construct_building_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/construct_building',
            data={'territory_id': '1', 'building_type': 'FARM'},
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/upgrade_building/<building_id>
# ---------------------------------------------------------------------------

class TestUpgradeBuilding:
    def test_upgrade_building_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/upgrade_building/1',
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_upgrade_building_nonexistent_dynasty_returns_404(self, econ_client):
        client, _ = econ_client
        response = client.post(
            '/dynasty/99999/upgrade_building/1',
            data={},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/repair_building/<building_id>
# ---------------------------------------------------------------------------

class TestRepairBuilding:
    def test_repair_building_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/repair_building/1',
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_repair_building_nonexistent_dynasty_returns_404(self, econ_client):
        client, _ = econ_client
        response = client.post(
            '/dynasty/99999/repair_building/1',
            data={},
        )
        assert response.status_code == 404
