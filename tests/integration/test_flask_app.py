# tests/integration/test_flask_app.py
import pytest
from flask import url_for
from flask_login import current_user, login_user
from models.db_models import User, DynastyDB

# Correct theme key as stored in cultural_themes.json
VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


@pytest.fixture
def client(app, db):
    """Create a test client for the Flask app."""
    with app.test_client() as client:
        with app.app_context():
            # Create the database tables
            db.drop_all()
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


def _create_dynasty(client, dynasty_name="Test Dynasty", start_year="1400"):
    """Submit the create dynasty form with the correct field names and route."""
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


@pytest.mark.integration
@pytest.mark.web
class TestFlaskApp:
    """Integration tests for the Flask application."""

    def test_home_page(self, client):
        """Test that the home page loads correctly."""
        response = client.get('/')
        assert response.status_code == 200
        # The index page title is "Dynasty Saga" (not "Royal Succession Simulation")
        assert b'Dynasty Saga' in response.data

    def test_login_page(self, client):
        """Test that the login page loads correctly."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Enter the Realm' in response.data
        assert b'username' in response.data  # input name attribute
        assert b'password' in response.data  # input name attribute

    def test_register_page(self, client):
        """Test that the register page loads correctly."""
        response = client.get('/register')
        assert response.status_code == 200
        assert b'Pledge Your Name' in response.data
        assert b'username' in response.data  # input name attribute
        assert b'Email' in response.data
        assert b'password' in response.data  # input name attribute

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

        # Log out before testing failed login so the session is clean
        client.get('/logout', follow_redirects=True)

        # Try to login with incorrect credentials
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    def test_register_functionality(self, client, app, db):
        """Test the register functionality."""
        # Register a new user — server expects 'password2', not 'confirm_password'
        response = client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpassword123',
            'password2': 'newpassword123'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Auth blueprint flash message: "your account has been created"
        assert b'account has been created' in response.data

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

        # Create a dynasty using the correct route and field names
        response = _create_dynasty(client)

        assert response.status_code == 200
        assert b'created successfully' in response.data

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

        # Create a dynasty using the correct route and field names
        _create_dynasty(client)

        # Get the dynasty ID
        with app.app_context():
            user = db.session.query(User).filter_by(username='testuser').first()
            dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
            dynasty_id = dynasty.id

        # View the dynasty — correct route is /dynasty/<id>/view
        response = client.get(f'/dynasty/{dynasty_id}/view')
        assert response.status_code == 200
        assert b'Test Dynasty' in response.data
        # Template renders "Current Year: 1400", not "Year: 1400"
        assert b'1400' in response.data
