"""Async narration / AI-turn offloading infrastructure (Story 9-3).

This module provides two pieces of plumbing:

1. ``run_in_background`` — spawn a daemon thread that runs a callable inside a
   given Flask app context, swallowing any exception (logged, never raised to
   the caller) and always cleaning up the thread-local DB session.

2. ``should_offload_ai_turns`` — a predicate deciding whether the wider-world
   AI turn processing should be pushed onto a background thread. It only
   returns True when the LLM is available AND the projected number of LLM
   calls (AI dynasties * AI_LLM_CALLS_PER_DYNASTY) meets the threshold. With
   the LLM off (e.g. in the test suite) it always returns False, preserving
   the existing synchronous behaviour.

ALL flask / db / model imports are performed lazily inside the functions so
this module imports cleanly in pure-Python unit tests with no Flask app.
"""

import threading
import logging

logger = logging.getLogger('royal_succession.async_narration')

# Projected number of LLM calls each AI dynasty makes during a turn. Used by
# ``should_offload_ai_turns`` to estimate total LLM load.
AI_LLM_CALLS_PER_DYNASTY = 4


def run_in_background(app, fn, *args, **kwargs) -> threading.Thread:
    """Run ``fn(*args, **kwargs)`` in a daemon thread inside ``app``'s context.

    ``app`` must be the real Flask app object (i.e. obtained via
    ``current_app._get_current_object()``), not the ``current_app`` proxy,
    because the proxy is bound to the calling thread.

    The worker:
    - pushes an application context,
    - runs ``fn``,
    - logs (but never re-raises) any exception,
    - always calls ``db.session.remove()`` to release the thread-local
      session in a ``finally`` block.

    Returns the already-started daemon thread. This function never lets an
    exception from ``fn`` escape to the caller.
    """

    def _worker():
        with app.app_context():
            try:
                fn(*args, **kwargs)
            except Exception:
                logger.error(
                    "run_in_background: background task raised an exception",
                    exc_info=True,
                )
            finally:
                try:
                    from models.db_models import db
                    db.session.remove()
                except Exception:
                    logger.error(
                        "run_in_background: failed to remove db session",
                        exc_info=True,
                    )

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread


def should_offload_ai_turns(session, user_id, threshold: int = 5) -> bool:
    """Return True if AI-turn processing should be offloaded to a background thread.

    The decision is:
    - If the LLM is not available, return False (keep everything synchronous;
      this is the path the test suite takes since the LLM is off).
    - Otherwise, count the user's AI-controlled dynasties and return whether
      ``count * AI_LLM_CALLS_PER_DYNASTY >= threshold``.

    All imports are lazy so the module stays importable without a Flask app.
    Never raises — any error resolves to False (safe synchronous fallback).
    """
    try:
        # Lazy LLM-availability check. Prefer the canonical helper in
        # turn_processor; fall back to re-checking the Flask config directly.
        try:
            from models.turn_processor import _llm_available
            llm = _llm_available()
        except Exception:
            try:
                from flask import current_app
                llm = current_app.config.get(
                    'FLASK_APP_GOOGLE_API_KEY_PRESENT', False
                )
            except Exception:
                llm = False

        if not llm:
            return False

        from models.db_models import DynastyDB
        count = (
            session.query(DynastyDB)
            .filter_by(user_id=user_id, is_ai_controlled=True)
            .count()
        )
        return count * AI_LLM_CALLS_PER_DYNASTY >= threshold
    except Exception:
        logger.error(
            "should_offload_ai_turns: failed to evaluate predicate",
            exc_info=True,
        )
        return False
