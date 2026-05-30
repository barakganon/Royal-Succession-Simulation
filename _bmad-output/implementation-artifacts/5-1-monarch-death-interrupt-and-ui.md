# Story 5-1: Monarch Death Interrupt + Succession Choice UI

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player whose monarch has just died,
I want the turn to halt on the death year and present a succession modal — the candidate heirs with portraits, traits, and the default (designated) heir highlighted — so I can choose who takes the throne instead of the engine auto-crowning the first eligible heir,
so that succession is a real decision and the dynasty's direction is mine.

Builds on the Epic-1 interrupt loop (`monarch_death` already halts `process_dynasty_turn`) and Story 4-1's `DynastyDB.designated_heir_id`.

## Current behaviour (what 5-1 changes)
`models/turn_processor.py:157-160` → on the reigning monarch's death, `process_succession(...)` **auto-crowns `eligible_heirs[0]`** and the loop halts with a `('monarch_death', year)` interrupt. The deceased keeps `is_monarch=True` only momentarily. 5-1 makes the **human** player choose; **AI dynasties keep auto-crowning**.

## Acceptance Criteria

1. **AC1 — Refactor succession into reusable helpers (`turn_processor.py`).**
   - `get_succession_candidates(dynasty, deceased_monarch, theme_config) -> list[PersonDB]` — extract the existing children→siblings→nobles selection + per-rule sort (`process_succession` lines ~552-611) into this pure helper (no crowning). Returns the ordered eligible heirs (possibly empty).
   - `crown_heir(dynasty, heir, current_year, theme_config) -> None` — extract the crowning side-effects (lines ~614-637): set ANY currently-`is_monarch` person of the dynasty to `is_monarch=False`, then `heir.is_monarch=True`, `heir.reign_start_year=current_year`, add the monarch title, and append a `succession_end` `HistoryLogEntryDB` ("X has become the new <title> of House Y").

2. **AC2 — Human monarch death halts WITHOUT auto-crowning; AI still auto-crowns.** Rework `process_succession(dynasty, deceased_monarch, current_year, theme_config)`:
   - Always append the `succession_start` log + compute `candidates = get_succession_candidates(...)`.
   - If `dynasty.is_ai_controlled` (or `not candidates`): keep TODAY's behaviour — `crown_heir(dynasty, candidates[0], ...)` when candidates exist (no-heir crisis path unchanged). Return falsy (no pending choice).
   - Else (human dynasty with ≥1 candidate): do **NOT** crown. Leave the deceased monarch as the pending marker (`is_monarch=True` AND `death_year` set). Return truthy (pending). The turn loop's existing `interrupt = ('monarch_death', current_year)` + `break` (lines 158-160) still fires — so the loop halts on the death year for the human, throne vacant.
   - Invariant: after a human monarch dies, the dynasty has **no living `is_monarch`** and exactly one dead `is_monarch` (the deceased) until the player chooses.

3. **AC3 — `GET /dynasty/<int:dynasty_id>/succession_candidates.json`** (`blueprints/dynasty.py`, `@login_required`, ownership→403). Finds the pending deceased monarch: `PersonDB` with `dynasty_id`, `is_monarch==True`, `death_year` IS NOT NULL. If none → `{"pending": false, "candidates": []}`. Else:
   ```json
   {"pending": true,
    "deceased": {"id":.., "name":"..", "surname":"..", "death_year":..},
    "candidates": [{"id":.., "name":"..", "surname":"..", "portrait_svg":"<svg…>",
                    "traits":["Brave",..], "birth_year":.., "age":.., "relation":"child|sibling|kin",
                    "is_default": true|false}, ...]}
   ```
   Candidates from `get_succession_candidates(deceased, theme_config)`. **Default** = the candidate whose id == `dynasty.designated_heir_id` if that id is among the candidates, else `candidates[0]`. `portrait_svg` via the existing portrait accessor (`person.portrait_svg` or `person.generate_portrait()`); `traits` via `person.get_traits()`; `age = death_year - birth_year` at succession. `relation` derived (child of deceased / sibling / other kin).

4. **AC4 — `POST /dynasty/<int:dynasty_id>/succession_choice`** (`@login_required`, `@block_if_turn_processing`, ownership→403). Body (form or JSON) `heir_id`. Validate: a pending succession exists AND `heir_id` is among the current candidates → else `{"ok":false,"message":".."}` (400). On success: `crown_heir(dynasty, heir, deceased.death_year, theme_config)` (which unsets the deceased's `is_monarch`), `db.session.commit()`, return `{"ok":true,"message":"<heir> crowned …"}`. Wrap in try/except + rollback.

5. **AC5 — Succession modal (frontend).** `templates/world_map.html` (+ `static/style.css`): a full-screen succession modal overlay (container marker `succession-modal`). It opens when (a) the Story 3-5 End-Turn flow returns `summary.interrupt_reason === 'monarch_death'`, OR (b) on `/world/map` load if `succession_candidates.json` reports `pending:true`. The modal fetches `succession_candidates.json` and renders: the deceased's name + a card per candidate showing `portrait_svg` (`innerHTML`, server-generated SVG), name, age, relation, traits, and a **"Default heir" badge** on the `is_default` candidate. Each card has a **"Crown"** button → POST `succession_choice` with `heir_id` → on `ok`, close the modal and refresh the page (or toast + reload). While a succession is pending, the **End Turn button is disabled/blocked** (can't advance a kingless realm). Match the Story 3-5 toast / `X-Requested-With` fetch style.

6. **AC6 — No regressions.** Full suite green (baseline **334**; new tests additive). AI dynasties still succeed automatically (GameManager turn processing unaffected). The existing no-heir crisis path is unchanged.

7. **AC7 — ≥6 new integration tests** (`tests/integration/test_succession.py`, fixture pattern from `test_detail_panel_render.py`; force deaths deterministically — e.g. set the monarch's `death_year`+keep `is_monarch=True` directly, or `mocker.patch('models.turn_processor.process_death_check')` to kill the monarch):
   - Human monarch death halts with `monarch_death` and does NOT auto-crown (deceased still `is_monarch`; no living `is_monarch`).
   - AI dynasty (`is_ai_controlled=True`) monarch death DOES auto-crown (a living `is_monarch` exists; not pending).
   - `succession_candidates.json` → `pending:true` with candidates, exactly one `is_default` (honouring `designated_heir_id` when set & eligible, else the first).
   - `succession_choice` crowns the chosen heir (`is_monarch=True`, `reign_start_year` set) AND unsets the deceased's `is_monarch`; a `succession_end` log is appended.
   - `succession_choice` with an ineligible/foreign `heir_id` → `{"ok":false}` (400); non-owner → 403.
   - `/world/map` HTML contains the modal markers (`succession-modal` + `succession_candidates` fetch).

8. **AC8 — Visual verification (Epic 3 retro lesson).** UI surface → not "done" on tests alone. Integrator runs the app: force a monarch death, End Turn → the succession modal appears with candidate portraits/traits + the default badge; crowning a heir closes it and the new ruler shows in the left rail.

## Tasks / Subtasks
- [ ] Task 1 — Backend: helpers + process_succession rework + 2 endpoints (`models/turn_processor.py`, `blueprints/dynasty.py`). [Agent A]
- [ ] Task 2 — Frontend: succession modal + End-Turn block (`templates/world_map.html`, `static/style.css`). [Agent B]
- [ ] Task 3 — Tests (`tests/integration/test_succession.py`). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A (backend)** — `models/turn_processor.py` (helpers + process_succession rework) + `blueprints/dynasty.py` (both endpoints). Keep AI auto-crown intact.
- **Agent B (frontend)** — `templates/world_map.html` + `static/style.css` only.
- **Agent C (tests)** — ONLY `tests/integration/test_succession.py`. Contract-first: fails in isolation, green on integration.
- No shared files.

### FROZEN INTERFACE CONTRACT
- `turn_processor`: `get_succession_candidates(dynasty, deceased_monarch, theme_config) -> list[PersonDB]`; `crown_heir(dynasty, heir, current_year, theme_config) -> None`. Pending-succession marker = a `PersonDB(dynasty_id, is_monarch=True, death_year not None)`. Human (`not is_ai_controlled`) death → no auto-crown; AI → auto-crown (unchanged).
- Endpoints: `GET /dynasty/<id>/succession_candidates.json` → `{pending, deceased?, candidates:[{id,name,surname,portrait_svg,traits,birth_year,age,relation,is_default}]}`; `POST /dynasty/<id>/succession_choice` (body `heir_id`) → `{ok, message}` (403/400 paths).
- Frontend markers (tests assert): `succession-modal` container + the literal `succession_candidates` in the fetch URL.
- Default heir = `dynasty.designated_heir_id` if among candidates else `candidates[0]`.

### Reuse / project rules
- Don't rewrite GameManager AI flow. Subsystem/helpers stay in `turn_processor.py`. DB writes guarded; route owns commit/rollback. `@login_required` (+ `@block_if_turn_processing` on `succession_choice`). Serialize before jsonify (build plain dicts; `traits` from `get_traits()`, portrait from the SVG accessor). SVG rendered with `innerHTML` (server-generated, safe). All chronicle entries via `HistoryLogEntryDB`. No new dependencies. `turn_summary` already carries `interrupt_reason` (`turn_processor.py:255,268`) and is surfaced by `advance_turn` (Story 3-5) → frontend reads `summary.interrupt_reason`.
- `process_death_check` (`turn_processor.py:307`) sets `death_year` but does NOT unset `is_monarch` — rely on that for the pending marker; `crown_heir` is what unsets the deceased's `is_monarch`.

### Out of scope / deferred (later Epic-5 stories)
- LLM candidate-card flavor → **Story 5-2** (5-1 shows traits/portrait deterministically). Pretender mechanics → **5-3**. Civil war / heir-majority interrupts → **5-4**. 5-1 is: halt + candidate list + choose + crown + modal.

## Previous Story Intelligence
- Same worktree contract-first flow (Epic 3/4 → zero conflicts). **Spawned agents default to plan mode** → each prompt says "EXECUTE NOW, pre-approved, no EnterPlanMode". Worktrees branch off `main`; contract inlined per prompt. **Watch the branch: do the wt/5-1-* merges onto a feature branch, then merge that to main** (in 4-2 the merges accidentally landed on main directly — still fine, but prefer the feature-branch path).
- `pytest` runs against an isolated temp DB rebuilt fresh per run (schema picked up). Baseline 334.
- 4-1 added `designated_heir_id`/`succession_law`; 4-2 added the free-action menu. 3-5 added the animated End-Turn JSON flow (`{ok,redirect,summary}` with `interrupt_reason`).
- **UI surface → run-the-app screenshot check before done (AC8).** Known: `test_military_routes` full-suite-ordering flake (unrelated); monarch-portrait-card overlap on `/world/map` (pre-existing, logged).

## References
- Turn loop + monarch_death halt: `models/turn_processor.py:121-199` (loop), `:157-160` (death→succession→interrupt).
- `process_succession` (to refactor): `models/turn_processor.py:536-650`.
- `turn_summary` carries interrupt_reason: `models/turn_processor.py:250-268`.
- `process_death_check`: `models/turn_processor.py:307`.
- `DynastyDB.designated_heir_id`/`succession_law`/`is_ai_controlled`: `models/db_models.py` (~87-94, :68).
- `/free_action` + `advance_turn` JSON conventions: `blueprints/dynasty.py` (Story 4-1/3-5).
- Portrait/traits accessors: `PersonDB.generate_portrait()`/`portrait_svg`, `get_traits()`/`traits_json` (`models/db_models.py` ~178-182).
- Toast/XHR pattern: `templates/world_map.html` (Story 3-5 `turn-toast-stack`, `X-Requested-With`).
- Test fixture: `tests/integration/test_detail_panel_render.py:13-39`.

## Dev Agent Record

### Agent Model Used

(to be filled by dev/integration)

### Debug Log References

### Completion Notes List

### File List
