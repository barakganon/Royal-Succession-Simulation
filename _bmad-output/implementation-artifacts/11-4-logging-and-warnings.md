# Story 11-4: Logging + SQLAlchemy Warnings Cleanup

Status: ready-for-dev

## Story
As a **developer running and operating the app**, I want **rotating logs, no stray `print()`, no pytest-exit logging noise, and the SQLAlchemy 2.0 deprecations cleared**, so that **logs are bounded and signal-rich and the test run is warning-clean (<50, down from ~1982).**

## Context (profiled)
- Test run emits ~1982 warnings, dominated by **`LegacyAPIWarning` from `.query.get(id)`** (71 unique sites, repeated). 22 `.query.get(` calls in app code (`models/turn_processor.py`, blueprints/*). Replacing them with `db.session.get(Model, id)` is the single biggest warning win.
- `utils/logging_config.py` ALREADY has a `RotatingFileHandler` (`:70`). But `main_flask_app.py:25` configures root logging with a plain `logging.FileHandler("flask_app.log")` — make it rotating.
- `main_flask_app.py:157` `atexit.register(cleanup)` fires during pytest teardown → "Logging error" / `ResourceWarning` after handlers close. Make conditional (skip under pytest).
- 35 `print(` in app code (`models/politics.py`, `models/traits.py`, `models/history.py`, blueprints/*, `main_flask_app.py`). 4 `datetime.utcnow(` sites.

## Acceptance Criteria
1. **AC1 — Rotating app log.** Replace the plain `FileHandler("flask_app.log")` in `main_flask_app.py` (~:25) with `RotatingFileHandler(maxBytes=5*1024*1024, backupCount=3)`. Reuse `utils/logging_config` if it fits; otherwise inline the rotating handler. Log file location unchanged behavior.
2. **AC2 — No stray `print()`.** Replace the 35 `print(` calls in app code (`models/`, `blueprints/`, `utils/`, `visualization/`, `main_flask_app.py`) with the module logger at appropriate level (`logger.debug/info/warning/error`). Each module already has / must get `logger = logging.getLogger('royal_succession.<module>')`. Do NOT touch `print(` in `tests/` or any `if __name__=='__main__'` CLI demo blocks that intentionally print to stdout (note any you skip). 
3. **AC3 — Conditional atexit.** `main_flask_app.py` `atexit.register(cleanup)` must NOT run under pytest (guard with `if 'pytest' not in sys.modules:` or an env check) so test teardown stops emitting "Logging error". App still cleans up normally when run via `python main_flask_app.py`.
4. **AC4 — `.query.get()` → `session.get()`.** Replace all 22 `Model.query.get(id)` with `db.session.get(Model, id)` (SQLAlchemy 2.0 API) across app code. Behavior identical (returns instance or None). Ensure `db` is imported where needed.
5. **AC5 — `datetime.utcnow()` → timezone-aware.** Replace the 4 `datetime.utcnow()` with `datetime.now(datetime.UTC)` (Python 3.11+: `datetime.UTC` exists). Verify no naive/aware comparison breaks (if a stored value is naive, keep consistent — prefer `datetime.now(timezone.utc)` and check the column usage; if it risks aware/naive comparison errors, document and use the minimal safe change).
6. **AC6 — Warning target + green.** Full suite `python -m pytest -p no:randomly -q` → **536 passed, 0 failed, 0 skipped**, and total warnings **< 50** (down from ~1982). `python -c "import main_flask_app"` clean. App boots on 8091; `/login`, `/world/map`, `/dashboard` 200; advance_turn cycle works.

## Tasks
- [ ] Task 1 — RotatingFileHandler in main_flask_app root logging (AC1).
- [ ] Task 2 — Conditional atexit guard (AC3).
- [ ] Task 3 — `.query.get()` → `db.session.get(Model, id)` ×22 (AC4) — biggest warning win.
- [ ] Task 4 — `print()` → logger ×35 in app code (AC2).
- [ ] Task 5 — `utcnow()` → `now(UTC)` ×4 (AC5).
- [ ] Task 6 — pytest 536 green + warnings <50; import clean; boot 8091 (AC6).

## Dev Notes
- Work on the CURRENT main checkout (Alembic/migrations from 11-2 and indexes/theme-cache from 11-3 are already merged — files like `db_initialization.py`, `db_models.py`, `main_flask_app.py`, `turn_processor.py` reflect that). Do not regress those.
- `.query.get()` needs `db` (`from models.db_models import db`) in scope — most files already import it.
- Loggers `royal_succession.<module>`; DB writes try/except+rollback. Stage files explicitly (never `git add .`; never stage `instance/*.db`, `__pycache__`, `*.pyc`, `*.log`).
- This is a mechanical sweep — keep behavior identical; the only observable change is fewer warnings and rotating logs.

## References
- `main_flask_app.py:14` (import atexit), `:25` (FileHandler), `:157` (atexit.register).
- `utils/logging_config.py:70` (existing RotatingFileHandler).
- `.query.get(`: turn_processor + blueprints (22). `print(`: politics/traits/history + blueprints (35). `utcnow(` ×4.

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-11 | spec(11-4); logging + SQLAlchemy 2.0 warnings cleanup |
