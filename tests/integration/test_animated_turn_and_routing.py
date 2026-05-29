# tests/integration/test_animated_turn_and_routing.py
# Sprint 3 Story 3-5 (Worktree C / tests): CONTRACT-FIRST tests for the
# animated turn-pass UX + dashboard->map routing rework.
#
# These tests assert the behavior/tokens the backend + frontend agents will
# produce.  Several WILL FAIL in this isolated worktree because the
# implementation is absent.  That is EXPECTED and CORRECT - do not weaken,
# stub, or skip them.
#
# Contract asserted here:
#   * /dashboard 302-redirects a player WITH a dynasty straight to /world/map.
#   * /dashboard?manage=1 still renders the dashboard (200).
#   * The old /dynasty/<id>/action_phase route is gone (404).
#   * /dynasty/<id>/advance_turn served as XHR returns JSON with keys
#     ok / redirect / summary.
#   * /world/map carries the animated-end-turn wiring (toast stack, XHR
#     header, end-turn button, endTurn JS).

import pytest
from unittest.mock import patch

from models.db_models import User, DynastyDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_login_and_create_dynasty(app, db, client, username="atr_user"):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': 'password123'})
    client.post('/dynasty/create', data={
        'dynasty_name': 'House Animated',
        'theme_type': 'predefined',
        'theme_key': VALID_THEME_KEY,
        'start_year': '1300',
        'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
    }, follow_redirects=True)


def _get_dynasty_id(app, db, username="atr_user"):
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
        return dynasty.id if dynasty else None


@pytest.fixture
def atr_client(app, db, session):
    with app.test_client() as c:
        _register_login_and_create_dynasty(app, db, c, username="atr_user")
        yield c


@pytest.mark.integration
class TestAnimatedTurnAndRouting:
    """Story 3-5 contract: animated turn pass + dashboard routing rework."""

    def test_dashboard_redirects_to_map_for_player(self, atr_client, app, db):
        """A logged-in user WITH a dynasty is 302-redirected to /world/map."""
        response = atr_client.get('/dashboard', follow_redirects=False)
        assert response.status_code == 302
        assert '/world/map' in response.headers['Location']

    def test_dashboard_manage_param_renders_dashboard(self, atr_client, app, db):
        """/dashboard?manage=1 still renders the dashboard (200)."""
        response = atr_client.get('/dashboard?manage=1')
        assert response.status_code == 200

    def test_action_phase_route_is_gone(self, atr_client, app, db):
        """The old /dynasty/<id>/action_phase route returns 404."""
        dynasty_id = _get_dynasty_id(app, db, "atr_user")
        assert dynasty_id is not None
        response = atr_client.get(f'/dynasty/{dynasty_id}/action_phase')
        assert response.status_code == 404

    def test_advance_turn_xhr_returns_json(self, atr_client, app, db):
        """advance_turn served as XHR returns JSON with ok/redirect/summary keys."""
        dynasty_id = _get_dynasty_id(app, db, "atr_user")
        assert dynasty_id is not None
        # Mock the death check so no real LLM/death logic runs during the turn.
        with patch('models.turn_processor.process_death_check', return_value=False):
            response = atr_client.get(
                f'/dynasty/{dynasty_id}/advance_turn',
                headers={'X-Requested-With': 'XMLHttpRequest'},
            )
        assert response.is_json or response.content_type.startswith('application/json')
        payload = response.get_json()
        assert payload is not None
        assert 'ok' in payload
        assert 'redirect' in payload
        assert 'summary' in payload

    def test_world_map_has_animated_end_turn_wiring(self, atr_client, app, db):
        """/world/map carries the animated end-turn wiring tokens."""
        response = atr_client.get('/world/map')
        assert response.status_code == 200
        body = response.data
        assert b"turn-toast-stack" in body
        assert b"X-Requested-With" in body
        assert b"end-turn-btn" in body
        assert b"endTurn" in body

    def test_advance_turn_xhr_summary_has_expected_keys(self, atr_client, app, db):
        """When advance_turn's XHR summary is non-null it carries year/events keys."""
        dynasty_id = _get_dynasty_id(app, db, "atr_user")
        assert dynasty_id is not None
        with patch('models.turn_processor.process_death_check', return_value=False):
            response = atr_client.get(
                f'/dynasty/{dynasty_id}/advance_turn',
                headers={'X-Requested-With': 'XMLHttpRequest'},
            )
        payload = response.get_json()
        assert payload is not None
        summary = payload.get('summary')
        if summary is not None:
            assert 'year' in summary
            assert 'events' in summary
