# Story 2-1: Project DB Model + Migration

Status: review

## Story

As a developer building the multi-year project system,
I want a `Project` table with the right columns, foreign keys, and relationships in place,
so that Story 2-2 (`project_system.py` core logic) can persist and query projects without any schema work, and so that the existing dev DB at `instance/dynastysim.db` gets the table on first boot.

## Acceptance Criteria

1. **AC1 — `Project` DB model exists in `models/db_models.py`** with the exact column set the master plan prescribes (see Dev Notes for full list). `__tablename__ = 'project'`. The class is suffixed `DB`-free per the master plan's snippet (`class Project(db.Model):`), matching the existing `Building`, `Army`, `War` naming convention rather than the `DynastyDB`/`PersonDB` convention. _Rationale: the master plan code snippet shows the bare name and the analogous Building / Army / War classes are also unsuffixed; suffixing would create an inconsistency._

2. **AC2 — Three person-FKs and two dynasty-FKs are correctly disambiguated.** The `Project` table has 3 FKs to `person_db.id` (`initiated_by_monarch_id`, `completed_by_monarch_id`, `target_person_id`) and 2 FKs to `dynasty.id` (`dynasty_id`, `target_dynasty_id`). Every SQLAlchemy `relationship()` that references the `Project` table from either side uses an explicit `foreign_keys=` argument so SQLAlchemy can resolve the join. No `backref=` is used — `back_populates=` only.

3. **AC3 — `DynastyDB.projects` relationship works as `dynasty.projects.all()`**. Lazy `'dynamic'` (so it returns a query, matching the existing `persons`, `military_units`, etc. pattern). Cascade `'all, delete-orphan'` so deleting a dynasty cleans up its projects. Uses `foreign_keys='Project.dynasty_id'` to disambiguate from `target_dynasty_id`.

4. **AC4 — All resource-cost / count columns have safe defaults.** `yearly_cost_gold`, `yearly_cost_food`, `yearly_cost_iron`, `yearly_cost_timber` default to `0`. `status` defaults to `'active'`. `started_year` and `completion_year` are `nullable=False` (a project that hasn't started doesn't exist as a row). `project_type` is `nullable=False`. Optional FKs (`target_*`, `completed_by_monarch_id`) are `nullable=True`. `params_json` is `Text`, `nullable=True`, with a model helper `get_params()` / `set_params(dict)` that JSON-encodes — mirroring the existing `Building.get_effects()` / `set_effects()` pattern.

5. **AC5 — Migration creates the `project` table on existing deployments.** `models/db_initialization.py` is updated so that on app start, `inspector.get_table_names()` is checked for `'project'`; if missing, the table is created via `Project.__table__.create(db.engine, checkfirst=True)` — mirroring the existing `chronicle_entry` and `loan` table-creation pattern at `db_initialization.py:138-155`. `Project` is added to the import block at the top of the file. The dev DB (`instance/dynastysim.db`) gets the table on next boot without manual intervention.

6. **AC6 — Tests cover model definition + migration.** New unit tests in `tests/unit/test_db_models.py` (extending the existing file) verify:
   - A `Project` row can be created with only the required fields and persisted (defaults populate correctly).
   - All 5 FKs accept valid IDs and reject orphans via the in-memory test DB.
   - `dynasty.projects.all()` returns only projects belonging to that dynasty (not `target_dynasty_id` ones).
   - `params_json` round-trips a dict through `set_params()` / `get_params()`.
   - The full test suite remains green: **pytest must report 222+ passed, 0 failed, 0 skipped** after all changes.

## Tasks / Subtasks

- [x] Task 1: Add `Project` model to `models/db_models.py` (AC1, AC2, AC4)
  - [x] Insert the class definition near other dynasty-owned models (after `Building`, before `TradeRoute` is reasonable). Use existing snippet (Dev Notes) as the template.
  - [x] Add `dynasty_id`, `project_type`, `target_territory_id`, `target_dynasty_id`, `target_person_id`, `params_json`, `started_year`, `completion_year`, 4 × `yearly_cost_*`, `status`, `initiated_by_monarch_id`, `completed_by_monarch_id` columns.
  - [x] Add `__repr__` returning `f"<Project '{self.project_type}' (ID: {self.id}, Dynasty: {self.dynasty_id}, Status: {self.status})>"`.
  - [x] Add `get_params() -> dict` and `set_params(params: dict) -> None` mirroring `Building.get_effects` / `set_effects` pattern (lines 612-618).
  - [x] Add 5 `db.relationship()` lines using explicit `foreign_keys=` (initiator monarch, completer monarch, target person, target dynasty, target territory). All use `back_populates=` (paired with the inverse side; if no inverse is needed yet — e.g., PersonDB doesn't gain a `projects_initiated` collection in this story — use a one-sided relationship without `back_populates`). For clarity, the relationships that DO need an inverse this story are dynasty.projects (AC3).

- [x] Task 2: Add `projects` relationship to `DynastyDB` (AC3)
  - [x] In the existing `DynastyDB` class (`models/db_models.py` line 42), after the `loans` relationship, add:
    ```python
    projects = db.relationship('Project',
                               foreign_keys='Project.dynasty_id',
                               back_populates='dynasty',
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    ```
  - [x] On `Project`, add the matching `dynasty = db.relationship('DynastyDB', foreign_keys=[dynasty_id], back_populates='projects')`.

- [x] Task 3: Migrate the existing dev DB (AC5)
  - [x] In `models/db_initialization.py` line 19, add `Project` to the import block.
  - [x] In `_create_tables_if_not_exist` (line 108), after the existing `loan` block (line 152-155), add:
    ```python
    # Create project table if missing (Sprint 2 Project model)
    if 'project' not in inspector.get_table_names():
        from models.db_models import Project
        Project.__table__.create(db.engine, checkfirst=True)
        self.logger.info("Created project table.")
    ```
  - [x] Verify the dev DB at `instance/dynastysim.db` picks up the new table on next boot by running the Flask app once locally (manual smoke), OR by an integration test that asserts `'project' in inspector.get_table_names()` post-init.

- [x] Task 4: Tests — extend `tests/unit/test_db_models.py` (AC6)
  - [x] Use existing in-memory SQLite fixture pattern from the file.
  - [x] Test: `Project(dynasty_id=d.id, project_type='build_walls', started_year=1300, completion_year=1305)` persists and defaults render (`status == 'active'`, all `yearly_cost_* == 0`).
  - [x] Test: `dynasty.projects.all()` returns this Project; an unrelated Project on a different dynasty does NOT show up; a Project with `target_dynasty_id=dynasty.id` but `dynasty_id != dynasty.id` does NOT show up either (proves foreign_keys disambiguation works).
  - [x] Test: `set_params({'unit_type': 'cavalry', 'count': 50})` then `get_params()` returns the same dict.
  - [x] Test: Deleting the dynasty cascades to delete its projects (verify count goes to 0).
  - [x] Test (in `tests/unit/test_db_models.py` or `tests/integration/`): integration / initialization test that asserts `'project'` appears in `inspector.get_table_names()` after `DatabaseInitializer.initialize_database()` runs against an empty in-memory DB.

- [x] Task 5: Run `pytest`, confirm 222+ passed, 0 failed, 0 skipped (AC6)

- [x] Task 6: Create branch `feature/project-db-model`, commit per Dev Notes commit plan, push.

## Dev Notes

### Files to change

| File | Change type | Description |
|---|---|---|
| `models/db_models.py` | UPDATE | Add `Project` class (~50 LoC); add `projects` relationship to `DynastyDB` (4 LoC) |
| `models/db_initialization.py` | UPDATE | Import `Project`; add 4-line table-creation guard in `_create_tables_if_not_exist` |
| `tests/unit/test_db_models.py` | UPDATE | Add ~6 tests for Project model + dynasty.projects relationship + migration smoke |

### Master plan reference

From `review_documents/8_master_plan_2026.md` lines 160-192 (the canonical `Project` snippet):

```python
class Project(db.Model):
    id = Column(Integer, primary_key=True)
    dynasty_id = Column(ForeignKey('dynasty.id'), nullable=False, index=True)
    project_type = Column(String, nullable=False)
    # 'recruit_unit', 'build_farm', 'build_walls', 'build_cathedral',
    # 'develop_territory', 'march_army', 'arrange_marriage', 'envoy_mission'

    target_territory_id = Column(ForeignKey('territory.id'), nullable=True)
    target_dynasty_id   = Column(ForeignKey('dynasty.id'), nullable=True)
    target_person_id    = Column(ForeignKey('person.id'), nullable=True)
    params_json         = Column(Text)

    started_year     = Column(Integer, nullable=False)
    completion_year  = Column(Integer, nullable=False)

    yearly_cost_gold   = Column(Integer, default=0)
    yearly_cost_food   = Column(Integer, default=0)
    yearly_cost_iron   = Column(Integer, default=0)
    yearly_cost_timber = Column(Integer, default=0)

    status = Column(String, default='active')
    # 'active', 'completed', 'cancelled', 'failed', 'stalled'

    initiated_by_monarch_id = Column(ForeignKey('person.id'))
    completed_by_monarch_id = Column(ForeignKey('person.id'), nullable=True)
```

**CRITICAL translation notes vs the snippet above:**
- The snippet says `ForeignKey('person.id')` — that's wrong for this codebase. The actual `PersonDB` table name is `'person_db'` (verified at `models/db_models.py:144`). Use `db.ForeignKey('person_db.id')` for all three person FKs.
- The snippet uses bare `Column`, `Integer`, `String`, `Text`, `ForeignKey` — this codebase uses `db.Column`, `db.Integer`, etc. (Flask-SQLAlchemy idiom; see existing models). Translate accordingly.
- Add `index=True` on `dynasty_id` (snippet has it) AND consider `index=True` on `status` (frequently filtered by Story 2-2's `get_active_projects(dynasty_id, status='active')`) — but only add the `status` index if it doesn't violate "Don't add features beyond what the task requires" (CLAUDE.md rule). Recommendation: skip the `status` index in this story; add it in Sprint 11 perf pass (`11-3-performance-optimizations` already lists this).

### Circular FK consideration

Three of the FKs target `person_db.id`. `DynastyDB` already uses `use_alter=True` for its `founder_person_db_id` FK because `DynastyDB.persons` cascades and creates a circular dependency between table creation orders (see `models/db_models.py:59-61`).

**The Project table itself does NOT create a new cycle:**
- `Project.dynasty_id` → `dynasty.id` — fine (dynasty already exists at create time)
- `Project.initiated_by_monarch_id` → `person_db.id` — fine (person_db already exists)
- `Project.target_*` — all fine (all targets exist by the time project is created)
- `DynastyDB.projects` is a one-way collection cascading TO projects, not from a Project FK BACK TO dynasty in a way that recreates the founder-cycle problem.

**Therefore: do NOT add `use_alter=True` to any of the new Project FKs.** Use plain `db.ForeignKey('table.id')`. If `db.create_all()` errors during the integration test with a metadata-ordering issue, THEN reconsider — but the analogy with `Building.territory_id` (no use_alter needed) suggests it'll be fine.

### Relationship pattern reference

Look at `DynastyDB.battles_won` (line 123-126) as the cleanest pattern for the dynasty-side `projects` relationship (uses `foreign_keys=` and `back_populates`). Look at `MilitaryUnit` (around line 700) for the person-side pattern.

For the Project class, the relationships needed are:
```python
# Inside Project class
dynasty = db.relationship('DynastyDB', foreign_keys=[dynasty_id], back_populates='projects')
target_territory = db.relationship('Territory', foreign_keys=[target_territory_id])
target_dynasty = db.relationship('DynastyDB', foreign_keys=[target_dynasty_id])
target_person = db.relationship('PersonDB', foreign_keys=[target_person_id])
initiator_monarch = db.relationship('PersonDB', foreign_keys=[initiated_by_monarch_id])
completer_monarch = db.relationship('PersonDB', foreign_keys=[completed_by_monarch_id])
```

Only the `dynasty` relationship uses `back_populates` (paired with `DynastyDB.projects`). The four `target_*` and two `*_monarch` relationships are one-sided (no inverse collection on the target side needed in this story — Sprint 2-2's `start_project` and friends only need to walk from Project → target_x, not target_x → projects). If reverse navigation is ever needed, add `back_populates` then.

### What this story does NOT touch (scope boundaries)

- `models/project_system.py` — does NOT exist yet; that's **Story 2-2**.
- `models/turn_processor.py` — no changes. Calling into `tick_projects` is **Story 2-3**.
- `blueprints/dynasty.py` `submit_actions` migration — **Story 2-3**.
- `Building.is_under_construction` replacement — **Story 2-3**. Leave the existing flag intact.
- Any UI / template changes for project slots — **Sprint 3** (Epic 3).
- LLM-narrated multi-generation completion chronicle entry — **Story 2-4**.
- Adding `status` index, `(dynasty_id, status, completion_year)` composite index, etc. — **Story 11-3**.

### `is_under_construction` is staying for now

The existing `Building.is_under_construction` machinery in `models/economy_system.py` (lines 639, 748, 784, 815) is still live. Sprint 2-3 will replace it with active `Project` rows. This story should NOT touch it. Just be aware that some test data fixtures may still create buildings with `is_under_construction=True`; that remains the canonical path until 2-3 ships.

### Snippet says `'person.id'` — DO NOT use that table name

The master plan snippet (line 172, 188-189) uses `ForeignKey('person.id')`. That table does NOT exist. The Person table is `person_db` (verified `models/db_models.py:144`). All three person FKs MUST use `db.ForeignKey('person_db.id')`.

### Test fixture quick-reference

Existing patterns in `tests/unit/test_db_models.py` should be reused — same `app` / `db` / `session` fixtures (per `_bmad-output/project-context.md` lines 76-79):
- `app` — session-scoped
- `db` — session-scoped, schema created once
- `session` — function-scoped, drops + recreates tables per test (correct isolation)

Theme key for any dynasty fixture: `VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'`.

### Why default parameter values (none here — none needed)

Unlike Story 1-4, this story doesn't change function signatures, so backward-compat defaults aren't relevant. Just the SQLAlchemy `default=` on Column definitions per AC4.

### Sprint 2 acceptance criteria — what 2-1 enables

Sprint 2's three acceptance criteria from master plan line 226-228 are:
1. Starting a 5-year project, then advancing 2 turns, shows completion at the right calendar year. ← **Story 2-2 / 2-3**
2. Cancelling a half-built project refunds 50% of resources. ← **Story 2-2**
3. A project started by a monarch who dies before completion shows both names in the chronicle entry. ← **Story 2-4**

This story (2-1) is the schema foundation. None of those three end-user criteria are testable until 2-2/2-3/2-4 ship.

### Branch name

`feature/project-db-model`

### Commit plan

- Commit 1: `feat(db): add Project model with FKs to dynasty/person/territory`
- Commit 2: `feat(db): add DynastyDB.projects relationship with foreign_keys disambiguation`
- Commit 3: `feat(db-init): create project table on app start for existing deployments`
- Commit 4: `test(db-models): unit tests for Project model, dynasty.projects, cascade, params_json`

### Scope boundaries

- **In scope:** `models/db_models.py` (Project class + DynastyDB.projects relationship), `models/db_initialization.py` (import + migration guard), `tests/unit/test_db_models.py` (new tests).
- **Out of scope:** business logic (Story 2-2), turn-processor wiring (Story 2-3), action migration (Story 2-3), chronicle hook (Story 2-4), UI (Sprint 3), performance indexes (Story 11-3).
- **Out of scope:** Building.is_under_construction removal (Story 2-3 will replace it; leave intact).

### References

- Master plan: `review_documents/8_master_plan_2026.md` lines 153-232 (Sprint 2 — Project model)
- Project type catalogue: `review_documents/8_master_plan_2026.md` lines 194-211
- Current `DynastyDB`: `models/db_models.py` lines 42-139
- Current `PersonDB` (`person_db` table name): `models/db_models.py` line 144
- Current `Building` (pattern reference): `models/db_models.py` lines 587-621
- Circular FK use_alter pattern: `models/db_models.py` lines 59-61
- Migration guard pattern: `models/db_initialization.py` lines 138-155
- Banking story precedent (also added a new table): `_bmad-output/implementation-artifacts/` (Loan model)
- Project rules: `_bmad-output/project-context.md` (especially DB error handling, naming, FK rules at lines 40-44 and 127-132)
- Sprint context: `_bmad-output/implementation-artifacts/sprint-status.yaml` lines 76-103

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (bmad-dev-story workflow, direct execution)

### Implementation Plan

1. Inserted `Project` class in `models/db_models.py` between `Building` and `TradeRoute` per the spec snippet (with `db.Column` Flask-SQLAlchemy idiom and `person_db.id` correction noted in Dev Notes).
2. Added `DynastyDB.projects` relationship with `foreign_keys='Project.dynasty_id'` disambiguation, `lazy='dynamic'`, `cascade='all, delete-orphan'`.
3. On the `Project` side: `dynasty` relationship with `back_populates='projects'`; four one-sided relationships for the targets and the two monarch FKs.
4. Updated `models/db_initialization.py`: added `Project` to the imports; added a 4-line migration guard after the existing `loan` block to create the `project` table on existing deployments.
5. Added `TestProjectModel` (7 tests) to `tests/unit/test_db_models.py`, plus a shared `_make_user_and_dynasty` helper.

### Completion Notes

- All 6 ACs satisfied; all 6 tasks (and their subtasks) checked.
- Sanity-checked `Project.__table__.columns` after edit — all 16 columns present.
- `pytest tests/unit/test_db_models.py::TestProjectModel` → 7 passed.
- Full regression suite: **229 passed, 0 failed, 0 skipped** (baseline was 222; +7 from this story).
- The SAWarning about FK cycle `dynasty / person_db / territory` is pre-existing (already present before this story), caused by the dynasty↔territory↔person_db founder/capital relationships, not by anything Project adds. Project's FKs are all one-way OUT to other tables.
- No `use_alter=True` was needed on any of the new Project FKs (anticipated in Dev Notes — confirmed by clean test run).
- Scope held: no business logic, no turn-processor wiring, no `Building.is_under_construction` removal, no UI, no LLM hooks. All deferred to Stories 2-2 / 2-3 / 2-4.

### File List

- `models/db_models.py` — MODIFIED (new `Project` class ~45 LoC inserted between `Building` and `TradeRoute`; new `DynastyDB.projects` relationship 5 LoC)
- `models/db_initialization.py` — MODIFIED (`Project` added to imports; 4-line migration guard for the `project` table)
- `tests/unit/test_db_models.py` — MODIFIED (added `Project` to imports; added `_make_user_and_dynasty` helper; added `TestProjectModel` class with 7 tests)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED (epic-2: backlog → in-progress; 2-1 status: backlog → ready-for-dev → in-progress → review)
- `_bmad-output/implementation-artifacts/2-1-project-db-model.md` — MODIFIED (status updates, Dev Agent Record sections populated)

### Change Log

| Date | Change |
|---|---|
| 2026-05-16 | feat(db): add Project model with FKs to dynasty/person/territory |
| 2026-05-16 | feat(db): add DynastyDB.projects relationship with foreign_keys disambiguation |
| 2026-05-16 | feat(db-init): create project table on app start for existing deployments |
| 2026-05-16 | test(db-models): unit tests for Project model, dynasty.projects, cascade, params_json |
| 2026-05-16 | pytest: 229 passed, 0 failed, 0 skipped |
| 2026-05-16 | Story status → review |
