# Story 3-1: World Map Side Panel Rebuild

Status: in-progress

## Story

As a player who wants the map to be the game's primary surface,
I want a vertical 60px icon rail on the left edge of the world map (dynasty CoA, resources, project slots, monarch portrait, chronicle/world/war buttons) and a stubbed slide-in detail panel on the right,
so that subsequent Sprint 3 stories (right-click context menus, detail panel content, pan/zoom, animated turn pass) have the structural surface they need without each story re-inventing the layout.

## Acceptance Criteria

1. **AC1 — New `.game-left-rail` element exists, 60px wide, full height of the game viewport.** Lives inside `.game-main`, to the LEFT of `.game-map-panel`. Vertical icon strip with these items in order (top → bottom):
   - **CoA icon** — small (40px) render of `dynasty.coat_of_arms_svg` (falls back to a generic shield icon when absent)
   - **Resource icons** — gold, iron, timber stacked vertically with their values
   - **3 project slot pills** — vertical pills showing the dynasty's active projects (up to 3 displayed; if fewer than 3 active, show empty placeholder pills with the slot number). Each pill is clickable.
   - **Monarch portrait** — 40px circular render of `current_monarch.portrait_svg` (falls back to a crown glyph)
   - **3 button icons** at the bottom — Chronicle (📖), World (🌍), War (⚔)

2. **AC2 — New `.game-detail-panel` slide-in `<aside>` exists, hidden by default.** Width 320px. Slides in from the right edge of the viewport on top of the existing right side panel (or directly on the map if the side panel is later removed). Toggled via a `.is-open` class. Has a close button (×) in the top-right of the panel that removes `.is-open`.

3. **AC3 — Project slot pills + bottom-rail buttons open the detail panel.** Clicking any of them sets a global JS variable `currentDetailContext` (e.g. `{type: 'project', id: 5}` or `{type: 'chronicle'}`) and adds `.is-open` to `.game-detail-panel`. The panel body is just stubbed text for now ("Project #5 detail — Story 3-3 fills this") — Story 3-3 wires the real content. The detail panel container reserves a `<div id="detail-body">` for that future content.

4. **AC4 — `world_map` route passes `active_projects` to the template.** The route calls `ProjectSystem(db.session).get_active_projects(dynasty_id)` (when `dynasty_id` is set) and renders a serialized list of dicts to the template: `[{'id': p.id, 'project_type': p.project_type, 'started_year': p.started_year, 'completion_year': p.completion_year}, ...]` (max 3 entries — the player gets the first 3 by `started_year` for deterministic ordering). The serialization is necessary because the template can't safely access raw ORM objects (project-context.md rule).

5. **AC5 — Existing canvas / tooltip / overlay buttons / right side panel are UNCHANGED.** Story 3-1 only adds the left rail + right detail panel. The existing `.game-side-panel` (action queue, chronicle feed, AP display) remains intact — Sprint 4 (Story 3-5) owns its removal.

6. **AC6 — Existing integration tests still pass.** `pytest` must stay at **277 passed, 0 failed, 0 skipped**. The new elements are additive; nothing in the existing template's hierarchy is removed. The existing `test_dynasty_routes.py` assertions on `House Ironwood` and on world_map response status stay green.

7. **AC7 — One new integration test asserts the new DOM elements exist.** `tests/integration/test_world_map_panels.py` (NEW) renders `/world/map` for an authenticated user with a dynasty and asserts the response HTML contains `id="game-left-rail"`, `class="game-detail-panel"` (or similar), `id="detail-body"`, and one project slot placeholder string. Skipping a real DOM parse — substring assertions are sufficient for stub content.

## Tasks / Subtasks

- [ ] Task 1: Add CSS for `.game-left-rail`, `.game-detail-panel`, `.game-project-slot`, `.game-rail-btn`, `.game-rail-resource` (AC1, AC2)
  - [ ] `.game-left-rail`: 60px wide, vertical flex, dark background matching `.game-side-panel`, scrolls if content overflows.
  - [ ] `.game-detail-panel`: 320px wide, positioned `absolute` right:0, transform `translateX(100%)` by default, `translateX(0)` when `.is-open`. Smooth transition.
  - [ ] `.game-project-slot`: rounded pill, ~36×36 area with optional badge for project_type abbreviation.

- [ ] Task 2: Restructure `templates/world_map.html` (AC1, AC2, AC3, AC5)
  - [ ] Insert `<div id="game-left-rail" class="game-left-rail">` as the first child of `.game-main`, before `.game-map-panel`.
  - [ ] Render CoA (40px), 3 resource entries (gold/iron/timber with value below icon), 3 project slots (iterate `active_projects`, fill empty slots with placeholder), monarch portrait, 3 bottom buttons.
  - [ ] Insert `<aside class="game-detail-panel" id="game-detail-panel">` as the last child of `.game-main` with a `<div id="detail-body">Loading...</div>` and a close button.
  - [ ] Leave existing `.game-side-panel` (action queue + chronicle feed) in place.
  - [ ] Existing `.game-topbar`: REMOVE the 5 resource pills (now in left rail). Keep CoA + dynasty name + year + End Turn.

- [ ] Task 3: Add JS toggle logic at the bottom of `world_map.html` `extra_scripts` block (AC3)
  - [ ] `window.currentDetailContext = null;`
  - [ ] `function openDetailPanel(ctx) { window.currentDetailContext = ctx; document.getElementById('game-detail-panel').classList.add('is-open'); document.getElementById('detail-body').textContent = JSON.stringify(ctx) + ' — Story 3-3 fills this.'; }`
  - [ ] `function closeDetailPanel() { document.getElementById('game-detail-panel').classList.remove('is-open'); }`
  - [ ] Wire the project slot pills and the 3 bottom buttons via `onclick` attributes calling these functions with the right context dict.

- [ ] Task 4: Update `blueprints/map.py::world_map` to pass `active_projects` (AC4)
  - [ ] Import `from models.project_system import ProjectSystem`.
  - [ ] When `dynasty_id` is set, call `ps = ProjectSystem(db.session); projects = ps.get_active_projects(dynasty_id)`.
  - [ ] Sort by `started_year` (ascending), take the first 3, serialize each to a plain dict.
  - [ ] Pass `active_projects=...` to `render_template`. If no dynasty, pass `active_projects=[]`.

- [ ] Task 5: Integration test in `tests/integration/test_world_map_panels.py` (NEW) (AC7)
  - [ ] GET `/world/map` as an authenticated user with a dynasty.
  - [ ] Assert response 200.
  - [ ] Assert `b'id="game-left-rail"' in response.data`.
  - [ ] Assert `b'id="game-detail-panel"' in response.data` or the slide-in class is present.
  - [ ] Assert `b'id="detail-body"' in response.data`.

- [ ] Task 6: Run `pytest`, confirm 278+ passed, 0 failed, 0 skipped (AC6, AC7)

- [ ] Task 7: Commit, push, merge.

## Dev Notes

### Files to change

| File | Change type | Description |
|---|---|---|
| `templates/world_map.html` | UPDATE | Add left rail + right detail panel; strip topbar resource pills; ~120 LoC added, ~10 removed |
| `static/style.css` | UPDATE | New `.game-left-rail`, `.game-detail-panel`, `.game-project-slot`, `.game-rail-btn`, `.game-rail-resource`. ~80 LoC added |
| `blueprints/map.py` | UPDATE | Import ProjectSystem; serialize active_projects; pass to template (~12 LoC) |
| `tests/integration/test_world_map_panels.py` | NEW | 1 integration test asserting the new DOM elements (~50 LoC) |

### Limitation: cannot run dev server in this session

CLAUDE.md says "For UI or frontend changes, start the dev server and use the feature in a browser before reporting the task as complete." This session can't do that. The story will be reported as **DONE for structure and tests**, but **VISUAL VERIFICATION DEFERRED** — flagged in completion notes for the user to verify manually before Sprint 3 stories pile on top.

### Why keep the existing `.game-side-panel`

Master plan's final-state layout shows the right side panel REPLACED by the slide-in detail panel. But the side panel currently hosts the action queue + chronicle feed — Sprint 4 (Story 4-1 free_action endpoint) owns the action queue's removal, and Sprint 3 Story 3-5 owns the world_map → dashboard re-routing. Story 3-1 just adds the new structural elements; removal of the legacy side panel is sequenced for those later stories. Keeping it now avoids breaking the existing turn-submission flow.

### Left rail layout (60px wide, top → bottom)

```
┌──────┐
│ CoA  │  40px square
├──────┤
│  💰  │  gold icon
│ 100  │  value (8pt font)
├──────┤
│  ⛏  │  iron
│  50  │
├──────┤
│  🪵  │  timber
│  50  │
├──────┤
│ ⚙ 1  │  project slot 1 (clickable)
├──────┤
│ ⚙ 2  │  project slot 2 (clickable)
├──────┤
│ ⚙ 3  │  project slot 3 (clickable)
├──────┤
│  👑  │  monarch portrait
├──────┤
│  📖  │  Chronicle button
├──────┤
│  🌍  │  World button
├──────┤
│  ⚔  │  War button
└──────┘
```

Project slots show `1 / 2 / 3` numbers when empty. When filled, they show a 2-letter abbreviation of `project_type` (e.g. `BF` for `build_farm`, `RI` for `recruit_infantry`).

### Right detail panel (320px wide, slide-in from right)

```
┌────────────────────────────┐
│ Detail              [×]    │  header bar with close button
├────────────────────────────┤
│                            │
│ <div id="detail-body">    │  Story 3-3 populates this
│   Loading...               │
│ </div>                     │
│                            │
└────────────────────────────┘
```

### `active_projects` serialization shape

```python
active_projects = [
    {
        'id': 5,
        'project_type': 'build_cathedral',
        'started_year': 1300,
        'completion_year': 1315,
    },
    ...
]
```

Max 3 entries. Sorted by `started_year` ascending. Empty list if no dynasty or no active projects.

### Why integration test uses substring assertions

Adding a full DOM parser (BeautifulSoup, lxml) for this one test would introduce a new dependency and isn't worth it. Substring checks for distinctive `id=` and `class=` attributes are sufficient to prove the new elements rendered.

### Limitation: project_type abbreviation rendering

`{{ project_type[:2].upper() }}` in the template gives `BU` for `build_farm`, not `BF`. To get `BF` we'd need a Python helper or a small JS-side mapping. For Story 3-1's stub purposes, a 2-character slice is fine; Sprint 3 Story 3-3 can wire a real `project_label` per the Story 2-4 `_PROJECT_LABELS` dict.

### What this story does NOT touch (scope boundaries)

- `models/db_models.py` — no schema changes.
- Existing canvas / tooltip / overlay-button code — unchanged.
- Existing right side panel (action queue, chronicle feed, AP display) — kept intact, removed in 3-5.
- Right-click context menu — Story 3-2.
- Detail panel content (territory / project / monarch templates) — Story 3-3.
- Border drawing, pan/zoom, overlay tabs — Story 3-4.
- Animated turn pass, routing change, action_phase.html deletion — Story 3-5.

### Branch name

`feature/world-map-panel-rebuild` (already created).

### Commit plan

- Commit 1: `feat(world-map): add 60px left rail with CoA / resources / project slots / monarch / nav buttons`
- Commit 2: `feat(world-map): add stub slide-in detail panel as right-side aside`
- Commit 3: `feat(map-route): pass active_projects to world_map template`
- Commit 4: `test: world_map renders new left rail + detail panel`

### References

- Master plan: `review_documents/8_master_plan_2026.md` lines 261-290 (Sprint 3 layout)
- Current world_map.html: `templates/world_map.html`
- Current world_map route: `blueprints/map.py:72-152`
- Layout CSS: `static/style.css` lines 813-905 (`.game-viewport` family)
- ProjectSystem.get_active_projects: `models/project_system.py`
- Existing integration test patterns: `tests/integration/test_dynasty_routes.py`

## Dev Agent Record

### Agent Model Used

(to be filled by dev agent)

### Implementation Plan

(to be filled by dev agent)

### Completion Notes

(to be filled by dev agent)

### File List

(to be filled by dev agent)

### Change Log

(to be filled by dev agent)
