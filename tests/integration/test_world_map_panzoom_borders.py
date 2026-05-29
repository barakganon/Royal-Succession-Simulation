# tests/integration/test_world_map_panzoom_borders.py
# Sprint 3 Story 3-4 (Worktree C / tests): CONTRACT-FIRST tests for the new
# pan/zoom camera, middle-drag panning, double-click recenter, border-drawing
# pass, the five-button overlay tab bar, and the updated world-card stub.
#
# These tests assert ONLY frontend DOM + JS string presence in the rendered
# /world/map response. They WILL FAIL in this isolated worktree because the
# Story 3-4 implementation is absent here — that is expected and correct.

import pytest

from models.db_models import DynastyDB, User

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_login_and_create_dynasty(app, db, client, username="pzb_user"):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': 'password123'})
    client.post('/dynasty/create', data={
        'dynasty_name': 'House Detail',
        'theme_type': 'predefined',
        'theme_key': VALID_THEME_KEY,
        'start_year': '1300',
        'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
    }, follow_redirects=True)


@pytest.fixture
def pzb_client(app, db, session):
    with app.test_client() as c:
        _register_login_and_create_dynasty(app, db, c, username="pzb_user")
        yield c


class TestWorldMapPanZoomBorders:
    """Story 3-4: pan/zoom camera + border pass + overlay tab bar + world card."""

    def test_pan_zoom_wheel_and_settransform_present(self, pzb_client):
        """Wheel-zoom handler and canvas setTransform camera are wired up."""
        response = pzb_client.get('/world/map')
        assert response.status_code == 200
        assert b"addEventListener('wheel'" in response.data
        assert b"setTransform" in response.data

    def test_middle_drag_pan_present(self, pzb_client):
        """Middle-mouse-button drag panning is handled (button === 1)."""
        response = pzb_client.get('/world/map')
        assert b"button === 1" in response.data

    def test_double_click_recenter_present(self, pzb_client):
        """Double-click recenter handler (dblclick) is bound."""
        response = pzb_client.get('/world/map')
        assert b"dblclick" in response.data

    def test_border_pass_present(self, pzb_client):
        """A dedicated drawBorders rendering pass exists."""
        response = pzb_client.get('/world/map')
        assert b"drawBorders" in response.data

    def test_overlay_tab_bar_with_five_buttons(self, pzb_client):
        """The overlay-tab-bar contains all five overlay buttons."""
        response = pzb_client.get('/world/map')
        body = response.data
        assert b"overlay-tab-bar" in body
        assert b'id="btn-terrain"' in body
        assert b'id="btn-armies"' in body
        assert b'id="btn-economy"' in body
        assert b'id="btn-threats"' in body
        assert b'id="btn-projects"' in body

    def test_world_card_stub_updated(self, pzb_client):
        """World card stub is updated; old 'coming in Story 3-4' text is gone."""
        response = pzb_client.get('/world/map')
        assert b"other realms and their news" in response.data
        assert b"coming in Story 3-4" not in response.data
