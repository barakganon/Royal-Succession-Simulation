# tests/integration/test_story_moment_choice.py
# Story 10-2 (Story-moment interrupt) — CONTRACT-FIRST integration tests written
# by Agent D in an isolated worktree.
#
# These pin the choice route built by Agent B in blueprints/dynasty.py and the
# world-map modal wiring built by Agent C:
#   - POST /dynasty/<id>/story_moment_choice (@login_required, owner only).
#     Body may be JSON or form: {template: <key>, choice: <choice key>}.
#       * valid template + valid choice (owner) -> 200, JSON ok:true, message ==
#         the chosen choice's label, AND a HistoryLogEntryDB with
#         event_type == 'story_moment' is written for that dynasty.
#       * unknown template OR unknown choice -> 400, JSON ok:false.
#       * a logged-in NON-owner -> 403.
#     (10-2 only RECORDS + DISMISSES — mechanical effects are Story 10-3.)
#   - templates/world_map.html contains 'story-moment-modal',
#     'openStoryMomentModal', and the reason === 'story_moment' dispatch branch.
#
# In this isolated worktree the route + template may not yet exist; these tests
# WILL FAIL until Agents B and C land them. That is EXPECTED for a
# contract-first suite. Do NOT weaken, stub, or skip these tests.

import os

import pytest

from models.db_models import DynastyDB, HistoryLogEntryDB, PersonDB, User
from models.story_moments import STORY_MOMENT_TEMPLATES

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# Use a real template + one of its real choice keys.
SAMPLE_TEMPLATE = STORY_MOMENT_TEMPLATES[0]
SAMPLE_TEMPLATE_KEY = SAMPLE_TEMPLATE['key']
SAMPLE_CHOICE = SAMPLE_TEMPLATE['mechanical_choices'][0]
SAMPLE_CHOICE_KEY = SAMPLE_CHOICE['key']
SAMPLE_CHOICE_LABEL = SAMPLE_CHOICE['label']


# ---------------------------------------------------------------------------
# Helpers (client + login + ownership, mirroring test_dynasty_routes.py and
# the direct-creation pattern from test_civil_war_majority.py)
# ---------------------------------------------------------------------------

def _create_user(app, db, username, password="password123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _create_dynasty(app, db, user_id, dynasty_name):
    with app.app_context():
        dynasty = DynastyDB(
            user_id=user_id,
            name=dynasty_name,
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=500,
            start_year=1200,
            current_simulation_year=1230,
            prestige=20,
            is_ai_controlled=False,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


def _add_monarch(app, db, dynasty_id):
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
        db.session.add(person)
        db.session.commit()
        return person.id


def _story_moment_entries(app, db, dynasty_id):
    with app.app_context():
        return HistoryLogEntryDB.query.filter_by(
            dynasty_id=dynasty_id, event_type='story_moment'
        ).all()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sm_owner_client(app, db, session):
    """Authenticated OWNER of a human dynasty with a living monarch.
    Yields (client, dynasty_id)."""
    user_id = _create_user(app, db, "sm_owner")
    dynasty_id = _create_dynasty(app, db, user_id, "House Story")
    _add_monarch(app, db, dynasty_id)
    with app.test_client() as c:
        c.post('/login', data={'username': 'sm_owner', 'password': 'password123'})
        yield c, dynasty_id


# ---------------------------------------------------------------------------
# 1. Valid choice -> 200 ok, label echoed, chronicle entry written
# ---------------------------------------------------------------------------

class TestStoryMomentChoiceValid:
    def test_valid_choice_records_and_dismisses(self, sm_owner_client, app, db):
        """Owner POSTs a valid template+choice -> 200 ok:true, message == label,
        and a story_moment HistoryLogEntryDB is written."""
        client, dynasty_id = sm_owner_client
        response = client.post(
            f'/dynasty/{dynasty_id}/story_moment_choice',
            json={'template': SAMPLE_TEMPLATE_KEY, 'choice': SAMPLE_CHOICE_KEY},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body is not None
        assert body.get('ok') is True
        assert body.get('message') == SAMPLE_CHOICE_LABEL

        entries = _story_moment_entries(app, db, dynasty_id)
        assert len(entries) >= 1

    def test_valid_choice_via_form_data(self, sm_owner_client, app, db):
        """The route also accepts form-encoded body."""
        client, dynasty_id = sm_owner_client
        response = client.post(
            f'/dynasty/{dynasty_id}/story_moment_choice',
            data={'template': SAMPLE_TEMPLATE_KEY, 'choice': SAMPLE_CHOICE_KEY},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body is not None and body.get('ok') is True


# ---------------------------------------------------------------------------
# 2. Invalid template / invalid choice -> 400 ok:false
# ---------------------------------------------------------------------------

class TestStoryMomentChoiceInvalid:
    def test_unknown_template_returns_400(self, sm_owner_client, app, db):
        client, dynasty_id = sm_owner_client
        response = client.post(
            f'/dynasty/{dynasty_id}/story_moment_choice',
            json={'template': 'no_such_moment', 'choice': SAMPLE_CHOICE_KEY},
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body is not None and body.get('ok') is False

    def test_unknown_choice_returns_400(self, sm_owner_client, app, db):
        client, dynasty_id = sm_owner_client
        response = client.post(
            f'/dynasty/{dynasty_id}/story_moment_choice',
            json={'template': SAMPLE_TEMPLATE_KEY, 'choice': 'no_such_choice'},
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body is not None and body.get('ok') is False


# ---------------------------------------------------------------------------
# 3. Non-owner -> 403
# ---------------------------------------------------------------------------

class TestStoryMomentChoiceOwnership:
    def test_non_owner_returns_403(self, app, db, session):
        """A logged-in user who does NOT own the dynasty -> HTTP 403."""
        owner_id = _create_user(app, db, "sm_real_owner")
        dynasty_id = _create_dynasty(app, db, owner_id, "House Owned")
        _add_monarch(app, db, dynasty_id)
        # A different, logged-in user.
        _create_user(app, db, "sm_intruder")

        with app.test_client() as client:
            client.post('/login', data={'username': 'sm_intruder', 'password': 'password123'})
            response = client.post(
                f'/dynasty/{dynasty_id}/story_moment_choice',
                json={'template': SAMPLE_TEMPLATE_KEY, 'choice': SAMPLE_CHOICE_KEY},
            )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4. world_map.html wiring (read the repo file at its worktree path)
# ---------------------------------------------------------------------------

class TestWorldMapStoryMomentWiring:
    def _world_map_source(self):
        # tests/integration/<this file> -> repo root is two levels up.
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.abspath(os.path.join(here, '..', '..'))
        path = os.path.join(repo_root, 'templates', 'world_map.html')
        with open(path, 'r', encoding='utf-8') as fh:
            return fh.read()

    def test_world_map_contains_story_moment_modal(self):
        assert 'story-moment-modal' in self._world_map_source()

    def test_world_map_contains_open_story_moment_modal(self):
        assert 'openStoryMomentModal' in self._world_map_source()

    def test_world_map_contains_story_moment_dispatch_branch(self):
        source = self._world_map_source()
        assert "story_moment" in source
        # The dispatch checks reason === 'story_moment' (single or double quotes).
        assert ("reason === 'story_moment'" in source
                or 'reason === "story_moment"' in source)
