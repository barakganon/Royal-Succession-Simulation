# CLAUDE.md — Royal Succession Simulation
> Read this file at the start of every session. Update STATUS.md after completing any task.

---

## What This Project Is

A browser-based grand strategy / dynasty management game inspired by Crusader Kings and Travian.
Players control a noble dynasty across generations: manage territory on a hex map, recruit and
march armies, build structures, arrange marriages, manage resources, and survive succession crises.

**The core design goal:** every turn the player makes 3 meaningful decisions before clicking End Turn.
The map is the main game screen — not a separate page. Actions happen in-context on the map.

---

## Current State (as of Sprint 7 complete)

- **163 tests pass, 0 failures, 17 skipped**
- All Flask routes extracted into 6 blueprints (`auth`, `dynasty`, `military`, `economy`, `diplomacy`, `map`)
- `main_flask_app.py` is ~290 lines (app setup + blueprint registration only)
- Medieval dark theme applied to all 27 templates (Cinzel/Crimson Text fonts, CSS variables)
- AI controller wired into every `advance_turn`; LLM or rule-based fallback
- SVG coat of arms + character portraits procedurally generated
- Real-time battle ticker via Flask-SocketIO
- Interactive HTML5 canvas map (hex grid, click to select, hover tooltip)

**Known remaining issues:**
- Circular FK cycle on dynasty/person_db DROP (`use_alter=True` needed)
- 3 GameManager unit tests skipped (stale API)
- 6 SimulationEngine unit tests skipped (stale API)
- No victory conditions / endgame screen
- No player tutorial / onboarding

---

## Active Sprint: Sprint 8 — Make It Feel Like a Game

This is the most important sprint. The project has great systems but no player agency between turns.
Two parallel tracks:

### Track A — Action Phase (gameplay)
Add a player decision screen between "click End Turn" and the simulation running.

**New route:** `GET /dynasty/<id>/action_phase`
- Renders `templates/action_phase.html`
- Passes to template: territories (player-owned), armies, nobles (unmarried), current resources,
  available building types, neighboring dynasties
- Player has **3 Action Points** to spend across 5 action types

**New route:** `POST /dynasty/<id>/submit_actions`
- Receives JSON list of chosen actions
- Executes them using existing system methods (see "Existing Systems" section below)
- Then calls `process_dynasty_turn()` and redirects to turn report

**Action types and their backing methods (all already implemented):**
| Action | Cost | Method to call |
|--------|------|----------------|
| Recruit troops | 1 AP | `MilitarySystem.recruit_unit(dynasty_id, unit_type, size, territory_id)` |
| Build structure | 1 AP | `EconomySystem.construct_building(territory_id, building_type)` |
| Develop territory | 1 AP | `EconomySystem.develop_territory(territory_id)` |
| March army | 1 AP | Move `Army.territory_id` to target territory_id |
| Arrange marriage | 1 AP | Reuse `process_marriage_check()` logic from `blueprints/dynasty.py` |
| Trade route | 1 AP | `EconomySystem.establish_trade_route(source_id, target_id, resource_type, amount)` |
| Declare war | 1 AP | `DiplomacySystem.declare_war(attacker_id, defender_id, casus_belli)` |

**Wire-up change in `blueprints/dynasty.py`:**
- `advance_turn` route currently does everything in one click
- Change: the "Advance Turn" button on `view_dynasty.html` now goes to `action_phase`
- The "End Turn" button on `action_phase.html` POSTs to `submit_actions`
- `submit_actions` executes queued actions, then calls `process_dynasty_turn()`, redirects to turn report

**Resource bar data** for `action_phase.html` comes from:
`EconomySystem(db.session).calculate_dynasty_economy(dynasty_id)` — already returns gold, food,
iron, timber, manpower totals and net production rates.


### Track B — Travian-Style Map UI

Replace the current `world_map.html` with a full-viewport game screen.
The mockup has been approved — implement it exactly.

**Layout structure (no Bootstrap grid on this page):**
```
┌─────────────────────────────────────────────────────────────┐
│  TOPBAR: dynasty name │ gold food iron timber manpower │ year │ END TURN btn │
├──────────────────────────────────────────┬──────────────────┤
│                                          │  Ruler mini card  │
│         HEX MAP CANVAS (flex: 1)         │  Action Points    │
│                                          │  Action list      │
│   hover → tooltip with territory info   │  Chronicle feed   │
│   click → select territory              │                   │
│   map-overlay buttons: Map/Armies/Econ  │                   │
├──────────────────────────────────────────┴──────────────────┤
│  BOTBAR: status message                    selected territory │
└─────────────────────────────────────────────────────────────┘
```

**Hex grid rendering** (replace current polygon GeoJSON approach):
- Each territory is a hex cell, stored with `col` and `row` in the DB
- `hexCenter(col, row)` → pixel center using flat-top hex math:
  `x = R * sqrt(3) * col + (row%2 * R * sqrt(3)/2)`, `y = R * 1.5 * row`
- Use `R = 28` pixels per hex
- Hit detection: find closest hex center within R pixels of click
- Terrain fills: plains `#3a4a2a`, hills `#4a4a3a`, forest `#1a3a1a`,
  mountains `#3a3a4a`, coastal `#1a2a4a`, river `#1a3a4a`
- Dynasty ownership overlay: `hsla(dynastyHue, 55%, 45%, 0.45)` clipped to hex
- Selected hex: gold `#f0c040` stroke, 2.5px
- Army token: red dot `#8b1a1a` with gold border at hex center + 8px offset
- Capital: gold filled circle at hex center - 8px

**GeoJSON route update** (`blueprints/map.py` → `map_geojson`):
Add `hex=true` query param mode that returns:
```json
{
  "features": [{
    "properties": {
      "territory_id": 1, "col": 3, "row": 2,
      "name": "Ironmoor", "terrain_type": "hills",
      "owner_dynasty_id": 1, "owner_dynasty_name": "House Mortimer",
      "population": 1240, "army_count": 1, "is_capital": false,
      "development_level": 3, "base_tax": 12
    }
  }]
}
```

**Resource bar** in topbar: call `EconomySystem.calculate_dynasty_economy(dynasty_id)` and
pass `total_production`, `total_consumption`, `net_production`, `current_treasury` to template.

**Action Point sidebar** on the map page:
- Shows the same 5 action types as `action_phase.html`
- Clicking an action + clicking a hex queues the action
- "End Turn" button in topbar submits queued actions to `submit_actions` route

**CSS additions to `static/style.css`:**
```css
.game-viewport { display:flex; flex-direction:column; height:calc(100vh - 60px); overflow:hidden; }
.game-topbar { ... }  /* resource bar */
.game-main { display:flex; flex:1; min-height:0; }
.game-map-panel { flex:1; position:relative; overflow:hidden; background:#0a1520; }
.game-side-panel { width:200px; ... }
.game-botbar { ... }
```

**base.html change:** add `{% block body_class %}{% endblock %}` to `<body>` tag.
`world_map.html` sets `{% block body_class %}game-page{% endblock %}` and overrides
the default `container mt-4` main wrapper to use `game-viewport` instead.


---

## Existing Systems — What's Already Built (Do Not Rewrite)

### blueprints/ (all routes)
| Blueprint | File | Key routes |
|-----------|------|-----------|
| auth | `blueprints/auth.py` | `/login`, `/logout`, `/register`, `/dashboard` |
| dynasty | `blueprints/dynasty.py` | `/dynasty/create`, `/dynasty/<id>/view`, `/dynasty/<id>/advance_turn`, `/dynasty/<id>/turn_report` |
| military | `blueprints/military.py` | `/dynasty/<id>/military`, `/recruit_unit`, `/form_army`, `/army/<id>/battle`, `/naval_battle` |
| economy | `blueprints/economy.py` | `/dynasty/<id>/economy`, `/build_building`, `/upgrade_building`, `/develop_territory`, `/trade` |
| diplomacy | `blueprints/diplomacy.py` | `/dynasty/<id>/diplomacy`, `/diplomatic_action`, `/declare_war`, `/negotiate_peace` |
| map | `blueprints/map.py` | `/world/map`, `/game/<id>/map.geojson`, `/territory/<id>`, `/game/<id>/chronicle`, `/game/<id>/advisor` |

### models/ (all implemented, use as-is)
- `MilitarySystem` — `recruit_unit()`, `form_army()`, `assign_commander()`, `initiate_battle()`, `resolve_naval_battle()`
- `EconomySystem` — `construct_building()`, `upgrade_building()`, `repair_building()`, `develop_territory()`, `establish_trade_route()`, `calculate_dynasty_economy()`, `update_dynasty_economy()`
- `DiplomacySystem` — `declare_war()`, `negotiate_peace()`, `create_treaty()`, `perform_diplomatic_action()`
- `AIController` — 4-phase AI, wired into `advance_turn` for non-human dynasties
- `GameManager` — `process_ai_turns(user_id)`, `create_new_game()`
- `MapGenerator` / `TerritoryManager` / `BorderSystem` — map generation, territory assignment
- `TimeSystem` — `process_turn()`, `get_current_season()`, `calculate_action_points()`

### visualization/ (all implemented, SVG stored in DB)
- `heraldry_renderer.py` — `generate_coat_of_arms(dynasty_id, name)` → SVG string
- `portrait_renderer.py` — `generate_portrait(person_id)` → SVG string (called via `person.generate_portrait()`)
- `map_renderer.py` — `generate_geojson(dynasty_id, session)` → GeoJSON dict

### db_models.py — Key tables
```
DynastyDB       id, name, user_id, current_wealth, current_iron, current_timber,
                current_simulation_year, start_year, coat_of_arms_svg,
                is_turn_processing, last_played_at, theme_identifier_or_json

PersonDB        id, dynasty_id, name, surname, gender, birth_year, death_year,
                is_monarch, is_noble, reign_start_year, spouse_sim_id,
                mother_sim_id, father_sim_id, portrait_svg, traits_json, titles_json

Territory       id, name, terrain_type, controller_dynasty_id, population,
                development_level, base_tax, base_manpower, fortification_level,
                x_coord, y_coord, is_capital, governor_id

MilitaryUnit    id, dynasty_id, unit_type, name, size, quality, morale,
                experience, territory_id, army_id, maintenance_cost, food_consumption

Army            id, dynasty_id, name, territory_id, commander_id, is_active, is_sieging

Building        id, territory_id, building_type, name, level, condition,
                is_under_construction, construction_year, completion_year

TradeRoute      id, source_dynasty_id, target_dynasty_id, resource_type,
                resource_amount, profit_source, profit_target, is_active

War             id, attacker_dynasty_id, defender_dynasty_id, is_active, start_year, end_year

HistoryLogEntryDB  id, dynasty_id, year, event_string, event_type, person1_sim_id, territory_id
ChronicleEntryDB   id, game_id, turn, year, text, created_at
```


---

## Coding Rules (Follow These Exactly)

### Python
- All DB writes wrapped in `try/except` with `db.session.rollback()` and `flash("...", "danger")`
- All LLM calls guarded: `if llm_model is None: return fallback_value`
- All prompt strings in `utils/llm_prompts.py` — never inline in routes or models
- `logger = logging.getLogger('royal_succession.<module_name>')` in every module
- No `print()` statements — use `logger.debug/info/warning/error`
- Subsystem classes take `session: Session` as only constructor arg
- DB model classes suffixed `DB` (e.g. `DynastyDB`, `PersonDB`)
- Foreign keys use `back_populates` not `backref`; explicit `foreign_keys=` when ambiguous
- `@login_required` on all game routes
- Flash categories: `"success"`, `"danger"`, `"info"`, `"warning"` only

### LLM token budgets
| Use case | max_tokens |
|----------|-----------|
| Chronicle narration | 150 |
| AI advisor | 200 |
| AI dynasty decision | 100 |
| Battle commentary | 60 |

### Templates
- All templates extend `base.html`
- Use `url_for('blueprint.function_name')` — never hardcode URLs
- Pass serialized data to templates — never raw ORM objects
- SVG strings rendered with `{{ svg_string | safe }}`
- Flash messages via `get_flashed_messages(with_categories=true)` already in `base.html`

### Tests
- Run `pytest` after every change — must stay at 163 passed, 0 failed
- New routes need at least one integration test in `tests/integration/`
- New game mechanics need a unit test in `tests/unit/`
- Never skip a test without a comment explaining why

---

## Environment

```bash
cd /Users/barakganon/personal_projects/Royal-Succession-Simulation
source .venv/bin/activate
python main_flask_app.py          # dev server → http://localhost:5000
pytest                            # run all tests
pytest tests/integration/ -v     # integration tests only

# LLM features require:
export GOOGLE_API_KEY="your_key_here"
```

Default login: username `test_user`, password `password`

DB location: `instance/dynastysim.db` (SQLite)
Logs location: `logs/` (performance logs per session)

---

## Sprint 8 Task List

| # | Task | File(s) to create/edit | Status |
|---|------|------------------------|--------|
| 8A | Add `action_phase` route | `blueprints/dynasty.py` | ✅ Done |
| 8B | Add `submit_actions` route | `blueprints/dynasty.py` | ✅ Done |
| 8C | Create `templates/action_phase.html` | new file | ✅ Done |
| 8D | Wire "Advance Turn" btn → action_phase | `templates/view_dynasty.html` | ✅ Done |
| 8E | Rewrite `templates/world_map.html` as full-viewport hex map | existing file | ✅ Done |
| 8F | Add hex grid support to `generate_geojson()` | `visualization/map_renderer.py` | ✅ Done |
| 8G | Add resource bar data to `world_map` route | `blueprints/map.py` | ✅ Done |
| 8H | Add game-viewport CSS | `static/style.css` | ✅ Done |
| 8I | Add `body_class` block to `base.html` | `templates/base.html` | ✅ Done |
| 8J | Write tests for new routes | `tests/integration/` | TODO |

**Do tasks in order. Run `pytest` after each task. Do not batch.**

---

## What NOT To Do

- Do not rewrite working subsystem classes (`MilitarySystem`, `EconomySystem`, etc.)
- Do not change the DB schema without a migration in `db_initialization.py`
- Do not add new dependencies without updating `requirements.txt`
- Do not use `backref=` in SQLAlchemy relationships — use `back_populates`
- Do not hardcode API keys — use `current_app.config.get('GOOGLE_API_KEY')`
- Do not inline LLM prompt strings outside `utils/llm_prompts.py`
- Do not change `main_flask_app.py` beyond app setup and blueprint registration
- Do not break existing tests

