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

    def test_create_dynasty(self, game_manager, session):
        """Test creating a new dynasty."""
        # Create a test user first
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()

        # Create a dynasty
        dynasty_name = "Test Dynasty"
        theme = "medieval_europe"
        start_year = 1400
        
        success, message, dynasty_id = game_manager.create_dynasty(
            user_id=user.id,
            name=dynasty_name,
            theme=theme,
            start_year=start_year
        )
        
        # Check the result
        assert success is True
        assert "Dynasty created successfully" in message
        assert dynasty_id is not None
        
        # Verify the dynasty was created in the database
        dynasty = session.query(DynastyDB).get(dynasty_id)
        assert dynasty is not None
        assert dynasty.name == dynasty_name
        assert dynasty.theme_identifier_or_json == theme
        assert dynasty.start_year == start_year
        assert dynasty.current_simulation_year == start_year
        
        # Verify the founder was created
        founder = session.query(PersonDB).filter_by(dynasty_id=dynasty_id).first()
        assert founder is not None
        assert founder.is_monarch is True

    def test_load_game(self, game_manager, session):
        """Test loading a game state."""
        # Create a test user and dynasty first
        user = User(username="testuser2", email="test2@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        success, message, dynasty_id = game_manager.create_dynasty(
            user_id=user.id,
            name="Test Dynasty 2",
            theme="medieval_europe",
            start_year=1400
        )
        
        # Load the game state
        game_state = game_manager.load_game(dynasty_id)
        
        # Check the result
        assert game_state is not None
        assert 'dynasty' in game_state
        assert game_state['dynasty']['name'] == "Test Dynasty 2"
        assert game_state['dynasty']['start_year'] == 1400
        assert 'ruler' in game_state
        assert 'territories' in game_state
        assert 'military' in game_state
        assert 'diplomacy' in game_state
        assert 'time' in game_state
        
        # Check that the state was cached
        assert dynasty_id in game_manager.game_state_cache['data']
        assert 'state' in game_manager.game_state_cache['data'][dynasty_id]

    def test_process_turn(self, game_manager, session):
        """Test processing a turn."""
        # Create a test user and dynasty first
        user = User(username="testuser3", email="test3@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        success, message, dynasty_id = game_manager.create_dynasty(
            user_id=user.id,
            name="Test Dynasty 3",
            theme="medieval_europe",
            start_year=1400
        )
        
        # Process a turn
        success, message, turn_results = game_manager.process_turn(dynasty_id)
        
        # Check the result
        assert success is True
        assert "Turn processed successfully" in message
        assert turn_results is not None
        assert 'year' in turn_results
        assert turn_results['year'] == 1401  # Should have advanced one year
        
        # Verify the dynasty year was updated in the database
        dynasty = session.query(DynastyDB).get(dynasty_id)
        assert dynasty.current_simulation_year == 1401
        
        # Check that the cache was invalidated
        assert dynasty_id not in game_manager.game_state_cache['data']