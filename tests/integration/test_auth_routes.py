# tests/integration/test_auth_routes.py
# Integration tests for authentication routes (register, login, logout, dashboard).
# These routes live directly in main_flask_app.py (no Blueprint yet).

import pytest
from models.db_models import User


# ---------------------------------------------------------------------------
# Shared client/user helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def client(app, db):
    """Test client with a clean DB for each test function."""
    with app.test_client() as c:
        with app.app_context():
            db.drop_all()
            db.create_all()
            yield c
            db.session.remove()
            db.drop_all()


@pytest.fixture
def registered_client(app, db):
    """Test client pre-loaded with a registered user."""
    with app.test_client() as c:
        with app.app_context():
            db.drop_all()
            db.create_all()
            user = User(username="authuser", email="auth@example.com")
            user.set_password("securepass123")
            db.session.add(user)
            db.session.commit()
            yield c
            db.session.remove()
            db.drop_all()


@pytest.fixture
def logged_in_client(app, db):
    """Test client with a user already logged in."""
    with app.test_client() as c:
        with app.app_context():
            db.drop_all()
            db.create_all()
            user = User(username="loggedinuser", email="loggedin@example.com")
            user.set_password("mypassword99")
            db.session.add(user)
            db.session.commit()
        # Perform login outside the app_context block so the session cookie persists
        c.post('/login', data={'username': 'loggedinuser', 'password': 'mypassword99'})
        yield c
        with app.app_context():
            db.session.remove()
            db.drop_all()


# ---------------------------------------------------------------------------
# GET /login
# ---------------------------------------------------------------------------

class TestLoginPage:
    def test_get_login_returns_200(self, client):
        response = client.get('/login')
        assert response.status_code == 200

    def test_get_login_contains_form_fields(self, client):
        response = client.get('/login')
        assert b'username' in response.data  # input name attribute
        assert b'password' in response.data  # input name attribute

    def test_get_login_contains_login_heading(self, client):
        response = client.get('/login')
        # Template renders "Enter the Realm" heading
        assert b'Enter the Realm' in response.data


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

class TestLoginPost:
    def test_valid_login_redirects_to_dashboard(self, registered_client):
        response = registered_client.post(
            '/login',
            data={'username': 'authuser', 'password': 'securepass123'},
            follow_redirects=True
        )
        assert response.status_code == 200
        # Dashboard page title contains "Dashboard"
        assert b'Dashboard' in response.data

    def test_valid_login_sets_session(self, registered_client):
        registered_client.post(
            '/login',
            data={'username': 'authuser', 'password': 'securepass123'}
        )
        with registered_client.session_transaction() as sess:
            assert sess.get('_user_id') is not None

    def test_invalid_password_stays_on_login(self, registered_client):
        response = registered_client.post(
            '/login',
            data={'username': 'authuser', 'password': 'wrongpassword'},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    def test_unknown_user_shows_error(self, client):
        response = client.post(
            '/login',
            data={'username': 'nobody', 'password': 'pass'},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    def test_missing_credentials_shows_error(self, client):
        response = client.post(
            '/login',
            data={'username': '', 'password': ''},
            follow_redirects=True
        )
        assert response.status_code == 200
        # Route flashes "Username and password are required."
        assert b'required' in response.data

    def test_already_logged_in_redirects_to_dashboard(self, logged_in_client):
        response = logged_in_client.get('/login', follow_redirects=True)
        assert response.status_code == 200
        assert b'Dashboard' in response.data


# ---------------------------------------------------------------------------
# GET /register
# ---------------------------------------------------------------------------

class TestRegisterPage:
    def test_get_register_returns_200(self, client):
        response = client.get('/register')
        assert response.status_code == 200

    def test_get_register_contains_form_fields(self, client):
        response = client.get('/register')
        assert b'username' in response.data  # input name attribute
        assert b'password' in response.data  # input name attribute

    def test_get_register_contains_email_field(self, client):
        response = client.get('/register')
        assert b'Email' in response.data


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------

class TestRegisterPost:
    def test_valid_registration_redirects_to_login(self, client):
        response = client.post(
            '/register',
            data={
                'username': 'brandnewuser',
                'email': 'brandnew@example.com',
                'password': 'strongPass1!',
                'password2': 'strongPass1!'
            },
            follow_redirects=True
        )
        assert response.status_code == 200
        # After successful registration, user is redirected to login page
        assert b'Enter the Realm' in response.data

    def test_valid_registration_shows_success_flash(self, client):
        response = client.post(
            '/register',
            data={
                'username': 'flashtestuser',
                'email': 'flash@example.com',
                'password': 'strongPass1!',
                'password2': 'strongPass1!'
            },
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'account has been created' in response.data

    def test_valid_registration_creates_user_in_db(self, client, app, db):
        client.post(
            '/register',
            data={
                'username': 'dbcheckuser',
                'email': 'dbcheck@example.com',
                'password': 'pass1234',
                'password2': 'pass1234'
            }
        )
        with app.app_context():
            user = db.session.query(User).filter_by(username='dbcheckuser').first()
            assert user is not None
            assert user.check_password('pass1234') is True

    def test_mismatched_passwords_shows_error(self, client):
        response = client.post(
            '/register',
            data={
                'username': 'mismatchuser',
                'email': 'mm@example.com',
                'password': 'pass1234',
                'password2': 'different'
            },
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Passwords do not match' in response.data

    def test_duplicate_username_shows_error(self, registered_client):
        response = registered_client.post(
            '/register',
            data={
                'username': 'authuser',  # already exists in registered_client fixture
                'email': 'other@example.com',
                'password': 'pass1234',
                'password2': 'pass1234'
            },
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Username already exists' in response.data

    def test_missing_required_fields_shows_error(self, client):
        response = client.post(
            '/register',
            data={'username': '', 'password': '', 'password2': ''},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'required' in response.data


# ---------------------------------------------------------------------------
# GET /logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_redirects_to_index(self, logged_in_client):
        response = logged_in_client.get('/logout', follow_redirects=True)
        assert response.status_code == 200
        # After logout, user is on the index page (Dynasty Saga landing)
        assert b'Dynasty Saga' in response.data

    def test_logout_shows_flash_message(self, logged_in_client):
        response = logged_in_client.get('/logout', follow_redirects=True)
        assert b'logged out' in response.data

    def test_logout_clears_session(self, logged_in_client):
        logged_in_client.get('/logout')
        with logged_in_client.session_transaction() as sess:
            assert sess.get('_user_id') is None

    def test_logout_unauthenticated_redirects_to_login(self, client):
        # Unauthenticated access to /logout should redirect to /login
        response = client.get('/logout', follow_redirects=True)
        assert response.status_code == 200
        assert b'Enter the Realm' in response.data


# ---------------------------------------------------------------------------
# GET /dashboard (auth guard)
# ---------------------------------------------------------------------------

class TestDashboardAuthGuard:
    def test_dashboard_unauthenticated_redirects(self, client):
        response = client.get('/dashboard', follow_redirects=False)
        assert response.status_code == 302

    def test_dashboard_unauthenticated_redirects_to_login(self, client):
        response = client.get('/dashboard', follow_redirects=True)
        assert response.status_code == 200
        assert b'Enter the Realm' in response.data

    def test_dashboard_authenticated_returns_200(self, logged_in_client):
        response = logged_in_client.get('/dashboard')
        assert response.status_code == 200

    def test_dashboard_authenticated_contains_heading(self, logged_in_client):
        response = logged_in_client.get('/dashboard')
        assert b'Dashboard' in response.data


# ---------------------------------------------------------------------------
# GET / (index)
# ---------------------------------------------------------------------------

class TestIndexRoute:
    def test_index_unauthenticated_returns_200(self, client):
        response = client.get('/')
        assert response.status_code == 200

    def test_index_contains_dynasty_saga(self, client):
        response = client.get('/')
        assert b'Dynasty Saga' in response.data

    def test_index_authenticated_redirects_to_dashboard(self, logged_in_client):
        response = logged_in_client.get('/', follow_redirects=True)
        assert response.status_code == 200
        assert b'Dashboard' in response.data
