# tests/integration/test_world_map_panels.py
# Sprint 3 Story 3-1: assert the new world_map left rail + slide-in detail
# panel render as expected.

import pytest

from models.db_models import DynastyDB, User

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_login_and_create_dynasty(app, db, client, username="wmp_user"):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': 'password123'})
    client.post('/dynasty/create', data={
        'dynasty_name': 'House Rail',
        'theme_type': 'predefined',
        'theme_key': VALID_THEME_KEY,
        'start_year': '1300',
        'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
    }, follow_redirects=True)


@pytest.fixture
def wmp_client(app, db, session):
    with app.test_client() as c:
        _register_login_and_create_dynasty(app, db, c, username="wmp_user")
        yield c


class TestWorldMapPanels:
    def test_world_map_returns_200(self, wmp_client):
        response = wmp_client.get('/world/map')
        assert response.status_code == 200

    def test_left_rail_renders(self, wmp_client):
        response = wmp_client.get('/world/map')
        assert b'id="game-left-rail"' in response.data
        assert b'class="game-left-rail"' in response.data

    def test_detail_panel_stub_renders(self, wmp_client):
        response = wmp_client.get('/world/map')
        assert b'id="game-detail-panel"' in response.data
        assert b'id="detail-body"' in response.data

    def test_three_project_slots_render(self, wmp_client):
        # New dynasty has 0 active projects → all 3 slots render as empty
        # placeholders with class "is-empty".
        response = wmp_client.get('/world/map')
        # Count substring occurrences of the empty-slot marker.
        empty_marker_count = response.data.count(b'game-project-slot is-empty')
        assert empty_marker_count == 3

    def test_topbar_no_longer_has_resource_pills(self, wmp_client):
        # Resource pills moved to left rail. The legacy id="res-gold" / "res-food"
        # / "res-manpower" pills (and the food/manpower placeholders) are gone.
        response = wmp_client.get('/world/map')
        assert b'id="res-food"' not in response.data
        assert b'id="res-manpower"' not in response.data

    def test_dynasty_name_still_present(self, wmp_client):
        # Sanity: removing the topbar pills must not have stripped the name.
        response = wmp_client.get('/world/map')
        assert b'House Rail' in response.data

    def test_project_slots_are_keyboard_operable(self, wmp_client):
        # AC1 + review patch: slots use <div role="button" tabindex="0">
        # with onkeydown, not just onclick.
        response = wmp_client.get('/world/map')
        assert b'role="button"' in response.data
        assert b'tabindex="0"' in response.data
        assert b'onkeydown=' in response.data

    def test_nav_buttons_have_aria_labels(self, wmp_client):
        # AC1 + review patch: emoji-only nav buttons need accessible names.
        response = wmp_client.get('/world/map')
        assert b'aria-label="Open chronicle"' in response.data
        assert b'aria-label="Open world overview"' in response.data
        assert b'aria-label="Open war overview"' in response.data

    def test_detail_panel_has_dialog_role(self, wmp_client):
        # AC2 + review patch: the slide-in is a dialog for screen readers.
        response = wmp_client.get('/world/map')
        assert b'role="dialog"' in response.data
        assert b'aria-labelledby="detail-header-label"' in response.data
