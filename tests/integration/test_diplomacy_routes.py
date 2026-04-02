# tests/integration/test_diplomacy_routes.py
# Integration tests for diplomacy routes.
#
# Routes covered:
#   GET  /dynasty/<id>/diplomacy
#   GET  /dynasty/<id>/treaties
#   POST /dynasty/<id>/diplomatic_action
#   POST /dynasty/<id>/create_treaty
#   POST /dynasty/<id>/declare_war
#
# Note: the url_for bug in diplomacy_view.html (missing war_id) was fixed in the
# template — it now uses war_id=0 and replaces '/0' with '/' + warId dynamically.
# All previously-skipped tests now run.

import pytest
from models.db_models import User, DynastyDB, War, WarGoal

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user_and_dynasty(app, db, username, dynasty_name, password="pass123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@ex.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        dynasty = DynastyDB(
            user_id=user.id,
            name=dynasty_name,
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
def diplo_client(app, db, session):
    """Authenticated client with one dynasty that has NO active wars."""
    _, dynasty_id = _create_user_and_dynasty(
        app, db, "diplo_user", "House Diplomat"
    )
    with app.test_client() as c:
        c.post('/login', data={'username': 'diplo_user', 'password': 'pass123'})
        yield c, dynasty_id


@pytest.fixture
def two_dynasty_client(app, db, session):
    """Authenticated client (user A) plus a second dynasty owned by user B, no active wars."""
    _, did_a = _create_user_and_dynasty(app, db, "diplo_ua", "House AlphaD")
    _, did_b = _create_user_and_dynasty(app, db, "diplo_ub", "House BetaD")
    with app.test_client() as c:
        c.post('/login', data={'username': 'diplo_ua', 'password': 'pass123'})
        yield c, did_a, did_b


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestDiplomacyAuthGuards:
    def test_diplomacy_view_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/diplomacy', follow_redirects=False)
        assert response.status_code == 302

    def test_diplomacy_view_unauthenticated_goes_to_login(self, plain_client):
        response = plain_client.get('/dynasty/1/diplomacy', follow_redirects=True)
        assert b'Enter the Realm' in response.data

    def test_treaties_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/treaties', follow_redirects=False)
        assert response.status_code == 302

    def test_treaties_unauthenticated_goes_to_login(self, plain_client):
        response = plain_client.get('/dynasty/1/treaties', follow_redirects=True)
        assert b'Enter the Realm' in response.data


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/diplomacy
# ---------------------------------------------------------------------------

class TestDiplomacyView:
    def test_diplomacy_view_returns_200(self, diplo_client):
        """diplomacy_view renders correctly when the dynasty has no active wars."""
        client, dynasty_id = diplo_client
        response = client.get(f'/dynasty/{dynasty_id}/diplomacy')
        assert response.status_code == 200

    def test_diplomacy_view_shows_dynasty_name(self, diplo_client):
        client, dynasty_id = diplo_client
        response = client.get(f'/dynasty/{dynasty_id}/diplomacy')
        assert b'House Diplomat' in response.data

    def test_diplomacy_view_nonexistent_returns_404(self, diplo_client):
        client, _ = diplo_client
        response = client.get('/dynasty/99999/diplomacy')
        assert response.status_code == 404

    def test_diplomacy_view_other_user_forbidden(self, app, db, session):
        _, did_b = _create_user_and_dynasty(app, db, "diplo_ua2", "House AlphaD2")
        _, did_b2 = _create_user_and_dynasty(app, db, "diplo_ub2", "House BetaD2")
        with app.test_client() as c:
            c.post('/login', data={'username': 'diplo_ua2', 'password': 'pass123'})
            # The forbidden check redirects to /dashboard (no wars there)
            response = c.get(f'/dynasty/{did_b2}/diplomacy', follow_redirects=True)
            assert b'Not authorized' in response.data


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/treaties
# ---------------------------------------------------------------------------

class TestTreatyView:
    def test_treaties_returns_200(self, diplo_client):
        client, dynasty_id = diplo_client
        response = client.get(f'/dynasty/{dynasty_id}/treaties')
        assert response.status_code == 200

    def test_treaties_shows_dynasty_name(self, diplo_client):
        client, dynasty_id = diplo_client
        response = client.get(f'/dynasty/{dynasty_id}/treaties')
        assert b'House Diplomat' in response.data

    def test_treaties_nonexistent_returns_404(self, diplo_client):
        client, _ = diplo_client
        response = client.get('/dynasty/99999/treaties')
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/diplomatic_action
# ---------------------------------------------------------------------------

class TestDiplomaticAction:
    def test_diplomatic_action_missing_params(self, diplo_client):
        client, dynasty_id = diplo_client
        response = client.post(
            f'/dynasty/{dynasty_id}/diplomatic_action',
            data={},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Missing required parameters' in response.data

    def test_diplomatic_action_missing_params_redirect_only(self, diplo_client):
        """Verify the route redirects (302) on missing params without following it."""
        client, dynasty_id = diplo_client
        response = client.post(
            f'/dynasty/{dynasty_id}/diplomatic_action',
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_diplomatic_action_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/diplomatic_action',
            data={'target_dynasty_id': '2', 'action_type': 'send_gift'},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_diplomatic_action_with_target(self, two_dynasty_client):
        client, did_a, did_b = two_dynasty_client
        response = client.post(
            f'/dynasty/{did_a}/diplomatic_action',
            data={'target_dynasty_id': str(did_b), 'action_type': 'send_gift'},
            follow_redirects=True,
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/create_treaty
# ---------------------------------------------------------------------------

class TestCreateTreaty:
    def test_create_treaty_missing_params(self, diplo_client):
        client, dynasty_id = diplo_client
        response = client.post(
            f'/dynasty/{dynasty_id}/create_treaty',
            data={},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Missing required parameters' in response.data

    def test_create_treaty_missing_params_redirect_only(self, diplo_client):
        """Verify route redirects on missing params without following the redirect."""
        client, dynasty_id = diplo_client
        response = client.post(
            f'/dynasty/{dynasty_id}/create_treaty',
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_create_treaty_invalid_type(self, two_dynasty_client):
        client, did_a, did_b = two_dynasty_client
        response = client.post(
            f'/dynasty/{did_a}/create_treaty',
            data={
                'target_dynasty_id': str(did_b),
                'treaty_type': 'INVALID_TREATY_XYZ',
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Invalid treaty type' in response.data

    def test_create_treaty_invalid_type_redirect_only(self, two_dynasty_client):
        """Verify route redirects on invalid treaty type without following."""
        client, did_a, did_b = two_dynasty_client
        response = client.post(
            f'/dynasty/{did_a}/create_treaty',
            data={
                'target_dynasty_id': str(did_b),
                'treaty_type': 'INVALID_TREATY_XYZ',
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_create_treaty_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/create_treaty',
            data={'target_dynasty_id': '2', 'treaty_type': 'NON_AGGRESSION_PACT'},
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# POST /dynasty/<id>/declare_war
# ---------------------------------------------------------------------------

class TestDeclareWar:
    def test_declare_war_unauthenticated_redirects(self, plain_client):
        response = plain_client.post(
            '/dynasty/1/declare_war',
            data={'target_dynasty_id': '2', 'war_goal': 'CONQUEST'},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_declare_war_missing_params(self, diplo_client):
        client, dynasty_id = diplo_client
        response = client.post(
            f'/dynasty/{dynasty_id}/declare_war',
            data={},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_declare_war_missing_params_redirect_only(self, diplo_client):
        """Verify declare_war redirects on missing params without following."""
        client, dynasty_id = diplo_client
        response = client.post(
            f'/dynasty/{dynasty_id}/declare_war',
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_declare_war_nonexistent_dynasty_returns_404(self, diplo_client):
        client, _ = diplo_client
        response = client.post(
            '/dynasty/99999/declare_war',
            data={'target_dynasty_id': '1', 'war_goal': 'CONQUEST'},
        )
        assert response.status_code == 404
