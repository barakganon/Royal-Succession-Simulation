# Royal Succession Simulation — Development Status

Last updated: 2026-04-02
Last commit: `1054a12` — Sprints 5-7: playability, UI overhaul, blueprint refactor

---

## Current State

**Tests:** 163 passed · 17 skipped · 0 failed
**App:** imports cleanly, all 6 blueprints registered
**`main_flask_app.py`:** 290 lines (down from ~3300) — app setup + blueprint registration only

---

## Feature Inventory (What Works)

### Auth — `blueprints/auth.py`
- Register, login, logout (Flask-Login + Werkzeug hashing)
- Dashboard: dynasty list paginated 20/page, AI advisor panel

### Dynasty — `blueprints/dynasty.py`
- Create dynasty (predefined themes or LLM-generated from user story)
- View dynasty: ruler card with SVG portrait, family grid, event timeline, coat of arms
- Advance turn (5 years): births, deaths, marriages, succession
- Turn report page: stat row, Your Chronicle event timeline, World News from AI dynasties
- Delete dynasty
- Double-submit protection (`is_turn_processing` lock + `block_if_turn_processing` decorator)
- Procedural SVG coat of arms (10+ charges, quartered shields, border treatments)
- Procedural SVG character portraits (4 age tiers, 7+ trait→visual mappings)
- Family tree PNG generation

### Military — `blueprints/military.py` (18 routes)
- 16 unit types, army formation, assign commander
- Land battles, siege resolution
- Naval combat + blockade
- Real-time battle ticker via SocketIO + LLM commentary
- Army / battle / siege detail pages

### Economy — `blueprints/economy.py` (13 routes)
- Resources: food, timber, stone, iron, gold
- Build, upgrade, repair buildings
- Develop territories, establish/cancel trade routes
- World economy overview, territory economy detail

### Diplomacy — `blueprints/diplomacy.py` (7 routes)
- Relation scores (color-coded with progress bars), prestige/honor/infamy
- Create/break treaties, send envoys
- Declare war, negotiate peace

### Map & Time — `blueprints/map.py` (18 routes)
- Interactive HTML5 canvas world map (click territories for sidebar detail)
- GeoJSON endpoint (`/game/<id>/map.geojson`)
- Territory detail, dynasty territories list
- Seasonal map, time view, timeline, advance time, schedule/cancel events
- Chronicle page: LLM-narrated entries or template fallback
- AI advisor: LLM or rule-based, cached per turn

### AI & LLM
- `AIController` — 4-phase per-turn decisions (diplomacy → military → economy → character)
- Wired into every `advance_turn` for all non-human dynasties
- Rule-based fallbacks when `GOOGLE_API_KEY` absent
- All prompts centralised in `utils/llm_prompts.py`

### UI
- Full medieval dark theme — all 27 templates styled
- Cinzel (headings) + Crimson Text (body) fonts
- CSS custom properties, Bootstrap 4 overrides, gold timeline, webkit scrollbars

---

## Known Issues

| Issue | Severity | Fix |
|-------|----------|-----|
| Circular FK cycle on dynasty/person_db/territory DROP | Medium | Add `use_alter=True` to affected FKs in `db_models.py` |
| 3 `GameManager` unit tests skipped | Low | Rewrite against current `create_new_game()` API |
| 6 `SimulationEngine` unit tests skipped | Low | Full rewrite — API is entirely stale |
| 7 diplomacy integration tests skipped | Low | Test fixtures need a second dynasty for relation tests |
| 2 dead placeholder routes in `blueprints/map.py` | Low | `create_dynasty_placeholder`, `view_dynasty_placeholder` — delete |
| `print()` statements in some model files | Low | Replace with `logger.debug()` |
| No victory conditions / game-over state | Medium | Not designed yet |
| No player onboarding / tutorial | Medium | First-time UX gap |
| Banking, espionage, court politics | Low | Post-MVP |

---

## Sprint 8 — Make It Feel Like a Game ✅

| # | Task | Files | Status |
|---|------|-------|--------|
| 8A | `action_phase` route — gathers territories, armies, economy, nobles | `blueprints/dynasty.py` | ✅ Done |
| 8B | `submit_actions` route — executes up to 3 AP of actions then calls process_dynasty_turn | `blueprints/dynasty.py` | ✅ Done |
| 8C | `templates/action_phase.html` — AP counter, 5 action cards, queue panel, ruler card, situation panel | new file | ✅ Done |
| 8D | "Advance Turn" button → "Take Actions" linking to action_phase | `templates/view_dynasty.html` | ✅ Done |
| 8E | Full-viewport hex map — topbar resources, hex canvas, side panel AP queue, chronicle feed, botbar | `templates/world_map.html` | ✅ Done |
| 8F | `generate_geojson(hex_mode=True)` — col/row/hue properties; `?hex=true` query param on route | `visualization/map_renderer.py`, `blueprints/map.py` | ✅ Done |

**Result:** Players now have a decision screen (3 Action Points across 5 action types) before each turn simulation runs. The world map is a full-viewport Travian-style hex canvas with resource topbar, action queue sidebar, and territory tooltip. Tests held at **163 passed, 0 failed**.

---

## Next Steps

| # | Task | Effort |
|---|------|--------|
| 9A | Fix 17 skipped tests (stale GameManager/SimulationEngine APIs + diplomacy fixtures) | Low |
| 9B | Fix circular FK cycle (`use_alter=True`) — unblocks dynasty DELETE test | Low |
| 9C | Victory conditions + endgame screen | Medium |
| 9D | Player onboarding / first-time tutorial | Medium |
| 9E | Banking / loans subsystem | High |
| 9F | Espionage / spy networks | High |
| 9G | ElevenLabs TTS narrator (requires API key) | Low |

---

## Architecture

| Concern | Decision |
|---------|----------|
| Routing | 6 Flask Blueprints: `auth`, `dynasty`, `military`, `economy`, `diplomacy`, `map` |
| `url_for()` | Always `'blueprint.function'` (e.g. `'dynasty.view_dynasty'`) |
| LLM prompts | All in `utils/llm_prompts.py` — never inline |
| LLM guard | `if llm_model is None: return fallback_value` everywhere |
| DB models | `back_populates` + `foreign_keys=` — never `backref=` |
| SVG storage | Stored as `Text` in DB, rendered with `\| safe` Jinja filter |
| SocketIO | `async_mode='threading'`, `allow_unsafe_werkzeug=True` for dev |
| Canvas map | Hexagonal territories using x/y centroids, auto-scaled |
| Turn summary | Stored in `flask_session` between `advance_turn` → `turn_report` redirect |
| Logging | Module loggers: `logging.getLogger('royal_succession.<module>')` |

---

## Sprint History

| Sprint | What | Result |
|--------|------|--------|
| 1 | SQLAlchemy fixes, auth Blueprint, integration tests | ✅ |
| 2 | AIController, living chronicle, AI advisor | ✅ |
| 3 | SVG coat of arms, SVG character portraits | ✅ |
| 4 | Naval combat, SocketIO battle ticker, HTML5 canvas map | ✅ |
| 5A | Wire AIController into every advance_turn | ✅ |
| 5B | Fix 7 legacy test failures, add 13 game-loop integration tests | ✅ |
| 5C | Turn-order enforcement (`is_turn_processing` lock) | ✅ |
| 5D | Chronicle table migration, dashboard pagination | ✅ |
| 6A | Full medieval dark CSS theme, base.html rewrite | ✅ |
| 6B | UI overhaul: view_dynasty, dashboard, military_view, economy_view | ✅ |
| 6C | Enhanced heraldry renderer, enhanced portrait renderer | ✅ |
| 6.5 | Turn report page, style remaining 5 templates | ✅ |
| 7 | Blueprint refactor: 5 blueprints extracted, main_flask_app 3300→290 lines | ✅ |
