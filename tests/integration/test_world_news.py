# tests/integration/test_world_news.py
# Story 9-3 (WORLD NEWS — 'letter from afar') — CONTRACT-FIRST integration tests
# by Agent C. Fixtures mirror tests/integration/test_ai_marriage.py.
#
# Pins the contract:
#
#   GameManager(session)._record_world_news(actor_dynasty, action_desc, year)
#     writes ONE HistoryLogEntryDB per PLAYER dynasty (is_ai_controlled=False)
#     under the actor's user_id, with:
#         event_type == 'world_news'
#         dynasty_id == player dynasty id
#         event_string == generate_world_news_fallback(actor.name, action_desc, year)
#                         (LLM is OFF in the test app)
#     and writes NO world_news row on the acting AI dynasty's own id.
#
#   should_offload_ai_turns(session, user_id) is False in the test app (LLM off),
#     documenting that advance_turn stays on the synchronous path during tests.
#
# Some assertions may FAIL in this isolated worktree until _record_world_news
# exists (built by another agent) — EXPECTED for a contract-first suite; do not
# weaken, stub, or skip them.

import pytest

from models.db_models import User, DynastyDB, HistoryLogEntryDB
from models.game_manager import GameManager
from utils.llm_prompts import generate_world_news_fallback

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers ('wn_' username space to avoid collisions)
# ---------------------------------------------------------------------------

def _create_user(app, db, username, password="password123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _add_dynasty(app, db, user_id, name, is_ai):
    with app.app_context():
        dynasty = DynastyDB(
            user_id=user_id,
            name=name,
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=500,
            start_year=1200,
            current_simulation_year=1300,
            is_ai_controlled=is_ai,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


# ---------------------------------------------------------------------------
# 1. _record_world_news writes the letter to the player, never the AI actor
# ---------------------------------------------------------------------------

class TestRecordWorldNews:
    def test_letter_written_to_player_only(self, app, db, session):
        """An AI war declaration produces a 'world_news' entry on the player's
        dynasty (fallback text, LLM off) and none on the AI actor's own id."""
        uid = _create_user(app, db, "wn_owner")
        player_id = _add_dynasty(app, db, uid, "House Player", is_ai=False)
        ai_id = _add_dynasty(app, db, uid, "House Aggressor", is_ai=True)

        with app.app_context():
            ai_dyn = db.session.get(DynastyDB, ai_id)
            GameManager(db.session)._record_world_news(
                ai_dyn, 'declared war on House Foo', 1300
            )
            db.session.commit()

        expected = generate_world_news_fallback(
            'House Aggressor', 'declared war on House Foo', 1300
        )

        with app.app_context():
            player_news = HistoryLogEntryDB.query.filter_by(
                event_type='world_news', dynasty_id=player_id
            ).all()
            assert len(player_news) == 1, "exactly one letter reaches the player"
            assert player_news[0].event_string == expected, (
                "the player's letter uses the deterministic world-news fallback "
                "when the LLM is off"
            )

            ai_news = HistoryLogEntryDB.query.filter_by(
                event_type='world_news', dynasty_id=ai_id
            ).all()
            assert ai_news == [], "the AI actor must not receive its own world-news letter"


# ---------------------------------------------------------------------------
# 2. Regression-safety: offload predicate is False under the test app (LLM off)
# ---------------------------------------------------------------------------

class TestOffloadDisabledInTests:
    def test_should_offload_is_false_with_llm_off(self, app, db, session):
        """With the LLM off (test app), should_offload_ai_turns is False, so
        advance_turn takes the synchronous process_ai_turns path."""
        from utils.async_narration import should_offload_ai_turns

        uid = _create_user(app, db, "wn_offload")
        # Two AI dynasties would clear the count*4>=5 bar IF the LLM were on,
        # so a False result here is driven purely by the LLM being off.
        _add_dynasty(app, db, uid, "House One", is_ai=True)
        _add_dynasty(app, db, uid, "House Two", is_ai=True)

        with app.app_context():
            assert should_offload_ai_turns(db.session, uid) is False
