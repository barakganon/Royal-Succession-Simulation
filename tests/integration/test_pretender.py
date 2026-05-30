# tests/integration/test_pretender.py
# Story 5-3 (Pretenders to the throne) — CONTRACT-FIRST integration tests
# written by Agent C in an isolated worktree.
#
# These tests pin the contract for pretenders. The schema columns
# (PersonDB.is_pretender / pretender_strength), the succession-time flagging,
# and the per-year strength accumulation (turn_processor.PRETENDER_STRENGTH_PER_YEAR)
# are built by OTHER agents. In this isolated worktree those pieces do NOT exist
# yet, so several of these tests WILL FAIL — that is EXPECTED and correct for a
# contract-first suite. Do NOT weaken, stub, or skip them.
#
# Contract under test
#   - PersonDB.is_pretender (default False) + pretender_strength (default 0).
#   - Choosing a NON-default heir via succession_choice -> the bypassed default
#     candidate gets is_pretender=True, pretender_strength>0, and a
#     HistoryLogEntryDB(event_type='pretender_claim') is written.
#   - Choosing the DEFAULT heir -> no pretender flagged, no pretender_claim entry.
#   - turn_processor.PRETENDER_STRENGTH_PER_YEAR == 5: each simulated year a living
#     is_pretender person's pretender_strength grows by 5 * years.

from unittest.mock import patch

import pytest

from models.db_models import DynastyDB, HistoryLogEntryDB, PersonDB, User

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_succession.py)
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
            surname="Pretendsson",
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

    Returns (deceased_monarch_id, [child_ids...]). The deceased monarch keeps
    is_monarch=True with a death_year set — the pending-succession marker the
    succession_choice route looks for.
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


def _set_designated_heir(app, db, dynasty_id, heir_id):
    with app.app_context():
        dyn = db.session.get(DynastyDB, dynasty_id)
        dyn.designated_heir_id = heir_id
        db.session.commit()


def _pretender_claim_entries(app, db, dynasty_id):
    with app.app_context():
        return HistoryLogEntryDB.query.filter_by(
            dynasty_id=dynasty_id, event_type='pretender_claim'
        ).all()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pret_client(app, db, session):
    """Authenticated owner (human dynasty) + a pending-succession DB state."""
    _, dynasty_id = _create_user_and_dynasty(app, db, "pret_user", "House Pretend")
    monarch_id, child_ids = _setup_pending_succession(app, db, dynasty_id)
    with app.test_client() as c:
        c.post('/login', data={'username': 'pret_user', 'password': 'password123'})
        yield c, dynasty_id, monarch_id, child_ids


# ---------------------------------------------------------------------------
# 1. Schema defaults
# ---------------------------------------------------------------------------

class TestPretenderColumnDefaults:
    def test_fresh_person_has_pretender_defaults(self, app, db, session):
        """A freshly created PersonDB has is_pretender == False and pretender_strength == 0."""
        _, dynasty_id = _create_user_and_dynasty(app, db, "pret_default", "House Default")
        pid = _add_person(app, db, dynasty_id, name="Freshborn", birth_year=1210)
        person = _get_person(app, db, pid)
        assert person.is_pretender is False
        assert person.pretender_strength == 0


# ---------------------------------------------------------------------------
# 2. Non-default heir flags the bypassed default as a pretender
# ---------------------------------------------------------------------------

class TestNonDefaultFlagsPretender:
    def test_non_default_choice_flags_bypassed_default(self, pret_client, app, db):
        """Crowning a non-default heir flags the bypassed designated heir: is_pretender True, strength>0, and a 'pretender_claim' log exists."""
        client, dynasty_id, monarch_id, child_ids = pret_client
        # Make the default deterministic: designate a specific candidate as heir.
        default_heir_id = child_ids[0]
        _set_designated_heir(app, db, dynasty_id, default_heir_id)
        # Crown a DIFFERENT (non-default) candidate.
        chosen_id = child_ids[1]
        assert chosen_id != default_heir_id

        response = client.post(
            f'/dynasty/{dynasty_id}/succession_choice',
            data={'heir_id': str(chosen_id)},
        )
        body = response.get_json()
        assert body is not None and body.get('ok') is True

        # The bypassed default candidate is now a pretender.
        bypassed = _get_person(app, db, default_heir_id)
        assert bypassed.is_pretender is True
        assert bypassed.pretender_strength > 0

        # The chosen (crowned) heir is NOT a pretender.
        crowned = _get_person(app, db, chosen_id)
        assert crowned.is_pretender is False

        # A pretender_claim history entry was written.
        claims = _pretender_claim_entries(app, db, dynasty_id)
        assert len(claims) >= 1
        assert any(c.person1_sim_id == default_heir_id for c in claims)


# ---------------------------------------------------------------------------
# 3. Choosing the default heir flags no pretender
# ---------------------------------------------------------------------------

class TestDefaultChoiceNoPretender:
    def test_default_choice_flags_no_pretender(self, pret_client, app, db):
        """Crowning the DEFAULT (designated) heir flags no pretender and writes no 'pretender_claim' entry."""
        client, dynasty_id, monarch_id, child_ids = pret_client
        default_heir_id = child_ids[0]
        _set_designated_heir(app, db, dynasty_id, default_heir_id)

        response = client.post(
            f'/dynasty/{dynasty_id}/succession_choice',
            data={'heir_id': str(default_heir_id)},
        )
        body = response.get_json()
        assert body is not None and body.get('ok') is True

        # No person in the dynasty is flagged as a pretender.
        with app.app_context():
            pretenders = PersonDB.query.filter_by(
                dynasty_id=dynasty_id, is_pretender=True
            ).all()
            assert pretenders == []

        # No pretender_claim history entry was written.
        claims = _pretender_claim_entries(app, db, dynasty_id)
        assert claims == []


# ---------------------------------------------------------------------------
# 4. Per-year strength accumulation
# ---------------------------------------------------------------------------

class TestPretenderAccumulation:
    def test_living_pretender_strength_grows_per_year(self, app, db, session):
        """A living pretender's strength grows by PRETENDER_STRENGTH_PER_YEAR * years over a processed turn."""
        from models import turn_processor as tp

        assert tp.PRETENDER_STRENGTH_PER_YEAR == 5

        _, dynasty_id = _create_user_and_dynasty(app, db, "pret_accum", "House Accum")
        # A living monarch so the turn has a head of house and does not crown anyone.
        _add_person(app, db, dynasty_id, name="LiveKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1210)
        # The pretender: a living noble pre-seeded with a known strength.
        pid = _add_person(app, db, dynasty_id, name="ClaimantPaul", gender="MALE",
                          birth_year=1205)
        with app.app_context():
            claimant = db.session.get(PersonDB, pid)
            claimant.is_pretender = True
            claimant.pretender_strength = 10
            db.session.commit()

        years = 5
        # Keep everyone alive across the turn so the pretender survives to accrue.
        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False):
                tp.process_dynasty_turn(dynasty_id, years_to_advance=years)

        after = _get_person(app, db, pid)
        assert after.pretender_strength == 10 + tp.PRETENDER_STRENGTH_PER_YEAR * years

    def test_dead_pretender_does_not_accumulate(self, app, db, session):
        """A DEAD pretender (death_year set) does not accrue pretender_strength over a turn."""
        from models import turn_processor as tp

        _, dynasty_id = _create_user_and_dynasty(app, db, "pret_dead", "House DeadClaim")
        _add_person(app, db, dynasty_id, name="LiveQueen", gender="FEMALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1210)
        # A dead pretender: death_year already set, strength frozen at 20.
        pid = _add_person(app, db, dynasty_id, name="GhostClaimant", gender="MALE",
                          birth_year=1200, death_year=1228)
        with app.app_context():
            ghost = db.session.get(PersonDB, pid)
            ghost.is_pretender = True
            ghost.pretender_strength = 20
            db.session.commit()

        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False):
                tp.process_dynasty_turn(dynasty_id, years_to_advance=5)

        after = _get_person(app, db, pid)
        assert after.pretender_strength == 20
