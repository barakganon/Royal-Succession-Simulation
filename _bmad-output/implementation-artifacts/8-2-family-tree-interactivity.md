# Story 8-2: Interactive Family-Tree Page

Status: done

## Story

Give the Story 8-1 family-tree SVG a real home: a dedicated **interactive family-tree page** with pan (drag) + zoom (wheel), a hover **tooltip** showing full character info, a **"Show deceased"** toggle (default ON), **"highlight bloodline"** on node click (light up a person's ancestors + descendants + spouse), and a **search box** that jumps to / centres a node by name. All vanilla JS in the project's house style (mirror `world_map.html`); no new libraries. (Story 8-3 then deletes matplotlib and embeds the tree into `view_dynasty.html` — 8-2 stands up the page + the interactions.)

## Acceptance Criteria

1. **AC1 — Renderer relationship hooks (`visualization/family_tree_svg.py`).** Extend each node `<g>` (including satellite cross-dynasty spouses) to ALSO carry `data-father-id`, `data-mother-id`, `data-spouse-id` (empty string `""` when the link is absent), in addition to the existing `data-person-id`. This is purely additive — `data-person-id` and its count are unchanged, and the SVG stays deterministic + valid. No other renderer behaviour changes. (These let the client walk the tree for highlight-bloodline without a round-trip.)

2. **AC2 — Routes (`blueprints/dynasty.py`).** Three `@login_required` routes, each mirroring `view_dynasty`'s ownership guard (`if dynasty.owner_user != current_user:` → flash "Not authorized." + redirect to `auth.dashboard` for the HTML route; the JSON/SVG routes mirror the existing `succession_candidates.json` ownership guard at dynasty.py:1130-1136):
   - `GET /dynasty/<int:dynasty_id>/family_tree` → fn **`family_tree`** → renders NEW `family_tree.html`, passing `dynasty`, `current_year=dynasty.current_simulation_year`, and `tree_svg=generate_family_tree_svg(dynasty_id, db.session, show_deceased=True)` (rendered inline with `| safe`). Lazy-import the renderer inside the function.
   - `GET /dynasty/<int:dynasty_id>/family_tree.svg` → fn **`family_tree_svg_route`** → returns the RAW svg string (`Response(svg, mimetype='image/svg+xml')`) honouring `?show_deceased=` (truthy `1/true/yes` → True, `0/false/no` → False; default True). Used by the toggle.
   - `GET /dynasty/<int:dynasty_id>/person/<int:person_id>.json` → fn **`person_detail_json`** → `jsonify` of a person serialized dict for the tooltip. Validate the person belongs to `dynasty_id` (or is a spouse of a member — accept any person whose `dynasty_id == dynasty_id` OR who is the `spouse_sim_id` of such a member); if not found → 404. Dict keys EXACTLY: `id, name, surname, gender, birth_year, death_year, age, traits (list), titles (list), is_monarch (bool), is_pretender (bool), reign_start_year`. `age = (death_year or current_year) - birth_year`. Use `get_traits()` / `get_titles()`.
   - url_for names: `dynasty.family_tree`, `dynasty.family_tree_svg_route`, `dynasty.person_detail_json`.

3. **AC3 — Interactive page (NEW `templates/family_tree.html`).** Extends `base.html`. Contains:
   - A breadcrumb / back link to `dynasty.view_dynasty`.
   - A toolbar with: a **"Show deceased"** checkbox (`id="ft-show-deceased"`, checked by default), a **search input** (`id="ft-search"`), and a **"Reset view"** button (`id="ft-reset"`).
   - A pan/zoom **viewport** container (`id="ft-viewport"`) wrapping an **inner group** (`id="ft-stage"`) that holds the inline `{{ tree_svg | safe }}`. A tooltip div (`id="ft-tooltip"`, hidden by default).
   - A `<script>` (vanilla, mirroring `world_map.html` patterns) implementing:
     - **Pan**: left-button (or any-button) drag on the viewport translates `ft-stage` (CSS transform `translate(panX,panY) scale(scale)`).
     - **Zoom**: wheel zoom, cursor-anchored, clamped (e.g. 0.3–3.0), like the map's wheel handler.
     - **Reset view**: button restores pan=0/scale=1 (fit).
     - **Tooltip**: on `mouseover`/`mousemove` of an element inside a node `<g data-person-id>`, `fetch` `person/<id>.json` (cache by id) and show name + life dates + traits + titles in `#ft-tooltip`, positioned near the cursor; hide on mouseout/pan/zoom. Use `url_for('dynasty.person_detail_json', dynasty_id=..., person_id='0')` with a JS id swap, or build the base URL in Jinja.
     - **Show-deceased toggle**: on change, `fetch` `family_tree.svg?show_deceased=0|1`, replace `#ft-stage`'s SVG innerHTML, and re-bind node listeners.
     - **Highlight bloodline**: on click of a node, walk `data-father-id`/`data-mother-id` upward (ancestors) and find descendants (nodes whose father/mother id == a highlighted id) downward, plus the `data-spouse-id`; add a highlight class (e.g. brighten / gold stroke) to those node `<g>`s and dim the rest; clicking empty space or the same node clears it.
     - **Search**: on input/enter, find the node whose name text contains the query (case-insensitive); pan/scale so it is centred in the viewport and flash its highlight; no match → a brief notice.
   - Use `url_for(...)` for all endpoints; never hardcode. Medieval theme consistent (reuse base.html CSS vars). Frozen DOM ids above so tests can assert.

4. **AC4 — Nav entry (`templates/view_dynasty.html`).** Add a visible link/button to `url_for('dynasty.family_tree', dynasty_id=dynasty.id)` (e.g. in the action bar at view_dynasty.html:26-45, or on the existing Family Tree card at :238-254) labelled e.g. "View Family Tree". Do NOT remove the existing static-image card yet (that's 8-3). Minimal, additive edit.

5. **AC5 — No regressions / no new deps.** Full suite green vs baseline **436 passed** (new tests additive). No new `requirements.txt` entries. Do NOT delete `plotter.py` / PNGs (8-3). Do NOT change the 8-1 renderer's output beyond the additive data-* attributes.

6. **AC6 — Tests (NEW files only) — ≥7.**
   - `tests/unit/test_family_tree_svg_dataattrs.py`: the renderer emits `data-father-id`, `data-mother-id`, `data-spouse-id` on nodes; a child node's `data-father-id`/`data-mother-id` equal the parent ids; a spouse's `data-spouse-id` is set; `data-person-id` count still equals person count (no regression of 8-1 behaviour).
   - `tests/integration/test_family_tree_page.py` (mirror `tests/integration/test_dynasty_routes.py` fixtures `dynasty_client` / `_register_and_login` / `_get_dynasty_id`):
     - `GET /dynasty/<id>/family_tree` (owner) → 200, body contains `<svg`, `id="ft-viewport"`, `id="ft-show-deceased"`, `id="ft-search"`.
     - `GET /dynasty/<id>/family_tree.svg` → 200, `image/svg+xml`, body startswith `<svg`; `?show_deceased=0` omits a deceased member present with default.
     - `GET /dynasty/<id>/person/<person_id>.json` (a member) → 200, JSON has the exact keys; a bogus person id → 404.
     - Ownership: another user GETting `/dynasty/<id>/family_tree` → redirect/"Not authorized" (mirror the existing forbidden-view test); the `.json`/`.svg` routes likewise guarded.
     - `view_dynasty` page now contains a link to the family-tree route (`/family_tree`).

## Tasks / Subtasks
- [ ] Task 1 — Renderer data-* attrs + 3 routes. [Agent A]
- [ ] Task 2 — `family_tree.html` interactive page + view_dynasty nav link. [Agent B]
- [ ] Task 3 — Tests (renderer data-attrs + page/routes). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `visualization/family_tree_svg.py` (additive data-* attrs) + `blueprints/dynasty.py` (3 routes). Lazy-import the renderer inside the route.
- **Agent B** — NEW `templates/family_tree.html` + `templates/view_dynasty.html` (add one nav link). No python.
- **Agent C** — NEW `tests/unit/test_family_tree_svg_dataattrs.py` + `tests/integration/test_family_tree_page.py`. No source files.
- No shared files.

### FROZEN INTERFACE CONTRACT (authoritative)
- Renderer node `<g>` attrs: `data-person-id`, `data-father-id`, `data-mother-id`, `data-spouse-id` (empty string when absent). Additive only; `data-person-id` count unchanged; deterministic; valid SVG.
- Routes (url_for): `dynasty.family_tree` (GET `/dynasty/<id>/family_tree`, HTML), `dynasty.family_tree_svg_route` (GET `/dynasty/<id>/family_tree.svg`, raw SVG, `?show_deceased=`), `dynasty.person_detail_json` (GET `/dynasty/<id>/person/<int:person_id>.json`). All `@login_required` + ownership-guarded.
- `person_detail_json` dict keys EXACTLY: `id, name, surname, gender, birth_year, death_year, age, traits, titles, is_monarch, is_pretender, reign_start_year`.
- Frozen DOM ids in `family_tree.html`: `ft-viewport`, `ft-stage`, `ft-tooltip`, `ft-show-deceased`, `ft-search`, `ft-reset`.

### Reuse / project rules
- Renderer: `generate_family_tree_svg(dynasty_id, session, current_year=None, show_deceased=True)` (visualization/family_tree_svg.py:317). Node groups already carry `data-person-id`; satellites for cross-dynasty spouses already positioned (8-1 integrator fix) — add the new data-* there too.
- Route patterns: `view_dynasty` (blueprints/dynasty.py:224, ownership at :229, render at :286-296); JSON-route + ownership guard: `succession_candidates_json` (dynasty.py:1130-1136); `free_action_catalogue.json` (:704). Blueprint object `dynasty_bp` (:41). `db.session` available; `DynastyDB.query.get_or_404`. Lazy-import renderer.
- JS house style: pan/zoom state + `screenToWorld` + wheel handler + drag pan + tooltip DOM (`world_map.html:1162-1169, 1490-1589`); toast `_pushTurnToast` (:410-447). Use CSS transform on `#ft-stage` (the map uses canvas; here we transform an inline-SVG container — simpler).
- PersonDB fields + `get_traits()`/`get_titles()`: db_models.py:160-286 (227-241). SVG inline via `| safe` (view_dynasty.html:19,64,152). Templates extend base.html. No `print()`; flash categories success/danger/info/warning. No new deps.

### Out of scope / deferred
- Deleting `visualization/plotter.py`, removing ~203 `visualizations/*.png`, gitignoring them, and embedding the SVG INTO `view_dynasty.html` (replacing the static image) + populating `DynastyDB.family_tree_svg` → **Story 8-3**. 8-2 only links to the new page and renders on demand.

## Previous Story Intelligence
- Worktree contract-first via the **Workflow tool**. Each agent prompt MUST say "EXECUTE NOW — do not enter plan mode / EnterPlanMode, pre-approved" and "write only inside your worktree root (verify with git rev-parse --show-toplevel)". Worktrees branch off `main`; story file absent → contract inlined.
- **Integrator caution:** 7-3 had an agent write to the MAIN tree; verify where each agent's edits landed before integrating; copy the right files; zero-overlap. **Signature/attr drift** between impl (A) and tests (C) bit 7-1/7-2 — the frozen attr names + dict keys + DOM ids above are authoritative. 8-1's agent claimed a branch was reachable when it wasn't — INTEGRATOR MUST actually run the new tests AND eyeball the rendered page.
- Baseline **436 passed**. Tests: isolated temp DB (root `tests/conftest.py` `DATABASE_URL`), reset `/tmp/rss_pytest.db`, `python -m pytest -p no:randomly -q`.
- **UI story → run-the-app visual check REQUIRED at integration** (Epic 3 retro lesson): `MPLBACKEND=Agg python main_flask_app.py` (port 8091), log in `test_user`/`password`, open `/dynasty/<id>/family_tree`, confirm the tree renders, pan/zoom works, hovering shows a tooltip, the deceased toggle re-fetches, clicking highlights a bloodline, and search jumps to a node. The dev DB has one dynasty (id 1).

## References
- Renderer: `visualization/family_tree_svg.py:96-160` (`_node_svg`, where data-person-id is emitted), `:317` (entrypoint). DynastyDB col: db_models.py:82.
- Routes: `blueprints/dynasty.py:41,224,229,286-296,704,1130-1136`. Template SVG inline: `templates/view_dynasty.html:19,238-254`.
- JS: `templates/world_map.html:1162-1169,1490-1589,410-447`.
- Person fields: `models/db_models.py:160-286`.
- Test fixtures: `tests/integration/test_dynasty_routes.py:21-82,229-255`.

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool + main-session integrator.

### Completion Notes List
- All ACs satisfied. Full suite **452 passed** (436 baseline + 16 new), 0 failed. 3 worktree agents via Workflow (run wf_f29b9081-c17), main-session integrator. Clean worktree isolation (no main-tree leaks), no signature/attr/DOM-id drift.
- **Run-the-app visual check (UI story, per Epic 3 retro):** live dev server on :8091, logged in as test_user. `GET /dynasty/1/family_tree` → 200 with all toolbar hooks (`ft-viewport/ft-stage/ft-tooltip/ft-show-deceased/ft-search/ft-reset`) and a real 7-person inline tree. `family_tree.svg` → 200 `image/svg+xml`, 750×388; `?show_deceased=0` drops 7→6 nodes (toggle works). `person/<id>.json` → 200 with the exact 12 contract keys (age = death_year−birth_year verified); bogus id → 404. Pan/zoom/hover/highlight/search JS present in the page (mouse interactions not curl-drivable, but DOM hooks + script verified).
- No new pip deps. plotter.py / PNGs untouched and the SVG is NOT yet embedded into view_dynasty.html (only a nav link added) — both deferred to Story 8-3 as specified.

### File List
- `visualization/family_tree_svg.py` — MODIFIED (data-* attrs)
- `blueprints/dynasty.py` — MODIFIED (3 routes)
- `templates/family_tree.html` — NEW (interactive page)
- `templates/view_dynasty.html` — MODIFIED (nav link)
- `tests/unit/test_family_tree_svg_dataattrs.py` — NEW
- `tests/integration/test_family_tree_page.py` — NEW
- `_bmad-output/implementation-artifacts/{8-2-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED

### Change Log
| Date | Change |
|---|---|
| 2026-05-30 | spec(8-2); ready-for-dev; 3 worktree agents via Workflow |
