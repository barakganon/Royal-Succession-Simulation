# tests/integration/test_trait_docs_and_tooltip.py
# Story 6-3 (Agent C / contract-first): two cross-cutting deliverables.
#
#   (1) The monarch rail portrait on /world/map must surface the living
#       monarch's trait name(s) in its title / aria-label region so a player
#       can read the monarch's traits on hover. We build a dynasty + a LIVING
#       (death_year=None) is_monarch=True PersonDB with set_traits([...]),
#       log in, GET /world/map, and assert the trait names appear in the
#       served HTML body.
#
#   (2) docs/traits.md must exist and name all 8 traits.
#
# LLM is OFF in tests. These tests are EXPECTED TO FAIL until the tooltip
# wiring lands and docs/traits.md is authored.

import os
import re

import pytest

from models.db_models import User, DynastyDB, PersonDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# Unique username space for this agent's tests.
_USERNAME = 'ctv_user'

ALL_TRAITS = [
    'Brave', 'Craven', 'Cunning', 'Wroth',
    'Patient', 'Pious', 'Greedy', 'Sickly',
]

# Repo root = two levels up from this file (tests/integration/ -> repo).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TRAITS_DOC = os.path.join(_REPO_ROOT, 'docs', 'traits.md')


def _make_user_dynasty_and_monarch(app, db, traits, username=_USERNAME,
                                   dynasty_name='House Trait', year=1305):
    """Create a User + DynastyDB + LIVING reigning monarch with `traits`.

    Returns (user_id, dynasty_id, monarch_id). Mirrors the direct-DB build
    pattern used by test_trait_effects_hooks.py.
    """
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        dynasty = DynastyDB(
            user_id=user_id,
            name=dynasty_name,
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=1000,
            start_year=1200,
            current_simulation_year=year,
        )
        db.session.add(dynasty)
        db.session.commit()
        dynasty_id = dynasty.id

        monarch = PersonDB(
            dynasty_id=dynasty_id,
            name='Aldric',
            surname='Traitsson',
            gender='MALE',
            birth_year=1270,
            death_year=None,
            is_monarch=True,
            is_noble=True,
            reign_start_year=1300,
        )
        monarch.set_traits(traits)
        db.session.add(monarch)
        db.session.commit()
        monarch_id = monarch.id

    return user_id, dynasty_id, monarch_id


@pytest.fixture
def ctv_client(app, db, session):
    """Logged-in client whose dynasty has a living, trait-bearing monarch."""
    _make_user_dynasty_and_monarch(app, db, traits=['Brave', 'Pious'])
    with app.test_client() as c:
        c.post('/login', data={'username': _USERNAME, 'password': 'password123'})
        yield c


class TestMonarchTraitTooltip:
    def test_world_map_monarch_portrait_region_shows_trait_names(self, ctv_client):
        """GET /world/map: trait names appear in the monarch rail portrait title/aria-label region."""
        response = ctv_client.get('/world/map')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        # Isolate the monarch rail portrait element's OPENING TAG, which carries
        # the title= / aria-label= region. We scope to this tag so the assertion
        # cannot be satisfied by the window.__monarchData JSON dump or the
        # detail-panel JS elsewhere on the page — only by the tooltip region.
        m = re.search(r'<div class="game-rail-portrait"[^>]*>', html)
        assert m is not None, "monarch rail portrait element not found in /world/map"
        rail_tag = m.group(0)
        # Sanity: the living monarch must have resolved into the rail (guards
        # against a "No monarch" rail silently masking the real contract gap).
        assert 'Aldric' in rail_tag, (
            f"living monarch did not resolve into the rail portrait: {rail_tag}"
        )
        # The living monarch's trait name(s) must be surfaced in the
        # title/aria-label region of the rail portrait.
        assert 'Brave' in rail_tag, f"'Brave' missing from rail portrait tooltip region: {rail_tag}"
        assert 'Pious' in rail_tag, f"'Pious' missing from rail portrait tooltip region: {rail_tag}"


class TestTraitDocs:
    def test_traits_doc_exists_and_names_all_eight_traits(self):
        """docs/traits.md exists at the repo path and its text contains all 8 trait names."""
        assert os.path.isfile(_TRAITS_DOC), f"Expected docs/traits.md at {_TRAITS_DOC}"
        with open(_TRAITS_DOC, encoding='utf-8') as fh:
            text = fh.read()
        for trait in ALL_TRAITS:
            assert trait in text, f"docs/traits.md is missing trait '{trait}'"
