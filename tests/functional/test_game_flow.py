# tests/functional/test_game_flow.py
import pytest
from flask import url_for
from models.db_models import User, DynastyDB, PersonDB, Territory


@pytest.fixture
def authenticated_client(app, db):
    """Create a test client with an authenticated user."""
    with app.test_client() as client:
        with app.app_context():
            # Create the database tables
            db.create_all()
            
            # Create a test user
            user = User(username="testuser", email="test@example.com")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            
            # Login the user
            client.post('/login', data={
                'username': 'testuser',
                'password': 'password123'
            })
            
            yield client, user
            
            # Clean up
            db.session.remove()
            db.drop_all()


@pytest.mark.functional
class TestGameFlow:
    """Functional tests for the game flow."""

    def test_complete_game_flow(self, authenticated_client, app, db):
        """Test a complete game flow from creation to turn processing."""
        client, user = authenticated_client
        
        # 1. Create a dynasty
        response = client.post('/create_dynasty', data={
            'name': 'Test Dynasty',
            'theme': 'medieval_europe',
            'start_year': '1400'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Dynasty created successfully' in response.data
        
        # Get the dynasty ID
        with app.app_context():
            dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
            dynasty_id = dynasty.id
        
        # 2. View the dynasty
        response = client.get(f'/dynasty/{dynasty_id}')
        assert response.status_code == 200
        assert b'Test Dynasty' in response.data
        
        # 3. View the dynasty's ruler
        with app.app_context():
            ruler = db.session.query(PersonDB).filter_by(
                dynasty_id=dynasty_id, 
                is_monarch=True
            ).first()
            
            assert ruler is not None
            ruler_id = ruler.id
        
        response = client.get(f'/person/{ruler_id}')
        assert response.status_code == 200
        assert ruler.name.encode() in response.data
        assert b'Ruler of Test Dynasty' in response.data
        
        # 4. Process a turn
        response = client.post(f'/dynasty/{dynasty_id}/process_turn', follow_redirects=True)
        assert response.status_code == 200
        assert b'Turn processed successfully' in response.data
        
        # Check that the year was advanced
        with app.app_context():
            dynasty = db.session.query(DynastyDB).get(dynasty_id)
            assert dynasty.current_simulation_year == 1401
        
        # 5. View the map
        response = client.get('/map')
        assert response.status_code == 200
        assert b'World Map' in response.data
        
        # 6. View the economy
        response = client.get(f'/dynasty/{dynasty_id}/economy')
        assert response.status_code == 200
        assert b'Economy' in response.data
        
        # 7. View the military
        response = client.get(f'/dynasty/{dynasty_id}/military')
        assert response.status_code == 200
        assert b'Military' in response.data
        
        # 8. View the diplomacy
        response = client.get(f'/dynasty/{dynasty_id}/diplomacy')
        assert response.status_code == 200
        assert b'Diplomacy' in response.data
        
        # 9. Process multiple turns
        for _ in range(5):
            response = client.post(f'/dynasty/{dynasty_id}/process_turn', follow_redirects=True)
            assert response.status_code == 200
            assert b'Turn processed successfully' in response.data
        
        # Check that the years were advanced
        with app.app_context():
            dynasty = db.session.query(DynastyDB).get(dynasty_id)
            assert dynasty.current_simulation_year == 1406
        
        # 10. Check for historical events
        response = client.get(f'/dynasty/{dynasty_id}/timeline')
        assert response.status_code == 200
        assert b'Timeline' in response.data
        
        # 11. Delete the dynasty
        response = client.post(f'/dynasty/{dynasty_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'has been permanently deleted' in response.data
        
        # Check that the dynasty was deleted
        with app.app_context():
            dynasty = db.session.query(DynastyDB).get(dynasty_id)
            assert dynasty is None


@pytest.mark.functional
class TestMultiDynastyInteraction:
    """Functional tests for interactions between multiple dynasties."""

    def test_dynasty_interactions(self, authenticated_client, app, db, game_manager):
        """Test interactions between multiple dynasties."""
        client, user = authenticated_client
        
        with app.app_context():
            # Create two dynasties for the same user
            success1, message1, dynasty1_id = game_manager.create_dynasty(
                user_id=user.id,
                name="Dynasty A",
                theme="medieval_europe",
                start_year=1400
            )
            
            success2, message2, dynasty2_id = game_manager.create_dynasty(
                user_id=user.id,
                name="Dynasty B",
                theme="medieval_japan",
                start_year=1400
            )
            
            assert success1 and success2
            
            # Create territories for both dynasties
            region = game_manager.map_system.create_region("Test Region", "temperate")
            province1 = game_manager.map_system.create_province(region.id, "Province A", "coastal")
            province2 = game_manager.map_system.create_province(region.id, "Province B", "plains")
            
            territory1 = game_manager.map_system.create_territory(
                province_id=province1.id,
                name="Territory A",
                terrain_type="coastal",
                x_coordinate=10.0,
                y_coordinate=10.0,
                controller_dynasty_id=dynasty1_id,
                is_capital=True
            )
            
            territory2 = game_manager.map_system.create_territory(
                province_id=province2.id,
                name="Territory B",
                terrain_type="plains",
                x_coordinate=20.0,
                y_coordinate=20.0,
                controller_dynasty_id=dynasty2_id,
                is_capital=True
            )
            
            # Update dynasties with capitals
            dynasty1 = db.session.query(DynastyDB).get(dynasty1_id)
            dynasty2 = db.session.query(DynastyDB).get(dynasty2_id)
            
            dynasty1.capital_territory_id = territory1.id
            dynasty2.capital_territory_id = territory2.id
            db.session.commit()
            
            # Create diplomatic relation
            relation = game_manager.diplomacy_system.create_diplomatic_relation(
                dynasty1_id=dynasty1_id,
                dynasty2_id=dynasty2_id,
                relation_type="neutral",
                base_score=0
            )
            
            # Process turns for both dynasties
            for _ in range(3):
                game_manager.process_turn(dynasty1_id)
                game_manager.process_turn(dynasty2_id)
            
            # Check that both dynasties advanced
            dynasty1 = db.session.query(DynastyDB).get(dynasty1_id)
            dynasty2 = db.session.query(DynastyDB).get(dynasty2_id)
            
            assert dynasty1.current_simulation_year == 1403
            assert dynasty2.current_simulation_year == 1403
            
            # Declare war
            war_id = game_manager.diplomacy_system.declare_war(
                attacker_dynasty_id=dynasty1_id,
                defender_dynasty_id=dynasty2_id,
                target_territory_id=territory2.id,
                cb_type="conquest"
            )
            
            assert war_id is not None
            
            # Process more turns during war
            for _ in range(2):
                game_manager.process_turn(dynasty1_id)
                game_manager.process_turn(dynasty2_id)
            
            # Check war status through the web interface
            response = client.get(f'/dynasty/{dynasty1_id}/diplomacy')
            assert response.status_code == 200
            assert b'War' in response.data
            assert b'Dynasty B' in response.data
            
            # End the war
            game_manager.diplomacy_system.end_war(
                war_id=war_id,
                winner_dynasty_id=dynasty1_id,
                territory_changes=[(territory2.id, dynasty1_id)]
            )
            
            # Check territory ownership
            territory2 = db.session.query(Territory).get(territory2.id)
            assert territory2.controller_dynasty_id == dynasty1_id
            
            # Check through web interface
            response = client.get(f'/dynasty/{dynasty1_id}/territories')
            assert response.status_code == 200
            assert b'Territory A' in response.data
            assert b'Territory B' in response.data