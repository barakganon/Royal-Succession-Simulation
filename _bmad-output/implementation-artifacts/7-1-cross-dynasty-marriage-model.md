# Story 7-1: Cross-Dynasty Marriage Matching + MarriageOffer Model

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the world fills with rival houses, I want marriages to first seek a real partner from ANOTHER dynasty (a political match) and only invent a stranger if none exists — and I want a `MarriageOffer` record to hang negotiation on (used by Story 7-2) — so marriages become instruments between actual dynasties. **Backend-only** — tests are the verification.

## Acceptance Criteria

1. **AC1 — Cross-dynasty matching in `process_marriage_check` (`models/turn_processor.py:417`).** When a marriageable person rolls to seek marriage, FIRST attempt a cross-dynasty match instead of immediately generating a stranger:
   - Add a helper `_find_cross_dynasty_spouse(session, person, current_year, min_age, max_age)` that queries `PersonDB` for an eligible partner: opposite `gender`, `death_year is None`, `is_noble == True`, `spouse_sim_id is None` (unmarried), `dynasty_id != person.dynasty_id` (a DIFFERENT dynasty), and marriageable age (`min_age <= current_year - birth_year <= max_age`). Return the first such person (deterministic order, e.g. by id), or `None`.
   - If a partner is found: link BOTH ways (`person.spouse_sim_id = partner.id`, `partner.spouse_sim_id = person.id`), append a `marriage` `HistoryLogEntryDB` naming both houses (a cross-dynasty union), and return True. **Both retain their own `dynasty_id`** (a political marriage; children/claims are Story 7-3).
   - If NO cross-dynasty partner exists: fall back to the EXISTING stranger-generation path unchanged.

2. **AC2 — `MarriageOffer` model + migration (`models/db_models.py` + `models/db_initialization.py`).** Add a `MarriageOfferDB` model (suffix `DB`, explicit `__tablename__ = 'marriage_offer'`):
   - `id` (PK), `proposer_dynasty_id` (FK dynasty.id), `target_dynasty_id` (FK dynasty.id), `proposer_person_id` (FK person_db.id, nullable), `target_person_id` (FK person_db.id, nullable), `status` (String, default `'pending'`), `created_year` (Integer), `created_at` (DateTime default utcnow). Use `back_populates`-free one-way FKs (no reverse collections needed yet) with explicit `foreign_keys=` where ambiguous; circular FK to person_db uses `use_alter=True, name='fk_marriageoffer_*'` if needed.
   - Idempotent migration in `db_initialization.py`: create the `marriage_offer` table if missing (mirror the `Project`/`Loan` lazy-create pattern). (Tests get it via `create_all`.) Not wired into matching in 7-1 — it scaffolds Story 7-2's AI acceptance.

3. **AC3 — No regressions.** Full suite green vs the current baseline (**~401 + the known isolation flake**; new tests additive). Single-dynasty test setups have no cross-dynasty candidates → fall back to stranger generation → existing marriage behavior preserved. The new model/table is additive.

4. **AC4 — ≥5 new tests** (`tests/integration/test_cross_dynasty_marriage.py`):
   - With TWO dynasties each having an eligible unmarried opposite-gender noble of marriageable age, forcing the marriage roll (patch `random.random` low), `process_marriage_check` links the two existing people (both `spouse_sim_id` set to each other) and creates NO new stranger PersonDB; a `marriage` history entry is written.
   - With only ONE dynasty (no cross-dynasty candidate), the marriage roll falls back to stranger generation (a new spouse PersonDB is created in the same dynasty) — existing behavior.
   - `_find_cross_dynasty_spouse` returns None when the only candidates are same-dynasty / married / dead / wrong-gender / wrong-age, and returns the eligible cross-dynasty person otherwise.
   - `MarriageOfferDB` table exists and a row can be created with the documented fields and defaults (`status='pending'`).
   - Marriage roll not triggered (patch `random.random` high) → no marriage, no stranger, no link.

## Tasks / Subtasks
- [ ] Task 1 — Cross-dynasty matching + `_find_cross_dynasty_spouse` (`models/turn_processor.py`). [Agent A]
- [ ] Task 2 — `MarriageOfferDB` model + migration (`models/db_models.py`, `models/db_initialization.py`). [Agent B]
- [ ] Task 3 — Tests (`tests/integration/test_cross_dynasty_marriage.py`). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `models/turn_processor.py` only (matching in `process_marriage_check` + helper).
- **Agent B** — `models/db_models.py` (+`MarriageOfferDB`) + `models/db_initialization.py` (migration).
- **Agent C** — NEW `tests/integration/test_cross_dynasty_marriage.py` only.
- No shared files. (A's matching does NOT need B's model in 7-1 — independent; C tests both.)

### FROZEN INTERFACE CONTRACT
- `process_marriage_check`: cross-dynasty match first (opposite gender, alive, noble, unmarried, different dynasty, marriageable age) → link both `spouse_sim_id` + `marriage` history entry, both keep their dynasty; else stranger fallback (unchanged). Helper `_find_cross_dynasty_spouse(session, person, current_year, min_age, max_age) -> PersonDB|None`.
- `MarriageOfferDB` (`__tablename__='marriage_offer'`): `id, proposer_dynasty_id, target_dynasty_id, proposer_person_id, target_person_id, status='pending', created_year, created_at`; idempotent `marriage_offer` table migration.

### Reuse / project rules
- Don't rewrite turn_processor — extend `process_marriage_check`. DB model suffix `DB`, explicit `__tablename__`, `back_populates` not `backref`, explicit `foreign_keys=`, `use_alter=True` for any circular FK to person_db/dynasty. Migration via the lazy-create pattern (`Project`/`Loan` in `db_initialization.py`), NOT bare create_all for schema evolution. `min_marriage_age=16`, `max_marriage_age` 45/55 by gender (already in the function). No new deps.

### Out of scope / deferred
- AI acceptance of offers + wedding chronicle (LLM) → **Story 7-2** (uses `MarriageOfferDB`). Children-with-claims + "propose marriage" UI → **Story 7-3**. 7-1 is the matching + the model scaffold only.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool (Epics 5/6 ran clean). Agents default to plan mode → "EXECUTE NOW, pre-approved, no EnterPlanMode"; worktrees branch off `main`; contract inlined. **Integrator caution:** an agent's Edit has twice leaked into the MAIN working tree — verify `git status` is clean (only expected files) before each merge; if a merge fails on a dirty tree, discard the leaked copies and merge the branch (its commit has the content).
- `pytest` against an isolated temp DB; **reset it before a run** (`rm -f $TMPDIR/rss_pytest.db`) and run sandbox-disabled if a "readonly database" error appears. A shared-state isolation flake intermittently fails a few tests under full-suite ordering (they pass in isolation) — not a regression. Baseline ~401.
- Backend-only → no run-the-app visual check.

## References
- `process_marriage_check`: `models/turn_processor.py:417` (stranger generation begins ~line 433+; `min_marriage_age`/`max_marriage_age`).
- Model + migration patterns: `models/db_models.py` (Project/Loan, FK conventions, `use_alter`), `models/db_initialization.py` (lazy-create for `project`/`loan`/`marriage_offer`).
- `PersonDB` (`spouse_sim_id`, `gender`, `is_noble`, `death_year`, `birth_year`, `dynasty_id`): `models/db_models.py`.
- Test fixtures: `tests/integration/test_succession.py`, `tests/integration/test_pretender.py`.

## Dev Agent Record

### Agent Model Used

(to be filled by dev/integration)

### Debug Log References

### Completion Notes List

### File List
