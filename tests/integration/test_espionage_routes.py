# tests/integration/test_espionage_routes.py
# Integration tests for the espionage blueprint routes.

import pytest

from models.db_models import User, DynastyDB, PersonDB, Project

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Shared helpers (mirror test_dynasty_routes.py patterns)
# ---------------------------------------------------------------------------

def _register_and_login(app, db, client, username="esp_user", password="esppass123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, dynasty_name="House Shadow", start_year="1200"):
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


def _get_dynasty_id(app, db, username="esp_user"):
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
        return dynasty.id if dynasty else None


def _create_rival_dynasty(app, db, username="rival_user", dynasty_name="House Rival"):
    """Create a second user+dynasty that serves as a spy target."""
    with app.app_context():
        rival_user = User(username=username, email=f"{username}@example.com")
        rival_user.set_password("rivalpass123")
        db.session.add(rival_user)
        db.session.flush()

        rival_dynasty = DynastyDB(
            name=dynasty_name,
            user_id=rival_user.id,
            theme_identifier_or_json=VALID_THEME_KEY,
            start_year=1200,
            current_simulation_year=1200,
            current_wealth=500,
        )
        db.session.add(rival_dynasty)
        db.session.flush()

        # Give the rival dynasty a living monarch so it exists as a valid target
        rival_monarch = PersonDB(
            dynasty_id=rival_dynasty.id,
            name="Rival",
            surname="Lord",
            gender="MALE",
            birth_year=1170,
            death_year=None,
            is_monarch=True,
            is_noble=True,
            reign_start_year=1200,
        )
        db.session.add(rival_monarch)
        db.session.commit()
        return rival_dynasty.id


def _give_dynasty_wealth(app, db, dynasty_id, wealth=1000):
    """Bump the dynasty's gold to ensure it can afford missions."""
    with app.app_context():
        dynasty = db.session.get(DynastyDB, dynasty_id)
        dynasty.current_wealth = wealth
        db.session.commit()


def _ensure_monarch(app, db, dynasty_id):
    """Make sure the dynasty has a living monarch (required by ProjectSystem.start_project)."""
    with app.app_context():
        monarch = (
            db.session.query(PersonDB)
            .filter_by(dynasty_id=dynasty_id, is_monarch=True, death_year=None)
            .first()
        )
        if monarch:
            return
        person = PersonDB(
            dynasty_id=dynasty_id,
            name="Shadow",
            surname="Monarch",
            gender="MALE",
            birth_year=1170,
            death_year=None,
            is_monarch=True,
            is_noble=True,
            reign_start_year=1200,
        )
        db.session.add(person)
        db.session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plain_client(app, db, session):
    """Unauthenticated client with a clean DB."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def esp_dynasty_client(app, db, session):
    """Client with a logged-in user who already owns one dynasty."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username="esp_user")
        _create_dynasty(c, dynasty_name="House Shadow")
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEspionagePageLoad:
    def test_espionage_page_loads(self, esp_dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="esp_user")
        assert dynasty_id is not None
        response = esp_dynasty_client.get(f'/dynasty/{dynasty_id}/espionage')
        assert response.status_code == 200

    def test_espionage_page_contains_dispatch_form(self, esp_dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="esp_user")
        response = esp_dynasty_client.get(f'/dynasty/{dynasty_id}/espionage')
        assert b'espionage_intel' in response.data or b'Intel' in response.data

    def test_espionage_page_contains_agent_option(self, esp_dynasty_client, app, db):
        """Page renders an agent <select> when a rival dynasty exists."""
        dynasty_id = _get_dynasty_id(app, db, username="esp_user")
        # Create a rival so the dispatch forms render (they require enemy_dynasties)
        _create_rival_dynasty(app, db, username="rival_agent_test", dynasty_name="House Rival Agent")
        response = esp_dynasty_client.get(f'/dynasty/{dynasty_id}/espionage')
        assert response.status_code == 200
        # The page should now show the dispatch forms with agent selects
        assert b'agent_person_id' in response.data


class TestEspionageAuthGuards:
    def test_espionage_non_owner_redirect(self, app, db, session):
        """A different authenticated user trying to view another user's espionage page is redirected."""
        # Create two users: owner and outsider, in the same DB context
        with app.app_context():
            owner = User(username="esp_owner2", email="esp_owner2@example.com")
            owner.set_password("ownerpass")
            db.session.add(owner)
            db.session.flush()

            outsider = User(username="esp_other2", email="esp_other2@example.com")
            outsider.set_password("otherpass")
            db.session.add(outsider)
            db.session.flush()

            dynasty = DynastyDB(
                name="House Owner",
                user_id=owner.id,
                theme_identifier_or_json=VALID_THEME_KEY,
                start_year=1200,
                current_simulation_year=1200,
                current_wealth=500,
            )
            db.session.add(dynasty)
            db.session.commit()
            dynasty_id = dynasty.id
            # Ensure IDs are different (sanity check)
            assert owner.id != outsider.id

        # Outsider logs in and tries to access owner's dynasty
        with app.test_client() as other_client:
            other_client.post('/login', data={'username': 'esp_other2', 'password': 'otherpass'})
            response = other_client.get(f'/dynasty/{dynasty_id}/espionage', follow_redirects=False)
            assert response.status_code == 302

    def test_espionage_unauthenticated_redirect(self, plain_client):
        response = plain_client.get('/dynasty/1/espionage', follow_redirects=False)
        assert response.status_code == 302
        assert b'/login' in response.data or response.location is not None


class TestEspionageDispatch:
    def test_espionage_dispatch_intel_valid(self, esp_dynasty_client, app, db):
        """POST a valid intel mission creates a Project with type espionage_intel."""
        dynasty_id = _get_dynasty_id(app, db, username="esp_user")
        _ensure_monarch(app, db, dynasty_id)
        _give_dynasty_wealth(app, db, dynasty_id, wealth=1000)

        # Create a rival dynasty to target
        rival_id = _create_rival_dynasty(app, db, username="rival_intel_user", dynasty_name="House Intel Target")

        # Get the monarch's id to use as agent
        with app.app_context():
            agent = (
                db.session.query(PersonDB)
                .filter_by(dynasty_id=dynasty_id, death_year=None)
                .first()
            )
            assert agent is not None
            agent_id = agent.id

        response = esp_dynasty_client.post(
            f'/dynasty/{dynasty_id}/espionage/dispatch',
            data={
                'mission_type': 'espionage_intel',
                'agent_person_id': str(agent_id),
                'target_dynasty_id': str(rival_id),
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Verify a Project was created
        with app.app_context():
            project = (
                db.session.query(Project)
                .filter_by(dynasty_id=dynasty_id, project_type='espionage_intel', status='active')
                .first()
            )
            assert project is not None, "Expected espionage_intel Project to be created"

    def test_espionage_dispatch_assassinate_missing_target(self, esp_dynasty_client, app, db):
        """POST assassinate without target_person_id → warning flash, no new Project."""
        dynasty_id = _get_dynasty_id(app, db, username="esp_user")
        _ensure_monarch(app, db, dynasty_id)
        _give_dynasty_wealth(app, db, dynasty_id, wealth=1000)

        rival_id = _create_rival_dynasty(app, db, username="rival_assass_user", dynasty_name="House Assass Target")

        with app.app_context():
            agent = (
                db.session.query(PersonDB)
                .filter_by(dynasty_id=dynasty_id, death_year=None)
                .first()
            )
            assert agent is not None
            agent_id = agent.id

            initial_count = (
                db.session.query(Project)
                .filter_by(dynasty_id=dynasty_id, project_type='espionage_assassinate')
                .count()
            )

        response = esp_dynasty_client.post(
            f'/dynasty/{dynasty_id}/espionage/dispatch',
            data={
                'mission_type': 'espionage_assassinate',
                'agent_person_id': str(agent_id),
                'target_dynasty_id': str(rival_id),
                # Deliberately omitting target_person_id
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        # No new Project for assassination
        with app.app_context():
            new_count = (
                db.session.query(Project)
                .filter_by(dynasty_id=dynasty_id, project_type='espionage_assassinate')
                .count()
            )
            assert new_count == initial_count, "Should not have created an assassination project without a target person"
