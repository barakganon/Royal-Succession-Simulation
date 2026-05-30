# tests/integration/test_succession_flavor.py
# Story 5-2 (Succession candidate flavor + coronation chronicle) — CONTRACT-FIRST
# integration tests written by Agent C in an isolated worktree.
#
# These tests pin the Story 5-2 contract that layers on top of the Story 5-1
# human-controlled monarch-death succession interrupt:
#   - GET /dynasty/<id>/succession_candidates.json: EVERY candidate carries a
#     non-empty "flavor" string (deterministic fallback when the LLM is off,
#     referencing the candidate's traits / relation). The number of "flavor"
#     fields equals the number of candidates.
#   - POST /dynasty/<id>/succession_choice (valid heir): in addition to the
#     5-1 behaviour (crowns heir, unsets deceased, returns {ok:true}), appends a
#     HistoryLogEntryDB with event_type='coronation' for the dynasty.
#   - /world/map HTML contains the literal "succession-candidate-flavor".
#
# These tests WILL FAIL in this isolated worktree because the flavor field,
# coronation chronicle entry, and template marker do not yet exist (the backend
# + frontend agents build them). That is EXPECTED and correct for a
# contract-first suite — do NOT weaken, stub, or skip them. LLM is off in tests,
# so the deterministic fallback flavor path is what gets exercised.

import pytest

from models.db_models import User, DynastyDB, PersonDB, HistoryLogEntryDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_succession.py / test_detail_panel_render.py)
# ---------------------------------------------------------------------------

def _create_user_and_dynasty(app, db, username, dynasty_name,
                             password="password123", is_ai=False):
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
            current_wealth=500,
            start_year=1200,
            current_simulation_year=1230,
            prestige=10,
            is_ai_controlled=is_ai,
        )
        db.session.add(dynasty)
        db.session.commit()
        return user.id, dynasty.id


def _add_person(app, db, dynasty_id, name, gender="MALE", birth_year=1180,
                death_year=None, is_monarch=False, is_noble=True,
                father_sim_id=None, mother_sim_id=None, reign_start_year=None):
    """Add a PersonDB; return its id."""
    with app.app_context():
        person = PersonDB(
            dynasty_id=dynasty_id,
            name=name,
            surname="Crownsson",
            gender=gender,
            birth_year=birth_year,
            death_year=death_year,
            is_monarch=is_monarch,
            is_noble=is_noble,
            father_sim_id=father_sim_id,
            mother_sim_id=mother_sim_id,
            reign_start_year=reign_start_year,
        )
        db.session.add(person)
        db.session.commit()
        return person.id


def _setup_pending_succession(app, db, dynasty_id):
    """Create a DEAD monarch + 3 living noble children in `dynasty_id`.

    Children have varied gender / birth_year (all before the death year so
    ages are positive) and father_sim_id pointing at the deceased monarch.
    Returns (deceased_monarch_id, [child_ids...]).
    """
    monarch_id = _add_person(
        app, db, dynasty_id, name="OldKing", gender="MALE",
        birth_year=1170, death_year=1230, is_monarch=True, is_noble=True,
        reign_start_year=1200,
    )
    child_a = _add_person(app, db, dynasty_id, name="ElderSon", gender="MALE",
                          birth_year=1200, father_sim_id=monarch_id)
    child_b = _add_person(app, db, dynasty_id, name="YoungerSon", gender="MALE",
                          birth_year=1205, father_sim_id=monarch_id)
    child_c = _add_person(app, db, dynasty_id, name="Daughter", gender="FEMALE",
                          birth_year=1198, father_sim_id=monarch_id)
    return monarch_id, [child_a, child_b, child_c]


def _get_person(app, db, person_id):
    with app.app_context():
        return db.session.get(PersonDB, person_id)


# ---------------------------------------------------------------------------
# Fixtures (unique username space: sf_*)
# ---------------------------------------------------------------------------

@pytest.fixture
def flavor_client(app, db, session):
    """Authenticated owner (human dynasty) + a pending-succession DB state."""
    _, dynasty_id = _create_user_and_dynasty(app, db, "sf_user", "House Flavor")
    monarch_id, child_ids = _setup_pending_succession(app, db, dynasty_id)
    with app.test_client() as c:
        c.post('/login', data={'username': 'sf_user', 'password': 'password123'})
        yield c, dynasty_id, monarch_id, child_ids


# ---------------------------------------------------------------------------
# 1 + 2. succession_candidates.json — flavor presence + count parity
# ---------------------------------------------------------------------------

class TestSuccessionCandidateFlavor:
    def test_every_candidate_has_nonempty_flavor(self, flavor_client, app, db):
        """Every candidate in succession_candidates.json has a non-empty 'flavor' string."""
        client, dynasty_id, monarch_id, child_ids = flavor_client
        response = client.get(f'/dynasty/{dynasty_id}/succession_candidates.json')
        assert response.status_code == 200
        body = response.get_json()
        assert body is not None
        candidates = body['candidates']
        assert isinstance(candidates, list) and len(candidates) >= 1
        for c in candidates:
            assert 'flavor' in c, "candidate missing 'flavor' field"
            assert isinstance(c['flavor'], str)
            assert c['flavor'].strip() != "", "candidate 'flavor' must be non-empty"

    def test_flavor_count_equals_candidate_count(self, flavor_client, app, db):
        """The number of 'flavor' fields equals the number of candidates."""
        client, dynasty_id, monarch_id, child_ids = flavor_client
        body = client.get(f'/dynasty/{dynasty_id}/succession_candidates.json').get_json()
        candidates = body['candidates']
        flavors = [c['flavor'] for c in candidates if c.get('flavor', '').strip()]
        assert len(flavors) == len(candidates)


# ---------------------------------------------------------------------------
# 3 + 4. succession_choice — coronation chronicle + preserved 5-1 behaviour
# ---------------------------------------------------------------------------

class TestCoronationChronicle:
    def test_coronation_history_entry_exists_after_choice(self, flavor_client, app, db):
        """After succession_choice(valid heir), a HistoryLogEntryDB event_type='coronation' exists for the dynasty."""
        client, dynasty_id, monarch_id, child_ids = flavor_client
        chosen_id = child_ids[0]
        response = client.post(
            f'/dynasty/{dynasty_id}/succession_choice',
            data={'heir_id': str(chosen_id)},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        with app.app_context():
            coronation = HistoryLogEntryDB.query.filter_by(
                dynasty_id=dynasty_id, event_type='coronation'
            ).first()
            assert coronation is not None, \
                "expected a HistoryLogEntryDB with event_type='coronation'"

    def test_choice_still_crowns_heir_ok_true(self, flavor_client, app, db):
        """succession_choice still returns ok:true and the chosen heir is_monarch=True (5-1 behaviour preserved)."""
        client, dynasty_id, monarch_id, child_ids = flavor_client
        chosen_id = child_ids[1]
        response = client.post(
            f'/dynasty/{dynasty_id}/succession_choice',
            data={'heir_id': str(chosen_id)},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        heir = _get_person(app, db, chosen_id)
        assert heir.is_monarch is True


# ---------------------------------------------------------------------------
# 5. /world/map renders the candidate-flavor marker
# ---------------------------------------------------------------------------

class TestWorldMapFlavorMarker:
    def test_world_map_contains_candidate_flavor_marker(self, flavor_client, app, db):
        """/world/map body contains the literal 'succession-candidate-flavor'."""
        client, dynasty_id, monarch_id, child_ids = flavor_client
        response = client.get('/world/map')
        assert response.status_code == 200
        assert b"succession-candidate-flavor" in response.data
