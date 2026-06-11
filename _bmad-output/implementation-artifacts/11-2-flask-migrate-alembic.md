# Story 11-2: Flask-Migrate / Alembic Adoption

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer maintaining the Royal Succession schema**,
I want **the ad-hoc, hand-rolled `ALTER TABLE` migration logic in `models/db_initialization.py` replaced by Flask-Migrate / Alembic with an initial migration that captures the current schema**,
so that **future schema changes are versioned, reviewable, ordered, and reproducible — instead of relying on idempotent `ADD COLUMN` snippets and a home-grown `db_version` integer that every agent must remember to extend.**

## Context & Problem

Today the schema evolves through **two parallel home-grown mechanisms** inside `models/db_initialization.py`, both run at app startup from `main_flask_app.py` (`if __name__ == '__main__'` block, `main_flask_app.py:258-289`):

1. **`_create_tables_if_not_exist()`** (`db_initialization.py:108-204`) — after `db.create_all()`, it inspects each table and fires guarded one-off `ALTER TABLE ... ADD COLUMN` statements for columns added over time (`dynasty.epic_story_text`, `designated_heir_id`, `succession_law`, `family_tree_svg`; `person_db.is_pretender`, `pretender_strength`, `has_seen_majority`), plus `create_all`-style creation of newer tables (`chronicle_entry`, `loan`, `project`, `marriage_offer`).
2. **Versioned path** — `perform_migrations()` (`:456`) reads a `db_version` row via `_get_db_version()` (`:489`), and if `< 1` runs `_migrate_from_v0_to_v1()` (`:585`) which `ALTER TABLE`s in the prestige/infamy/honor/piety/skill/history-FK columns, then `_set_db_version(1)` (`:570`).

This is exactly the "Schema changes require migration … Do not rely on `db.create_all()` for schema evolution" rule in `project-context.md` — but implemented by hand. It is fragile: column order/defaults drift between `db.create_all()` (used by tests) and the live dev DB (built by accreted ALTERs), there is no down-migration, no history, and adding a column means editing two methods plus bumping an integer.

**This story replaces that machinery with Alembic (via Flask-Migrate),** generates one initial migration reflecting the live ORM models as the baseline, stamps the existing dev DB to that baseline, and documents the workflow.

## Acceptance Criteria

1. **AC1 — Dependencies.** Add `Flask-Migrate` (which pulls `alembic`) to `requirements.txt` (pin a current stable version, e.g. `Flask-Migrate>=4.0`). Install into `.venv`. No other new runtime deps.

2. **AC2 — Wire Flask-Migrate into the app.** Initialize `Migrate(app, db)` in `main_flask_app.py` **app-setup region only** (next to `db_initializer = DatabaseInitializer(app)` at `main_flask_app.py:79`) — this is within the allowed "app setup + blueprint registration" scope for that file and keeps it ≤ ~300 lines. Do **not** add route handlers or business logic.

3. **AC3 — Migrations scaffold + initial migration.** Run `flask db init` to create the `migrations/` directory, then `flask db migrate -m "baseline: current schema"` to autogenerate the **initial migration that reflects the current ORM models** in `models/db_models.py` (all tables incl. `dynasty`, `person_db`, `chronicle_entry`, `loan`, `project`, `marriage_offer`, history FKs, and the prestige/infamy/honor/piety/skill columns). Review the generated migration: it must `create_table` every model table with the columns the ORM declares — **inspect for and remove any spurious drops/renames** autogen invents from SQLite quirks (SQLite reports limited type/constraint info; circular `use_alter` FKs between `dynasty`↔`person_db` need `op.create_foreign_key(..., use_alter)`/batch handling — verify these render correctly). Configure `FLASK_APP` discovery (Flask-Migrate needs an app context — document the `FLASK_APP=main_flask_app.py` env or add a tiny `flask db` entrypoint note).

4. **AC4 — Stamp the existing dev DB.** The live `instance/dynastysim.db` already has the full schema (built by the old ALTERs). It must **not** be rebuilt. Run `flask db stamp head` against it so Alembic records the baseline revision in a new `alembic_version` table **without** re-running DDL. Document this one-time step (devs with an existing DB stamp; fresh DBs run `flask db upgrade`). Confirm the dev DB still opens and the app runs (port 8091) afterward.

5. **AC5 — Retire the ad-hoc migration logic (carefully, no behavior regression).**
   - Remove the hand-rolled `ALTER TABLE` blocks from `_create_tables_if_not_exist()` (`:139-197`) and the entire versioned path (`perform_migrations()`, `_get_db_version()`, `_set_db_version()`, `_migrate_from_v0_to_v1()`) **OR** make them no-ops that defer to Alembic — pick deletion; keep the diff explicit.
   - Update the `main_flask_app.py` bootstrap (`:258-289`): replace the `perform_migrations()` call with `flask db upgrade` semantics — i.e. call `upgrade()` from Flask-Migrate / Alembic config programmatically at startup (or document that `flask db upgrade` is the deploy step and have bootstrap no longer hand-migrate). **Keep `initialize_database()`'s non-migration duties** (dir/permission setup, `_initialize_default_resources()`, integrity check) — only the schema-evolution ALTERs leave.
   - The `db_version`/`alembic_version` distinction: the old `db_version` table is dead after this; leave it in place on existing DBs (harmless) but stop reading/writing it.

6. **AC6 — `db.create_all()` test path must keep working unchanged.** Tests build schema via `mfa.db.create_all()` / `db.drop_all()` in `tests/conftest.py`, `tests/integration/conftest.py`, `tests/functional/conftest.py` — they do **NOT** go through Alembic. This story must **not** route tests through migrations (no `flask db upgrade` in conftest). `create_all()` from the ORM metadata stays the test schema source. Verify the ORM models still fully define every column the old ALTERs used to add (they must already — the ALTERs were catch-up for old DBs; the models are the source of truth). If any column the ALTERs added is **missing from `models/db_models.py`**, that is a latent bug — surface it, add the column to the model so `create_all()` and the Alembic baseline agree (do not silently rely on ALTER).

7. **AC7 — Document the workflow in CLAUDE.md.** Add a short "Database Migrations (Alembic / Flask-Migrate)" subsection: how to create a migration (`flask db migrate -m "..."`), apply (`flask db upgrade`), the `FLASK_APP` requirement, the one-time `flask db stamp head` for pre-existing DBs, and the rule "schema change → new model field + `flask db migrate`; never hand-write `ALTER TABLE` in `db_initialization.py` again." Replace/append the existing "Do not change the DB schema without a migration in `db_initialization.py`" line accordingly. Also reflect in `project-context.md` (the migration rule at line ~130).

8. **AC8 — No regressions.** Full suite green (baseline **536 passed**, 0 failures, 0 skipped). `python -c "import main_flask_app"` imports clean. App boots on 8091, `instance/dynastysim.db` opens with stamped baseline, and `/world/map`, `/dashboard`, `/dynasty/<id>/view`, an `advance_turn` cycle all work. `migrations/` is committed; the SQLite dev DB and `alembic_version` data are **not** committed (already gitignored / instance/). No tests skipped without an inline reason.

## Tasks / Subtasks

- [ ] **Task 1 — Add dep + wire Migrate (AC1, AC2).**
  - [ ] Add `Flask-Migrate>=4.0` to `requirements.txt`; `pip install -r requirements.txt` in `.venv`.
  - [ ] In `main_flask_app.py` app-setup region (~`:79`): `from flask_migrate import Migrate` and `migrate = Migrate(app, db)`. Confirm `main_flask_app.py` stays ≤ ~300 lines.
- [ ] **Task 2 — Scaffold + baseline migration (AC3).**
  - [ ] `export FLASK_APP=main_flask_app.py`; `flask db init`.
  - [ ] `flask db migrate -m "baseline: current schema"`; open the generated file under `migrations/versions/`.
  - [ ] Hand-review: every ORM table present, no spurious DROP/ALTER from SQLite autogen noise, circular `dynasty`↔`person_db` FKs (`use_alter`) handled (batch ops if needed). Edit the migration until `flask db upgrade` on a **fresh empty SQLite file** reproduces the exact `create_all()` schema.
- [ ] **Task 3 — Stamp existing dev DB (AC4).**
  - [ ] Back up `instance/dynastysim.db` first. `flask db stamp head`. Confirm `alembic_version` row exists and no table data lost. App boots on 8091.
- [ ] **Task 4 — Retire ad-hoc logic (AC5, AC6).**
  - [ ] Verify each old-ALTER column exists in `models/db_models.py`; add any missing one to the model (so `create_all` + baseline agree).
  - [ ] Delete the ALTER blocks in `_create_tables_if_not_exist()` and the whole `perform_migrations`/`_get_db_version`/`_set_db_version`/`_migrate_from_v0_to_v1` path. Keep dir/permission/default-resource/integrity logic.
  - [ ] Update `main_flask_app.py:258-289` bootstrap: drop `perform_migrations()` call; apply migrations via Alembic `upgrade()` at startup OR document `flask db upgrade` as the deploy step. Keep `initialize_test_user()` / `backfill_coat_of_arms()` / theme load intact.
- [ ] **Task 5 — Docs (AC7).** CLAUDE.md migrations subsection + project-context.md rule update.
- [ ] **Task 6 — Verify (AC8).** `pytest` → 536 passed / 0 failed / 0 skipped. `python -c "import main_flask_app"`. Boot app, smoke `/world/map`, `/dashboard`, `/dynasty/<id>/view`, advance_turn. Confirm `migrations/` staged, DB files not staged.

## Dev Notes

### Current state of files being modified (READ BEFORE EDITING)
- **`models/db_initialization.py`** (696 lines). `DatabaseInitializer` class. Schema-evolution surface to retire:
  - `_create_tables_if_not_exist()` `:108-204` — `db.create_all()` (keep for fresh DBs) + guarded `ALTER TABLE` catch-up (`:139-197`, remove) for `dynasty`/`person_db` columns and `chronicle_entry`/`loan`/`project`/`marriage_offer` table creation.
  - `perform_migrations()` `:456-487`, `_get_db_version()` `:489-568`, `_set_db_version()` `:570-583`, `_migrate_from_v0_to_v1()` `:585-696` — the versioned `db_version` path. Remove entirely.
  - **Keep**: `initialize_database()` orchestration minus the migration call, `_check_database_integrity()` `:206`, `_fix_database_issues()` `:268`, `_initialize_default_resources()` `:351`, the SQLite dir/permission setup `:62-87`.
- **`main_flask_app.py`** — `DatabaseInitializer` imported `:43`, instantiated `:79`; bootstrap calls `initialize_database()` `:263` + `perform_migrations()` `:268` inside `if __name__=='__main__'` `:258`. Add `Migrate(app, db)` near `:79`; rework the bootstrap migration call. App-setup-only scope; keep ≤ ~300 lines.
- **`models/db_models.py`** — the ORM source of truth (imports listed in `db_initialization.py:15-20`). The Alembic baseline must equal `db.create_all()` from this metadata. Circular `use_alter=True` FK between `DynastyDB`↔`PersonDB` (see project-context rule) — autogen must render this correctly.

### Why this is subtle (the trap)
- **Tests never touch migrations** — they `create_all()` from ORM metadata (`tests/conftest.py`, `tests/integration/conftest.py:20,38`, `tests/functional/conftest.py:16,34`). So the regression risk is NOT in tests; it is in the **live dev DB** and **fresh-DB bootstrap**. The baseline migration's job is to make a fresh empty DB match `create_all()`, and `stamp head` makes the existing DB agree without DDL.
- **SQLite autogenerate is lossy.** Alembic on SQLite under-reports types, server defaults, and constraints; autogen frequently proposes phantom `ALTER`/`DROP`. Hand-review the baseline. Use Alembic **batch mode** (`render_as_batch=True` in `migrations/env.py`) so future SQLite `ALTER`s work (SQLite can't drop/alter columns natively).
- **Model-vs-ALTER drift check (AC6):** the old ALTERs existed to retrofit columns onto *old* DBs. The ORM models should already declare all of them. If one is missing from the model, `create_all()` (and thus tests + baseline) silently lacks it while the live DB has it — fix the model, don't preserve the ALTER.

### Reuse / project rules (from project-context.md)
- DB writes in `try/except` + rollback; loggers `royal_succession.<module>`; no `print()`; `back_populates` not `backref`; circular FK `use_alter=True, name='fk_...'`; `__tablename__` explicit. New dep → update `requirements.txt`. Stage files explicitly (never `git add .`); never commit `instance/dynastysim.db`. Branch: `refactor/flask-migrate-alembic` (or `infra/...`). Conventional commits; `git merge --no-ff`; run `pytest` before merge; update `STATUS.md`.

### Out of scope / deferred
- Perf indexes (Story 11-3). Logging/`RotatingFileHandler` + SQLAlchemy warnings + `session.get()`/`datetime.now(UTC)` (Story 11-4). The `Building.is_under_construction`/`completion_year` phantom-column construction bug (separate, pre-existing — see memory `construct-building-phantom-columns-bug`; do **not** try to "fix" it via the baseline, but the baseline must reflect whatever the model actually declares). Matplotlib full removal (separate).

## Previous Story Intelligence (from 11-1)
- 11-1 (dead-code retirement) was a single coordinated main-session pass — this story is similar: the migration scaffold, the ad-hoc-logic deletion, and the bootstrap rewire are coupled and must land together, gated by the full suite. No parallel worktree agents needed.
- 11-1's lesson: **the plan's assumptions can be stale vs. the live code** ("dead" placeholder routes were actually linked from `base.html` → 72 failures). Apply the same caution here: before deleting `perform_migrations()`, grep for any *other* caller besides `main_flask_app.py:268` (e.g. tests, scripts). Baseline test count after 11-1: **536 passed**. Tests run with a temp DB; `python -m pytest -p no:randomly -q`.
- Memory `multi-agent-and-verification-workflow`: mandatory run-the-app check — boot on **port 8091** and confirm the dev DB opens after stamping before declaring done.

## References
- `models/db_initialization.py`: `_create_tables_if_not_exist` `:108-204` (ALTERs `:139-197`), `perform_migrations` `:456`, `_get_db_version` `:489`, `_set_db_version` `:570`, `_migrate_from_v0_to_v1` `:585`.
- `main_flask_app.py`: import `:43`, instantiate `:79`, bootstrap `:258-289` (`initialize_database` `:263`, `perform_migrations` `:268`).
- `models/db_models.py` (ORM source of truth; imports at `db_initialization.py:15-20`).
- Test schema path: `tests/conftest.py`, `tests/integration/conftest.py:20,38`, `tests/functional/conftest.py:16,34`.
- Rule: `project-context.md` "Schema changes require migration" `:130`; CLAUDE.md "Do not change the DB schema without a migration".
- sprint-status.yaml: `11-2-flask-migrate-alembic` (epic-11 in-progress).

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m]

### Debug Log References

### Completion Notes List

### File List

### Change Log
| Date | Change |
|---|---|
| 2026-06-11 | spec(11-2); Flask-Migrate/Alembic adoption story drafted (ready-for-dev) |
