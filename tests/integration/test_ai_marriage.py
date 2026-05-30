# tests/integration/test_ai_marriage.py
# Story 7-2 (AI marriage-offer acceptance gate + wedding chronicle) — CONTRACT-FIRST
# integration tests written by Agent C in an isolated worktree.
#
# Builds on Story 7-1 (cross-dynasty marriage matching in
# models.turn_processor.process_marriage_check + _find_cross_dynasty_spouse).
# These tests pin the Story 7-2 contract:
#
#   - AIController.decide_marriage_response(context) -> bool
#         Constructed as AIController(session, dynasty_id, personality).
#         Rejects (returns False) when context['relation_score'] is hostile
#         (< -20); accepts (returns True) when the score is neutral or high.
#
#   - process_marriage_check cross-dynasty branch is GATED by the AI partner's
#     decision: when the candidate partner belongs to an AI-controlled dynasty,
#     the match only goes through if that dynasty's AIController accepts.
#         * Accepted  -> both people linked spouse<->spouse, the DiplomaticRelation
#           between the two dynasties gains +30, and a 'marriage' HistoryLogEntryDB
#           is written.
#         * Rejected  -> the seeker is NOT linked to that AI partner (it may fall
#           back to a same-dynasty stranger spouse), and the relation does NOT
#           gain +30.
#         * Non-AI (player) partner -> links without any gate (Story 7-1 preserved).
#
#   - utils.llm_prompts.build_wedding_chronicle_prompt(...) -> str
#         Contains both spouse names and at least one trait.
#   - utils.llm_prompts.generate_wedding_fallback(...) -> str
#         Non-empty and names both houses.
#
# Several of these tests WILL FAIL in this isolated worktree because
# AIController.decide_marriage_response, the AI gate inside
# process_marriage_check, the +30 relation bump, and the wedding-prompt helpers
# do not yet exist (other agents build them). That is EXPECTED and correct for a
# contract-first suite — do not weaken, stub, or skip them.

from unittest.mock import patch

import pytest

from models.db_models import (
    User, DynastyDB, PersonDB, HistoryLogEntryDB, DiplomaticRelation,
)
from models import turn_processor as tp
from models.ai_controller import AIController
from models.diplomacy_system import DiplomacySystem
from utils.theme_manager import get_theme

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# A marriageable-age suitor in year 1230 is born in 1200 (age 30).
SUITOR_BIRTH_YEAR = 1200


# ---------------------------------------------------------------------------
# Helpers (unique 'aim_' username space so we never collide with 7-1 tests)
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


def _add_person(app, db, dynasty_id, name, gender="MALE", birth_year=SUITOR_BIRTH_YEAR,
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


def _set_relation(app, db, dynasty1_id, dynasty2_id, score):
    """Create/overwrite the DiplomaticRelation score between two dynasties.

    Uses the same id-ordering convention as DiplomacySystem.get_diplomatic_relation
    so a later read by the production code finds this exact row.
    """
    with app.app_context():
        ds = DiplomacySystem(db.session)
        relation = ds.get_diplomatic_relation(dynasty1_id, dynasty2_id)
        relation.relation_score = score
        db.session.commit()


def _relation_score(app, db, dynasty1_id, dynasty2_id):
    with app.app_context():
        ds = DiplomacySystem(db.session)
        relation = ds.get_diplomatic_relation(dynasty1_id, dynasty2_id,
                                              create_if_not_exists=False)
        return relation.relation_score if relation else None


def _theme():
    return get_theme(VALID_THEME_KEY) or {}


def _person_count(app, db):
    with app.app_context():
        return PersonDB.query.count()


# ---------------------------------------------------------------------------
# 1. decide_marriage_response: accepts neutral/high, rejects hostile
# ---------------------------------------------------------------------------

class TestDecideMarriageResponse:
    def test_accepts_neutral_and_high_rejects_hostile(self, app, db, session):
        """decide_marriage_response accepts at relation_score 0 and high, rejects at -80 (hostile < -20)."""
        did = _create_user_and_dynasty(app, db, "aim_dmr_ai", "House Judge", is_ai=True)
        with app.app_context():
            controller = AIController(db.session, did, "House Judge is cautious.")
            assert controller.decide_marriage_response({'relation_score': 0}) is True
            assert controller.decide_marriage_response({'relation_score': 60}) is True
            assert controller.decide_marriage_response({'relation_score': -80}) is False

    def test_rejects_just_below_threshold_accepts_at_threshold(self, app, db, session):
        """The hostile cutoff is -20: score < -20 rejects, score == -20 accepts."""
        did = _create_user_and_dynasty(app, db, "aim_dmr_thr", "House Edge", is_ai=True)
        with app.app_context():
            controller = AIController(db.session, did, "House Edge is precise.")
            assert controller.decide_marriage_response({'relation_score': -21}) is False
            assert controller.decide_marriage_response({'relation_score': -20}) is True


# ---------------------------------------------------------------------------
# 2. AI-target accepted -> linked, relation +30, marriage logged
# ---------------------------------------------------------------------------

class TestAITargetAccepted:
    def test_accepted_links_bumps_relation_and_logs(self, app, db, session):
        """Neutral relation + AI partner -> seeker linked to AI partner, relation +30, 'marriage' logged."""
        did_a = _create_user_and_dynasty(app, db, "aim_acc_a", "House Alpha")
        did_b = _create_user_and_dynasty(app, db, "aim_acc_b", "House Beta", is_ai=True)
        groom_id = _add_person(app, db, did_a, "Groom", gender="MALE", surname="Alpha")
        bride_id = _add_person(app, db, did_b, "Bride", gender="FEMALE", surname="Beta")
        _set_relation(app, db, did_a, did_b, 0)  # neutral -> accept

        before_score = _relation_score(app, db, did_a, did_b)
        with app.app_context():
            dynasty = db.session.get(DynastyDB, did_a)
            person = db.session.get(PersonDB, groom_id)
            with patch('models.turn_processor.random.random', return_value=0.0):
                result = tp.process_marriage_check(dynasty, person, 1230, _theme())
            db.session.commit()

        assert result is True
        with app.app_context():
            groom = db.session.get(PersonDB, groom_id)
            bride = db.session.get(PersonDB, bride_id)
            assert groom.spouse_sim_id == bride_id
            assert bride.spouse_sim_id == groom_id
            marriage = HistoryLogEntryDB.query.filter_by(event_type="marriage").first()
            assert marriage is not None
        after_score = _relation_score(app, db, did_a, did_b)
        assert after_score == before_score + 30, "accepted AI marriage bumps the inter-dynasty relation by +30"


# ---------------------------------------------------------------------------
# 3. AI-target rejected (hostile) -> NOT linked to AI partner, no +30
# ---------------------------------------------------------------------------

class TestAITargetRejected:
    def test_rejected_does_not_link_to_ai_partner_or_bump_relation(self, app, db, session):
        """Hostile relation (-80) + AI partner -> seeker NOT linked to that partner and relation gains no +30 (stranger fallback allowed)."""
        did_a = _create_user_and_dynasty(app, db, "aim_rej_a", "House Gamma")
        did_b = _create_user_and_dynasty(app, db, "aim_rej_b", "House Delta", is_ai=True)
        groom_id = _add_person(app, db, did_a, "Suitor", gender="MALE", surname="Gamma")
        snub_id = _add_person(app, db, did_b, "Snubbed", gender="FEMALE", surname="Delta")
        _set_relation(app, db, did_a, did_b, -80)  # hostile -> reject

        before_score = _relation_score(app, db, did_a, did_b)
        with app.app_context():
            dynasty = db.session.get(DynastyDB, did_a)
            person = db.session.get(PersonDB, groom_id)
            with patch('models.turn_processor.random.random', return_value=0.0):
                result = tp.process_marriage_check(dynasty, person, 1230, _theme())
            db.session.commit()

        # The roll succeeded; a stranger-fallback spouse may have been created, but
        # the seeker must NOT have been wed to the hostile AI dynasty's noble.
        with app.app_context():
            groom = db.session.get(PersonDB, groom_id)
            snubbed = db.session.get(PersonDB, snub_id)
            assert groom.spouse_sim_id != snub_id, "rejected AI partner must not be linked to the seeker"
            assert snubbed.spouse_sim_id is None, "the rejected AI noble stays unmarried"
        after_score = _relation_score(app, db, did_a, did_b)
        assert after_score == before_score, "a rejected AI marriage must not bump the relation by +30"


# ---------------------------------------------------------------------------
# 4. Non-AI (player) target links without the gate (Story 7-1 preserved)
# ---------------------------------------------------------------------------

class TestNonAITargetUngated:
    def test_player_target_links_without_gate(self, app, db, session):
        """A player-controlled (non-AI) partner with an eligible noble links unconditionally — 7-1 cross-dynasty behaviour preserved."""
        did_a = _create_user_and_dynasty(app, db, "aim_pl_a", "House Eta")
        did_b = _create_user_and_dynasty(app, db, "aim_pl_b", "House Theta", is_ai=False)
        groom_id = _add_person(app, db, did_a, "Groom", gender="MALE", surname="Eta")
        bride_id = _add_person(app, db, did_b, "Bride", gender="FEMALE", surname="Theta")

        before = _person_count(app, db)
        with app.app_context():
            dynasty = db.session.get(DynastyDB, did_a)
            person = db.session.get(PersonDB, groom_id)
            with patch('models.turn_processor.random.random', return_value=0.0):
                result = tp.process_marriage_check(dynasty, person, 1230, _theme())
            db.session.commit()

        assert result is True
        assert _person_count(app, db) == before, "cross-dynasty match must not create a stranger PersonDB"
        with app.app_context():
            groom = db.session.get(PersonDB, groom_id)
            bride = db.session.get(PersonDB, bride_id)
            assert groom.spouse_sim_id == bride_id
            assert bride.spouse_sim_id == groom_id


# ---------------------------------------------------------------------------
# 5. Wedding chronicle prompt + fallback
# ---------------------------------------------------------------------------

class TestWeddingChronicleText:
    def test_prompt_contains_both_names_and_a_trait(self, app, db, session):
        """build_wedding_chronicle_prompt(name, traits, name, traits, house, house, year) contains both spouse names and at least one trait."""
        from utils.llm_prompts import build_wedding_chronicle_prompt

        # Signature: (spouse1_name, spouse1_traits, spouse2_name, spouse2_traits, house1, house2, year)
        result = build_wedding_chronicle_prompt(
            'Aldric', ['Brave'],
            'Mirelle', ['Pious'],
            'Alpha', 'Beta', 1230,
        )
        assert isinstance(result, str) and result
        assert 'Aldric' in result
        assert 'Mirelle' in result
        assert ('Brave' in result) or ('Pious' in result), "the prompt must mention at least one spouse trait"

    def test_fallback_non_empty_and_names_both_houses(self, app, db, session):
        """generate_wedding_fallback(...) is non-empty and names both houses."""
        from utils.llm_prompts import generate_wedding_fallback

        result = generate_wedding_fallback(
            spouse1_name='Aldric',
            spouse2_name='Mirelle',
            house1='Alpha',
            house2='Beta',
            year=1230,
        )
        assert isinstance(result, str)
        assert len(result) > 20, "fallback must be a non-empty chronicle line"
        assert 'Alpha' in result
        assert 'Beta' in result
