# Story 8-1: Family-Tree SVG Renderer + DynastyDB column

Status: done

## Story

Replace the matplotlib/NetworkX family-tree PNG with a self-contained, deterministic **SVG renderer** drawn in pure Python: a tidy (Reingold-Tilford-style) generational tree where each person is a node (name + life dates + a crown for monarchs, portrait optional) and edges encode relationships (solid parent→child, double-line marriage, dashed for a cross-dynasty marriage), on a parchment palette. Also add a `family_tree_svg` TEXT column to `DynastyDB` (with a migration) to hold the rendered string later. **8-1 ships the renderer + the column only** — pan/zoom + hover + toggles are Story 8-2; deleting matplotlib and wiring the SVG into `view_dynasty.html` is Story 8-3.

## Acceptance Criteria

1. **AC1 — `generate_family_tree_svg` (NEW `visualization/family_tree_svg.py`).** Signature **`generate_family_tree_svg(dynasty_id: int, session, current_year: int | None = None, show_deceased: bool = True) -> str`** (mirrors `visualization/map_renderer.py::generate_geojson(dynasty_id, session)`). Behavior:
   - Query `PersonDB` for `dynasty_id` (include deceased when `show_deceased`; otherwise only `death_year is None`). Also resolve each person's spouse via `spouse_sim_id` even if the spouse is in another dynasty (for marriage edges). If `current_year` is None, derive it from the dynasty's `current_simulation_year` (fallback to the max birth/death year present, else a constant).
   - **BFS generation assignment:** roots = dynasty persons whose `father_sim_id` and `mother_sim_id` are both absent-from-this-tree (no in-tree parent); assign generation 0 to roots, child generation = parent generation + 1 (a child via `father_sim_id`/`mother_sim_id`). Guard against cycles with a visited set; a person with no resolvable parent defaults to generation 0.
   - **Layout:** a pure-Python tidy tree (Reingold-Tilford-style) — y by generation (top = oldest), x spread so siblings/subtrees don't overlap; spouses placed adjacent. NO networkx / graphviz / matplotlib imports (those are being removed in 8-3).
   - **Nodes:** one group per person with a rounded `<rect>` card, the name (`name surname`), life dates (`b.{birth_year}` + `–d.{death_year}` when dead, else `–`), and a crown mark (e.g. a `<text>👑</text>` or a small gold polygon) when `is_monarch`. If `person.portrait_svg` is present you MAY embed it scaled into the card (nested `<svg>`); otherwise draw a simple placeholder — robustness over fidelity. Deceased nodes visually muted (e.g. lower opacity / gray stroke). Each node group carries `data-person-id="{id}"` (so Story 8-2 JS can hook it).
   - **Edges:** solid line parent→child; a **double parallel line** between spouses; **dashed** stroke when the spouse is in a different `dynasty_id` (cross-dynasty marriage). Draw edges beneath nodes.
   - **Palette:** parchment background (`#f4ecd8`-ish), dark-brown strokes, gold crown — consistent with the medieval theme. Define a small palette dict at module top.
   - **Output:** a single complete SVG string that **starts with `<svg`** and **ends with `</svg>`**, includes `xmlns="http://www.w3.org/2000/svg"` and a computed `width`/`height` (and a `viewBox`). Deterministic for the same data (no `random`, or seed by `dynasty_id`). **Never raises** — on empty dynasty return a minimal valid SVG (a parchment rect, still `<svg>…</svg>`); on any internal error log via the module logger and return a minimal valid SVG.
   - `logger = logging.getLogger('royal_succession.family_tree_svg')`. No `print()`.

2. **AC2 — `DynastyDB.family_tree_svg` column (`models/db_models.py`).** Add `family_tree_svg = db.Column(db.Text, nullable=True)` to `DynastyDB` (mirror `coat_of_arms_svg` at db_models.py:79). Picked up automatically by `db.create_all()` for fresh DBs.

3. **AC3 — Migration (`models/db_initialization.py`).** Add the idempotent column-existence-checked `ALTER TABLE dynasty ADD COLUMN family_tree_svg TEXT` (mirror the existing pattern at db_initialization.py:143-161 used for prior column adds), so existing SQLite DBs gain the column without data loss. Log at info on add.

4. **AC4 — No regressions / no new deps.** Full suite green vs baseline **427 passed** (new tests additive). NO new entries in `requirements.txt` (pure-Python layout). Do NOT delete `plotter.py` or touch templates (that's 8-3). Do NOT add JS (that's 8-2).

5. **AC5 — Tests (NEW `tests/unit/test_family_tree_svg.py`) — ≥6.** (No existing visualization tests — establish the pattern.)
   - Returns a string that startswith `<svg` and endswith `</svg>` and contains `xmlns="http://www.w3.org/2000/svg"`.
   - **Deterministic:** two calls with identical data return identical strings.
   - Contains a node per living person (assert each person's name appears, and `data-person-id` count matches person count).
   - A monarch node renders the crown mark; a non-monarch does not get it.
   - A married couple produces a marriage edge; a **cross-dynasty** spouse produces a **dashed** edge (assert `stroke-dasharray` present for that edge).
   - `show_deceased=False` omits dead persons; `show_deceased=True` (default) includes them.
   - Empty dynasty (no persons) → still a valid minimal SVG (`<svg`…`</svg>`), no exception.
   - Use a session-based fixture (build a small dynasty with a monarch, spouse, and 2 children, plus one cross-dynasty spouse) consistent with the integration conftest, OR drive the renderer against an in-memory session. Mirror the fixture helpers in `tests/integration/test_cross_dynasty_marriage.py` if a real session is needed.

## Tasks / Subtasks
- [ ] Task 1 — `visualization/family_tree_svg.py` renderer. [Agent A]
- [ ] Task 2 — `DynastyDB.family_tree_svg` column + migration. [Agent B]
- [ ] Task 3 — Renderer unit tests. [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — NEW `visualization/family_tree_svg.py` ONLY. Import `PersonDB`/`DynastyDB` from `models.db_models` (no cycle — db_models doesn't import visualization). Query via the passed `session`.
- **Agent B** — `models/db_models.py` (one column on DynastyDB) + `models/db_initialization.py` (migration) ONLY.
- **Agent C** — NEW `tests/unit/test_family_tree_svg.py` ONLY.
- No shared files. A and B are independent (the renderer does NOT need the new column — population into the column is Story 8-3).

### FROZEN INTERFACE CONTRACT (authoritative)
- **`generate_family_tree_svg(dynasty_id: int, session, current_year: int | None = None, show_deceased: bool = True) -> str`** — returns a complete SVG string (`<svg`…`</svg>`, with `xmlns` + `viewBox` + width/height), deterministic, never raises (minimal valid SVG on empty/error). Node groups carry `data-person-id`. Edges: solid parent-child, double-line marriage, dashed cross-dynasty. Parchment palette. No networkx/graphviz/matplotlib; no `random` (or seed by dynasty_id).
- **`DynastyDB.family_tree_svg`** = `db.Column(db.Text, nullable=True)`.
- **Migration:** idempotent `ALTER TABLE dynasty ADD COLUMN family_tree_svg TEXT` guarded by a column-existence check, in `db_initialization.py`.

### Reuse / project rules
- Mirror the SVG house style of `visualization/heraldry_renderer.py::generate_coat_of_arms(dynasty_id, dynasty_name)` and `portrait_renderer.py::generate_portrait(...)` — raw-string SVG assembly, private `_helper()` fragment functions, `logger.debug` at the end. Mirror the session/id entrypoint of `map_renderer.generate_geojson(dynasty_id, session)`.
- PersonDB fields (db_models.py:157-282): `name`(165), `surname`(166), `birth_year`(168), `death_year`(169, nullable), `is_monarch`(192), `portrait_svg`(222), `mother_sim_id`(172), `father_sim_id`(173), `spouse_sim_id`(174), `dynasty_id`(162). Children = `PersonDB.query.filter((father_sim_id==pid)|(mother_sim_id==pid))` — but use the passed **session** (`session.query(PersonDB)...`) not the bare `PersonDB.query`, so the renderer works with any session. Cross-dynasty marriage = `spouse.dynasty_id != person.dynasty_id`.
- DynastyDB `coat_of_arms_svg` Text column pattern: db_models.py:79. `current_simulation_year` exists on DynastyDB. No `print()`; module logger. No new dependencies.

### Out of scope / deferred
- Pan/zoom, hover tooltips, "show deceased" toggle UI, highlight-bloodline, search-jump → **Story 8-2** (JS). (8-1 already emits `data-person-id` + a `show_deceased` param so 8-2 can build on it.)
- Deleting `visualization/plotter.py`, removing the ~203 `visualizations/family_tree_*.png`, gitignoring `visualizations/*.png`, and rendering `dynasty.family_tree_svg | safe` into `templates/view_dynasty.html` → **Story 8-3**. Do NOT do these in 8-1.
- Actually POPULATING `DynastyDB.family_tree_svg` during gameplay → 8-3.

## Previous Story Intelligence
- Worktree contract-first via the **Workflow tool**. Agents default to plan mode → each prompt MUST say "EXECUTE NOW — do not enter plan mode / EnterPlanMode, pre-approved." Worktrees branch off `main`; story file absent in their trees → FULL contract inlined per prompt.
- **Integrator caution (recurring, hit again in 7-3):** an agent may write to the MAIN working tree instead of its worktree, or leak then self-revert — verify where each agent's changes actually landed (`git status` + check the worktree path) before integrating; copy the right files in; keep zero-overlap. **Signature drift** between impl and tests agents bit 7-1/7-2 — the FROZEN CONTRACT signature above is authoritative.
- Baseline **427 passed** (Epic 7 complete; flake eliminated via autouse RNG seed). Tests run against an isolated temp DB (root `tests/conftest.py` sets `DATABASE_URL`); reset `/tmp/rss_pytest.db` before a run; `python -m pytest -p no:randomly -q`.
- This is a renderer (backend) story producing an SVG STRING — no live UI yet (8-2/8-3 wire it in). A lightweight visual sanity check (write the SVG to a file and eyeball / confirm it opens) is optional; the unit tests are the contract.

## References
- Sibling SVG renderers: `visualization/heraldry_renderer.py:505` (`generate_coat_of_arms`), `visualization/portrait_renderer.py:361` (`generate_portrait`). Session/id entrypoint: `visualization/map_renderer.py` (`generate_geojson(dynasty_id, session)`).
- Current matplotlib tree (to be REPLACED in 8-3, untouched here): `visualization/plotter.py:22` (`visualize_family_tree_snapshot`). FamilyTree model: `models/family_tree.py:38`.
- PersonDB fields + relationship FKs: `models/db_models.py:157-282` (FKs 172-185). DynastyDB `coat_of_arms_svg`: `models/db_models.py:79`. `PersonDB.generate_portrait()`: db_models.py:240-266.
- Migration idiom: `models/db_initialization.py:143-161` (column-existence-checked ALTER TABLE).

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool + main-session integrator.

### Completion Notes List
- All ACs satisfied. Full suite **436 passed** (427 baseline + 9 new), 0 failed. 3 worktree agents via Workflow (run wf_63c0ca65-2da), main-session integrator. Sanity render validated as well-formed XML (xml.dom.minidom), 483×262 for a monarch + cross-dynasty spouse + 2 children incl. one deceased.
- **Integrator fix (one):** the renderer queries only the requesting dynasty's persons, so a cross-dynasty *in-married* spouse (who lives in another dynasty) was never positioned — the marriage-edge loop's `if sid not in positions: continue` silently dropped the edge, so the contract-required **dashed cross-dynasty edge** never rendered and `test_cross_dynasty_spouse_draws_dashed_edge` failed. Fixed by positioning out-of-tree spouses as **satellite nodes** beside their in-tree partner (combined `all_positions`/`all_objs` views) without disturbing the core tidy layout. Agent A had asserted the dash branch was reachable, but it wasn't for the standard in-married case.
- Clean worktree isolation this run (no main-tree leaks). No signature drift. No new pip deps. plotter.py / templates / JS untouched (deferred to 8-2/8-3 as specified).

### File List
- `visualization/family_tree_svg.py` — NEW (renderer)
- `models/db_models.py` — MODIFIED (`DynastyDB.family_tree_svg`)
- `models/db_initialization.py` — MODIFIED (migration)
- `tests/unit/test_family_tree_svg.py` — NEW
- `_bmad-output/implementation-artifacts/{8-1-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED

### Change Log
| Date | Change |
|---|---|
| 2026-05-30 | spec(8-1); ready-for-dev; 3 worktree agents via Workflow |
