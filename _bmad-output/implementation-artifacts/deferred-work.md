# Deferred Work Log

## Deferred from: code review of sprint01-task01-turn-processor-extraction (2026-05-02)

All items below are pre-existing issues in `blueprints/dynasty.py` surfaced during the Sprint 1 Task 1 refactor review. None were introduced by this PR.

- **2-tuple early exits in `process_dynasty_turn`** [`models/turn_processor.py:72,85`] — `return False, "Dynasty not found"` and `return False, "Invalid theme configuration"` are 2-tuples; docstring promises 3-tuple. Callers guard with `len(result)==3` so no live bug. Harden the contract in Sprint 1 Task 1-2 when the function signature changes anyway.

- **`FLASK_APP_GOOGLE_API_KEY` config key** [`models/turn_processor.py:182`] — `current_app.config.get("FLASK_APP_GOOGLE_API_KEY")` always returns `None` because the app only sets `FLASK_APP_GOOGLE_API_KEY_PRESENT` (bool). The `os.environ.get("GOOGLE_API_KEY")` fallback makes it work. Clean this up in Sprint 11 config audit.

- **`max_output_tokens: 300` violates 150-token chronicle budget** [`models/turn_processor.py:196`] — CLAUDE.md mandates 150 for chronicle narration; this uses 300. Address when refactoring the epic story generation in Sprint 9 (LLM storytelling spine).

- **`current_simulation_year` advances outside per-year `try/except`** [`models/turn_processor.py:138`] — A year that raises an exception still advances the clock, silently losing that year's lifecycle events. Sprint 1 Task 1-2 (interrupt-driven loop) will restructure this loop and can fix it then.

- **Sibling NULL FK query** [`models/turn_processor.py:510`] — `PersonDB.father_sim_id == deceased_monarch.father_sim_id` is vacuously false when father is NULL, so founders skip the sibling path and fall straight to "any living noble." Low impact (succession still works via fallback). Sprint 5 succession drama is the right fix point.

- **`_llm_available()` asymmetry** [`blueprints/dynasty.py:37`] — dynasty.py version has no try/except; will raise `RuntimeError` if called outside a Flask app context. Not a current bug (only called in request handlers). Consolidate into a shared util in Sprint 11 cleanup.

- **Double `DynastyDB.query.get` after commit** [`models/turn_processor.py:213`] — `dynasty_obj = DynastyDB.query.get(dynasty_id)` re-queries the same object already in session. Extra round-trip, plus silent `None` fallback. Fix in Sprint 11 N+1 query pass.

- **`monarch_title` NameError if `titles` is empty** [`models/turn_processor.py:566`] — `monarch_title` assigned inside `if titles:` but used unconditionally in an f-string below. Mitigated by `theme_config.get(title_key, ["Leader"])` default (list always has ≥1 item in practice). Harden in Sprint 5 succession drama work.

- **`BankingSystem.accrue_interest` post-commit rollback gap** [`models/turn_processor.py:153`] — Called after `db.session.commit()` with only a log on failure; partial writes could be orphaned. Address in Sprint 10B follow-on or Sprint 11 transaction audit.
