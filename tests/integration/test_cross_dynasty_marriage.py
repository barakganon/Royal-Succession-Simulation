# tests/integration/test_cross_dynasty_marriage.py
# Story 7-1 (Cross-dynasty marriage matching + MarriageOffer model) — CONTRACT-FIRST
# integration tests written by Agent C in an isolated worktree.
#
# These tests pin the contract for cross-dynasty marriage matching:
#   - process_marriage_check(dynasty, person, current_year, theme_config): on a
#     successful marriage roll it FIRST tries _find_cross_dynasty_spouse
#     (opposite gender, alive, noble, unmarried, DIFFERENT dynasty, marriageable
#     age 16..45 for FEMALE / 16..55 for MALE). If found, it links both people's
#     spouse_sim_id to each other, both keep their own dynasty, writes a marriage
#     HistoryLogEntryDB, and creates NO new stranger PersonDB. Otherwise it falls
#     back to creating a new stranger spouse PersonDB in the same dynasty.
#   - _find_cross_dynasty_spouse(session, person, current_year, min_age, max_age) returns an eligible
#     opposite-gender, alive, noble, unmarried person in a DIFFERENT dynasty of
#     marriageable age, else None.
#   - MarriageOfferDB(__tablename__='marriage_offer'): id, proposer_dynasty_id,
#     target_dynasty_id, proposer_person_id, target_person_id,
#     status (default 'pending'), created_year, created_at.
#
# Several of these tests WILL FAIL in this isolated worktree because the
# cross-dynasty matching branch (_find_cross_dynasty_spouse) and the
# MarriageOfferDB model do not yet exist (the backend agent builds them). That
# is EXPECTED and correct for a contract-first suite — do not weaken, stub, or
# skip them.

from unittest.mock import patch

import pytest

from models.db_models import User, DynastyDB, PersonDB, HistoryLogEntryDB
from models import turn_processor as tp
from utils.theme_manager import get_theme

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_succession / test_pretender)
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


def _add_person(app, db, dynasty_id, name, gender="MALE", birth_year=1200,
                death_year=None, is_noble=True, spouse_sim_id=None,
                surname="House"):
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


def _theme():
    return get_theme(VALID_THEME_KEY) or {}


def _person_count(app, db):
    with app.app_context():
        return PersonDB.query.count()


# A marriageable-age suitor in year 1230 is born in 1200 (age 30).
SUITOR_BIRTH_YEAR = 1200


# ---------------------------------------------------------------------------
# 1. Cross-dynasty match links two existing people, no stranger created
# ---------------------------------------------------------------------------

class TestCrossDynastyMatch:
    def test_match_links_existing_people_no_stranger(self, app, db, session):
        """Two dynasties with eligible opposite-gender nobles -> they are linked, both keep dynasty, no stranger created, marriage logged."""
        did_a = _create_user_and_dynasty(app, db, "cdm_user1", "House Alpha")
        did_b = _create_user_and_dynasty(app, db, "cdm_user2", "House Beta")
        groom_id = _add_person(app, db, did_a, "Groom", gender="MALE",
                               birth_year=SUITOR_BIRTH_YEAR, surname="Alpha")
        bride_id = _add_person(app, db, did_b, "Bride", gender="FEMALE",
                               birth_year=SUITOR_BIRTH_YEAR, surname="Beta")

        before = _person_count(app, db)
        with app.app_context():
            dynasty = db.session.get(DynastyDB, did_a)
            person = db.session.get(PersonDB, groom_id)
            with patch('models.turn_processor.random.random', return_value=0.0):
                result = tp.process_marriage_check(dynasty, person, 1230, _theme())
            db.session.commit()

        assert result is True
        assert _person_count(app, db) == before, "no stranger PersonDB should be created on a cross-dynasty match"
        with app.app_context():
            groom = db.session.get(PersonDB, groom_id)
            bride = db.session.get(PersonDB, bride_id)
            assert groom.spouse_sim_id == bride_id
            assert bride.spouse_sim_id == groom_id
            assert groom.dynasty_id == did_a
            assert bride.dynasty_id == did_b
            marriage = HistoryLogEntryDB.query.filter_by(event_type="marriage").first()
            assert marriage is not None


# ---------------------------------------------------------------------------
# 2. No cross-dynasty candidate -> stranger fallback
# ---------------------------------------------------------------------------

class TestStrangerFallback:
    def test_no_candidate_creates_stranger_in_same_dynasty(self, app, db, session):
        """Single dynasty, no cross-dynasty candidate -> a NEW spouse PersonDB is created in the same dynasty and linked."""
        did = _create_user_and_dynasty(app, db, "cdm_solo", "House Solo")
        person_id = _add_person(app, db, did, "Lonely", gender="MALE",
                                birth_year=SUITOR_BIRTH_YEAR, surname="Solo")

        before = _person_count(app, db)
        with app.app_context():
            dynasty = db.session.get(DynastyDB, did)
            person = db.session.get(PersonDB, person_id)
            with patch('models.turn_processor.random.random', return_value=0.0):
                result = tp.process_marriage_check(dynasty, person, 1230, _theme())
            db.session.commit()

        assert result is True
        assert _person_count(app, db) == before + 1, "stranger fallback must create exactly one new PersonDB"
        with app.app_context():
            person = db.session.get(PersonDB, person_id)
            assert person.spouse_sim_id is not None
            spouse = db.session.get(PersonDB, person.spouse_sim_id)
            assert spouse is not None
            assert spouse.dynasty_id == did, "stranger spouse lives in the same dynasty"
            assert spouse.spouse_sim_id == person_id


# ---------------------------------------------------------------------------
# 3. _find_cross_dynasty_spouse eligibility rules
# ---------------------------------------------------------------------------

class TestFindCrossDynastySpouse:
    def test_returns_none_for_ineligible_only(self, app, db, session):
        """_find_cross_dynasty_spouse returns None when every candidate is same-dynasty / married / dead / wrong-gender / out-of-age."""
        did_a = _create_user_and_dynasty(app, db, "cdm_inelig_a", "House InelA")
        did_b = _create_user_and_dynasty(app, db, "cdm_inelig_b", "House InelB")
        seeker_id = _add_person(app, db, did_a, "Seeker", gender="MALE",
                                birth_year=SUITOR_BIRTH_YEAR, surname="InelA")
        # Same-dynasty opposite-gender noble (excluded: same dynasty).
        _add_person(app, db, did_a, "SameHouseFem", gender="FEMALE",
                    birth_year=SUITOR_BIRTH_YEAR, surname="InelA")
        # Cross-dynasty but already married (excluded).
        _add_person(app, db, did_b, "MarriedFem", gender="FEMALE",
                    birth_year=SUITOR_BIRTH_YEAR, spouse_sim_id=99999, surname="InelB")
        # Cross-dynasty but dead (excluded).
        _add_person(app, db, did_b, "DeadFem", gender="FEMALE",
                    birth_year=SUITOR_BIRTH_YEAR, death_year=1229, surname="InelB")
        # Cross-dynasty but wrong gender (excluded: same gender as seeker).
        _add_person(app, db, did_b, "WrongGender", gender="MALE",
                    birth_year=SUITOR_BIRTH_YEAR, surname="InelB")
        # Cross-dynasty opposite gender but too young (born 1220 -> age 10).
        _add_person(app, db, did_b, "TooYoung", gender="FEMALE",
                    birth_year=1220, surname="InelB")

        with app.app_context():
            seeker = db.session.get(PersonDB, seeker_id)
            match = tp._find_cross_dynasty_spouse(db.session, seeker, 1230, 16, 55)
            assert match is None

    def test_returns_eligible_cross_dynasty_person(self, app, db, session):
        """_find_cross_dynasty_spouse returns the eligible opposite-gender, alive, noble, unmarried cross-dynasty person of marriageable age."""
        did_a = _create_user_and_dynasty(app, db, "cdm_elig_a", "House ElA")
        did_b = _create_user_and_dynasty(app, db, "cdm_elig_b", "House ElB")
        seeker_id = _add_person(app, db, did_a, "Seeker", gender="MALE",
                                birth_year=SUITOR_BIRTH_YEAR, surname="ElA")
        eligible_id = _add_person(app, db, did_b, "EligibleFem", gender="FEMALE",
                                  birth_year=SUITOR_BIRTH_YEAR, surname="ElB")

        with app.app_context():
            seeker = db.session.get(PersonDB, seeker_id)
            match = tp._find_cross_dynasty_spouse(db.session, seeker, 1230, 16, 55)
            assert match is not None
            assert match.id == eligible_id
            assert match.dynasty_id == did_b


# ---------------------------------------------------------------------------
# 4. MarriageOfferDB model
# ---------------------------------------------------------------------------

class TestMarriageOfferModel:
    def test_marriage_offer_row_defaults_and_query(self, app, db, session):
        """A MarriageOfferDB row persists with its fields and status defaults to 'pending'."""
        from models.db_models import MarriageOfferDB

        did_a = _create_user_and_dynasty(app, db, "cdm_offer_a", "House OffA")
        did_b = _create_user_and_dynasty(app, db, "cdm_offer_b", "House OffB")
        proposer_id = _add_person(app, db, did_a, "Proposer", gender="MALE",
                                  birth_year=SUITOR_BIRTH_YEAR, surname="OffA")
        target_id = _add_person(app, db, did_b, "Target", gender="FEMALE",
                                birth_year=SUITOR_BIRTH_YEAR, surname="OffB")

        with app.app_context():
            offer = MarriageOfferDB(
                proposer_dynasty_id=did_a,
                target_dynasty_id=did_b,
                proposer_person_id=proposer_id,
                target_person_id=target_id,
                created_year=1230,
            )
            db.session.add(offer)
            db.session.commit()
            offer_id = offer.id

        with app.app_context():
            fetched = db.session.get(MarriageOfferDB, offer_id)
            assert fetched is not None
            assert fetched.proposer_dynasty_id == did_a
            assert fetched.target_dynasty_id == did_b
            assert fetched.proposer_person_id == proposer_id
            assert fetched.target_person_id == target_id
            assert fetched.created_year == 1230
            assert fetched.status == 'pending'
            assert fetched.created_at is not None


# ---------------------------------------------------------------------------
# 5. Marriage roll not triggered
# ---------------------------------------------------------------------------

class TestMarriageRollNotTriggered:
    def test_failed_roll_leaves_person_unmarried(self, app, db, session):
        """A high marriage roll -> person stays unmarried, no stranger, no cross-dynasty link."""
        did_a = _create_user_and_dynasty(app, db, "cdm_norun_a", "House NoRunA")
        did_b = _create_user_and_dynasty(app, db, "cdm_norun_b", "House NoRunB")
        person_id = _add_person(app, db, did_a, "Bachelor", gender="MALE",
                                birth_year=SUITOR_BIRTH_YEAR, surname="NoRunA")
        # An otherwise-eligible cross-dynasty candidate that must NOT be touched.
        candidate_id = _add_person(app, db, did_b, "Candidate", gender="FEMALE",
                                   birth_year=SUITOR_BIRTH_YEAR, surname="NoRunB")

        before = _person_count(app, db)
        with app.app_context():
            dynasty = db.session.get(DynastyDB, did_a)
            person = db.session.get(PersonDB, person_id)
            with patch('models.turn_processor.random.random', return_value=0.99):
                result = tp.process_marriage_check(dynasty, person, 1230, _theme())
            db.session.commit()

        assert result is False
        assert _person_count(app, db) == before, "no stranger created when the roll fails"
        with app.app_context():
            person = db.session.get(PersonDB, person_id)
            candidate = db.session.get(PersonDB, candidate_id)
            assert person.spouse_sim_id is None
            assert candidate.spouse_sim_id is None
