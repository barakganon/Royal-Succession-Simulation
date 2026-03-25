# tests/conftest.py
# Common test fixtures and configuration for pytest

import os
import sys
import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Force the non-interactive Agg backend so that plt.show() is a no-op in tests.
# This must happen before any matplotlib import elsewhere in the process.
os.environ.setdefault('MPLBACKEND', 'Agg')

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.db_models import db as _db
from models.game_manager import GameManager


@pytest.fixture(scope='session')
def app():
    """Create and configure a Flask app for testing."""
    app = Flask(__name__)
    
    # Use an in-memory SQLite database for testing
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    
    return app


@pytest.fixture(scope='session')
def db(app):
    """Create and configure a database for testing."""
    _db.init_app(app)
    
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope='function')
def session(db, app):
    """Create a clean database session for each test.

    Flask-SQLAlchemy 3.x removed create_scoped_session. We drop and recreate
    all tables per test so committed rows from one test never bleed into the next.
    """
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield db.session
        db.session.rollback()
        db.session.remove()


@pytest.fixture(scope='function')
def game_manager(session, app):
    """Create a GameManager instance for testing."""
    with app.app_context():
        manager = GameManager(session)
        yield manager