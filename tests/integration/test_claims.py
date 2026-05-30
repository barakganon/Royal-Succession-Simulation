# tests/integration/test_claims.py
# Story 7-3 (Cross-dynasty birth claims) — CONTRACT-FIRST integration tests
# written by Agent D (TESTS) in an isolated worktree.
#
# These tests drive models.turn_processor.process_childbirth_check directly and
# pin the Story 7-3 contract for ClaimDB registration:
#
#   * Claim direction: a child takes the MOTHER's dynasty; the claim is on the
#     FATHER's dynasty.
#         target_dynasty_id = spouse.dynasty_id (father)
#         source_dynasty_id = woman.dynasty_id (mother)
#         claimant_sim_id    = child.id
#     A ClaimDB is registered ONLY when the child survives birth
#     (child.death_year is None) AND spouse.dynasty_id != woman.dynasty_id.
#         - claim_type == 'cross_dynasty_birth', is_active is True.
#   * Same-dynasty birth (mother and father share a dynasty) -> NO ClaimDB.
#   * Infant dies at birth (15% mortality fires) -> NO ClaimDB.
#
# Several of these tests WILL FAIL in this isolated worktree because the ClaimDB
# model and its registration inside process_childbirth_check do not yet exist
# (other agents build them). That is EXPECTED and correct for a contract-first
# suite — do not weaken, stub, or skip them.
#
# Determinism: the autouse RNG seed fixture in tests/conftest.py runs before
# every test. To control the two random.random()-gated branches in
# process_childbirth_check (the 0.4 pregnancy gate and the 0.15 infant-mortality
# gate) we patch models.turn_processor.random.random:
#   * a constant < 0.15  -> pregnancy fires AND infant DIES   (mortality < 0.15)
#   * a constant in [0.15, 0.4) -> pregnancy fires AND infant SURVIVES
# The contract phrases these as "0.0 (death)" and "0.99 (survival)"; because the
# same constant also feeds the 0.4 pregnancy gate, a flat 0.99 would block the
# birth outright, so the survival case uses a constant that passes pregnancy yet
# clears the survival threshold. (random.choice for gender/name is NOT patched —
# it draws from the seeded RNG, keeping the child creation deterministic.)

from unittest.mock import patch

import pytest

from models.db_models import User, DynastyDB, PersonDB
from models import turn_processor as tp
from utils.theme_manager import get_theme

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# A childbearing-age woman in year 1230 is born in 1200 (age 30).
MOTHER_BIRTH_YEAR = 1200

# Constant fed to random.random(): clears the 0.4 pregnancy gate (so a child is
# born) and clears the 0.15 mortality gate (so the infant SURVIVES).
SURVIVE_RANDOM = 0.16
# Constant fed to random.random(): clears pregnancy (0.0 < 0.4) and fires the
# 0.15 mortality gate (0.0 < 0.15) so the infant DIES at birth.
DIE_RANDOM = 0.0


# ---------------------------------------------------------------------------
# Local self-contained helpers (mirror test_cross_dynasty_marriage.py)
# ---------------------------------------------------------------------------

def _create_user_and_dynasty(app, db, username, dynasty_name,
                             password="password123", is_ai=False):
    """Create a User + DynastyDB directly; return dynasty_id."""
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
        return dynasty.id


def _add_person(app, db, dynasty_id, name, gender="MALE", birth_year=MOTHER_BIRTH_YEAR,
                death_year=None, is_noble=True, spouse_sim_id=None, surname="House"):
    """Add a PersonDB; return its id."""
    with app.app_context():
        person = PersonDB(
            dynasty_id=dynasty_id,
            name=name,
            surname=surname,
            gender=gender,
            birth_year=birth_year,
            death_year=death_year,
            is_noble=is_noble,
            spouse_sim_id=spouse_sim_id,
        )
        db.session.add(person)
        db.session.commit()
        return person.id


def _link_spouses(app, db, person_a_id, person_b_id):
    """Mutually link two people as spouses."""
    with app.app_context():
        a = db.session.get(PersonDB, person_a_id)
        b = db.session.get(PersonDB, person_b_id)
        a.spouse_sim_id = person_b_id
        b.spouse_sim_id = person_a_id
        db.session.commit()


def _theme():
    return get_theme(VALID_THEME_KEY) or {}


# ---------------------------------------------------------------------------
# 1. Cross-dynasty birth registers exactly one ClaimDB with correct direction
# ---------------------------------------------------------------------------

class TestCrossDynastyBirthClaim:
    def test_cross_dynasty_surviving_birth_registers_one_claim(self, app, db, session):
        """Wife in dynasty M married to husband in dynasty F -> exactly one
        active ClaimDB: target=F (father), source=M (mother), claimant=child."""
        from models.db_models import ClaimDB

        did_m = _create_user_and_dynasty(app, db, "claim_mother", "House Mother")
        did_f = _create_user_and_dynasty(app, db, "claim_father", "House Father")
        wife_id = _add_person(app, db, did_m, "Wife", gender="FEMALE",
                              birth_year=MOTHER_BIRTH_YEAR, surname="Mother")
        husband_id = _add_person(app, db, did_f, "Husband", gender="MALE",
                                 birth_year=MOTHER_BIRTH_YEAR, surname="Father")
        _link_spouses(app, db, wife_id, husband_id)

        with app.app_context():
            dynasty_m = db.session.get(DynastyDB, did_m)
            wife = db.session.get(PersonDB, wife_id)
            with patch('models.turn_processor.random.random', return_value=SURVIVE_RANDOM):
                result = tp.process_childbirth_check(dynasty_m, wife, 1230, _theme())
            db.session.commit()

        assert result is True
        with app.app_context():
            claims = ClaimDB.query.all()
            assert len(claims) == 1, "exactly one cross-dynasty birth claim should be registered"
            claim = claims[0]
            # The surviving newborn is the claimant.
            child = PersonDB.query.filter_by(mother_sim_id=wife_id).first()
            assert child is not None
            assert child.death_year is None, "the infant must survive for a claim to be registered"
            assert claim.claimant_sim_id == child.id
            assert claim.target_dynasty_id == did_f, "claim targets the FATHER's dynasty"
            assert claim.source_dynasty_id == did_m, "claim originates from the MOTHER's dynasty"
            assert claim.claim_type == 'cross_dynasty_birth'
            assert claim.is_active is True


# ---------------------------------------------------------------------------
# 2. Same-dynasty birth -> NO ClaimDB
# ---------------------------------------------------------------------------

class TestSameDynastyBirthNoClaim:
    def test_same_dynasty_surviving_birth_registers_no_claim(self, app, db, session):
        """Mother and father in the SAME dynasty -> no ClaimDB row."""
        from models.db_models import ClaimDB

        did = _create_user_and_dynasty(app, db, "claim_same", "House Same")
        wife_id = _add_person(app, db, did, "Wife", gender="FEMALE",
                              birth_year=MOTHER_BIRTH_YEAR, surname="Same")
        husband_id = _add_person(app, db, did, "Husband", gender="MALE",
                                 birth_year=MOTHER_BIRTH_YEAR, surname="Same")
        _link_spouses(app, db, wife_id, husband_id)

        with app.app_context():
            dynasty = db.session.get(DynastyDB, did)
            wife = db.session.get(PersonDB, wife_id)
            with patch('models.turn_processor.random.random', return_value=SURVIVE_RANDOM):
                result = tp.process_childbirth_check(dynasty, wife, 1230, _theme())
            db.session.commit()

        assert result is True
        with app.app_context():
            child = PersonDB.query.filter_by(mother_sim_id=wife_id).first()
            assert child is not None
            assert child.death_year is None
            assert ClaimDB.query.count() == 0, "a same-dynasty birth must NOT create a claim"


# ---------------------------------------------------------------------------
# 3. Infant dies at birth -> NO ClaimDB
# ---------------------------------------------------------------------------

class TestDeadInfantNoClaim:
    def test_cross_dynasty_dead_infant_registers_no_claim(self, app, db, session):
        """Cross-dynasty birth where the infant dies (mortality fires) -> no ClaimDB."""
        from models.db_models import ClaimDB

        did_m = _create_user_and_dynasty(app, db, "claim_dead_m", "House DeadM")
        did_f = _create_user_and_dynasty(app, db, "claim_dead_f", "House DeadF")
        wife_id = _add_person(app, db, did_m, "Wife", gender="FEMALE",
                              birth_year=MOTHER_BIRTH_YEAR, surname="DeadM")
        husband_id = _add_person(app, db, did_f, "Husband", gender="MALE",
                                 birth_year=MOTHER_BIRTH_YEAR, surname="DeadF")
        _link_spouses(app, db, wife_id, husband_id)

        with app.app_context():
            dynasty_m = db.session.get(DynastyDB, did_m)
            wife = db.session.get(PersonDB, wife_id)
            with patch('models.turn_processor.random.random', return_value=DIE_RANDOM):
                result = tp.process_childbirth_check(dynasty_m, wife, 1230, _theme())
            db.session.commit()

        assert result is True
        with app.app_context():
            child = PersonDB.query.filter_by(mother_sim_id=wife_id).first()
            assert child is not None
            assert child.death_year is not None, "infant mortality must fire for this case"
            assert ClaimDB.query.count() == 0, "a dead infant must NOT create a claim"
