# Story 5-3: Pretender Mechanics

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the dynasty's story unfolds,
I want heirs who are passed over for the throne to become pretenders whose claim grows stronger over time,
so that a contested succession plants a future threat (the seed for civil-war drama in Story 5-4).

Builds on Story 5-1 (`succession_choice`, `_default_candidate_id`, `crown_heir`). **Backend-only** — no UI surface in 5-3 (pretender threat is surfaced/acted-on in 5-4).

## Acceptance Criteria

1. **AC1 — Schema: two `PersonDB` columns + migration.** Add to `PersonDB` (`models/db_models.py`, after `reign_start_year` ~:193):
   - `is_pretender = db.Column(db.Boolean, default=False, nullable=False)`
   - `pretender_strength = db.Column(db.Integer, default=0, nullable=False)`
   Add an idempotent migration in `models/db_initialization.py` mirroring the existing `ALTER TABLE … ADD COLUMN` pattern (dynasty cols at :145-159; there's already a `person_db` column-inspection block ~:471): inspect `person_db` columns and `ALTER TABLE person_db ADD COLUMN is_pretender BOOLEAN DEFAULT 0` / `ADD COLUMN pretender_strength INTEGER DEFAULT 0` if missing. (Tests get the columns via `create_all`.)

2. **AC2 — Pretender accumulation in the lifecycle tick (`models/turn_processor.py`).** In `process_dynasty_turn`'s per-person yearly loop (the `for person in living_persons:` block ~:149-170), for each LIVING person with `is_pretender` truthy, increment `person.pretender_strength` by a fixed module constant `PRETENDER_STRENGTH_PER_YEAR` (define it, e.g. `5`) once per simulated year. Deterministic; do this without disturbing the death/marriage/childbirth checks already there (e.g. add it for non-dead persons each year). A dead person stops accumulating (they're skipped / removed from `living_persons`).

3. **AC3 — Choosing a non-default heir flags the bypassed default as a pretender (`blueprints/dynasty.py` `succession_choice`).** After `crown_heir(...)` succeeds (~:1253) and before the commit: compute `default_id = _default_candidate_id(dynasty, candidates)` (the helper at :1118). If the chosen `heir_id != default_id` AND a distinct default candidate exists, set that bypassed default candidate's `is_pretender = True` and give it a starting `pretender_strength` (module/blueprint constant, e.g. `10`), and append ONE `HistoryLogEntryDB(dynasty_id, year=deceased.death_year, event_string="<name>, passed over for the crown, nurses a rival claim.", event_type='pretender_claim', person1_sim_id=<bypassed>.id)`. If the chosen heir IS the default, no pretender is created. Keep the single commit + existing try/except/rollback; `{ok, message}` shape unchanged.

4. **AC4 — No regressions.** Full suite green (baseline **347**; new tests additive). 5-1/5-2 succession + coronation behavior preserved (crowning the default heir creates no pretender; the candidate JSON shape is unchanged — `is_pretender`/`pretender_strength` are NOT added to the candidate serialization in 5-3).

5. **AC5 — ≥5 new integration tests** (`tests/integration/test_pretender.py`, fixture pattern from `tests/integration/test_succession.py`):
   - The two new columns exist and default to `False`/`0` on a freshly created `PersonDB`.
   - Choosing a **non-default** heir via `succession_choice` flags the bypassed default candidate `is_pretender=True` with `pretender_strength > 0`, and writes a `pretender_claim` history entry.
   - Choosing the **default** heir creates NO pretender (no person flagged, no `pretender_claim` entry).
   - Accumulation: a living `is_pretender` person's `pretender_strength` increases after advancing the turn (call `process_dynasty_turn` / `advance_turn` and assert the strength grew by `PRETENDER_STRENGTH_PER_YEAR × years`). Mock `process_death_check` to keep the pretender alive if needed.
   - A DEAD pretender does not keep accumulating.

6. **AC6 — No visual check needed** — 5-3 has no UI surface (pretenders are data only; they surface in 5-4). Tests are the verification.

## Tasks / Subtasks
- [ ] Task 1 — Schema + migration + accumulation (`models/db_models.py`, `models/db_initialization.py`, `models/turn_processor.py`). [Agent A]
- [ ] Task 2 — Non-default-heir pretender flagging (`blueprints/dynasty.py`). [Agent B]
- [ ] Task 3 — Tests (`tests/integration/test_pretender.py`). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `models/db_models.py` (+2 PersonDB cols), `models/db_initialization.py` (migration), `models/turn_processor.py` (`PRETENDER_STRENGTH_PER_YEAR` + accumulation in the per-person loop).
- **Agent B** — `blueprints/dynasty.py` only (`succession_choice` flagging).
- **Agent C** — ONLY `tests/integration/test_pretender.py`. Contract-first.
- No shared files. (A owns models/*; B owns the blueprint; C the new test.)

### FROZEN INTERFACE CONTRACT
- `PersonDB.is_pretender` (Boolean, default False, not null) + `PersonDB.pretender_strength` (Integer, default 0, not null); idempotent `ALTER TABLE person_db` migration.
- `turn_processor.PRETENDER_STRENGTH_PER_YEAR` (int, e.g. 5); each simulated year, every living `is_pretender` person's `pretender_strength += PRETENDER_STRENGTH_PER_YEAR`.
- `succession_choice`: when `heir_id != _default_candidate_id(...)` and a distinct default exists → bypassed default `is_pretender=True`, `pretender_strength = 10` (starting), + a `HistoryLogEntryDB(event_type='pretender_claim', person1_sim_id=<bypassed>.id)`. Choosing the default → no pretender. `{ok,message}` unchanged; candidate JSON unchanged.

### Reuse / project rules
- Migration via the idempotent `ALTER TABLE … ADD COLUMN` pattern (NOT create_all for schema evolution) — `models/db_initialization.py:145-159`. DB models suffixed `DB`. DB writes guarded; route owns commit/rollback. No new deps. Don't touch GameManager AI flow. B's flagging sets attributes on the model; in B's isolated worktree the columns don't exist yet (assigning an unmapped attr is harmless) — they land on integration with A.

### Out of scope / deferred
- **Civil-war interrupt when pretender_strength crosses a threshold, and heir-majority interrupts → Story 5-4.** Surfacing pretenders in the UI → 5-4. 5-3 is data + accumulation + flagging only.

## Previous Story Intelligence
- Worktree contract-first flow via the **Workflow tool** (5-2 ran clean this way). Agents default to plan mode → "EXECUTE NOW, pre-approved, no EnterPlanMode" per prompt; worktrees branch off `main`; contract inlined. (5-2 quirk: an agent's Edit tool can resolve against the main working copy — integrator verifies the main tree is clean before merging.)
- `pytest` runs against an isolated temp DB rebuilt per run (schema picked up). Baseline 347. Known `test_military_routes` ordering flake (unrelated).
- 5-1/5-2 delivered `succession_candidates_json`/`succession_choice`/`crown_heir`/`_default_candidate_id` + candidate flavor + coronation entry.

## References
- `PersonDB` columns: `models/db_models.py:188-193`. Migration pattern: `models/db_initialization.py:145-159` (dynasty), person_db inspection ~:471.
- Lifecycle per-person loop: `models/turn_processor.py:149-170`.
- `succession_choice` + `_default_candidate_id` + `crown_heir` call: `blueprints/dynasty.py:1222`, `:1118`, `:1253`.
- Test fixtures: `tests/integration/test_succession.py`, `tests/integration/test_detail_panel_render.py:13-39`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool (run `wf_3bb61336-c69`), + main-session integrator.

### Completion Notes List

- All ACs satisfied. `pytest -p no:randomly`: **352 passed, 0 failed** (347 baseline + 5). Contract-first: C's 5 tests failed in isolation (missing columns/constant), green on integration. Backend-only → no visual check.
- A `wt/5-3-backend` (`b7f43cb`): `PersonDB.is_pretender`/`pretender_strength` + idempotent `person_db` migration; `PRETENDER_STRENGTH_PER_YEAR=5`; accumulation in the per-person yearly loop (living pretenders only; dead skip). B `wt/5-3-flagging` (`ef44aff`): `succession_choice` flags the bypassed default heir (`is_pretender=True`, `pretender_strength=10`) + a `pretender_claim` history entry when a non-default heir is crowned (`PRETENDER_START_STRENGTH=10`). C `wt/5-3-tests` (`e56d33e`): 5 tests. Clean merges, zero file overlap.
- 5-1/5-2 preserved: crowning the default heir creates no pretender; candidate JSON unchanged.

### File List

- `models/db_models.py` — MODIFIED (PersonDB +is_pretender/+pretender_strength)
- `models/db_initialization.py` — MODIFIED (idempotent person_db migration)
- `models/turn_processor.py` — MODIFIED (`PRETENDER_STRENGTH_PER_YEAR` + yearly accumulation)
- `blueprints/dynasty.py` — MODIFIED (`succession_choice` bypassed-default flagging + `pretender_claim` log)
- `tests/integration/test_pretender.py` — NEW (5 tests)
- `_bmad-output/implementation-artifacts/{5-3-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED

### Change Log

| Date | Change |
|---|---|
| 2026-05-30 | spec(5-3); 3 worktree agents via Workflow; merged clean; 352 passed; Story 5-3 → done |
