# tests/integration/test_succession.py
# Story 5-1 (Monarch death interrupt + succession choice) — CONTRACT-FIRST
# integration tests written by Agent C in an isolated worktree.
#
# These tests pin the contract for the human-controlled monarch-death
# succession interrupt:
#   - Pending-succession marker = a PersonDB(dynasty_id, is_monarch=True,
#     death_year not None). A HUMAN (is_ai_controlled=False) monarch death halts
#     WITHOUT auto-crowning; an AI (is_ai_controlled=True) monarch death
#     auto-crowns immediately (no pending state).
#   - GET  /dynasty/<id>/succession_candidates.json
#       -> {pending, deceased?, candidates:[{id,name,surname,portrait_svg,
#           traits,birth_year,age,relation,is_default}]}; exactly one is_default
#           (== designated_heir_id if among candidates else the first candidate).
#   - POST /dynasty/<id>/succession_choice (body heir_id)
#       -> {ok, message}; crowns the heir (is_monarch=True, reign_start_year set)
#          and unsets the deceased's is_monarch. Ineligible/foreign heir -> 400;
#          non-owner -> 403.
#   - /world/map HTML contains 'succession-modal' + 'succession_candidates'.
#
# Several of these tests WILL FAIL in this isolated worktree because the
# endpoints / template markers / AI-vs-human succession branch do not yet
# exist (the backend + frontend agents build them). That is EXPECTED and
# correct for a contract-first suite — do not weaken, stub, or skip them.

import pytest

from models.db_models import User, DynastyDB, PersonDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_free_action_endpoint / test_detail_panel_render)
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

    Returns (deceased_monarch_id, [child_ids...]) with children spanning
    varied birth_year/gender so primogeniture ordering is deterministic.
    Mirrors the human-halt pending-succession DB state directly so the
    candidates endpoint can be exercised without running a full turn.
    """
    monarch_id = _add_person(
        app, db, dynasty_id, name="OldKing", gender="MALE",
        birth_year=1170, death_year=1230, is_monarch=True, is_noble=True,
        reign_start_year=1200,
    )
    # Eldest son, younger son, daughter — all living nobles, children of monarch.
    child_a = _add_person(app, db, dynasty_id, name="ElderSon", gender="MALE",
                          birth_year=1200, father_sim_id=monarch_id)
    child_b = _add_person(app, db, dynasty_id, name="YoungerSon", gender="MALE",
                          birth_year=1205, father_sim_id=monarch_id)
    child_c = _add_person(app, db, dynasty_id, name="Daughter", gender="FEMALE",
                          birth_year=1198, father_sim_id=monarch_id)
    return monarch_id, [child_a, child_b, child_c]


def _get_dynasty(app, db, dynasty_id):
    with app.app_context():
        return db.session.get(DynastyDB, dynasty_id)


def _get_person(app, db, person_id):
    with app.app_context():
        return db.session.get(PersonDB, person_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def succ_client(app, db, session):
    """Authenticated owner (human dynasty) + a pending-succession DB state."""
    _, dynasty_id = _create_user_and_dynasty(app, db, "succ_user", "House Crown")
    monarch_id, child_ids = _setup_pending_succession(app, db, dynasty_id)
    with app.test_client() as c:
        c.post('/login', data={'username': 'succ_user', 'password': 'password123'})
        yield c, dynasty_id, monarch_id, child_ids


@pytest.fixture
def succ_two_client(app, db, session):
    """Owner client (user A) plus a second dynasty owned by user B (pending)."""
    _, did_a = _create_user_and_dynasty(app, db, "succ_user_a", "House AlphaC")
    _, did_b = _create_user_and_dynasty(app, db, "succ_user_b", "House BetaC")
    monarch_b, children_b = _setup_pending_succession(app, db, did_b)
    with app.test_client() as c:
        c.post('/login', data={'username': 'succ_user_a', 'password': 'password123'})
        yield c, did_a, did_b, monarch_b, children_b


# ---------------------------------------------------------------------------
# 1. succession_candidates.json — pending human dynasty
# ---------------------------------------------------------------------------

class TestSuccessionCandidates:
    def test_pending_human_dynasty_lists_candidates_with_one_default(self, succ_client, app, db):
        """Human dynasty with a dead monarch -> pending:true, candidates listed, exactly one is_default."""
        client, dynasty_id, monarch_id, child_ids = succ_client
        response = client.get(f'/dynasty/{dynasty_id}/succession_candidates.json')
        assert response.status_code == 200
        body = response.get_json()
        assert body is not None
        assert body['pending'] is True
        candidates = body['candidates']
        assert isinstance(candidates, list) and len(candidates) >= 1
        # Every listed candidate must be one of the living children.
        cand_ids = {c['id'] for c in candidates}
        assert cand_ids.issubset(set(child_ids))
        # Required candidate fields are present.
        for c in candidates:
            for field in ('id', 'name', 'surname', 'portrait_svg', 'traits',
                          'birth_year', 'age', 'relation', 'is_default'):
                assert field in c, f"candidate missing field '{field}'"
        # Exactly one candidate is the default selection.
        defaults = [c for c in candidates if c['is_default']]
        assert len(defaults) == 1

    def test_default_honours_designated_heir_id(self, succ_client, app, db):
        """Setting designated_heir_id to a non-first candidate makes that candidate is_default."""
        client, dynasty_id, monarch_id, child_ids = succ_client
        # Probe the natural (un-designated) default first.
        first = client.get(f'/dynasty/{dynasty_id}/succession_candidates.json').get_json()
        natural_default_id = next(c['id'] for c in first['candidates'] if c['is_default'])
        # Pick a candidate that is NOT the natural default.
        other_id = next(cid for cid in child_ids if cid != natural_default_id)
        with app.app_context():
            dyn = db.session.get(DynastyDB, dynasty_id)
            dyn.designated_heir_id = other_id
            db.session.commit()
        body = client.get(f'/dynasty/{dynasty_id}/succession_candidates.json').get_json()
        defaults = [c for c in body['candidates'] if c['is_default']]
        assert len(defaults) == 1
        assert defaults[0]['id'] == other_id

    def test_no_pending_succession_for_living_monarch(self, app, db, session):
        """A dynasty with a LIVING monarch (no dead monarch) -> pending:false."""
        _, dynasty_id = _create_user_and_dynasty(app, db, "succ_live", "House Living")
        _add_person(app, db, dynasty_id, name="LiveKing", gender="MALE",
                    birth_year=1190, death_year=None, is_monarch=True,
                    reign_start_year=1210)
        with app.test_client() as client:
            client.post('/login', data={'username': 'succ_live', 'password': 'password123'})
            response = client.get(f'/dynasty/{dynasty_id}/succession_candidates.json')
            assert response.status_code == 200
            body = response.get_json()
            assert body is not None
            assert body['pending'] is False


# ---------------------------------------------------------------------------
# 2. succession_choice — crowning + validation + auth
# ---------------------------------------------------------------------------

class TestSuccessionChoice:
    def test_valid_choice_crowns_heir_and_unsets_deceased(self, succ_client, app, db):
        """A valid candidate -> ok:true; chosen heir crowned (is_monarch + reign_start_year) and deceased un-crowned."""
        client, dynasty_id, monarch_id, child_ids = succ_client
        chosen_id = child_ids[1]  # the younger son — an explicit, valid choice
        response = client.post(
            f'/dynasty/{dynasty_id}/succession_choice',
            data={'heir_id': str(chosen_id)},
        )
        body = response.get_json()
        assert body is not None and body['ok'] is True
        heir = _get_person(app, db, chosen_id)
        assert heir.is_monarch is True
        assert heir.reign_start_year is not None
        deceased = _get_person(app, db, monarch_id)
        assert deceased.is_monarch is False

    def test_foreign_or_ineligible_heir_rejected_400(self, succ_two_client, app, db):
        """A foreign/ineligible heir_id -> ok:false with HTTP 400."""
        client, did_a, did_b, monarch_b, children_b = succ_two_client
        # children_b belong to dynasty B; user A owns dynasty A. Set up A as pending
        # so the endpoint reaches eligibility validation rather than "no pending".
        _setup_pending_succession(app, db, did_a)
        foreign_heir = children_b[0]
        response = client.post(
            f'/dynasty/{did_a}/succession_choice',
            data={'heir_id': str(foreign_heir)},
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body is not None and body['ok'] is False

    def test_non_owner_succession_choice_returns_403(self, succ_two_client, app, db):
        """A logged-in non-owner posting succession_choice against another dynasty -> 403."""
        client, did_a, did_b, monarch_b, children_b = succ_two_client  # logged in as user A
        response = client.post(
            f'/dynasty/{did_b}/succession_choice',
            data={'heir_id': str(children_b[0])},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# 3. AI auto-crown (no pending state)
# ---------------------------------------------------------------------------

class TestAIAutoCrown:
    def test_ai_dynasty_auto_crowns_on_monarch_death(self, app, db, session):
        """AI dynasty: running succession leaves a LIVING is_monarch (auto-crowned, not pending)."""
        from models import turn_processor as tp
        from utils.theme_manager import get_theme

        _, dynasty_id = _create_user_and_dynasty(
            app, db, "succ_ai", "House Machina", is_ai=True
        )
        monarch_id, child_ids = _setup_pending_succession(app, db, dynasty_id)

        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            deceased = db.session.get(PersonDB, monarch_id)
            theme_config = get_theme(VALID_THEME_KEY) or {}
            # Drive the succession path directly for the AI dynasty.
            tp.process_succession(dynasty, deceased, 1230, theme_config)
            db.session.commit()

        # A living monarch must now exist for the AI dynasty (auto-crowned).
        with app.app_context():
            living_monarch = PersonDB.query.filter_by(
                dynasty_id=dynasty_id, is_monarch=True, death_year=None
            ).first()
            assert living_monarch is not None
            assert living_monarch.id in child_ids


# ---------------------------------------------------------------------------
# 4. /world/map renders the succession modal + JS seed
# ---------------------------------------------------------------------------

class TestWorldMapSuccessionModal:
    def test_world_map_contains_succession_modal_and_seed(self, succ_client, app, db):
        """/world/map body contains the 'succession-modal' DOM + 'succession_candidates' JS seed."""
        client, dynasty_id, monarch_id, child_ids = succ_client
        response = client.get('/world/map')
        assert response.status_code == 200
        assert b"succession-modal" in response.data
        assert b"succession_candidates" in response.data
