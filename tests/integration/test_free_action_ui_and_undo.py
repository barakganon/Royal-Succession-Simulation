# tests/integration/test_free_action_ui_and_undo.py
# Story 4-2 (Free Action UI + reversible Undo + catalogue) — CONTRACT-FIRST.
#
# Agent C's contract suite. Several of these WILL FAIL in the isolated worktree
# because the backend (catalogue JSON + deterministic LLM flavor fallback +
# reversible undo session stack) and the frontend (/world/map markers) are built
# by other agents. Expected-failure is correct for a contract-first suite —
# do NOT weaken, stub, or skip these.
#
# Contract under test:
#   GET  /dynasty/<id>/free_action_catalogue.json
#        → {"actions":[{action_type,label,category,needs_target,undoable}...]}
#          for all 9 actions; 403 for a non-owner.
#   POST /dynasty/<id>/free_action  (form or JSON) → {ok,message}; appends a
#        HistoryLogEntryDB(event_type='free_action') whose event_string is the
#        deterministic flavor fallback (non-empty) when the LLM is off.
#   POST /dynasty/<id>/free_action/undo → {ok,message}; reverses the LAST
#        reversible action via a SERVER SESSION stack. Empty stack →
#        {"ok": false, "message": "Nothing to undo"}.
#          Reversible    = {name_heir, adopt_succession_law, hold_feast,
#                           hold_tournament, pardon_vassal}
#          Non-reversible= {declare_war, propose_treaty, send_envoy,
#                           issue_ultimatum}  (never pushed → not undoable)
#   /world/map HTML contains `free_action_catalogue`, a `ctx-free-actions`
#        container, and an undo control.
#
# IMPORTANT: undo uses a server *session* stack, so a single test_client must
# be reused across the perform+undo calls in one test (the client persists the
# session cookie).

import pytest

from models.db_models import User, DynastyDB, PersonDB, HistoryLogEntryDB, War

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

ALL_ACTION_TYPES = {
    'name_heir', 'adopt_succession_law', 'hold_feast', 'hold_tournament',
    'pardon_vassal', 'declare_war', 'propose_treaty', 'send_envoy',
    'issue_ultimatum',
}
REVERSIBLE = {
    'name_heir', 'adopt_succession_law', 'hold_feast', 'hold_tournament',
    'pardon_vassal',
}


# ---------------------------------------------------------------------------
# Helpers (mirror test_free_action_endpoint.py / test_detail_panel_render.py)
# ---------------------------------------------------------------------------

def _create_user_and_dynasty(app, db, username, dynasty_name,
                             password="password123", wealth=500):
    """Create a User + DynastyDB directly; return (user_id, dynasty_id)."""
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        dynasty = DynastyDB(
            user_id=user.id,
            name=dynasty_name,
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=wealth,
            start_year=1200,
            current_simulation_year=1200,
            prestige=10,
        )
        db.session.add(dynasty)
        db.session.commit()
        return user.id, dynasty.id


def _get_dynasty(app, db, dynasty_id):
    with app.app_context():
        return db.session.get(DynastyDB, dynasty_id)


def _free_action_log_count(app, db, dynasty_id):
    with app.app_context():
        return HistoryLogEntryDB.query.filter_by(
            dynasty_id=dynasty_id, event_type='free_action'
        ).count()


# ---------------------------------------------------------------------------
# Fixtures (unique username space: fa2_*)
# ---------------------------------------------------------------------------

@pytest.fixture
def fa2_client(app, db, session):
    """Authenticated owner client + dynasty id (single persistent client)."""
    _, dynasty_id = _create_user_and_dynasty(app, db, "fa2_user", "House Free2")
    with app.test_client() as c:
        c.post('/login', data={'username': 'fa2_user', 'password': 'password123'})
        yield c, dynasty_id


@pytest.fixture
def fa2_two_dynasty_client(app, db, session):
    """Owner client (user A) plus a second dynasty owned by user B."""
    _, did_a = _create_user_and_dynasty(app, db, "fa2_user_a", "House Alpha2")
    _, did_b = _create_user_and_dynasty(app, db, "fa2_user_b", "House Beta2")
    with app.test_client() as c:
        c.post('/login', data={'username': 'fa2_user_a', 'password': 'password123'})
        yield c, did_a, did_b


# ---------------------------------------------------------------------------
# 1. Catalogue contract
# ---------------------------------------------------------------------------

class TestCatalogue:
    def test_catalogue_lists_nine_actions_with_metadata(self, fa2_client, app, db):
        """Catalogue returns all 9 actions with category/needs_target/undoable;
        hold_feast undoable, declare_war non-undoable + needs_target."""
        client, dynasty_id = fa2_client
        response = client.get(f'/dynasty/{dynasty_id}/free_action_catalogue.json')
        assert response.status_code == 200
        body = response.get_json()
        assert body is not None and 'actions' in body
        actions = body['actions']
        by_type = {a['action_type']: a for a in actions}
        assert set(by_type.keys()) == ALL_ACTION_TYPES
        for a in actions:
            assert 'label' in a and a['label']
            assert 'category' in a
            assert 'needs_target' in a
            assert 'undoable' in a
        assert by_type['hold_feast']['undoable'] is True
        assert by_type['declare_war']['undoable'] is False
        assert by_type['declare_war']['needs_target'] is True
        # Every reversible action is flagged undoable, every other one is not.
        for atype, a in by_type.items():
            assert a['undoable'] is (atype in REVERSIBLE)

    def test_catalogue_non_owner_returns_403(self, fa2_two_dynasty_client):
        """A different logged-in user fetching another dynasty's catalogue → 403."""
        client, did_a, did_b = fa2_two_dynasty_client  # logged in as user A
        response = client.get(f'/dynasty/{did_b}/free_action_catalogue.json')
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# 2. Deterministic flavor fallback (LLM off in tests)
# ---------------------------------------------------------------------------

class TestFlavorFallback:
    def test_free_action_writes_nonempty_flavor_event_string(self, fa2_client, app, db, monkeypatch):
        """A free action logs a HistoryLogEntryDB with a non-empty deterministic
        flavor event_string when the LLM is off."""
        import main_flask_app as mfa
        monkeypatch.setattr(mfa, 'llm_model', None, raising=False)
        client, dynasty_id = fa2_client
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'hold_feast'},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        with app.app_context():
            entry = HistoryLogEntryDB.query.filter_by(
                dynasty_id=dynasty_id, event_type='free_action'
            ).order_by(HistoryLogEntryDB.id.desc()).first()
            assert entry is not None
            assert entry.event_string is not None and entry.event_string.strip() != ''


# ---------------------------------------------------------------------------
# 3. Undo of a reversible action restores state
# ---------------------------------------------------------------------------

class TestUndoReversible:
    def test_undo_hold_feast_restores_wealth_prestige_and_log(self, fa2_client, app, db, monkeypatch):
        """Undoing hold_feast restores current_wealth + prestige and removes its
        free_action history row (same client → shared server session stack)."""
        import main_flask_app as mfa
        monkeypatch.setattr(mfa, 'llm_model', None, raising=False)
        client, dynasty_id = fa2_client

        before = _get_dynasty(app, db, dynasty_id)
        wealth_before, prestige_before = before.current_wealth, before.prestige
        logs_before = _free_action_log_count(app, db, dynasty_id)

        perform = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'hold_feast'},
        )
        pbody = perform.get_json()
        assert pbody is not None and pbody['ok'] is True

        undo = client.post(f'/dynasty/{dynasty_id}/free_action/undo')
        ubody = undo.get_json()
        assert ubody is not None and ubody['ok'] is True

        after = _get_dynasty(app, db, dynasty_id)
        assert after.current_wealth == wealth_before
        assert after.prestige == prestige_before
        assert _free_action_log_count(app, db, dynasty_id) == logs_before


# ---------------------------------------------------------------------------
# 4. Undo with an empty stack
# ---------------------------------------------------------------------------

class TestUndoEmptyStack:
    def test_undo_empty_stack_returns_nothing_to_undo(self, fa2_client):
        """A fresh client with no performed action → ok:false / 'Nothing to undo'."""
        client, dynasty_id = fa2_client
        response = client.post(f'/dynasty/{dynasty_id}/free_action/undo')
        body = response.get_json()
        assert body is not None
        assert body['ok'] is False
        assert body['message'] == 'Nothing to undo'


# ---------------------------------------------------------------------------
# 5. Non-reversible action is never undoable
# ---------------------------------------------------------------------------

class TestUndoNonReversible:
    def test_declare_war_is_not_pushed_to_undo_stack(self, fa2_two_dynasty_client, app, db, monkeypatch):
        """declare_war is non-reversible: after performing it, undo reports
        'Nothing to undo' and the War row still exists."""
        import main_flask_app as mfa
        monkeypatch.setattr(mfa, 'llm_model', None, raising=False)
        client, did_a, did_b = fa2_two_dynasty_client

        perform = client.post(
            f'/dynasty/{did_a}/free_action',
            data={
                'action_type': 'declare_war',
                'target_dynasty_id': str(did_b),
                'war_goal': 'CONQUEST',
            },
        )
        pbody = perform.get_json()
        assert pbody is not None and pbody['ok'] is True

        undo = client.post(f'/dynasty/{did_a}/free_action/undo')
        ubody = undo.get_json()
        assert ubody is not None
        assert ubody['ok'] is False
        assert ubody['message'] == 'Nothing to undo'

        with app.app_context():
            war = War.query.filter_by(
                attacker_dynasty_id=did_a, defender_dynasty_id=did_b
            ).first()
            assert war is not None


# ---------------------------------------------------------------------------
# 6. /world/map frontend markers
# ---------------------------------------------------------------------------

class TestWorldMapMarkers:
    def test_world_map_has_free_action_catalogue_container_and_undo(self, fa2_client):
        """/world/map embeds the catalogue, a ctx-free-actions container, and an
        undo control marker."""
        client, _ = fa2_client
        response = client.get('/world/map')
        assert response.status_code == 200
        body = response.data
        assert b'free_action_catalogue' in body
        assert b'ctx-free-actions' in body
        # Undo control marker (id/data-hook used by the menu's undo button).
        assert b'free-action-undo' in body
