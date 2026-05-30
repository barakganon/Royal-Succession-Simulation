# tests/integration/test_free_action_endpoint.py
# Story 4-1 (Free Action Endpoint) — CONTRACT-FIRST integration tests.
#
# These tests pin the contract for POST /dynasty/<id>/free_action:
#   - Body (form or JSON) carries `action_type` + params.
#   - Response is JSON {"ok": bool, "message": str}.
#   - 403 for a non-owner; 400 for unknown action / missing action_type.
#   - On success the change is committed and a HistoryLogEntryDB row with
#     event_type='free_action' is appended.
#   - The free action NEVER advances current_simulation_year (no-tick invariant).
#
# Several of these tests WILL FAIL until the FreeActionSystem, the two new
# DynastyDB columns (designated_heir_id, succession_law) and the route exist.
# That is expected and correct for a contract-first suite — do not weaken them.

import pytest

from models.db_models import User, DynastyDB, PersonDB, HistoryLogEntryDB, War

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror the patterns in test_detail_panel_render / test_diplomacy_routes)
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


def _add_person(app, db, dynasty_id, name="Heir", alive=True):
    """Add a PersonDB to the dynasty; return its id. Dead if alive=False."""
    with app.app_context():
        person = PersonDB(
            dynasty_id=dynasty_id,
            name=name,
            surname="Heirsson",
            gender="MALE",
            birth_year=1180,
            death_year=None if alive else 1199,
        )
        db.session.add(person)
        db.session.commit()
        return person.id


def _get_dynasty(app, db, dynasty_id):
    with app.app_context():
        return db.session.get(DynastyDB, dynasty_id)


def _free_action_log_count(app, db, dynasty_id):
    with app.app_context():
        return HistoryLogEntryDB.query.filter_by(
            dynasty_id=dynasty_id, event_type='free_action'
        ).count()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fa_client(app, db, session):
    """Authenticated owner client + dynasty id."""
    _, dynasty_id = _create_user_and_dynasty(app, db, "fa_user", "House Free")
    with app.test_client() as c:
        c.post('/login', data={'username': 'fa_user', 'password': 'password123'})
        yield c, dynasty_id


@pytest.fixture
def fa_two_dynasty_client(app, db, session):
    """Owner client (user A) plus a second dynasty owned by user B."""
    _, did_a = _create_user_and_dynasty(app, db, "fa_user_a", "House AlphaF")
    _, did_b = _create_user_and_dynasty(app, db, "fa_user_b", "House BetaF")
    with app.test_client() as c:
        c.post('/login', data={'username': 'fa_user_a', 'password': 'password123'})
        yield c, did_a, did_b


# ---------------------------------------------------------------------------
# 1. name_heir
# ---------------------------------------------------------------------------

class TestNameHeir:
    def test_name_heir_valid_living_person_sets_designated_heir(self, fa_client, app, db):
        """name_heir with a living dynasty member → ok:true and designated_heir_id set."""
        client, dynasty_id = fa_client
        heir_id = _add_person(app, db, dynasty_id, name="Valid", alive=True)
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'name_heir', 'heir_person_id': str(heir_id)},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        assert _get_dynasty(app, db, dynasty_id).designated_heir_id == heir_id

    def test_name_heir_dead_person_rejected(self, fa_client, app, db):
        """name_heir targeting a dead person → ok:false, heir not set."""
        client, dynasty_id = fa_client
        dead_id = _add_person(app, db, dynasty_id, name="Dead", alive=False)
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'name_heir', 'heir_person_id': str(dead_id)},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is False
        assert _get_dynasty(app, db, dynasty_id).designated_heir_id != dead_id

    def test_name_heir_other_dynasty_person_rejected(self, fa_two_dynasty_client, app, db):
        """name_heir targeting a person from another dynasty → ok:false."""
        client, did_a, did_b = fa_two_dynasty_client
        foreign_id = _add_person(app, db, did_b, name="Foreign", alive=True)
        response = client.post(
            f'/dynasty/{did_a}/free_action',
            data={'action_type': 'name_heir', 'heir_person_id': str(foreign_id)},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is False
        assert _get_dynasty(app, db, did_a).designated_heir_id != foreign_id


# ---------------------------------------------------------------------------
# 2. adopt_succession_law
# ---------------------------------------------------------------------------

class TestAdoptSuccessionLaw:
    def test_adopt_valid_law_sets_succession_law(self, fa_client, app, db):
        """adopt_succession_law with a valid law → ok:true and succession_law set."""
        client, dynasty_id = fa_client
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'adopt_succession_law', 'law': 'ELECTIVE'},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        assert _get_dynasty(app, db, dynasty_id).succession_law == 'ELECTIVE'

    def test_adopt_invalid_law_rejected(self, fa_client, app, db):
        """adopt_succession_law with a bogus law value → ok:false."""
        client, dynasty_id = fa_client
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'adopt_succession_law', 'law': 'NONSENSE_LAW'},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is False
        assert _get_dynasty(app, db, dynasty_id).succession_law != 'NONSENSE_LAW'


# ---------------------------------------------------------------------------
# 3. hold_feast
# ---------------------------------------------------------------------------

class TestHoldFeast:
    def test_hold_feast_spends_wealth_gains_prestige(self, fa_client, app, db):
        """hold_feast → ok:true, wealth decreased and prestige increased."""
        client, dynasty_id = fa_client
        before = _get_dynasty(app, db, dynasty_id)
        wealth_before, prestige_before = before.current_wealth, before.prestige
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'hold_feast'},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        after = _get_dynasty(app, db, dynasty_id)
        assert after.current_wealth < wealth_before
        assert after.prestige > prestige_before

    def test_hold_feast_insufficient_wealth_rejected(self, app, db, session):
        """hold_feast with wealth below cost → ok:false, nothing spent."""
        _, dynasty_id = _create_user_and_dynasty(
            app, db, "fa_poor", "House Pauper", wealth=0
        )
        with app.test_client() as client:
            client.post('/login', data={'username': 'fa_poor', 'password': 'password123'})
            response = client.post(
                f'/dynasty/{dynasty_id}/free_action',
                data={'action_type': 'hold_feast'},
            )
            body = response.get_json()
            assert body is not None and body['ok'] is False
            assert _get_dynasty(app, db, dynasty_id).current_wealth == 0


# ---------------------------------------------------------------------------
# 4. Diplomatic delegation (declare_war)
# ---------------------------------------------------------------------------

class TestDiplomaticDelegation:
    def test_declare_war_creates_war_row(self, fa_two_dynasty_client, app, db, monkeypatch):
        """declare_war free action delegates to diplomacy → a War row exists."""
        client, did_a, did_b = fa_two_dynasty_client
        # Guard against any LLM path the delegation might take.
        import main_flask_app as mfa
        monkeypatch.setattr(mfa, 'llm_model', None, raising=False)

        response = client.post(
            f'/dynasty/{did_a}/free_action',
            data={
                'action_type': 'declare_war',
                'target_dynasty_id': str(did_b),
                'war_goal': 'CONQUEST',
            },
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        with app.app_context():
            war = War.query.filter_by(
                attacker_dynasty_id=did_a, defender_dynasty_id=did_b
            ).first()
            assert war is not None


# ---------------------------------------------------------------------------
# 5. Validation: unknown / missing action_type
# ---------------------------------------------------------------------------

class TestActionValidation:
    def test_unknown_action_type_returns_400(self, fa_client):
        """Unknown action_type='nope' → HTTP 400 and ok:false."""
        client, dynasty_id = fa_client
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'nope'},
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body is not None and body['ok'] is False

    def test_missing_action_type_returns_400(self, fa_client):
        """Missing action_type → HTTP 400."""
        client, dynasty_id = fa_client
        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 6. No-tick invariant + history log
# ---------------------------------------------------------------------------

class TestNoTickInvariant:
    def test_free_action_does_not_advance_year_and_logs_event(self, fa_client, app, db):
        """A successful free action leaves current_simulation_year unchanged and
        appends a HistoryLogEntryDB row with event_type='free_action'."""
        client, dynasty_id = fa_client
        year_before = _get_dynasty(app, db, dynasty_id).current_simulation_year
        logs_before = _free_action_log_count(app, db, dynasty_id)

        response = client.post(
            f'/dynasty/{dynasty_id}/free_action',
            data={'action_type': 'hold_feast'},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True

        after = _get_dynasty(app, db, dynasty_id)
        assert after.current_simulation_year == year_before
        assert _free_action_log_count(app, db, dynasty_id) == logs_before + 1


# ---------------------------------------------------------------------------
# 7. Non-owner authorization
# ---------------------------------------------------------------------------

class TestAuthorization:
    def test_non_owner_post_returns_403(self, fa_two_dynasty_client):
        """A different logged-in user posting against did_b → 403."""
        client, did_a, did_b = fa_two_dynasty_client  # logged in as user A
        response = client.post(
            f'/dynasty/{did_b}/free_action',
            data={'action_type': 'hold_feast'},
        )
        assert response.status_code == 403
