# tests/functional/test_game_flow.py
import pytest
from unittest.mock import patch
from flask import url_for
from models.db_models import User, DynastyDB, PersonDB, Territory

# Correct theme key as stored in cultural_themes.json
VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _create_user_and_login(app, db, client, username="testuser", password="password123"):
    """Create a DB user (inside app_context) and log in via the test client."""
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, dynasty_name="Test Dynasty", start_year="1400"):
    """Submit the create-dynasty form and follow redirects."""
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


def _get_first_dynasty_id(app, db, username="testuser"):
    """Return the first DynastyDB id owned by the given user (inside app_context)."""
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
def authenticated_client(app, db):
    """Test client with a logged-in user and a clean DB."""
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as client:
        _create_user_and_login(app, db, client)
        # Fetch the user object so callers can reference user.id
        with app.app_context():
            user = db.session.query(User).filter_by(username="testuser").first()
        yield client, user

        with app.app_context():
            db.session.remove()
            db.drop_all()


# ---------------------------------------------------------------------------
# TestGameFlow
# ---------------------------------------------------------------------------

@pytest.mark.functional
class TestGameFlow:
    """Functional tests for the game flow."""

    def test_complete_game_flow(self, authenticated_client, app, db):
        """Test a complete game flow from dynasty creation through turn advancement."""
        client, user = authenticated_client

        # 1. Create a dynasty
        response = _create_dynasty(client)
        assert response.status_code == 200
        assert b'created successfully' in response.data

        # Get the dynasty ID
        dynasty_id = _get_first_dynasty_id(app, db)
        assert dynasty_id is not None

        # 2. View the dynasty (correct route: /dynasty/<id>/view)
        response = client.get(f'/dynasty/{dynasty_id}/view')
        assert response.status_code == 200
        assert b'Test Dynasty' in response.data

        # 3. Verify a ruler was created
        with app.app_context():
            ruler = db.session.query(PersonDB).filter_by(
                dynasty_id=dynasty_id,
                is_monarch=True
            ).first()
            assert ruler is not None

        # 4. Advance a turn (GET /dynasty/<id>/advance_turn — advances 5 years)
        # Patch death check to guarantee no monarch death interrupt fires, ensuring
        # exactly 5 years advance and a deterministic year assertion.
        with patch('models.turn_processor.process_death_check', return_value=False):
            response = client.get(f'/dynasty/{dynasty_id}/advance_turn', follow_redirects=True)
        assert response.status_code == 200
        # Flash message contains the advance summary
        assert b'Advanced' in response.data or b'advanced' in response.data or b'Error' not in response.data

        # Check that the year was advanced by 5
        with app.app_context():
            dynasty = db.session.query(DynastyDB).get(dynasty_id)
            assert dynasty.current_simulation_year == 1405

        # 5. View the world map
        response = client.get('/world/map')
        assert response.status_code == 200

        # 6. View the economy
        response = client.get(f'/dynasty/{dynasty_id}/economy')
        assert response.status_code == 200
        assert b'Economy' in response.data

        # 7. View the military
        response = client.get(f'/dynasty/{dynasty_id}/military')
        assert response.status_code == 200
        assert b'Military' in response.data

        # 8. View diplomacy
        response = client.get(f'/dynasty/{dynasty_id}/diplomacy')
        assert response.status_code == 200

        # 9. Advance multiple turns and verify cumulative year
        # Patch death check to guarantee no interrupt, so exactly 5 years advance per turn.
        with patch('models.turn_processor.process_death_check', return_value=False):
            for _ in range(3):
                client.get(f'/dynasty/{dynasty_id}/advance_turn', follow_redirects=True)

        with app.app_context():
            dynasty = db.session.query(DynastyDB).get(dynasty_id)
            # Started at 1400, advanced 4 turns × 5 years each = 1420
            assert dynasty.current_simulation_year == 1420

        # 10. View the timeline
        response = client.get(f'/dynasty/{dynasty_id}/timeline')
        assert response.status_code == 200
        assert b'Timeline' in response.data


# ---------------------------------------------------------------------------
# TestMultiDynastyInteraction
# ---------------------------------------------------------------------------

@pytest.mark.functional
class TestMultiDynastyInteraction:
    """Functional tests for interactions between multiple dynasties owned by one user."""

    def test_dynasty_interactions(self, authenticated_client, app, db):
        """Test that two dynasties can be created, turns advanced, and viewed."""
        client, user = authenticated_client

        # Create Dynasty A via the web form (outside any explicit app_context —
        # the test client manages its own context per request)
        _create_dynasty(client, dynasty_name="Dynasty A", start_year="1400")

        # Create Dynasty B via the web form
        _create_dynasty(client, dynasty_name="Dynasty B", start_year="1400")

        # Retrieve both dynasty IDs from DB
        with app.app_context():
            user_obj = db.session.query(User).filter_by(username="testuser").first()
            all_dynasties = (
                db.session.query(DynastyDB)
                .filter_by(user_id=user_obj.id)
                .order_by(DynastyDB.id)
                .all()
            )
        assert len(all_dynasties) == 2
        dynasty_a_id = all_dynasties[0].id
        dynasty_b_id = all_dynasties[1].id

        # Advance turns for both dynasties
        # Patch death check to guarantee no interrupt, so exactly 5 years advance per turn.
        for dynasty_id in (dynasty_a_id, dynasty_b_id):
            with patch('models.turn_processor.process_death_check', return_value=False):
                response = client.get(
                    f'/dynasty/{dynasty_id}/advance_turn',
                    follow_redirects=True
                )
            assert response.status_code == 200

        # Verify both dynasties advanced 5 years
        with app.app_context():
            dynasty_a = db.session.query(DynastyDB).get(dynasty_a_id)
            dynasty_b = db.session.query(DynastyDB).get(dynasty_b_id)
            assert dynasty_a.current_simulation_year == 1405
            assert dynasty_b.current_simulation_year == 1405

        # Verify diplomacy view loads for Dynasty A
        response = client.get(f'/dynasty/{dynasty_a_id}/diplomacy')
        assert response.status_code == 200

        # Verify territories view loads for Dynasty A
        response = client.get(f'/dynasty/{dynasty_a_id}/territories')
        assert response.status_code == 200
