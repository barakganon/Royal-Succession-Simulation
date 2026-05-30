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

# Redirect the application database to a throwaway temp file for the whole test
# run, so the integration suite (which imports the real app via main_flask_app)
# NEVER touches the developer's instance/dynastysim.db. main_flask_app reads
# DATABASE_URL at import time, *before* db.init_app binds the engine — and this
# root conftest is imported before any test or other conftest pulls in the app —
# so setting it here is what actually takes effect (a late
# app.config['SQLALCHEMY_DATABASE_URI'] override after import is a no-op because
# the engine is already bound, which previously let drop_all() wipe the dev DB).
# A temp FILE is used rather than sqlite:///:memory: because in-memory SQLite is
# per-connection and would not be shared across pooled connections.
import tempfile as _tempfile
if 'DATABASE_URL' not in os.environ:
    _test_db_file = os.path.join(_tempfile.gettempdir(), 'rss_pytest.db')
    # Start every run from a clean schema: SQLite's create_all() does NOT ALTER an
    # existing table, so a stale temp DB would silently miss newly-added columns
    # (e.g. a story that adds a column would fail until the file is rebuilt).
    try:
        os.remove(_test_db_file)
    except FileNotFoundError:
        pass
    os.environ['DATABASE_URL'] = 'sqlite:///' + _test_db_file

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import random as _random


@pytest.fixture(autouse=True)
def _deterministic_random():
    """Seed the global RNG before EVERY test so random-driven code paths are
    order-independent.

    Root cause of the intermittent full-suite flakes (e.g. heir-majority /
    military / project-lifecycle tests passing in isolation but failing under
    full-suite ordering): turn processing (process_dynasty_turn — births,
    deaths, marriages, majority) consumes the global `random` state, which
    carried over from whatever tests ran earlier. Re-seeding here resets that
    state to a fixed point per test, making turn outcomes deterministic
    regardless of order. Tests that `mocker.patch` random.* are unaffected
    (the patch overrides the seed).
    """
    _random.seed(1_234_567)
    yield


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