# Story 11-3: Performance Optimizations

Status: ready-for-dev

## Story
As a **developer keeping turn processing fast as dynasties grow**, I want **N+1 query elimination, theme-config caching, and composite DB indexes**, so that **turn advancement and hot read paths scale without redundant queries or full-table scans.**

## Acceptance Criteria
1. **AC1 — N+1 kill in turn_processor.** In `models/turn_processor.py`, the per-person loops (e.g. `living_persons = PersonDB.query.filter_by(...).all()` ~:116, and the death/marriage/lifecycle passes) access PersonDB relationships per row. Add eager loading (`joinedload`/`selectinload` from `sqlalchemy.orm`) ONLY for relationships demonstrably accessed inside a loop. Be conservative — do not eager-load relationships that aren't iterated. Behavior must be identical (same results); this is purely fewer queries.
2. **AC2 — Theme-config cache.** The block that derives `theme_config` from `dynasty.theme_identifier_or_json` (via `get_theme()` / `json.loads()`) is duplicated and recomputed every request in `blueprints/economy.py:35-44` and `blueprints/dynasty.py`. Add a memoized helper (e.g. `utils/theme_manager.get_dynasty_theme_config(dynasty)`) cached per `(dynasty.id, theme_identifier_or_json)` so re-parsing is skipped on repeat reads. Use it at both call sites. Cache must invalidate when the theme string changes (key includes it). Do NOT cache mutable ORM objects — cache the plain dict.
3. **AC3 — Composite indexes (via Alembic).** `HistoryLogEntryDB` already has single-col indexes on `dynasty_id` and `year`; add a COMPOSITE `db.Index('ix_history_dynasty_year', 'dynasty_id', 'year')` via `__table_args__` (the hot query filters `dynasty_id` + orders by `year`, `turn_processor.py:369-373`). `Project`: add composite `db.Index('ix_project_dynasty_status_completion', 'dynasty_id', 'status', 'completion_year')`. Keep existing single-col indexes.
4. **AC4 — Migration.** These index additions are schema changes. Generate an Alembic migration via the 11-2 workflow: `export FLASK_APP=main_flask_app.py && flask db migrate -m "11-3 composite indexes"`. HAND-REVIEW the generated file: it must `create_index` the two new composite indexes and NOTHING else (no spurious drops/recreates from SQLite autogen). Verify `flask db upgrade` applies on a fresh DB AND that a fresh-DB upgrade schema still equals `create_all()` (the indexes exist in both).
5. **AC5 — No regressions.** Full suite green (baseline 536 passed, 0 failed, 0 skipped). `python -c "import main_flask_app"` clean. App boots on 8091; `/dashboard`, `/world/map`, a `/dynasty/<id>/view` + advance_turn cycle all work.

## Tasks
- [ ] Task 1 — joinedload/selectinload in turn_processor per-person loops (AC1).
- [ ] Task 2 — `get_dynasty_theme_config()` memoized helper + use in economy.py & dynasty.py (AC2).
- [ ] Task 3 — composite indexes on HistoryLogEntryDB + Project models (AC3).
- [ ] Task 4 — `flask db migrate` for the indexes; hand-review; verify upgrade==create_all (AC4).
- [ ] Task 5 — pytest 536 green; import clean; app boots 8091 (AC5).

## Dev Notes
- Migration workflow is now Alembic/Flask-Migrate (Story 11-2 — see CLAUDE.md "Database Migrations"). NEVER hand-write ALTER TABLE. `render_as_batch=True` already set in `migrations/env.py`.
- Index additions: models are source of truth; `create_all()` (tests) will include them automatically, and the migration adds them to existing DBs — both must agree.
- Don't rewrite working subsystems; `turn_processor` changes are query-shape only, not logic. `.query.get()→session.get()` and datetime/logging cleanups are Story 11-4 — OUT OF SCOPE here (avoid touching them to prevent merge conflicts with 11-4).
- Loggers `royal_succession.<module>`; no `print()`; DB writes try/except+rollback; stage files explicitly (never `git add .`; never stage `instance/*.db`); commit the new `migrations/versions/*.py`.

## References
- `models/turn_processor.py:116,123,369-373,425,459,571-591` (PersonDB loops/queries).
- `blueprints/economy.py:35-44`, `blueprints/dynasty.py:130-159` (theme_config derivation).
- `models/db_models.py` HistoryLogEntryDB (~:288) + Project (existing `dynasty_id index=True`).
- CLAUDE.md "Database Migrations (Alembic / Flask-Migrate)".

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-11 | spec(11-3); perf optimizations (joinedload, theme cache, composite indexes) |
