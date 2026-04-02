# tests/unit/test_game_manager.py
import pytest
from models.game_manager import GameManager
from models.db_models import DynastyDB, User, PersonDB


@pytest.mark.unit
@pytest.mark.game_manager
class TestGameManager:
    """Unit tests for the GameManager class."""

    def test_initialization(self, game_manager):
        """Test that the GameManager initializes correctly."""
        assert game_manager is not None
        assert game_manager.session is not None
        assert isinstance(game_manager, GameManager)
        assert hasattr(game_manager, 'game_state_cache')
        assert 'data' in game_manager.game_state_cache
        assert 'ttl' in game_manager.game_state_cache
        assert 'invalidation_keys' in game_manager.game_state_cache

    def test_create_dynasty(self, game_manager, session, app):
        """Test that create_new_game() creates a dynasty and persists it to the DB."""
        with app.app_context():
            user = User(username="testuser_gm1", email="gm1@example.com")
            user.set_password("password123")
            session.add(user)
            session.commit()

            success, message, dynasty_id = game_manager.create_new_game(
                user_id=user.id,
                game_name="Test Game",
            )

            assert success is True, f"create_new_game failed: {message}"
            assert dynasty_id is not None

            dynasty = session.query(DynastyDB).get(dynasty_id)
            assert dynasty is not None
            assert dynasty.user_id == user.id

    def test_load_game(self, game_manager, session, app):
        """Test that load_game() returns a dict with dynasty info."""
        with app.app_context():
            user = User(username="testuser_gm2", email="gm2@example.com")
            user.set_password("password123")
            session.add(user)
            session.commit()

            success, message, dynasty_id = game_manager.create_new_game(
                user_id=user.id,
                game_name="Load Test Game",
            )
            assert success is True, f"create_new_game failed: {message}"

            game_state = game_manager.load_game(dynasty_id)

            assert game_state is not None
            assert 'dynasty' in game_state
            assert game_state['dynasty']['id'] == dynasty_id

    def test_process_turn(self, game_manager, session, app):
        """Test that process_turn() runs without error for an existing dynasty."""
        with app.app_context():
            user = User(username="testuser_gm3", email="gm3@example.com")
            user.set_password("password123")
            session.add(user)
            session.commit()

            success, message, dynasty_id = game_manager.create_new_game(
                user_id=user.id,
                game_name="Turn Test Game",
            )
            assert success is True, f"create_new_game failed: {message}"

            success, msg, turn_results = game_manager.process_turn(dynasty_id)

            assert success is True, f"process_turn failed: {msg}"
            assert turn_results is not None
            assert 'year' in turn_results
