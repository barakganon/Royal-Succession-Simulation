# tests/integration/test_detail_panel_render.py
# Sprint 3 Story 3-3 (Worktree B / frontend): assert the new conditional
# detail-panel rendering + Threats/Projects overlay buttons + JS seeds.
#
# These tests assert ONLY frontend DOM + JS string presence in the rendered
# /world/map response. The backend agent's /territory/<id>/details.json
# endpoint is exercised in test_territory_details_endpoint.py.

import pytest

from models.db_models import DynastyDB, User

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_login_and_create_dynasty(app, db, client, username="dpr_user"):
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
def dpr_client(app, db, session):
    with app.test_client() as c:
        _register_login_and_create_dynasty(app, db, c, username="dpr_user")
        yield c


class TestDetailPanelRender:
    """AC8 (frontend half): structural assertions on the world_map response."""

    def test_world_map_renders_five_overlay_buttons(self, dpr_client):
        """AC5: terrain + armies + economy + threats + projects."""
        response = dpr_client.get('/world/map')
        assert response.status_code == 200
        assert b'id="btn-terrain"' in response.data
        assert b'id="btn-armies"' in response.data
        assert b'id="btn-economy"' in response.data
        assert b'id="btn-threats"' in response.data
        assert b'id="btn-projects"' in response.data

    def test_detail_panel_stub_literal_is_gone(self, dpr_client):
        """AC3: the Story-3-1 stub literal must no longer appear in the JS."""
        response = dpr_client.get('/world/map')
        assert b'Story 3-3 will fill this' not in response.data

    def test_active_projects_by_id_seed_present(self, dpr_client):
        """AC3: window.__activeProjectsById initializer is in the page."""
        response = dpr_client.get('/world/map')
        assert b'window.__activeProjectsById' in response.data
        # Also assert the initialization pattern (forEach loop) is present so
        # we know it's seeded, not just declared.
        assert b'activeProjectsArr.forEach' in response.data

    def test_set_overlay_supports_threats_and_projects(self, dpr_client):
        """AC5: JS setOverlay must reference both new modes."""
        response = dpr_client.get('/world/map')
        body = response.data
        # The mode-name array passed to forEach must include both new modes.
        assert b"'threats'" in body
        assert b"'projects'" in body
        # And the drawAll branches for each overlay must exist.
        assert b"overlay === 'threats'" in body
        assert b"overlay === 'projects'" in body

    def test_detail_panel_switch_has_territory_case(self, dpr_client):
        """Bonus: the conditional switch on ctx.type is rendered."""
        response = dpr_client.get('/world/map')
        assert b"switch (type)" in response.data
        assert b"case 'territory':" in response.data

    def test_left_click_handler_opens_detail_panel(self, dpr_client):
        """AC4: the canvas click handler must call openDetailPanel
        with a territory ctx (sanity-check the literal string is present)."""
        response = dpr_client.get('/world/map')
        assert b"openDetailPanel({ type: 'territory', id: p.territory_id })" in response.data
