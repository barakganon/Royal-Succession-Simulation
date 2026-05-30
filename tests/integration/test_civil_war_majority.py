# tests/integration/test_civil_war_majority.py
# Story 5-4 (Civil war + heir-majority interrupts) — CONTRACT-FIRST integration
# tests written by Agent C in an isolated worktree.
#
# These tests pin the contract for two new turn interrupts plus the civil-war
# resolution route. The pieces under test (turn_processor civil_war detection,
# the new CIVIL_WAR_THRESHOLD / HEIR_MAJORITY_AGE constants, the
# PersonDB.has_seen_majority column, and the /dynasty/<id>/civil_war_resolve
# route + world-map modal/notice DOM) are built by OTHER agents. In this
# isolated worktree several of these tests WILL FAIL — that is EXPECTED and
# correct for a contract-first suite. Do NOT weaken, stub, or skip them.
#
# Contract under test
#   - turn_processor: 'civil_war' in INTERRUPT_REASONS; CIVIL_WAR_THRESHOLD == 50;
#     HEIR_MAJORITY_AGE == 16. PersonDB.has_seen_majority (default False).
#   - Detection (drive process_dynasty_turn directly; it returns
#     (success, message, turn_summary), assert turn_summary['interrupt_reason']):
#       * human dynasty + living is_pretender with pretender_strength >= 50
#         -> interrupt_reason == 'civil_war'; the pretender is NOT cleared.
#       * AI dynasty (is_ai_controlled=True) same condition -> auto-resolved:
#         no 'civil_war' interrupt, pretender cleared (is_pretender False), and a
#         civil_war HistoryLogEntryDB written.
#       * human noble reaching age >= HEIR_MAJORITY_AGE with has_seen_majority
#         False -> interrupt_reason == 'heir_majority' and has_seen_majority set
#         True; running again does not re-fire.
#   - POST /dynasty/<id>/civil_war_resolve {choice}:
#       * fight: prestige >= strength -> pretender exiled/cleared (loyalists win);
#                prestige <  strength -> pretender becomes monarch.
#       * negotiate: gold deducted, pretender cleared.
#       * abdicate: pretender becomes monarch.
#       * invalid choice -> 400; no pending civil war -> 400.
#   - /world/map HTML contains 'civil-war-modal' and 'heir-majority-notice'.

from unittest.mock import patch

import pytest

from models.db_models import DynastyDB, HistoryLogEntryDB, PersonDB, User

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_pretender.py / test_succession.py)
# ---------------------------------------------------------------------------

def _create_user_and_dynasty(app, db, username, dynasty_name,
                             password="password123", is_ai=False,
                             prestige=10, wealth=500):
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
            current_simulation_year=1230,
            prestige=prestige,
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
            surname="Civilwarsson",
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


def _make_pretender(app, db, person_id, strength=50):
    """Flag an existing person as a living pretender with the given strength."""
    with app.app_context():
        person = db.session.get(PersonDB, person_id)
        person.is_pretender = True
        person.pretender_strength = strength
        db.session.commit()


def _get_person(app, db, person_id):
    with app.app_context():
        return db.session.get(PersonDB, person_id)


def _get_dynasty(app, db, dynasty_id):
    with app.app_context():
        return db.session.get(DynastyDB, dynasty_id)


def _civil_war_entries(app, db, dynasty_id):
    with app.app_context():
        return HistoryLogEntryDB.query.filter_by(
            dynasty_id=dynasty_id, event_type='civil_war'
        ).all()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cw_client(app, db, session):
    """Authenticated owner of a HUMAN dynasty with a living monarch + a living
    pretender at the civil-war threshold. Yields (client, dynasty_id,
    monarch_id, pretender_id)."""
    _, dynasty_id = _create_user_and_dynasty(
        app, db, "cw_user", "House CivilWar", prestige=60, wealth=500
    )
    monarch_id = _add_person(app, db, dynasty_id, name="SittingKing", gender="MALE",
                             birth_year=1190, is_monarch=True, reign_start_year=1215)
    pretender_id = _add_person(app, db, dynasty_id, name="ClaimantCarl", gender="MALE",
                               birth_year=1205)
    _make_pretender(app, db, pretender_id, strength=50)
    with app.test_client() as c:
        c.post('/login', data={'username': 'cw_user', 'password': 'password123'})
        yield c, dynasty_id, monarch_id, pretender_id


# ===========================================================================
# 1. Schema default: has_seen_majority
# ===========================================================================

class TestHasSeenMajorityDefault:
    def test_fresh_person_has_seen_majority_defaults_false(self, app, db, session):
        """A freshly created PersonDB has has_seen_majority == False."""
        _, dynasty_id = _create_user_and_dynasty(app, db, "cw_default", "House Default")
        pid = _add_person(app, db, dynasty_id, name="Freshborn", birth_year=1225)
        person = _get_person(app, db, pid)
        assert person.has_seen_majority is False


# ===========================================================================
# 2. Constants + INTERRUPT_REASONS membership
# ===========================================================================

class TestCivilWarConstants:
    def test_civil_war_constants_and_interrupt_reason(self):
        """turn_processor exposes CIVIL_WAR_THRESHOLD==50, HEIR_MAJORITY_AGE==16, and 'civil_war' is a valid interrupt reason."""
        from models import turn_processor as tp

        assert tp.CIVIL_WAR_THRESHOLD == 50
        assert tp.HEIR_MAJORITY_AGE == 16
        assert 'civil_war' in tp.INTERRUPT_REASONS


# ===========================================================================
# 3. Detection — human dynasty halts on civil war (pretender NOT cleared)
# ===========================================================================

class TestCivilWarDetectionHuman:
    def test_human_living_strong_pretender_triggers_civil_war_interrupt(self, app, db, session):
        """Human dynasty + a living pretender at/above threshold -> interrupt_reason 'civil_war'; pretender NOT cleared."""
        from models import turn_processor as tp

        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_human", "House Halt", is_ai=False
        )
        _add_person(app, db, dynasty_id, name="LiveKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)
        pid = _add_person(app, db, dynasty_id, name="StrongClaimant", gender="MALE",
                          birth_year=1205)
        _make_pretender(app, db, pid, strength=50)

        # Keep everyone alive so the only interrupt that can fire is civil_war.
        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False):
                success, _msg, turn_summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert turn_summary is not None
        assert turn_summary['interrupt_reason'] == 'civil_war'

        # The pretender survives the (un-resolved) interrupt — it is the human
        # player who decides via the resolve route.
        after = _get_person(app, db, pid)
        assert after.is_pretender is True


# ===========================================================================
# 4. Detection — AI dynasty auto-resolves (no interrupt, pretender cleared)
# ===========================================================================

class TestCivilWarDetectionAI:
    def test_ai_dynasty_auto_resolves_civil_war(self, app, db, session):
        """AI dynasty + a living strong pretender -> no 'civil_war' interrupt; pretender cleared and a civil_war history entry exists."""
        from models import turn_processor as tp

        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_ai", "House Machina", is_ai=True
        )
        _add_person(app, db, dynasty_id, name="AIKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)
        pid = _add_person(app, db, dynasty_id, name="AIClaimant", gender="MALE",
                          birth_year=1205)
        _make_pretender(app, db, pid, strength=50)

        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False):
                success, _msg, turn_summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert turn_summary is not None
        # AI resolves immediately — the turn does not halt for civil war.
        assert turn_summary['interrupt_reason'] != 'civil_war'

        # The pretender has been crushed/cleared by the AI.
        after = _get_person(app, db, pid)
        assert after.is_pretender is False

        # A civil_war history entry records the auto-resolution.
        entries = _civil_war_entries(app, db, dynasty_id)
        assert len(entries) >= 1


# ===========================================================================
# 5. civil_war_resolve — fight (loyalists win + pretender wins)
# ===========================================================================

class TestCivilWarResolveFight:
    def test_fight_prestige_ge_strength_loyalists_win(self, app, db, session):
        """fight with prestige >= pretender_strength -> ok:true and pretender cleared (loyalists win)."""
        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_fight_win", "House Loyal", prestige=80, wealth=500
        )
        _add_person(app, db, dynasty_id, name="LoyalKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)
        pid = _add_person(app, db, dynasty_id, name="DoomedClaimant", gender="MALE",
                          birth_year=1205)
        _make_pretender(app, db, pid, strength=50)

        with app.test_client() as client:
            client.post('/login', data={'username': 'cw_fight_win', 'password': 'password123'})
            response = client.post(
                f'/dynasty/{dynasty_id}/civil_war_resolve',
                data={'choice': 'fight'},
            )
        body = response.get_json()
        assert body is not None and body.get('ok') is True

        after = _get_person(app, db, pid)
        assert after.is_pretender is False

    def test_fight_prestige_lt_strength_pretender_becomes_monarch(self, app, db, session):
        """fight with prestige < pretender_strength -> the pretender wins and becomes monarch."""
        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_fight_lose", "House Weak", prestige=10, wealth=500
        )
        old_monarch_id = _add_person(app, db, dynasty_id, name="WeakKing", gender="MALE",
                                     birth_year=1190, is_monarch=True, reign_start_year=1215)
        pid = _add_person(app, db, dynasty_id, name="VictorClaimant", gender="MALE",
                          birth_year=1205)
        _make_pretender(app, db, pid, strength=50)

        with app.test_client() as client:
            client.post('/login', data={'username': 'cw_fight_lose', 'password': 'password123'})
            response = client.post(
                f'/dynasty/{dynasty_id}/civil_war_resolve',
                data={'choice': 'fight'},
            )
        body = response.get_json()
        assert body is not None and body.get('ok') is True

        # The pretender usurped the throne.
        winner = _get_person(app, db, pid)
        assert winner.is_monarch is True
        assert winner.is_pretender is False


# ===========================================================================
# 6. civil_war_resolve — negotiate / abdicate / invalid / no-pending
# ===========================================================================

class TestCivilWarResolveOther:
    def test_negotiate_deducts_gold_and_clears_pretender(self, app, db, session):
        """negotiate -> gold decreased and the pretender cleared (is_pretender False)."""
        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_negotiate", "House Bribe", prestige=20, wealth=500
        )
        _add_person(app, db, dynasty_id, name="BribingKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)
        pid = _add_person(app, db, dynasty_id, name="BoughtClaimant", gender="MALE",
                          birth_year=1205)
        _make_pretender(app, db, pid, strength=50)

        gold_before = _get_dynasty(app, db, dynasty_id).current_wealth

        with app.test_client() as client:
            client.post('/login', data={'username': 'cw_negotiate', 'password': 'password123'})
            response = client.post(
                f'/dynasty/{dynasty_id}/civil_war_resolve',
                data={'choice': 'negotiate'},
            )
        body = response.get_json()
        assert body is not None and body.get('ok') is True

        gold_after = _get_dynasty(app, db, dynasty_id).current_wealth
        assert gold_after < gold_before

        after = _get_person(app, db, pid)
        assert after.is_pretender is False

    def test_abdicate_makes_pretender_monarch(self, app, db, session):
        """abdicate -> the pretender becomes monarch (is_monarch True)."""
        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_abdicate", "House Yield", prestige=20, wealth=500
        )
        _add_person(app, db, dynasty_id, name="YieldingKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)
        pid = _add_person(app, db, dynasty_id, name="CrownedClaimant", gender="MALE",
                          birth_year=1205)
        _make_pretender(app, db, pid, strength=50)

        with app.test_client() as client:
            client.post('/login', data={'username': 'cw_abdicate', 'password': 'password123'})
            response = client.post(
                f'/dynasty/{dynasty_id}/civil_war_resolve',
                data={'choice': 'abdicate'},
            )
        body = response.get_json()
        assert body is not None and body.get('ok') is True

        after = _get_person(app, db, pid)
        assert after.is_monarch is True

    def test_invalid_choice_returns_400(self, cw_client, app, db):
        """An unrecognised resolution choice -> HTTP 400."""
        client, dynasty_id, monarch_id, pretender_id = cw_client
        response = client.post(
            f'/dynasty/{dynasty_id}/civil_war_resolve',
            data={'choice': 'banish_to_the_moon'},
        )
        assert response.status_code == 400

    def test_no_pending_civil_war_returns_400(self, app, db, session):
        """civil_war_resolve against a dynasty with NO pending civil war -> HTTP 400."""
        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_none", "House Peaceful", prestige=20, wealth=500
        )
        _add_person(app, db, dynasty_id, name="CalmKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)
        # No pretender flagged -> nothing to resolve.
        with app.test_client() as client:
            client.post('/login', data={'username': 'cw_none', 'password': 'password123'})
            response = client.post(
                f'/dynasty/{dynasty_id}/civil_war_resolve',
                data={'choice': 'fight'},
            )
        assert response.status_code == 400


# ===========================================================================
# 7. Detection — heir majority interrupt fires once
# ===========================================================================

class TestHeirMajorityInterrupt:
    def test_heir_turning_majority_age_triggers_interrupt_once(self, app, db, session):
        """A human noble reaching majority age with has_seen_majority False -> interrupt_reason 'heir_majority'; the flag is set and does not re-fire."""
        from models import turn_processor as tp

        _, dynasty_id = _create_user_and_dynasty(
            app, db, "cw_majority", "House Majority", is_ai=False
        )
        _add_person(app, db, dynasty_id, name="MajKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)
        # Born so the heir is UNDER 16 at the turn's start year (1230) and
        # CROSSES HEIR_MAJORITY_AGE (16) mid-turn: birth_year 1216 -> age 14 at
        # start, turns 16 in 1232 (within the 1230-1234 turn). (Anyone already
        # >=16 at start is backfilled as has_seen_majority and never fires.)
        heir_id = _add_person(app, db, dynasty_id, name="ComingOfAgeHeir",
                              gender="MALE", birth_year=1216)

        # Patch out marriage + childbirth so the only person who can cross the
        # majority boundary is the heir under test. The marriage spawner would
        # otherwise mint stranger spouses (some of them minors) who then come of
        # age in a later turn and fire a *second* heir_majority — order/seed
        # dependent noise unrelated to what this test asserts about the heir.
        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False), \
                 patch('models.turn_processor.process_marriage_check', return_value=False), \
                 patch('models.turn_processor.process_childbirth_check', return_value=False):
                success, _msg, summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert summary is not None
        assert summary['interrupt_reason'] == 'heir_majority'

        # The majority flag is now set so it does not retrigger.
        heir = _get_person(app, db, heir_id)
        assert heir.has_seen_majority is True

        # Run another turn: the same heir must NOT fire heir_majority again.
        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False), \
                 patch('models.turn_processor.process_marriage_check', return_value=False), \
                 patch('models.turn_processor.process_childbirth_check', return_value=False):
                success2, _msg2, summary2 = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )
        assert success2 is True
        assert summary2 is not None
        assert summary2['interrupt_reason'] != 'heir_majority'


# ===========================================================================
# 8. /world/map renders the civil-war modal + heir-majority notice
# ===========================================================================

class TestWorldMapCivilWarMajority:
    def test_world_map_contains_civil_war_modal_and_majority_notice(self, cw_client, app, db):
        """/world/map body contains the 'civil-war-modal' DOM and the 'heir-majority-notice' element."""
        client, dynasty_id, monarch_id, pretender_id = cw_client
        response = client.get('/world/map')
        assert response.status_code == 200
        assert b"civil-war-modal" in response.data
        assert b"heir-majority-notice" in response.data
