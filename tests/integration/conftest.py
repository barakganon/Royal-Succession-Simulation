# tests/integration/conftest.py
# Overrides the root conftest `app` and `db` fixtures so that integration
# tests run against the real Flask application (all routes registered) rather
# than the minimal app used by unit tests.
import pytest


@pytest.fixture(scope='module')
def app():
    """Return the real Flask app configured for testing."""
    import main_flask_app as mfa
    mfa.app.config['TESTING'] = True
    mfa.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    mfa.app.config['WTF_CSRF_ENABLED'] = False
    mfa.app.config['LOGIN_DISABLED'] = False
    with mfa.app.app_context():
        mfa.db.create_all()
    return mfa.app


@pytest.fixture(scope='module')
def db(app):
    """Return the db bound to the real app."""
    import main_flask_app as mfa
    yield mfa.db
    with app.app_context():
        mfa.db.drop_all()


@pytest.fixture(scope='function')
def session(db, app):
    """Clean DB state per test function."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield db.session
        db.session.rollback()
        db.session.remove()
