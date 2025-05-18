# tests/integration/test_flask_app.py
import pytest
from flask import url_for
from flask_login import current_user, login_user
from models.db_models import User, DynastyDB


@pytest.fixture
def client(app, db):
    """Create a test client for the Flask app."""
    with app.test_client() as client:
        with app.app_context():
            # Create the database tables
            db.create_all()
            
            # Create a test user
            user = User(username="testuser", email="test@example.com")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            
            yield client
            
            # Clean up
            db.session.remove()
            db.drop_all()


@pytest.mark.integration
@pytest.mark.web
class TestFlaskApp:
    """Integration tests for the Flask application."""

    def test_home_page(self, client):
        """Test that the home page loads correctly."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Royal Succession Simulation' in response.data

    def test_login_page(self, client):
        """Test that the login page loads correctly."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data
        assert b'Username' in response.data
        assert b'Password' in response.data

    def test_register_page(self, client):
        """Test that the register page loads correctly."""
        response = client.get('/register')
        assert response.status_code == 200
        assert b'Register' in response.data
        assert b'Username' in response.data
        assert b'Email' in response.data
        assert b'Password' in response.data

    def test_login_functionality(self, client, app):
        """Test the login functionality."""
        # Try to login with correct credentials
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Dashboard' in response.data
        
        # Check that the user is logged in
        with client.session_transaction() as session:
            assert session.get('_user_id') is not None
        
        # Try to login with incorrect credentials
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    def test_register_functionality(self, client, app, db):
        """Test the register functionality."""
        # Register a new user
        response = client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Account created successfully' in response.data
        
        # Check that the user was created in the database
        with app.app_context():
            user = db.session.query(User).filter_by(username='newuser').first()
            assert user is not None
            assert user.email == 'new@example.com'
            assert user.check_password('newpassword123') is True

    def test_protected_routes(self, client, app, db):
        """Test that protected routes require authentication."""
        # Try to access the dashboard without logging in
        response = client.get('/dashboard', follow_redirects=True)
        assert response.status_code == 200
        assert b'Please log in to access this page' in response.data
        
        # Login
        client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        
        # Try to access the dashboard after logging in
        response = client.get('/dashboard')
        assert response.status_code == 200
        assert b'Dashboard' in response.data

    def test_create_dynasty(self, client, app, db):
        """Test creating a dynasty."""
        # Login first
        client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        
        # Create a dynasty
        response = client.post('/create_dynasty', data={
            'name': 'Test Dynasty',
            'theme': 'medieval_europe',
            'start_year': '1400'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Dynasty created successfully' in response.data
        
        # Check that the dynasty was created in the database
        with app.app_context():
            user = db.session.query(User).filter_by(username='testuser').first()
            dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
            assert dynasty is not None
            assert dynasty.name == 'Test Dynasty'
            assert dynasty.start_year == 1400

    def test_view_dynasty(self, client, app, db):
        """Test viewing a dynasty."""
        # Login first
        client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        
        # Create a dynasty
        response = client.post('/create_dynasty', data={
            'name': 'Test Dynasty',
            'theme': 'medieval_europe',
            'start_year': '1400'
        }, follow_redirects=True)
        
        # Get the dynasty ID
        with app.app_context():
            user = db.session.query(User).filter_by(username='testuser').first()
            dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
            dynasty_id = dynasty.id
        
        # View the dynasty
        response = client.get(f'/dynasty/{dynasty_id}')
        assert response.status_code == 200
        assert b'Test Dynasty' in response.data
        assert b'Year: 1400' in response.data