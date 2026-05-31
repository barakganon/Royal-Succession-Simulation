# tests/integration/test_story_moment_interrupt.py
# Story 10-2 (Story-moment interrupt) — CONTRACT-FIRST integration tests written
# by Agent D in an isolated worktree.
#
# These pin the turn-loop wiring built by Agent A in models/turn_processor.py:
#   - 'story_moment' is a valid INTERRUPT_REASONS member.
#   - A HUMAN dynasty's turn is INTERRUPTED when
#     story_moments.maybe_trigger_story_moment(...) returns a template, AND no
#     higher-priority interrupt (monarch_death/civil_war/heir_majority) fired.
#   - The turn_summary then carries summary['story_moment'] with key/title/prose
#     (non-empty)/choices (2..3 dicts of key/label/description).
#   - When maybe_trigger_story_moment returns None, no story_moment interrupt.
#   - Story moments fire ONLY for human dynasties: an AI dynasty (is_ai_controlled
#     True) with the trigger patched to a template does NOT halt on story_moment.
#
# In this isolated worktree the wiring may not yet exist; these tests WILL FAIL
# until Agent A lands it. That is EXPECTED and correct for a contract-first
# suite. Do NOT weaken, stub, or skip these tests.

from unittest.mock import patch

import pytest

from models.db_models import DynastyDB, PersonDB, User
from models.story_moments import STORY_MOMENT_TEMPLATES

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# A real template from the 10-1 library; the contract says the interrupt builds
# its summary from whatever maybe_trigger_story_moment returns.
SAMPLE_TEMPLATE = STORY_MOMENT_TEMPLATES[0]


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_civil_war_majority.py)
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
            surname="Storyson",
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


# ---------------------------------------------------------------------------
# 1. 'story_moment' is a valid interrupt reason
# ---------------------------------------------------------------------------

class TestStoryMomentInterruptReason:
    def test_story_moment_in_interrupt_reasons(self):
        """turn_processor exposes 'story_moment' as a valid interrupt reason."""
        from models import turn_processor as tp

        assert 'story_moment' in tp.INTERRUPT_REASONS


# ---------------------------------------------------------------------------
# 2. Human dynasty: a triggered template halts the turn with a story_moment
# ---------------------------------------------------------------------------

class TestStoryMomentDetectionHuman:
    def test_human_triggered_template_halts_with_story_moment(self, app, db, session):
        """Human dynasty + maybe_trigger_story_moment -> a template -> interrupt
        'story_moment' and a fully-formed summary['story_moment']."""
        from models import turn_processor as tp

        _, dynasty_id = _create_user_and_dynasty(
            app, db, "sm_human", "House Story", is_ai=False
        )
        _add_person(app, db, dynasty_id, name="StoryKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)

        # Isolate the story-moment interrupt: keep everyone alive, suppress
        # marriage + childbirth so no other interrupt can pre-empt it.
        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False), \
                 patch('models.turn_processor.process_marriage_check', return_value=False), \
                 patch('models.turn_processor.process_childbirth_check', return_value=False), \
                 patch('models.story_moments.maybe_trigger_story_moment',
                       return_value=SAMPLE_TEMPLATE):
                success, _msg, summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert summary is not None
        assert summary['interrupt_reason'] == 'story_moment'

        sm = summary['story_moment']
        assert sm['key'] == SAMPLE_TEMPLATE['key']
        assert sm['title'] == SAMPLE_TEMPLATE['title']
        assert isinstance(sm['prose'], str) and sm['prose'].strip() != ''

        choices = sm['choices']
        assert isinstance(choices, list)
        assert 2 <= len(choices) <= 3
        for choice in choices:
            assert 'key' in choice
            assert 'label' in choice
            assert 'description' in choice


# ---------------------------------------------------------------------------
# 3. Human dynasty: no trigger -> no story_moment interrupt
# ---------------------------------------------------------------------------

class TestStoryMomentNoTrigger:
    def test_human_no_trigger_does_not_fire_story_moment(self, app, db, session):
        """When maybe_trigger_story_moment returns None there is no story_moment
        interrupt."""
        from models import turn_processor as tp

        _, dynasty_id = _create_user_and_dynasty(
            app, db, "sm_none", "House Quiet", is_ai=False
        )
        _add_person(app, db, dynasty_id, name="QuietKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)

        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False), \
                 patch('models.turn_processor.process_marriage_check', return_value=False), \
                 patch('models.turn_processor.process_childbirth_check', return_value=False), \
                 patch('models.story_moments.maybe_trigger_story_moment',
                       return_value=None):
                success, _msg, summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert summary is not None
        assert summary['interrupt_reason'] != 'story_moment'


# ---------------------------------------------------------------------------
# 4. AI dynasty: story moments never fire
# ---------------------------------------------------------------------------

class TestStoryMomentAISuppressed:
    def test_ai_dynasty_never_fires_story_moment(self, app, db, session):
        """An AI dynasty with the trigger patched to a template still does NOT
        halt on a story moment — story moments are human-only."""
        from models import turn_processor as tp

        _, dynasty_id = _create_user_and_dynasty(
            app, db, "sm_ai", "House Machina", is_ai=True
        )
        _add_person(app, db, dynasty_id, name="AIKing", gender="MALE",
                    birth_year=1190, is_monarch=True, reign_start_year=1215)

        with app.app_context():
            with patch('models.turn_processor.process_death_check', return_value=False), \
                 patch('models.turn_processor.process_marriage_check', return_value=False), \
                 patch('models.turn_processor.process_childbirth_check', return_value=False), \
                 patch('models.story_moments.maybe_trigger_story_moment',
                       return_value=SAMPLE_TEMPLATE):
                success, _msg, summary = tp.process_dynasty_turn(
                    dynasty_id, years_to_advance=5
                )

        assert success is True
        assert summary is not None
        assert summary['interrupt_reason'] != 'story_moment'
