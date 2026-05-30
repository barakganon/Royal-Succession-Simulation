# tests/integration/test_family_tree_inline_view.py
# Integration test for Story 8-3: the dynasty view embeds the family tree as
# an INLINE SVG (from DynastyDB.family_tree_svg) instead of an <img> pointing
# at a generated PNG under /static/visualizations/.
#
# We mirror the fixtures/helpers from test_dynasty_routes.py
# (dynasty_client / _register_and_login / _get_dynasty_id) so the owner is
# logged in and already owns a dynasty.

import pytest
from models.db_models import User, DynastyDB

# The correct theme key as stored in cultural_themes.json
VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Shared helpers (mirrored from test_dynasty_routes.py)
# ---------------------------------------------------------------------------

def _register_and_login(app, db, client, username="tree_user", password="treepass123"):
    """Create a user in the DB (inside app_context) and log in via the client."""
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, dynasty_name="House Treeford", start_year="1200"):
    """Submit the create dynasty form and return the response."""
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


def _get_dynasty_id(app, db, username="tree_user"):
    """Return the first dynasty id owned by the given user."""
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
def dynasty_client(app, db, session):
    """Client with a logged-in user who already owns one dynasty."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username="tree_user")
        _create_dynasty(c)
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFamilyTreeInlineView:
    def test_view_returns_200(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="tree_user")
        assert dynasty_id is not None
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/view')
        assert response.status_code == 200

    def test_view_contains_inline_svg(self, dynasty_client, app, db):
        """The family tree is rendered inline as an <svg> element."""
        dynasty_id = _get_dynasty_id(app, db, username="tree_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/view')
        assert response.status_code == 200
        assert b'<svg' in response.data

    def test_view_has_no_legacy_png_references(self, dynasty_client, app, db):
        """The retired matplotlib plotter path must be gone: no
        family_tree_image kwarg/var and no /static/visualizations/ img src."""
        dynasty_id = _get_dynasty_id(app, db, username="tree_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/view')
        assert response.status_code == 200
        assert b'family_tree_image' not in response.data
        assert b'/static/visualizations/' not in response.data
