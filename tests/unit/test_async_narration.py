# tests/unit/test_async_narration.py
# Story 9-3 (async AI-turn offload) — CONTRACT-FIRST unit tests by Agent C.
#
# Pins the utils.async_narration contract:
#
#   - run_in_background(app, fn, *args, **kwargs) -> threading.Thread
#       Spawns a daemon thread that runs fn inside app.app_context().
#       NEVER raises to the caller, even when fn raises — it just returns the
#       thread (the error is logged and swallowed inside the thread).
#
#   - should_offload_ai_turns(session, user_id, threshold=5) -> bool
#       Returns False whenever the LLM is unavailable (regardless of how many AI
#       dynasties exist). When the LLM is available, returns
#       (#AI dynasties for user) * AI_LLM_CALLS_PER_DYNASTY >= threshold,
#       i.e. True for >=2 AI dynasties (2*4=8>=5) and False for 1 (1*4=4<5).
#
# These tests force _llm_available via monkeypatch on
# models.turn_processor._llm_available (the lazy reference the production code
# imports). Some may FAIL in this isolated worktree until utils.async_narration
# exists (built by another agent) — that is EXPECTED for a contract-first suite;
# do not weaken, stub, or skip them.

import threading

import pytest

from models.db_models import User, DynastyDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(db, username):
    user = User(username=username, email=f"{username}@x.test")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user.id


def _add_dynasty(db, user_id, name, is_ai):
    dynasty = DynastyDB(
        user_id=user_id,
        name=name,
        theme_identifier_or_json=VALID_THEME_KEY,
        current_wealth=500,
        start_year=1200,
        current_simulation_year=1230,
        is_ai_controlled=is_ai,
    )
    db.session.add(dynasty)
    db.session.commit()
    return dynasty.id


# ---------------------------------------------------------------------------
# 1. run_in_background runs fn inside the app context
# ---------------------------------------------------------------------------

class TestRunInBackground:
    def test_runs_fn_in_app_context(self, app, db):
        """run_in_background runs fn (in an app context) and returns a joinable thread."""
        from utils.async_narration import run_in_background

        effects = []

        def _job():
            # Touch the app/db so it would blow up outside an app context;
            # if this records, the function ran inside app.app_context().
            from flask import current_app
            effects.append(current_app.name)

        with app.app_context():
            real_app = app
        thread = run_in_background(real_app, _job)
        assert isinstance(thread, threading.Thread)
        thread.join(timeout=5)
        assert not thread.is_alive(), "background thread should finish promptly"
        assert effects, "fn must have executed inside the background thread"

    def test_passes_args_and_kwargs(self, app, db):
        """run_in_background forwards *args and **kwargs to fn."""
        from utils.async_narration import run_in_background

        captured = {}

        def _job(a, b, c=None):
            captured['a'] = a
            captured['b'] = b
            captured['c'] = c

        thread = run_in_background(app, _job, 1, 2, c=3)
        thread.join(timeout=5)
        assert captured == {'a': 1, 'b': 2, 'c': 3}

    def test_swallows_fn_errors(self, app, db):
        """A throwing fn must NOT propagate to the caller; a thread is still returned."""
        from utils.async_narration import run_in_background

        def _boom():
            raise RuntimeError("kaboom")

        # The call itself must not raise.
        thread = run_in_background(app, _boom)
        assert isinstance(thread, threading.Thread)
        thread.join(timeout=5)
        assert not thread.is_alive(), "thread should terminate even after fn raised"


# ---------------------------------------------------------------------------
# 2. should_offload_ai_turns predicate
# ---------------------------------------------------------------------------

class TestShouldOffloadAiTurns:
    def test_false_when_llm_unavailable_even_with_many_ai(self, app, db, session, monkeypatch):
        """LLM off -> always False, even with several AI dynasties."""
        from utils import async_narration

        uid = _create_user(db, "off_llm_off")
        _add_dynasty(db, uid, "House One", is_ai=True)
        _add_dynasty(db, uid, "House Two", is_ai=True)
        _add_dynasty(db, uid, "House Three", is_ai=True)

        import models.turn_processor as tp
        monkeypatch.setattr(tp, "_llm_available", lambda: False)

        assert async_narration.should_offload_ai_turns(db.session, uid) is False

    def test_true_when_llm_on_and_two_ai_dynasties(self, app, db, session, monkeypatch):
        """LLM on + 2 AI dynasties (2*4=8 >= 5) -> True."""
        from utils import async_narration

        uid = _create_user(db, "off_llm_on_two")
        _add_dynasty(db, uid, "House A", is_ai=True)
        _add_dynasty(db, uid, "House B", is_ai=True)
        # A player dynasty must NOT count toward the AI total.
        _add_dynasty(db, uid, "House Player", is_ai=False)

        import models.turn_processor as tp
        monkeypatch.setattr(tp, "_llm_available", lambda: True)

        assert async_narration.should_offload_ai_turns(db.session, uid) is True

    def test_false_when_llm_on_but_only_one_ai_dynasty(self, app, db, session, monkeypatch):
        """LLM on + 1 AI dynasty (1*4=4 < 5) -> False."""
        from utils import async_narration

        uid = _create_user(db, "off_llm_on_one")
        _add_dynasty(db, uid, "House Solo", is_ai=True)
        _add_dynasty(db, uid, "House Player", is_ai=False)

        import models.turn_processor as tp
        monkeypatch.setattr(tp, "_llm_available", lambda: True)

        assert async_narration.should_offload_ai_turns(db.session, uid) is False
