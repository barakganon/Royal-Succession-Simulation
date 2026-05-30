# tests/integration/test_propose_marriage.py
# Story 7-3 (Player-driven foreign marriage proposals) — CONTRACT-FIRST
# integration tests written by Agent D (TESTS) in an isolated worktree.
#
# These tests pin the Story 7-3 contract for MarriageSystem (new
# models/marriage_system.py, constructed as MarriageSystem(session)) and the
# diplomacy blueprint routes:
#
#   * list_foreign_marriageable(dynasty_id, year=None) -> list[dict]
#       Other-dynasty, alive, unmarried, noble PersonDB aged 16..55. year=None
#       derives the year from the requesting dynasty's current_simulation_year.
#       Excludes: own-dynasty, married, dead, age-10 child, age-60 elder.
#       dict keys: id, name, surname, gender, age, dynasty_id, dynasty_name,
#                  traits, is_ai.
#   * eligible_children(dynasty_id, target_gender) -> list[dict]
#       The requester's OWN alive, unmarried nobles aged >= 16 of the gender
#       OPPOSITE target_gender. dict keys: id, name, surname, gender, age.
#   * propose_marriage(proposer_person_id, target_person_id, year) -> dict
#       Neutral AI target (relation 0) -> accepted: both linked, relation +30,
#         a 'marriage' HistoryLogEntryDB exists, offer.status == 'accepted'.
#       Hostile AI target (relation -80) -> rejected: neither linked, relation
#         unchanged, offer.status == 'rejected'.
#       Validation failures (same dynasty / same gender / married target) ->
#         {'ok': False, ...}.
#   * Routes (blueprints/diplomacy.py), @login_required + ownership check:
#       GET  /game/<id>/foreign_characters.json -> {'characters': [...]}
#       POST /game/<id>/propose_marriage        -> {'accepted': bool, ...}
#
# Several of these tests WILL FAIL in this isolated worktree because
# MarriageSystem and the routes do not yet exist (other agents build them).
# That is EXPECTED and correct for a contract-first suite — do not weaken,
# stub, or skip them.
#
# LLM-off determinism: tests run without GOOGLE_API_KEY, so the accepted path
# uses utils.llm_prompts.generate_wedding_fallback for the chronicle line.

import pytest

from models.db_models import (
    User, DynastyDB, PersonDB, HistoryLogEntryDB, MarriageOfferDB,
)
from models.diplomacy_system import DiplomacySystem

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# Marriageable-age people in year 1230 are born in 1200 (age 30).
ADULT_BIRTH_YEAR = 1200
CURRENT_YEAR = 1230


# ---------------------------------------------------------------------------
# Local self-contained helpers
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
            current_simulation_year=CURRENT_YEAR,
            prestige=10,
            is_ai_controlled=is_ai,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


def _add_person(app, db, dynasty_id, name, gender="MALE", birth_year=ADULT_BIRTH_YEAR,
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
    """Create/overwrite the DiplomaticRelation score between two dynasties."""
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


def _login_client(app, username, password="password123"):
    """Return a test client logged in as the given user."""
    c = app.test_client()
    c.post('/login', data={'username': username, 'password': password})
    return c


# ---------------------------------------------------------------------------
# 1. list_foreign_marriageable filters correctly
# ---------------------------------------------------------------------------

class TestListForeignMarriageable:
    def test_only_other_dynasty_alive_unmarried_noble_age_16_55(self, app, db, session):
        """list_foreign_marriageable returns only other-dynasty, alive, unmarried,
        noble people aged 16..55; excludes own/married/dead/child/elder."""
        from models.marriage_system import MarriageSystem

        did_self = _create_user_and_dynasty(app, db, "lfm_self", "House Self")
        did_other = _create_user_and_dynasty(app, db, "lfm_other", "House Other")

        # Eligible foreign noble (age 30).
        eligible_id = _add_person(app, db, did_other, "Eligible", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="Other")
        # Excluded: own dynasty.
        own_id = _add_person(app, db, did_self, "OwnPerson", gender="FEMALE",
                             birth_year=ADULT_BIRTH_YEAR, surname="Self")
        # Excluded: married.
        married_id = _add_person(app, db, did_other, "Married", gender="FEMALE",
                                 birth_year=ADULT_BIRTH_YEAR, spouse_sim_id=99999,
                                 surname="Other")
        # Excluded: dead.
        dead_id = _add_person(app, db, did_other, "Dead", gender="FEMALE",
                              birth_year=ADULT_BIRTH_YEAR, death_year=1229,
                              surname="Other")
        # Excluded: age 10 (born 1220).
        child_id = _add_person(app, db, did_other, "Child", gender="FEMALE",
                               birth_year=1220, surname="Other")
        # Excluded: age 60 (born 1170).
        elder_id = _add_person(app, db, did_other, "Elder", gender="FEMALE",
                               birth_year=1170, surname="Other")

        with app.app_context():
            ms = MarriageSystem(db.session)
            results = ms.list_foreign_marriageable(did_self)
            ids = {r['id'] for r in results}

        assert eligible_id in ids
        assert own_id not in ids, "own-dynasty person excluded"
        assert married_id not in ids, "married person excluded"
        assert dead_id not in ids, "dead person excluded"
        assert child_id not in ids, "age-10 child excluded"
        assert elder_id not in ids, "age-60 elder excluded"

        with app.app_context():
            ms = MarriageSystem(db.session)
            results = ms.list_foreign_marriageable(did_self)
            match = next(r for r in results if r['id'] == eligible_id)
            for key in ('id', 'name', 'surname', 'gender', 'age',
                        'dynasty_id', 'dynasty_name', 'traits', 'is_ai'):
                assert key in match, f"missing dict key {key!r}"
            assert match['age'] == 30
            assert match['dynasty_id'] == did_other
            assert isinstance(match['traits'], list)
            assert isinstance(match['is_ai'], bool)


# ---------------------------------------------------------------------------
# 2. eligible_children returns own opposite-gender nobles age >= 16
# ---------------------------------------------------------------------------

class TestEligibleChildren:
    def test_opposite_gender_of_target(self, app, db, session):
        """target_gender='MALE' -> own FEMALE nobles age>=16;
        target_gender='FEMALE' -> own MALE nobles age>=16."""
        from models.marriage_system import MarriageSystem

        did = _create_user_and_dynasty(app, db, "ec_self", "House EC")
        daughter_id = _add_person(app, db, did, "Daughter", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="EC")
        son_id = _add_person(app, db, did, "Son", gender="MALE",
                             birth_year=ADULT_BIRTH_YEAR, surname="EC")

        with app.app_context():
            ms = MarriageSystem(db.session)
            female_results = ms.eligible_children(did, target_gender='MALE')
            male_results = ms.eligible_children(did, target_gender='FEMALE')
            female_ids = {r['id'] for r in female_results}
            male_ids = {r['id'] for r in male_results}

        assert daughter_id in female_ids
        assert son_id not in female_ids
        assert son_id in male_ids
        assert daughter_id not in male_ids

        with app.app_context():
            ms = MarriageSystem(db.session)
            results = ms.eligible_children(did, target_gender='MALE')
            match = next(r for r in results if r['id'] == daughter_id)
            for key in ('id', 'name', 'surname', 'gender', 'age'):
                assert key in match, f"missing dict key {key!r}"


# ---------------------------------------------------------------------------
# 3. propose_marriage to a neutral AI dynasty -> accepted
# ---------------------------------------------------------------------------

class TestProposeAccepted:
    def test_neutral_ai_accepts_links_bumps_relation_logs(self, app, db, session):
        """Neutral AI target (relation 0) -> accepted, both linked, relation +30,
        'marriage' logged, offer.status == 'accepted'."""
        from models.marriage_system import MarriageSystem

        did_player = _create_user_and_dynasty(app, db, "pa_player", "House Player")
        did_ai = _create_user_and_dynasty(app, db, "pa_ai", "House AI", is_ai=True)
        proposer_id = _add_person(app, db, did_player, "Daughter", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="Player")
        target_id = _add_person(app, db, did_ai, "Lord", gender="MALE",
                                birth_year=ADULT_BIRTH_YEAR, surname="AI")
        _set_relation(app, db, did_player, did_ai, 0)

        before_score = _relation_score(app, db, did_player, did_ai)
        with app.app_context():
            ms = MarriageSystem(db.session)
            result = ms.propose_marriage(proposer_id, target_id, CURRENT_YEAR)
            db.session.commit()

        assert result['ok'] is True
        assert result['accepted'] is True
        with app.app_context():
            proposer = db.session.get(PersonDB, proposer_id)
            target = db.session.get(PersonDB, target_id)
            assert proposer.spouse_sim_id == target_id
            assert target.spouse_sim_id == proposer_id
            marriage = HistoryLogEntryDB.query.filter_by(event_type="marriage").first()
            assert marriage is not None
            offer = db.session.get(MarriageOfferDB, result['offer_id'])
            assert offer is not None
            assert offer.status == 'accepted'
        after_score = _relation_score(app, db, did_player, did_ai)
        assert after_score == before_score + 30, "accepted proposal bumps the relation by exactly +30"


# ---------------------------------------------------------------------------
# 4. propose_marriage to a hostile AI dynasty -> rejected
# ---------------------------------------------------------------------------

class TestProposeRejected:
    def test_hostile_ai_rejects_no_link_no_bump(self, app, db, session):
        """Hostile AI target (relation -80) -> rejected, neither linked,
        offer.status == 'rejected', relation NOT +30."""
        from models.marriage_system import MarriageSystem

        did_player = _create_user_and_dynasty(app, db, "pr_player", "House PlayerR")
        did_ai = _create_user_and_dynasty(app, db, "pr_ai", "House AIR", is_ai=True)
        proposer_id = _add_person(app, db, did_player, "Daughter", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="PlayerR")
        target_id = _add_person(app, db, did_ai, "Lord", gender="MALE",
                                birth_year=ADULT_BIRTH_YEAR, surname="AIR")
        _set_relation(app, db, did_player, did_ai, -80)

        before_score = _relation_score(app, db, did_player, did_ai)
        with app.app_context():
            ms = MarriageSystem(db.session)
            result = ms.propose_marriage(proposer_id, target_id, CURRENT_YEAR)
            db.session.commit()

        assert result['ok'] is True
        assert result['accepted'] is False
        with app.app_context():
            proposer = db.session.get(PersonDB, proposer_id)
            target = db.session.get(PersonDB, target_id)
            assert proposer.spouse_sim_id is None, "rejected proposal must not link the proposer"
            assert target.spouse_sim_id is None, "rejected proposal must not link the target"
            offer = db.session.get(MarriageOfferDB, result['offer_id'])
            assert offer is not None
            assert offer.status == 'rejected'
        after_score = _relation_score(app, db, did_player, did_ai)
        assert after_score == before_score, "a rejected proposal must not bump the relation"


# ---------------------------------------------------------------------------
# 5. propose_marriage validation failures
# ---------------------------------------------------------------------------

class TestProposeValidation:
    def test_same_dynasty_proposer_and_target_invalid(self, app, db, session):
        """Proposer and target in the same dynasty -> ok is False."""
        from models.marriage_system import MarriageSystem

        did = _create_user_and_dynasty(app, db, "pv_same", "House Same")
        proposer_id = _add_person(app, db, did, "Daughter", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="Same")
        target_id = _add_person(app, db, did, "Son", gender="MALE",
                                birth_year=ADULT_BIRTH_YEAR, surname="Same")

        with app.app_context():
            ms = MarriageSystem(db.session)
            result = ms.propose_marriage(proposer_id, target_id, CURRENT_YEAR)
        assert result['ok'] is False
        assert result['accepted'] is False

    def test_same_gender_invalid(self, app, db, session):
        """Same-gender proposer/target -> ok is False."""
        from models.marriage_system import MarriageSystem

        did_a = _create_user_and_dynasty(app, db, "pv_gen_a", "House GenA")
        did_b = _create_user_and_dynasty(app, db, "pv_gen_b", "House GenB")
        proposer_id = _add_person(app, db, did_a, "Daughter", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="GenA")
        target_id = _add_person(app, db, did_b, "Lady", gender="FEMALE",
                                birth_year=ADULT_BIRTH_YEAR, surname="GenB")

        with app.app_context():
            ms = MarriageSystem(db.session)
            result = ms.propose_marriage(proposer_id, target_id, CURRENT_YEAR)
        assert result['ok'] is False
        assert result['accepted'] is False

    def test_already_married_target_invalid(self, app, db, session):
        """Already-married target -> ok is False."""
        from models.marriage_system import MarriageSystem

        did_a = _create_user_and_dynasty(app, db, "pv_mar_a", "House MarA")
        did_b = _create_user_and_dynasty(app, db, "pv_mar_b", "House MarB")
        proposer_id = _add_person(app, db, did_a, "Daughter", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="MarA")
        target_id = _add_person(app, db, did_b, "Lord", gender="MALE",
                                birth_year=ADULT_BIRTH_YEAR, spouse_sim_id=99999,
                                surname="MarB")

        with app.app_context():
            ms = MarriageSystem(db.session)
            result = ms.propose_marriage(proposer_id, target_id, CURRENT_YEAR)
        assert result['ok'] is False
        assert result['accepted'] is False


# ---------------------------------------------------------------------------
# 6. Route smoke tests (logged-in owner of the dynasty)
# ---------------------------------------------------------------------------

class TestRouteSmoke:
    def test_foreign_characters_json_returns_characters(self, app, db, session):
        """GET /game/<id>/foreign_characters.json -> 200 with a 'characters' list."""
        did_self = _create_user_and_dynasty(app, db, "rs_self", "House RSSelf")
        did_other = _create_user_and_dynasty(app, db, "rs_other", "House RSOther")
        _add_person(app, db, did_other, "Foreigner", gender="FEMALE",
                    birth_year=ADULT_BIRTH_YEAR, surname="RSOther")

        client = _login_client(app, "rs_self")
        response = client.get(f'/game/{did_self}/foreign_characters.json')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert 'characters' in data
        assert isinstance(data['characters'], list)

    def test_propose_marriage_route_returns_accepted(self, app, db, session):
        """POST /game/<id>/propose_marriage -> 200 with an 'accepted' key."""
        did_self = _create_user_and_dynasty(app, db, "rs_prop_self", "House RSProp")
        did_ai = _create_user_and_dynasty(app, db, "rs_prop_ai", "House RSPropAI",
                                          is_ai=True)
        proposer_id = _add_person(app, db, did_self, "Daughter", gender="FEMALE",
                                  birth_year=ADULT_BIRTH_YEAR, surname="RSProp")
        target_id = _add_person(app, db, did_ai, "Lord", gender="MALE",
                                birth_year=ADULT_BIRTH_YEAR, surname="RSPropAI")
        _set_relation(app, db, did_self, did_ai, 0)

        client = _login_client(app, "rs_prop_self")
        response = client.post(
            f'/game/{did_self}/propose_marriage',
            data={'proposer_person_id': proposer_id, 'target_person_id': target_id},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert 'accepted' in data
