# Royal Succession Simulation — Development Status

Last updated: 2026-03-25 (Sprint 6.5 complete)

---

## Sprint 7 — Blueprint Refactor ✅

| # | Blueprint | Routes Extracted | Status |
|---|-----------|-----------------|--------|
| 7-1 | `blueprints/dynasty.py` | create_dynasty, view_dynasty, advance_turn, turn_report, delete_dynasty + 9 helpers | ✅ Done |
| 7-2 | `blueprints/military.py` | 18 routes: military_view, recruit_unit, form_army, battle, siege, naval_battle, move_army, etc. | ✅ Done |
| 7-3 | `blueprints/economy.py` | 13 routes: dynasty_economy, build/upgrade/repair_building, develop_territory, trade, etc. | ✅ Done |
| 7-4 | `blueprints/diplomacy.py` | 7 routes: diplomacy_view, treaty_view, diplomatic_action, declare_war, negotiate_peace, etc. | ✅ Done |
| 7-5 | `blueprints/map.py` | 18 routes: world_map, map.geojson, territory_details, dynasty_territories, chronicle, advisor, time_view, etc. | ✅ Done |

**Result:** `main_flask_app.py` reduced from ~3300 lines → 290 lines (app setup, blueprint registration, shared helpers only).
All tests maintained: **163 passed, 17 skipped, 0 failures** after every extraction step.
All `url_for()` references updated across all templates to use `blueprint.function` prefixes.

---

## Sprint 6.5 — Turn Report & Remaining Page Styling ✅

| # | Task | Status |
|---|------|--------|
| 6.5A-1 | `process_dynasty_turn()` returns 3-tuple `(success, message, turn_summary)` with structured event list | ✅ Done |
| 6.5A-2 | `advance_turn` stores summary in flask session; redirects to `/dynasty/<id>/turn_report` | ✅ Done |
| 6.5A-3 | `turn_report` route queries AI dynasty events for World News panel | ✅ Done |
| 6.5A-4 | `templates/turn_report.html` — stat row, Your Chronicle timeline, World News panel, event type breakdown, Continue button | ✅ Done |
| 6.5B-1 | `templates/login.html` — "Enter the Realm" card with gold top-border | ✅ Done |
| 6.5B-2 | `templates/register.html` — "Pledge Your Name" card | ✅ Done |
| 6.5B-3 | `templates/create_dynasty.html` — "Found Your Dynasty" with themed theme selector | ✅ Done |
| 6.5B-4 | `templates/diplomacy_view.html` — breadcrumb, color-coded relation scores with progress bars, war/treaty sections | ✅ Done |
| 6.5B-5 | `templates/chronicle.html` — parchment-style entry cards with year badges, empty state, CoA header | ✅ Done |

**CSS additions in `static/style.css`:**
- `.turn-report-stat` stat box (big number + label)
- `.turn-report-event-list` flex event list (inline icons, no absolute positioning)
- `.section-divider` gold diamond divider line

---

## Sprint 6B — UI Panel & Template Overhaul ✅

| # | Task | Status |
|---|------|--------|
| 6B-1 | `templates/view_dynasty.html` — ruler card with portrait, family grid, event timeline, CoA header, action bar | ✅ Done |
| 6B-2 | `templates/dashboard.html` — dynasty cards with CoA thumbnails, paginated list, AI advisor parchment panel | ✅ Done |
| 6B-3 | `templates/military_view.html` — breadcrumb, themed cards, action buttons | ✅ Done |
| 6B-4 | `templates/economy_view.html` — same treatment as military | ✅ Done |

---

## Sprint 6C — Art Layer ✅

| # | Task | Status |
|---|------|--------|
| 6C-1 | `visualization/heraldry_renderer.py` enhanced — 10+ charges, quartered shields, border treatments, motto banner | ✅ Done |
| 6C-2 | `visualization/portrait_renderer.py` enhanced — 4 age tiers, 7 trait mappings, crown/collar accessories | ✅ Done |

---

## Sprint 6A — Medieval Dark Theme ✅

| # | Task | Status |
|---|------|--------|
| 6A-1 | Rewrite `static/style.css` — full medieval dark theme with CSS variables, Cinzel/Crimson Text fonts, custom buttons/cards/alerts/tables/timeline/scrollbars | ✅ Done |
| 6A-2 | Rewrite `templates/base.html` — Google Fonts preconnect, gold navbar brand with sword glyph, dark footer with chronicle tagline, `extra_scripts` block | ✅ Done |
| 6A-3 | Flask app-load verification — no errors introduced | ✅ Verified |

**Key design choices:**
- CSS variables for the full colour palette (parchment, blood-red, gold, forest, midnight, dark-card, dark-border, text-light, text-muted).
- `Cinzel` for all headings, nav brand, card headers, button labels; `Crimson Text` for body copy — both loaded via Google Fonts with `<link rel="preconnect">` in `<head>` and `@import` in CSS for fallback environments.
- Bootstrap 4 component overrides (cards, buttons, alerts, list-groups, tables, badges, forms, modals, pagination) keep full Bootstrap grid functionality while replacing all light-mode colours.
- `.card-header::before` injects a sword glyph (`⚔`) automatically on every card header.
- Timeline rewritten with gold gradient left-border and glowing gold dot markers.
- Webkit scrollbar styled thin/dark with gold thumb.
- Footer changed from `bg-light` to `var(--midnight)` with gold text and the tagline "Dynasty Saga — A Chronicle of Power".
- All existing `url_for` calls and Jinja blocks left intact.

---

## Sprint 5B — Test Suite Fixes & Game-Loop Integration Tests ✅

| # | Task | Status |
|---|------|--------|
| 5B-1 | Fix 7 pre-existing failures in `test_flask_app.py` + `test_game_flow.py` | ✅ Done |
| 5B-2 | Add `tests/functional/conftest.py` to wire real Flask app into functional tests | ✅ Done |
| 5B-3 | Set `MPLBACKEND=Agg` in root `tests/conftest.py` so `plt.show()` is a no-op | ✅ Done |
| 5B-4 | Create `tests/integration/test_game_loop.py` (13 new tests) | ✅ Done |

**Root causes fixed:**
- `test_flask_app.py` used `/create_dynasty` (wrong URL), `name`/`theme`/`confirm_password` (wrong form field names), `Royal Succession Simulation` (wrong page title), `Year: 1400` (wrong — template renders `Current Year:`), and `/dynasty/<id>` (wrong — correct path is `/dynasty/<id>/view`). Also needed a logout before testing wrong-password flow.
- `test_game_flow.py` used the root conftest's minimal Flask app (no routes). Added `tests/functional/conftest.py` to override `app`/`db` with the real Flask app. Fixed URLs, form fields, turn advancement route (`GET /dynasty/<id>/advance_turn` instead of `POST /dynasty/<id>/process_turn`), and year increments (5 per turn). Removed delete step (blocked by pre-existing `CircularDependencyError` on dynasty/person_db FK cycle).
- Matplotlib `plt.show()` hangs in CI — fixed by setting `MPLBACKEND=Agg` in root conftest.

**New game-loop tests (`tests/integration/test_game_loop.py`):**
- `TestCreateDynastyAndView` (4 tests) — dynasty creation, dashboard presence, view page, founder check
- `TestAdvanceTurn` (3 tests) — HTTP 200, year increments by 5, flash message
- `TestAdvanceMultipleTurns` (3 tests) — 3 turns → year 1315, history events exist, timeline accessible
- `TestSuccession` (1 test) — monarch death mocked, succession logic verified
- `TestAdvanceTurnUnauthorized` (2 tests) — unauthenticated redirect to login; second user cannot advance another's turn

**Final test counts:** 163 passed, 17 skipped, **0 failures**.

---

## Sprint 5D — DB Migration & Pagination ✅

| # | Task | Status |
|---|------|--------|
| 5D-1 | `chronicle_entry` table guaranteed on startup via explicit check in `_create_tables_if_not_exist` | ✅ Done |
| 5D-2 | `ChronicleEntryDB` added to `db_initialization.py` imports | ✅ Done |
| 5D-3 | Dashboard dynasty list paginated (20/page) in `blueprints/auth.py` + `templates/dashboard.html` | ✅ Done |
| 5D-4 | `living_nobles` in `view_dynasty` capped at 50 rows | ✅ Done |
| 5D-5 | `recent_events` (limit 10) and history log queries already limited — no change needed | ✅ Confirmed |

---

## Sprint 5C — Turn-Order Enforcement ✅

| # | Task | Status |
|---|------|--------|
| 5C-1 | Add `is_turn_processing` Boolean column to `DynastyDB` | ✅ Complete |
| 5C-2 | DB migration in `db_initialization.py` (`_migrate_from_v0_to_v1` + version check) | ✅ Complete |
| 5C-3 | `block_if_turn_processing` decorator in `main_flask_app.py` | ✅ Complete |
| 5C-4 | Apply decorator + `try/finally` lock to `advance_turn` route | ✅ Complete |

**Approach:** A simple Boolean lock (`is_turn_processing`) on `DynastyDB` prevents concurrent or double-submitted turn advances.

- `block_if_turn_processing` reads the flag before the route handler runs; if `True` it flashes a `"warning"` message and redirects to the dynasty view.
- Inside `advance_turn`, the flag is set to `True` (committed immediately) then wrapped in an outer `try/finally` block so it is always cleared to `False` and committed — even if `process_dynasty_turn`, the AI loop, or any inner exception causes an early return or propagation.
- `from functools import wraps` added to `main_flask_app.py` imports.
- Migration: `is_turn_processing BOOLEAN DEFAULT 0 NOT NULL` added to `_migrate_from_v0_to_v1`; column name added to the `required_columns` list in `_get_db_version` so existing DBs are auto-migrated on next startup.

---

## Sprint 5A — AIController Wiring ✅

| # | Task | Status |
|---|------|--------|
| 5A | Wire AIController into `advance_turn` loop so AI dynasties decide every turn | ✅ Complete |

**Root cause found:** `advance_turn` route called `process_dynasty_turn()` (human-only) but never called `GameManager.process_ai_turns()`. The `AIController` class and `GameManager.process_ai_turns()` / `register_ai_dynasties()` were fully implemented but never invoked from the turn-advancement path.

**Fix applied:** After `process_dynasty_turn()` succeeds, `advance_turn` now instantiates `GameManager(db.session)` and calls `process_ai_turns(user_id=current_user.id)`. This triggers `register_ai_dynasties()` (auto-registers controllers on first run), then runs all 4 AIController phases (diplomacy → military → economy → character) for every `is_ai_controlled=True` dynasty owned by the user. LLM is used when available; rule-based fallbacks run when `LLM_MODEL_GLOBAL is None`. All decisions logged at `logger.info`. AI failures are caught and logged without aborting the human player's turn.

---

## ✅ ALL PREVIOUS SPRINTS COMPLETE

---

## Sprint 1 — Stability ✅

| # | Task | Status |
|---|------|--------|
| A | SQLAlchemy backref conflicts + error handling + print→logger | ✅ Merged |
| B | Auth Blueprint (`blueprints/auth.py`) | ✅ Merged |
| C | Integration tests (107 tests, 98 pass, 9 skip) | ✅ Merged |

---

## Sprint 2 — AI & LLM Features ✅

| # | Task | Status |
|---|------|--------|
| D | AI player (`models/ai_controller.py` — 4 phases, LLM + rule-based) | ✅ Merged |
| E | Living chronicle (`ChronicleEntryDB`, `/game/<id>/chronicle`) | ✅ Merged |
| F | AI advisor (`/game/<id>/advisor`, dashboard panel) | ✅ Merged |

---

## Sprint 3 — Visual Layer ✅

| # | Task | Status |
|---|------|--------|
| G | SVG coat of arms (`visualization/heraldry_renderer.py`) | ✅ Merged |
| H | SVG character portraits (`visualization/portrait_renderer.py`) | ✅ Merged |

---

## Sprint 4 — Infrastructure ✅

| # | Task | Status |
|---|------|--------|
| I | Naval combat + blockade + `/dynasty/<id>/naval_battle` | ✅ Merged |
| J | Real-time battle ticker (Flask-SocketIO + LLM commentary) | ✅ Merged |
| K | Interactive HTML5 canvas map (replaces Matplotlib PNG) | ✅ Merged |

---

## Final Test Suite

| Category | Count |
|----------|-------|
| **Passed** | **163** |
| **Failed** | **0** |
| Skipped | 17 |
| Total | 180 |

Sprint 5B fixed the 7 pre-existing failures in `test_flask_app.py` + `test_game_flow.py` and added 13 new game-loop integration tests in `tests/integration/test_game_loop.py`.

---

## Complete Feature Inventory

### Authentication
- `/login`, `/logout`, `/register` — Flask Blueprint (`blueprints/auth.py`)
- `/dashboard` — user hub with dynasty list, AI advisor panel

### Dynasty & Characters
- `/dynasty/create`, `/dynasty/<id>`, `/dynasty/<id>/territories`
- Procedural coat of arms SVG on dashboard + territory page
- Procedural character portrait SVG on dynasty view (ruler + family)

### Military
- `/dynasty/<id>/military`, `/recruit_unit`, `/form_army`, `/army/<id>/battle`
- `/dynasty/<id>/naval_battle` — naval combat with blockade mechanics
- Real-time battle ticker via SocketIO (live round feed + LLM commentary)

### Economy
- `/dynasty/<id>/economy`, `/build`, `/upgrade`, `/repair`, `/develop_territory`

### Diplomacy
- `/dynasty/<id>/diplomacy`, `/diplomatic_action`, `/declare_war`, `/negotiate_peace`

### AI & LLM
- `/game/<id>/advisor` — AI advisor (LLM or rule-based fallback, cached per turn)
- `/game/<id>/chronicle` — dynasty chronicle (LLM narrated or template fallback)
- `AIController` — 4-phase AI for non-human dynasties (diplomacy/military/economy/character)

### World Map
- `/world/map` — Interactive HTML5 canvas map (click territories, sidebar details)
- `/game/<id>/map.geojson` — territory data as GeoJSON

---

## Known Remaining Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| 7 legacy test failures | ✅ Fixed | Fixed in Sprint 5B — URLs, form fields, page titles, matplotlib Agg backend |
| Circular FK cycle on dynasty/person_db/territory DROP | Medium | `use_alter=True` on FKs needed |
| `main_flask_app.py` still a monolith | High | Auth done; 5 more Blueprints remaining (military/economy/diplomacy/map/dynasty) |
| Turn-order enforcement | ✅ Fixed | `is_turn_processing` Boolean lock + `block_if_turn_processing` decorator (Sprint 5C) |
| No pagination on list endpoints | ✅ Fixed | Dashboard paginated 20/page (Sprint 5D); living_nobles capped at 50 |
| `chronicle_entry` table creation | ✅ Fixed | `checkfirst=True` on explicit `.create()` call (Sprint 5D) |
| Banking/loans, espionage, court politics | Low | Post-MVP |

---

## Architecture Decisions Made

- Auth Blueprint: all auth `url_for` calls use `'auth.<name>'`
- All LLM prompts in `utils/llm_prompts.py` (6 functions: ai_decision, chronicle, chronicle_fallback, advisor, advisor_fallback, battle_commentary)
- LLM guard everywhere: `if llm_model is None: return fallback_value`
- DB models use `back_populates` + `foreign_keys=` — never `backref=`
- SVGs stored as Text in DB, rendered with `| safe` Jinja filter
- SocketIO: `async_mode='threading'`, `allow_unsafe_werkzeug=True` for dev
- Canvas map: hexagonal territories (Territory only has x/y centroids, no polygon data), auto-scaled to canvas
