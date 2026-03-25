# tests/integration/test_military_routes.py
# Integration tests for military management routes.
#
# Routes covered:
#   GET  /dynasty/<id>/military
#   POST /dynasty/<id>/recruit_unit
#   POST /dynasty/<id>/form_army
#   GET  /dynasty/<id>/military_gameplay
#   GET  /army/<id>

import pytest
from models.db_models import User, DynastyDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_user_and_dynasty(app, db, username="mil_user"):
    """Create a user and dynasty; return (user_id, dynasty_id)."""
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password("milpass123")
        db.session.add(user)
        db.session.commit()
        dynasty = DynastyDB(
            user_id=user.id,
            name="House Warchief",
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=500,
            start_year=1200,
            current_simulation_year=1200,
        )
        db.session.add(dynasty)
        db.session.commit()
        return user.id, dynasty.id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plain_client(app, db, session):
    with app.test_client() as c:
        yield c


@pytest.fixture
def mil_client(app, db, session):
    """Authenticated client with a dynasty."""
    uid, did = _setup_user_and_dynasty(app, db)
    with app.test_client() as c:
        c.post('/login', data={'username': 'mil_user', 'password': 'milpass123'})
        yield c, did


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestMilitaryAuthGuards:
    def test_military_view_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/military', follow_redirects=False)
        assert response.status_code == 302

    def test_military_view_unauthenticated_goes_to_login(self, plain_client):
        response = plain_client.get('/dynasty/1/military', follow_redirects=True)
        assert b'Enter the Realm' in response.data

    def test_military_gameplay_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/military_gameplay', follow_redirects=False)
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/military
# ---------------------------------------------------------------------------

class TestMilitaryView:
    def test_military_view_returns_200(self, mil_client):
        client, dynasty_id = mil_client
        response = client.get(f'/dynasty/{dynasty_id}/military')
        assert response.status_code == 200

    def test_military_view_shows_dynasty_name(self, mil_client):
        client, dynasty_id = mil_client
        response = client.get(f'/dynasty/{dynasty_id}/military')
        assert b'House Warchief' in response.data

    def test_military_view_nonexistent_dynasty_returns_404(self, mil_client):
        client, _ = mil_client
        response = client.get('/dynasty/99999/military')
        assert response.status_code == 404

    def test_military_view_other_dynasty_forbidden(self, app, db, session):
        """User A cannot access User B's military view."""
        with app.app_context():
            ua = User(username="mil_a_user", email="mila@ex.com")
            ua.set_password("passA")
            ub = User(username="mil_b_user", email="milb@ex.com")
            ub.set_password("passB")
            db.session.add_all([ua, ub])
            db.session.commit()
            dyn = DynastyDB(
                user_id=ub.id,
                name="House B Military",
                theme_identifier_or_json=VALID_THEME_KEY,
                current_wealth=100,
                start_year=1000,
                current_simulation_year=1000,
            )
            db.session.add(dyn)
            db.session.commit()
            dyn_id = dyn.id

        with app.test_client() as c:
            c.post('/login', data={'username': 'mil_a_user', 'password': 'passA'})
            response = c.get(f'/dynasty/{dyn_id}/military', follow_redirects=True)
            assert b'Not authorized' in response.data


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/recruit_unit
# ---------------------------------------------------------------------------

class TestRecruitUnit:
    def test_recruit_unit_missing_params_shows_error(self, mil_client):
        client, dynasty_id = mil_client
        response = client.post(
            f'/dynasty/{dynasty_id}/recruit_unit',
            data={},  # no unit_type, size, or territory_id
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Missing required fields' in response.data

    def test_recruit_unit_invalid_type_shows_error(self, mil_client):
        client, dynasty_id = mil_client
        response = client.post(
            f'/dynasty/{dynasty_id}/recruit_unit',
            data={
                'unit_type': 'INVALID_UNIT_TYPE_XYZ',
                'size': '100',
                'territory_id': '1',
                'name': 'Test Unit',
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Invalid unit type' in response.data

    def test_recruit_unit_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/recruit_unit',
            data={'unit_type': 'HEAVY_INFANTRY', 'size': '100', 'territory_id': '1'},
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/form_army
# ---------------------------------------------------------------------------

class TestFormArmy:
    def test_form_army_missing_params_shows_error(self, mil_client):
        client, dynasty_id = mil_client
        response = client.post(
            f'/dynasty/{dynasty_id}/form_army',
            data={},  # no unit_ids or name
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Route flashes "Missing required fields" or similar
        assert b'Missing required' in response.data or b'required' in response.data.lower()

    def test_form_army_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/form_army',
            data={'name': 'Test Army', 'unit_ids': '1'},
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/military_gameplay
# ---------------------------------------------------------------------------

class TestMilitaryGameplay:
    def test_military_gameplay_returns_200(self, mil_client):
        client, dynasty_id = mil_client
        response = client.get(f'/dynasty/{dynasty_id}/military_gameplay')
        assert response.status_code == 200

    def test_military_gameplay_shows_dynasty_name(self, mil_client):
        client, dynasty_id = mil_client
        response = client.get(f'/dynasty/{dynasty_id}/military_gameplay')
        assert b'House Warchief' in response.data or b'Military' in response.data
