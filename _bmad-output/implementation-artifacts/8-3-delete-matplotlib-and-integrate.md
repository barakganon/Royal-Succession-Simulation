# Story 8-3: Retire the Matplotlib Family-Tree Plotter + Integrate the SVG

Status: ready-for-dev (scope decision flagged — see Scope Decision below)

## Scope Decision (needs confirmation — plan vs. codebase conflict)

The Epic-8 plan line for 8-3 says *"Delete matplotlib"*. A blast-radius scan shows **matplotlib + networkx are imported by FIVE other renderers** that are unrelated to the family tree:
`visualization/diplomacy_renderer.py`, `military_renderer.py`, `time_renderer.py`, `economy_renderer.py`, `map_renderer.py` (plus the `MPLBACKEND=Agg` setup in `tests/conftest.py`). Removing matplotlib/networkx from `requirements.txt` would break all five.

**Therefore this story is scoped CONSERVATIVELY:** retire only the matplotlib **family-tree plotter** (`visualization/plotter.py`) and wire the Story 8-1/8-2 SVG into the dynasty view. **matplotlib + networkx STAY in `requirements.txt`** (still needed by the five renderers). Fully uninstalling matplotlib is a **separate, larger migration** (port or delete those five renderers first) — recorded as a follow-up, NOT done here.
> If you actually want matplotlib fully gone, say so and we'll spin a dedicated epic to migrate/remove the five remaining matplotlib renderers first.

## Story

Replace the legacy matplotlib/NetworkX family-tree **PNG** pipeline with the deterministic SVG renderer from Story 8-1: delete `visualization/plotter.py`, remove its import/call sites, populate `DynastyDB.family_tree_svg` at the same lifecycle points (turn processing / dynasty view) using `generate_family_tree_svg`, and render that SVG **inline** in `view_dynasty.html` (replacing the `<img>`), with the "View Family Tree" link to the interactive page (Story 8-2) kept. Stop writing PNGs and remove the one tracked PNG.

## Acceptance Criteria

1. **AC1 — Delete the matplotlib plotter.** Remove `visualization/plotter.py`. Remove its re-export from `visualization/__init__.py:4` (`from .plotter import visualize_family_tree_snapshot`). After this, `grep -rn "visualize_family_tree_snapshot\|visualization.plotter\|from .plotter"` over `*.py` (excluding `.venv`) returns NOTHING.

2. **AC2 — Rewire the call sites to the SVG (no PNG).**
   - `simulation_engine.py` (import at :27-28; calls at :555 and :620): remove the import and the two `visualize_family_tree_snapshot(...)` calls. Where a family-tree artifact was produced, either (a) call `generate_family_tree_svg(dynasty_id, session)` and store into `DynastyDB.family_tree_svg`, or (b) simply drop the PNG generation if no `dynasty_id`/session is available there (the dynasty-view route regenerates on demand — AC4). Preserve all surrounding simulation behaviour; do not change turn/sim outcomes.
   - `models/turn_processor.py` (lazy import at :1006; call at :1072): replace the PNG generation with populating `DynastyDB.family_tree_svg` via `generate_family_tree_svg(dynasty.id, db.session)` (lazy-import the SVG renderer), wrapped in try/except + logged so a render failure never aborts a turn. Keep it cheap (only when it already ran — same cadence).
   - No remaining reference to matplotlib/networkx from the family-tree path. (The five OTHER renderers keep theirs — untouched.)

3. **AC3 — Inline SVG in `view_dynasty.html` (+ `themes/view_dynasty.html`).** Replace the `{% if family_tree_image %}<img ...>{% endif %}` block (templates/view_dynasty.html:248-249; themes/view_dynasty.html:129-130) with inline `{{ dynasty.family_tree_svg | safe }}` when present, else a graceful "No family tree yet" placeholder. KEEP the Story 8-2 "View Family Tree" link to the interactive page. The static-image card becomes the inline static SVG preview.

4. **AC4 — Dynasty view route populates/serves the SVG (`blueprints/dynasty.py:280-295`).** In `view_dynasty`, drop the `family_tree_image`/`url_for('static', ...)` logic (:280-284). Ensure `dynasty.family_tree_svg` is available to the template: if it's empty/stale, generate it on demand via `generate_family_tree_svg(dynasty_id, db.session)` (lazy import), optionally caching it into the column (best-effort, try/except). Remove `family_tree_image=` from the `render_template` kwargs (template no longer uses it).

5. **AC5 — Stop writing PNGs + drop the tracked one.** `git rm visualizations/family_tree_Chosokabe_year_1505_living_nobles.png` (the only tracked PNG). Confirm `.gitignore` already ignores `visualizations/` (it does, lines 14-16) — no change needed there. Do NOT bulk-`rm` the ~203 untracked working-dir PNGs in this story (they're gitignored and harmless; optional local cleanup only).

6. **AC6 — matplotlib/networkx STAY in requirements.txt.** Do NOT edit `requirements.txt` (the five other renderers depend on them). See Scope Decision.

7. **AC7 — No regressions.** Full suite green vs baseline **452 passed**. Any test that asserted on the PNG/`family_tree_image` (search `tests/` for `family_tree_image`, `plotter`, `visualize_family_tree_snapshot`) is updated to assert the inline SVG / new behaviour instead, with a comment. New behaviour gets at least one test (view_dynasty contains inline `<svg` and no `family_tree_image`).

## Tasks / Subtasks
- [ ] Task 1 — Delete plotter.py + rewire simulation_engine.py + visualization/__init__.py + turn_processor.py to the SVG. [Agent A]
- [ ] Task 2 — Inline SVG in view_dynasty.html (+ themes/) + view route changes in blueprints/dynasty.py. [Agent B]
- [ ] Task 3 — Update/extend tests; drop tracked PNG. [Agent C + integrator]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `visualization/plotter.py` (DELETE), `visualization/__init__.py`, `simulation_engine.py`, `models/turn_processor.py`. (The matplotlib-plotter removal + SVG rewiring — the delicate core part. Lazy-import `generate_family_tree_svg`.)
- **Agent B** — `templates/view_dynasty.html`, `themes/view_dynasty.html`, `blueprints/dynasty.py` (the `view_dynasty` route only). (Inline SVG + route kwargs.)
- **Agent C** — test files only (update any test referencing the PNG/plotter; add the inline-SVG assertion). The integrator does the `git rm` of the tracked PNG.
- No shared files. NOTE: A and B both conceptually touch "the family tree on the view" but via DIFFERENT files (A = sim/turn population + plotter delete; B = route + templates) — confirm no overlap on `blueprints/dynasty.py` (only B) and `models/turn_processor.py` (only A).

### FROZEN CONTRACT
- `generate_family_tree_svg(dynasty_id, session, current_year=None, show_deceased=True) -> str` (8-1, unchanged). `DynastyDB.family_tree_svg` TEXT column (8-1). Interactive page route `dynasty.family_tree` (8-2) — keep the link.
- After 8-3: no `visualize_family_tree_snapshot` / `visualization.plotter` references anywhere in `*.py`; no `family_tree_image` in routes/templates; `view_dynasty.html` shows inline `{{ dynasty.family_tree_svg | safe }}`; matplotlib/networkx remain in requirements.

### Reuse / project rules
- Lazy-import the SVG renderer where used (avoid import cycles). All DB writes (column population) in try/except + rollback; a render failure must never abort a turn or a page load. No `print()`; module loggers. `@login_required` preserved on the view route. Templates extend base.html; SVG via `| safe`.

### Out of scope / deferred
- Full matplotlib/networkx uninstall (requires migrating/removing diplomacy/military/time/economy/map renderers) → separate epic. Bulk deletion of the ~203 untracked PNGs (gitignored; optional local cleanup). Epic-8 retrospective (`epic-8-retrospective`, optional) after 8-3.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool; "EXECUTE NOW, no plan mode"; write only inside the worktree root; contract inlined. Integrator: verify where each agent's edits landed; run the FULL suite before merge (this story edits the simulation core — `simulation_engine.py` + `turn_processor.py` — so a regression would surface there); eyeball `/dynasty/<id>/view` rendering the inline SVG.
- Baseline **452 passed**. Tests: isolated temp DB; `python -m pytest -p no:randomly -q`. This is partly a UI change → run-the-app check of `view_dynasty` showing the inline tree.

## References
- Plotter + call sites: `visualization/plotter.py`, `visualization/__init__.py:4`, `simulation_engine.py:27-28,555,620`, `models/turn_processor.py:1006,1072`.
- View route + image: `blueprints/dynasty.py:280-295`. Templates: `templates/view_dynasty.html:248-249`, `themes/view_dynasty.html:129-130`.
- SVG renderer: `visualization/family_tree_svg.py:317`. Column: `models/db_models.py` (`family_tree_svg`). Interactive page (8-2): `dynasty.family_tree`.
- matplotlib users to LEAVE ALONE: `visualization/{diplomacy,military,time,economy,map}_renderer.py`, `tests/conftest.py` (MPLBACKEND).
- Tracked PNG to drop: `visualizations/family_tree_Chosokabe_year_1505_living_nobles.png`.

## Dev Agent Record
### Agent Model Used
_pending_
### Completion Notes List
- _pending_
### File List
- DELETE `visualization/plotter.py`; MOD `visualization/__init__.py`, `simulation_engine.py`, `models/turn_processor.py`, `blueprints/dynasty.py`, `templates/view_dynasty.html`, `themes/view_dynasty.html`; tests; `git rm` the one tracked PNG.
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(8-3); conservative scope (keep matplotlib for 5 other renderers); ready-for-dev pending scope confirmation |
