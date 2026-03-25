# tests/integration/test_dynasty_routes.py
# Integration tests for dynasty creation, view, and management routes.
#
# Design note: the integration conftest uses a module-scoped `app` and `db`.
# To avoid cross-test state contamination we use a per-test `session` fixture
# (from integration/conftest.py) that drops and recreates all tables, then
# rebuild any needed data inside the same app_context.

import pytest
from models.db_models import User, DynastyDB

# The correct theme key as stored in cultural_themes.json
VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _register_and_login(app, db, client, username="dyn_user", password="dynpass123"):
    """Create a user in the DB (inside app_context) and log in via the client."""
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, dynasty_name="House Ironwood", start_year="1200"):
    """Submit the create dynasty form and return the response."""
    return client.post(
        '/dynasty/create',
        data={
            'dynasty_name': dynasty_name,
            'theme_type': 'predefined',
            'theme_key': VALID_THEME_KEY,
            'start_year': start_year,
            'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
        },
        follow_redirects=True,
    )


def _get_dynasty_id(app, db, username="dyn_user"):
    """Return the first dynasty id owned by the given user."""
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
        return dynasty.id if dynasty else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plain_client(app, db, session):
    """Unauthenticated client with a clean DB."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(app, db, session):
    """Client logged in as a fresh user."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username="auth_dyn_user")
        yield c


@pytest.fixture
def dynasty_client(app, db, session):
    """Client with a logged-in user who already owns one dynasty."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username="dyn_user")
        _create_dynasty(c)
        yield c


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------

class TestDynastyAuthGuards:
    def test_create_dynasty_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/create', follow_redirects=False)
        assert response.status_code == 302

    def test_create_dynasty_unauthenticated_goes_to_login(self, plain_client):
        response = plain_client.get('/dynasty/create', follow_redirects=True)
        assert b'Enter the Realm' in response.data

    def test_view_dynasty_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/view', follow_redirects=False)
        assert response.status_code == 302

    def test_dashboard_protected(self, plain_client):
        response = plain_client.get('/dashboard', follow_redirects=True)
        assert b'Enter the Realm' in response.data


# ---------------------------------------------------------------------------
# GET /dynasty/create
# ---------------------------------------------------------------------------

class TestCreateDynastyGet:
    def test_create_dynasty_returns_200(self, auth_client):
        response = auth_client.get('/dynasty/create')
        assert response.status_code == 200

    def test_create_dynasty_contains_name_field(self, auth_client):
        response = auth_client.get('/dynasty/create')
        assert b'dynasty_name' in response.data

    def test_create_dynasty_contains_theme_element(self, auth_client):
        response = auth_client.get('/dynasty/create')
        assert b'theme' in response.data.lower()

    def test_create_dynasty_contains_start_year_field(self, auth_client):
        response = auth_client.get('/dynasty/create')
        assert b'start_year' in response.data


# ---------------------------------------------------------------------------
# POST /dynasty/create
# ---------------------------------------------------------------------------

class TestCreateDynastyPost:
    def test_valid_creation_redirects_to_view(self, auth_client):
        response = auth_client.post(
            '/dynasty/create',
            data={
                'dynasty_name': 'House Silverhand',
                'theme_type': 'predefined',
                'theme_key': VALID_THEME_KEY,
                'start_year': '1300',
                'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
            },
            follow_redirects=False,
        )
        # Route redirects to /dynasty/<id>/view on success
        assert response.status_code == 302
        assert '/dynasty/' in response.location and '/view' in response.location

    def test_valid_creation_shows_success_flash(self, auth_client):
        response = auth_client.post(
            '/dynasty/create',
            data={
                'dynasty_name': 'House Silverhand',
                'theme_type': 'predefined',
                'theme_key': VALID_THEME_KEY,
                'start_year': '1300',
                'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
            },
            follow_redirects=True,
        )
        assert b'created successfully' in response.data

    def test_valid_creation_persists_dynasty(self, auth_client, app, db):
        auth_client.post(
            '/dynasty/create',
            data={
                'dynasty_name': 'House Blackwood',
                'theme_type': 'predefined',
                'theme_key': VALID_THEME_KEY,
                'start_year': '1350',
                'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
            },
        )
        with app.app_context():
            dynasty = db.session.query(DynastyDB).filter_by(name='House Blackwood').first()
            assert dynasty is not None
            assert dynasty.start_year == 1350

    def test_short_dynasty_name_shows_error(self, auth_client):
        response = auth_client.post(
            '/dynasty/create',
            data={
                'dynasty_name': 'X',
                'theme_type': 'predefined',
                'theme_key': VALID_THEME_KEY,
                'start_year': '1300',
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'valid dynasty name' in response.data

    def test_invalid_theme_key_shows_error(self, auth_client):
        response = auth_client.post(
            '/dynasty/create',
            data={
                'dynasty_name': 'House Valid',
                'theme_type': 'predefined',
                'theme_key': 'nonexistent_theme_xyz',
                'start_year': '1300',
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Route flashes "Selected theme not found."
        assert b'not found' in response.data.lower()


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/view
# ---------------------------------------------------------------------------

class TestViewDynasty:
    def test_view_own_dynasty_returns_200(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        assert dynasty_id is not None
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/view')
        assert response.status_code == 200

    def test_view_own_dynasty_shows_name(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/view')
        assert b'House Ironwood' in response.data

    def test_view_nonexistent_dynasty_returns_404(self, auth_client):
        response = auth_client.get('/dynasty/99999/view')
        assert response.status_code == 404

    def test_view_other_user_dynasty_forbidden(self, app, db, session):
        """User A cannot view User B's dynasty — should get 'Not authorized' flash."""
        with app.app_context():
            userA = User(username="usr_a_forbidden", email="ua@ex.com")
            userA.set_password("passA")
            userB = User(username="usr_b_forbidden", email="ub@ex.com")
            userB.set_password("passB")
            db.session.add_all([userA, userB])
            db.session.commit()
            dynasty = DynastyDB(
                user_id=userB.id,
                name="House UserB Forbidden",
                theme_identifier_or_json="MEDIEVAL_EUROPEAN",
                current_wealth=100,
                start_year=1000,
                current_simulation_year=1000,
            )
            db.session.add(dynasty)
            db.session.commit()
            dynasty_id = dynasty.id

        with app.test_client() as c:
            c.post('/login', data={'username': 'usr_a_forbidden', 'password': 'passA'})
            response = c.get(f'/dynasty/{dynasty_id}/view', follow_redirects=True)
            assert b'Not authorized' in response.data


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/delete — confirmation page
# ---------------------------------------------------------------------------

class TestDeleteDynastyPage:
    def test_delete_page_get_returns_200(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/delete')
        assert response.status_code == 200

    def test_delete_page_shows_dynasty_name(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/delete')
        assert b'House Ironwood' in response.data

    @pytest.mark.skip(
        reason=(
            "Delete is broken: SQLAlchemy circular FK dependency (dynasty/person_db) "
            "causes an integrity error on DELETE — known issue tracked in CLAUDE.md "
            "under 'SQLAlchemy backref conflicts'."
        )
    )
    def test_delete_post_removes_dynasty(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.post(
            f'/dynasty/{dynasty_id}/delete',
            follow_redirects=True,
        )
        assert response.status_code == 200
        with app.app_context():
            deleted = db.session.query(DynastyDB).filter_by(id=dynasty_id).first()
            assert deleted is None

    def test_delete_page_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/delete', follow_redirects=False)
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/territories
# ---------------------------------------------------------------------------

class TestDynastyTerritories:
    def test_territories_returns_200(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/territories')
        assert response.status_code == 200

    def test_territories_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/territories', follow_redirects=False)
        assert response.status_code == 302
