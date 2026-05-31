# tests/integration/test_story_moment_effects.py
# Story 10-3 (Story-moment EFFECTS + COOLDOWN) — CONTRACT-FIRST integration
# tests written by Agent C in an isolated worktree.
#
# These pin the contract completed in Story 10-3:
#   (A) models/turn_processor.py — STORY_MOMENT_COOLDOWN_YEARS = 25 gates the
#       10-2 story-moment trigger: if the latest resolved story_moment
#       HistoryLogEntryDB for the dynasty is within the cooldown of the current
#       year, maybe_trigger_story_moment is NOT called and no story_moment fires.
#   (B) blueprints/dynasty.py — module-level _apply_story_moment_effects(dynasty,
#       effects) applies prestige_delta / wealth_delta / infamy_delta (clamped
#       >= 0) and add_trait_to_monarch (idempotent) to the living monarch.
#       chronicle_note / exile_person / relation_delta are NARRATIVE-ONLY (no
#       state mutation, never raise). The story_moment_choice route applies the
#       chosen choice's effects before its single commit and still writes exactly
#       one event_type='story_moment' HistoryLogEntryDB per resolved choice.
#
# In this isolated worktree the applicator + cooldown may not yet exist; these
# tests WILL FAIL until Agents A and B land them. That is EXPECTED for a
# contract-first suite. Do NOT weaken, stub, or skip these tests.

from unittest.mock import patch

import pytest

from models.db_models import DynastyDB, HistoryLogEntryDB, PersonDB, User
from models.story_moments import STORY_MOMENT_TEMPLATES

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Locate real templates/choices to drive the route + applicator tests.
# ---------------------------------------------------------------------------

def _find_template(key):
    for t in STORY_MOMENT_TEMPLATES:
        if t['key'] == key:
            return t
    raise AssertionError(f"template {key!r} not found in STORY_MOMENT_TEMPLATES")


def _find_choice(template, choice_key):
    for c in template['mechanical_choices']:
        if c['key'] == choice_key:
            return c
    raise AssertionError(f"choice {choice_key!r} not found in template {template['key']!r}")


def _find_choice_with_effect(effect_key):
    """Return (template, choice) for the first choice whose effects include
    effect_key. Used so the route tests use REAL data from the templates."""
    for t in STORY_MOMENT_TEMPLATES:
        for c in t['mechanical_choices']:
            if effect_key in (c.get('effects') or {}):
                return t, c
    raise AssertionError(f"no choice with effect {effect_key!r} found")


# forbidden_love / deny -> {prestige_delta: 5, add_trait_to_monarch: Cunning}
PRESTIGE_TEMPLATE = _find_template('forbidden_love')
PRESTIGE_CHOICE = _find_choice(PRESTIGE_TEMPLATE, 'deny')
PRESTIGE_DELTA = PRESTIGE_CHOICE['effects']['prestige_delta']

# forbidden_love / banish -> {prestige_delta: 8, exile_person: True}
EXILE_TEMPLATE = _find_template('forbidden_love')
EXILE_CHOICE = _find_choice(EXILE_TEMPLATE, 'banish')

# bonds_of_kin / grant_title -> {wealth_delta: -60, relation_delta: {...}}
RELATION_TEMPLATE = _find_template('bonds_of_kin')
RELATION_CHOICE = _find_choice(RELATION_TEMPLATE, 'grant_title')


# ---------------------------------------------------------------------------
# Helpers (client + login + ownership; mirror test_story_moment_choice.py and
# the direct-creation pattern from test_civil_war_majority.py)
# ---------------------------------------------------------------------------

def _create_user(app, db, username, password="password123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _create_dynasty(app, db, user_id, dynasty_name, prestige=20, wealth=500,
                    infamy=10, is_ai=False, sim_year=1230):
    with app.app_context():
        dynasty = DynastyDB(
            user_id=user_id,
            name=dynasty_name,
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=wealth,
            start_year=1200,
            current_simulation_year=sim_year,
            prestige=prestige,
            infamy=infamy,
            is_ai_controlled=is_ai,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


def _add_monarch(app, db, dynasty_id, traits=None):
    with app.app_context():
        person = PersonDB(
            dynasty_id=dynasty_id,
            name="StoryKing",
            surname="Storyson",
            gender="MALE",
            birth_year=1190,
            is_monarch=True,
            is_noble=True,
            reign_start_year=1215,
        )
        if traits is not None:
            person.set_traits(list(traits))
        db.session.add(person)
        db.session.commit()
        return person.id


def _get_dynasty(app, db, dynasty_id):
    with app.app_context():
        return db.session.get(DynastyDB, dynasty_id)


def _get_person(app, db, person_id):
    with app.app_context():
        return db.session.get(PersonDB, person_id)


def _story_moment_entries(app, db, dynasty_id):
    with app.app_context():
        return HistoryLogEntryDB.query.filter_by(
            dynasty_id=dynasty_id, event_type='story_moment'
        ).all()


def _add_story_moment_log(app, db, dynasty_id, year):
    with app.app_context():
        entry = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=year,
            event_string="An earlier story moment was resolved.",
            event_type='story_moment',
        )
        db.session.add(entry)
        db.session.commit()
        return entry.id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sm_owner_client(app, db, session):
    """Authenticated OWNER of a human dynasty with a living monarch.
    Yields (client, dynasty_id, monarch_id)."""
    user_id = _create_user(app, db, "sme_owner")
    dynasty_id = _create_dynasty(app, db, user_id, "House Effects")
    monarch_id = _add_monarch(app, db, dynasty_id)
    with app.test_client() as c:
        c.post('/login', data={'username': 'sme_owner', 'password': 'password123'})
        yield c, dynasty_id, monarch_id


# ===========================================================================
# 1. _apply_story_moment_effects — numeric deltas applied + clamped >= 0
# ===========================================================================

class TestApplyNumericDeltas:
    def test_prestige_wealth_infamy_deltas_applied(self, app, db, session):
        """prestige_delta / wealth_delta / infamy_delta each shift the matching
        dynasty field by the delta."""
        from blueprints.dynasty import _apply_story_moment_effects

        user_id = _create_user(app, db, "sme_num")
        dynasty_id = _create_dynasty(
            app, db, user_id, "House Numbers",
            prestige=30, wealth=200, infamy=10,
        )
        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            _apply_story_moment_effects(
                dynasty,
                {'prestige_delta': 15, 'wealth_delta': -50, 'infamy_delta': 7},
            )
            db.session.commit()

        after = _get_dynasty(app, db, dynasty_id)
        assert after.prestige == 30 + 15
        assert after.current_wealth == 200 - 50
        assert after.infamy == 10 + 7

    def test_numeric_deltas_clamp_at_zero(self, app, db, session):
        """A negative delta larger than the current value clamps the field to 0
        (never goes negative)."""
        from blueprints.dynasty import _apply_story_moment_effects

        user_id = _create_user(app, db, "sme_clamp")
        dynasty_id = _create_dynasty(
            app, db, user_id, "House Clamp",
            prestige=5, wealth=20, infamy=3,
        )
        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            _apply_story_moment_effects(
                dynasty,
                {'prestige_delta': -999, 'wealth_delta': -999, 'infamy_delta': -999},
            )
            db.session.commit()

        after = _get_dynasty(app, db, dynasty_id)
        assert after.prestige == 0
        assert after.current_wealth == 0
        assert after.infamy == 0


# ===========================================================================
# 2. _apply_story_moment_effects — add_trait_to_monarch (idempotent)
# ===========================================================================

class TestApplyAddTrait:
    def test_add_trait_to_living_monarch(self, app, db, session):
        """add_trait_to_monarch adds the trait to the living monarch's traits."""
        from blueprints.dynasty import _apply_story_moment_effects

        user_id = _create_user(app, db, "sme_trait")
        dynasty_id = _create_dynasty(app, db, user_id, "House Trait")
        monarch_id = _add_monarch(app, db, dynasty_id, traits=[])

        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            _apply_story_moment_effects(dynasty, {'add_trait_to_monarch': 'Cunning'})
            db.session.commit()

        monarch = _get_person(app, db, monarch_id)
        assert 'Cunning' in monarch.get_traits()

    def test_add_trait_is_idempotent(self, app, db, session):
        """Applying the same trait twice does not create a duplicate entry."""
        from blueprints.dynasty import _apply_story_moment_effects

        user_id = _create_user(app, db, "sme_trait_idem")
        dynasty_id = _create_dynasty(app, db, user_id, "House Idem")
        monarch_id = _add_monarch(app, db, dynasty_id, traits=[])

        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            _apply_story_moment_effects(dynasty, {'add_trait_to_monarch': 'Brave'})
            _apply_story_moment_effects(dynasty, {'add_trait_to_monarch': 'Brave'})
            db.session.commit()

        monarch = _get_person(app, db, monarch_id)
        traits = monarch.get_traits()
        assert traits.count('Brave') == 1


# ===========================================================================
# 3. _apply_story_moment_effects — narrative-only / robustness
# ===========================================================================

class TestApplyNarrativeOnly:
    def test_chronicle_exile_relation_do_not_mutate_state(self, app, db, session):
        """chronicle_note / exile_person / relation_delta are narrative-only:
        they must NOT change dynasty fields and must NOT raise."""
        from blueprints.dynasty import _apply_story_moment_effects

        user_id = _create_user(app, db, "sme_narr")
        dynasty_id = _create_dynasty(
            app, db, user_id, "House Narrative",
            prestige=25, wealth=300, infamy=8,
        )
        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            _apply_story_moment_effects(
                dynasty,
                {
                    'chronicle_note': 'A tale was told.',
                    'exile_person': True,
                    'relation_delta': {'target': 'kin', 'amount': 20},
                },
            )
            db.session.commit()

        after = _get_dynasty(app, db, dynasty_id)
        assert after.prestige == 25
        assert after.current_wealth == 300
        assert after.infamy == 8

    def test_none_and_unknown_effects_are_safe(self, app, db, session):
        """None effects and unknown keys must not raise and must not mutate."""
        from blueprints.dynasty import _apply_story_moment_effects

        user_id = _create_user(app, db, "sme_safe")
        dynasty_id = _create_dynasty(app, db, user_id, "House Safe", prestige=12)

        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            # Must not raise on None.
            _apply_story_moment_effects(dynasty, None)
            # Unknown keys ignored.
            _apply_story_moment_effects(dynasty, {'banish_to_moon': True})
            db.session.commit()

        after = _get_dynasty(app, db, dynasty_id)
        assert after.prestige == 12

    def test_one_bad_effect_does_not_abort_others(self, app, db, session):
        """A malformed effect value must not prevent the valid effects in the
        same dict from being applied (defensive, never raises)."""
        from blueprints.dynasty import _apply_story_moment_effects

        user_id = _create_user(app, db, "sme_partial")
        dynasty_id = _create_dynasty(app, db, user_id, "House Partial", prestige=10)

        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            _apply_story_moment_effects(
                dynasty,
                {'prestige_delta': 'not-an-int', 'wealth_delta': 25},
            )
            db.session.commit()

        after = _get_dynasty(app, db, dynasty_id)
        # The good wealth_delta still landed.
        assert after.current_wealth == 500 + 25


# ===========================================================================
# 4. story_moment_choice route — applies a real prestige_delta choice + writes
#    exactly one story_moment HistoryLogEntryDB
# ===========================================================================

class TestRouteAppliesPrestigeDelta:
    def test_route_applies_prestige_delta_and_writes_one_log(self, sm_owner_client, app, db):
        """Owner POSTs a real {template, choice} whose effects include
        prestige_delta -> 200, dynasty.prestige shifts by the delta, and exactly
        one event_type='story_moment' HistoryLogEntryDB exists for the dynasty."""
        client, dynasty_id, monarch_id = sm_owner_client

        before = _get_dynasty(app, db, dynasty_id).prestige

        response = client.post(
            f'/dynasty/{dynasty_id}/story_moment_choice',
            json={'template': PRESTIGE_TEMPLATE['key'], 'choice': PRESTIGE_CHOICE['key']},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body is not None and body.get('ok') is True
        assert body.get('message') == PRESTIGE_CHOICE['label']

        after = _get_dynasty(app, db, dynasty_id).prestige
        assert after == max(0, before + PRESTIGE_DELTA)

        # Exactly one story_moment log for this resolved choice (no duplicates).
        entries = _story_moment_entries(app, db, dynasty_id)
        assert len(entries) == 1


class TestRouteNarrativeChoiceSafe:
    def test_route_exile_relation_choice_ok(self, sm_owner_client, app, db):
        """A real choice carrying exile_person / relation_delta applies without
        error (route returns ok) and does not crash (narrative-only)."""
        client, dynasty_id, monarch_id = sm_owner_client

        # First POST: forbidden_love/banish carries exile_person (+ prestige_delta).
        response = client.post(
            f'/dynasty/{dynasty_id}/story_moment_choice',
            json={'template': EXILE_TEMPLATE['key'], 'choice': EXILE_CHOICE['key']},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body is not None and body.get('ok') is True

        # Second POST: bonds_of_kin/grant_title carries relation_delta.
        response2 = client.post(
            f'/dynasty/{dynasty_id}/story_moment_choice',
            json={'template': RELATION_TEMPLATE['key'], 'choice': RELATION_CHOICE['key']},
        )
        assert response2.status_code == 200
        body2 = response2.get_json()
        assert body2 is not None and body2.get('ok') is True


# ===========================================================================
# 5. COOLDOWN — STORY_MOMENT_COOLDOWN_YEARS gates the trigger
# ===========================================================================

class TestStoryMomentCooldown:
    def test_cooldown_constant_is_25_years(self):
        """turn_processor exposes STORY_MOMENT_COOLDOWN_YEARS == 25."""
        from models import turn_processor as tp

        assert tp.STORY_MOMENT_COOLDOWN_YEARS == 25

    def test_recent_story_moment_blocks_new_trigger(self, app, db, session):
        """With a story_moment HistoryLogEntryDB within the cooldown of the
        current year, process_dynasty_turn must NOT fire a story_moment interrupt
        (the cooldown gate skips maybe_trigger_story_moment entirely)."""
        from models import turn_processor as tp

        user_id = _create_user(app, db, "sme_cd_recent")
        # current_simulation_year defaults to 1230.
        dynasty_id = _create_dynasty(app, db, user_id, "House Cooldown", sim_year=1230)
        _add_monarch(app, db, dynasty_id)

        # Recent resolved story moment: 1225 is within 25 years of 1230.
        _add_story_moment_log(app, db, dynasty_id, year=1225)

        # Force maybe_trigger_story_moment to ALWAYS return a template so the
        # ONLY thing that can suppress a story_moment interrupt is the cooldown.
        template = _find_template('forbidden_love')
        with app.app_context():
            with patch('models.story_moments.maybe_trigger_story_moment',
                       return_value=template), \
                 patch('models.turn_processor.process_death_check', return_value=False), \
                 patch('models.turn_processor.process_marriage_check', return_value=False), \
                 patch('models.turn_processor.process_childbirth_check', return_value=False):
                success, _msg, summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert summary is not None
        assert summary.get('interrupt_reason') != 'story_moment'

    def test_no_recent_story_moment_allows_trigger(self, app, db, session):
        """With NO story_moment within the cooldown window (none / far in the
        past), process_dynasty_turn DOES fire a story_moment interrupt when
        maybe_trigger_story_moment returns a template."""
        from models import turn_processor as tp

        user_id = _create_user(app, db, "sme_cd_old")
        dynasty_id = _create_dynasty(app, db, user_id, "House Free", sim_year=1230)
        _add_monarch(app, db, dynasty_id)

        # An OLD story moment well outside the 25-year cooldown (1100 << 1230-25).
        _add_story_moment_log(app, db, dynasty_id, year=1100)

        template = _find_template('forbidden_love')
        with app.app_context():
            with patch('models.story_moments.maybe_trigger_story_moment',
                       return_value=template), \
                 patch('models.turn_processor.process_death_check', return_value=False), \
                 patch('models.turn_processor.process_marriage_check', return_value=False), \
                 patch('models.turn_processor.process_childbirth_check', return_value=False):
                success, _msg, summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert summary is not None
        assert summary.get('interrupt_reason') == 'story_moment'
