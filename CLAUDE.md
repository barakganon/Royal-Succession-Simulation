# CLAUDE.md — Royal Succession Simulation

## Project Purpose

A browser-based grand strategy / dynasty management game inspired by Crusader Kings. Players control a noble dynasty across generations, managing territory, armies, diplomacy, economy, and succession. Supports single-player (vs. AI) and multi-player sessions. An optional LLM integration generates narrative flavor text, custom cultural themes, in-game advisor counsel, and chronicle narration from game events.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web framework | Flask |
| ORM | SQLAlchemy |
| Database | SQLite (file: `instance/dynastysim.db`) |
| Auth | Flask-Login + Werkzeug password hashing |
| Visualizations | Matplotlib (server-side PNG) → being replaced by Canvas/SVG (see Roadmap) |
| Real-time | Flask-SocketIO (planned for battle ticker) |
| Graph algorithms | NetworkX (family tree traversal) |
| Map / math | NumPy |
| LLM (optional) | Google Generative AI (`google-generativeai`) |
| Testing | pytest + pytest-cov |
| Python version | 3.8+ |

---

## File Structure

```
Royal-Succession-Simulation/
├── main_flask_app.py          # Flask app: all routes (40+), app config, LLM setup (~3300 lines)
├── simulation_engine.py       # Standalone simulation runner; wraps GameManager + LLM narrative
├── run_local_simulation.py    # CLI entry point for headless simulations
├── check_dynasty.py           # Dev utility to inspect DB state
│
├── models/
│   ├── db_models.py           # SQLAlchemy ORM: all DB tables and relationships
│   ├── db_initialization.py   # Schema creation + seed data
│   ├── game_manager.py        # Central coordinator: initialises all subsystems, high-level API
│   ├── map_system.py          # Map generation, territory management, pathfinding, borders
│   ├── military_system.py     # Unit recruitment, armies, battles, sieges, naval combat
│   ├── diplomacy_system.py    # Relations, treaties, wars, casus belli, reputation
│   ├── economy_system.py      # Resources, buildings, trade routes, production
│   ├── time_system.py         # Turn engine, seasons, events, game phases
│   ├── family_tree.py         # Succession rules, inheritance, family relationships
│   ├── person.py              # Character modelling: traits, marriage, fertility
│   ├── traits.py              # Trait definitions and stat effects
│   ├── history.py             # Event logging
│   ├── chronicle.py           # (planned) LLM-narrated dynasty history per turn
│   └── ai_controller.py       # (planned) Personality-driven AI dynasty decision logic
│
├── visualization/
│   ├── map_renderer.py        # World map PNG generation → to be replaced by canvas map
│   ├── military_renderer.py   # Army / battle visualizations
│   ├── diplomacy_renderer.py  # Diplomatic network graphs
│   ├── economy_renderer.py    # Economic charts
│   ├── time_renderer.py       # Timeline / event charts
│   ├── plotter.py             # Family tree PNG generation
│   ├── portrait_renderer.py   # (planned) SVG procedural character portraits
│   └── heraldry_renderer.py   # (planned) SVG procedural coat of arms generator
│
├── blueprints/                # (planned) Flask Blueprints extracted from main_flask_app.py
│   ├── auth.py
│   ├── military.py
│   ├── diplomacy.py
│   ├── economy.py
│   ├── map.py
│   └── dynasty.py
│
├── templates/                 # 27 Jinja2 HTML templates
│   ├── base.html              # Layout, nav
│   ├── dashboard.html         # User's game hub
│   ├── world_map.html         # Strategic map view → target for canvas map replacement
│   ├── chronicle.html         # (planned) Scrollable LLM-narrated dynasty history
│   ├── military_*.html        # Military management
│   ├── diplomacy_view.html    # Diplomatic relations
│   ├── economy_view.html      # Economy management
│   ├── time_view.html         # Timeline
│   └── dynasty_territories.html
│
├── static/
│   ├── style.css              # Main stylesheet (~100 lines, minimal)
│   ├── heraldry/              # (planned) SVG coat of arms assets per dynasty
│   └── visualizations/        # Generated PNG output directory
│
├── utils/
│   ├── theme_manager.py       # Load/generate cultural themes (JSON + LLM)
│   ├── helpers.py             # Shared utilities; LLM global injection
│   ├── llm_prompts.py         # (planned) Centralised LLM prompt templates
│   └── logging_config.py      # Centralised logger setup
│
├── themes/
│   └── cultural_themes.json   # Predefined cultural theme definitions
│
├── tests/
│   ├── conftest.py            # pytest fixtures
│   ├── unit/                  # Unit tests: db_models, game_manager, simulation_engine
│   ├── integration/           # Integration tests: Flask app routes
│   └── functional/            # Functional tests: full game flow
│
├── docs/                      # Design and technical docs (do not edit these as code)
├── instance/                  # SQLite DB (git-ignored in prod)
└── logs/                      # App and game logs
```

---

## What's Working

- **Authentication** — register, login, logout (Flask-Login + hashed passwords)
- **Dynasty creation** — name, start year, cultural theme selection or LLM-generated theme
- **Character system** — traits, marriage, children, succession, family tree
- **Military system** — 16 unit types, army creation, land battles, siege resolution
- **Economy** — resource production (food/timber/stone/iron/gold), buildings, trade routes, seasonal modifiers
- **Diplomacy** — relations scores, treaty types (alliance, NAP, vassalage, trade), war declaration
- **Turn engine** — 6-phase turn cycle, 4 seasons, population growth, event processing
- **World map** — territory ownership, pathfinding, border calculation
- **Visualization pipeline** — all renderers produce PNGs served via Flask routes
- **LLM theme generation** — optional; guarded with `FLASK_APP_LLM_MODEL is not None` checks
- **Logging** — structured logging via `utils/logging_config.py`; module-level loggers named `royal_succession.<module>`

---

## What's Broken / Incomplete (Current)

### Critical
- **`AIController` wiring unverified** — the class exists but it's unclear whether `decide_*` methods are called on every `advance_turn` for non-human dynasties. → Sprint 5A.

### High Priority
- **`main_flask_app.py` is still a monolith (~3300 lines).** Auth Blueprint extracted; 5 more remain (military, economy, diplomacy, map, dynasty). → Sprint 7.
- **Turn enforcement missing** — players can submit actions out of turn; no server-side turn-order lock. → Sprint 5C.
- **7 legacy test failures** — `test_flask_app.py` + `test_game_flow.py` use wrong expected strings/URLs from before auth Blueprint refactor. → Sprint 5B.

### Medium Priority
- **`chronicle_entry` table** — may not be created on all deployments; needs explicit migration. → Sprint 5D.
- **No pagination** — list endpoints load all DB rows; will degrade at scale. → Sprint 5D / Sprint 7.
- **CSS is minimal** — `static/style.css` is ~100 lines; UI is functional but rough. → Sprint 6.
- **Circular FK cycle** on dynasty/person_db/territory DROP — needs `use_alter=True` on FKs. → Sprint 7.

### Low Priority
- **`print()` statements** remain in some model files — replace with `logger.debug()`. → Sprint 7.
- **Banking / loans, espionage, court politics** — not implemented. → Sprint 8.
- **Terrain-specific production tuning** — terrain types exist but multipliers are uniform.

---

## Original Roadmap — P1–P5 (All Complete ✅)

> These are preserved for historical reference. See "Active Roadmap — Sprints 5–8" above for current work.

### P1 — Personality-driven AI dynasties (`models/ai_controller.py`)
**Why first:** fixes the critical "no AI player" blocker while making it interesting rather than purely rule-based.

Each AI dynasty is assigned a one-sentence personality string at game creation (e.g. "House Vane is paranoid and expansionist — always assumes neighbours are plotting"). This personality is injected into LLM prompts when the AI makes decisions, so different dynasties genuinely think and behave differently.

Implementation notes:
- Create `models/ai_controller.py` with an `AIController` class. Constructor takes `session`, `dynasty_id`, and `personality: str`.
- Register one controller per non-human dynasty in `GameManager.process_turn()` via `self.ai_controllers`.
- Each phase method (`decide_diplomacy`, `decide_military`, `decide_economy`, `decide_character`) calls the LLM with: game state summary + personality string + available actions → returns chosen action.
- Fall back to rule-based defaults if LLM is unavailable (`FLASK_APP_LLM_MODEL is None`).
- Rule-based fallbacks: relations < -50 + weaker → propose NAP; army > 1.5× enemy → attack; food < 20% → build food; leader age > 55 + no heir → arrange marriage.
- Log every AI decision at `logger.info` level with dynasty name and reasoning.
- Predefined personalities live in `themes/cultural_themes.json` alongside cultural themes.

### P2a — Living chronicle (`models/chronicle.py`, `templates/chronicle.html`)
**Why now:** LLM hook already exists; wiring turn events into narrative is low effort, high drama.

After each turn resolves, collect the turn's key events (battles, deaths, treaties, disasters) and pass them to the LLM with a prompt instructing it to write 2-3 sentences in the style of a medieval chronicler. Store the result in a new `ChronicleEntryDB` table (columns: `game_id`, `turn`, `year`, `text`, `created_at`). Render as a scrollable timeline on `templates/chronicle.html`.

Implementation notes:
- Prompt template lives in `utils/llm_prompts.py` (create this file as the single source of all LLM prompts in the project).
- Chronicle generation is triggered at the end of `TimeSystem.end_turn()`.
- If LLM is unavailable, generate a simple template string from event data instead.
- `ChronicleEntryDB` belongs in `models/db_models.py`.

### P2b — In-game AI advisor / "Hand of the King" (`utils/llm_prompts.py`, new route)
**Why now:** same LLM infrastructure as the chronicle; can share `utils/llm_prompts.py`.

At the start of each turn's Planning Phase, the advisor reads the player's current game state (treasury, military strength, relations scores, active threats) and returns 2-3 prioritised strategic suggestions written in character as a loyal counsellor. Displayed as a dismissible panel on the dashboard.

Implementation notes:
- Route: `GET /game/<id>/advisor` → returns JSON `{suggestions: [str, str, str]}`.
- Prompt template in `utils/llm_prompts.py`. Include dynasty name, current year, season, treasury level, strongest neighbour, active wars.
- Cache the advisor response for the current turn in the session to avoid redundant LLM calls on page refresh.
- Degrade gracefully: if LLM unavailable, return 2 rule-based tips based on game state thresholds.

### P3a — Procedural coat of arms (`visualization/heraldry_renderer.py`)
**Why now:** pure SVG, zero dependencies, no LLM needed, high visual impact.

Generate a unique heraldic shield SVG for each dynasty at creation time. The shield is deterministic — same dynasty_id always produces the same arms.

Components (all randomly seeded from dynasty_id):
- **Tincture**: background colour from heraldic palette (or, argent, gules, azure, sable, vert, purpure)
- **Ordinary**: geometric division (bend, chevron, pale, fess, cross, saltire)
- **Charge**: central symbol (lion passant, eagle displayed, fleur-de-lis, cross pattée, tower) — drawn as SVG paths
- **Motto**: dynasty name in small-caps below the shield

Output: a standalone SVG string stored as `DynastyDB.coat_of_arms_svg` (Text column). Rendered inline on the dashboard, family tree header, battle reports, and the world map tooltip.

### P3b — Procedural character portraits (`visualization/portrait_renderer.py`)
**Why now:** same SVG-only approach as coat of arms; makes the family tree feel alive.

Generate a unique SVG face for each `PersonDB` record, driven by their traits and stats.

Trait → visual mapping examples:
- `brave` → strong jaw, direct gaze
- `shrewd` → narrowed eyes, raised brow
- `kind` → soft features, slight smile
- `old` (age > 60) → grey hair, wrinkles
- `ill` → pale fill, sunken eyes
- Gender field drives hair length and facial hair options.

Output: SVG string stored as `PersonDB.portrait_svg`. Rendered in character detail pages and the family tree.

### P4 — Real-time battle ticker (`Flask-SocketIO`)
**Why after P3:** depends on Flask-SocketIO being added to requirements; more moving parts.

When a battle resolves, stream the round-by-round combat log to the client via WebSocket instead of a static page reload. Each round, the LLM writes one sentence of dramatic commentary.

Implementation notes:
- Add `flask-socketio` to `requirements.txt`.
- Emit `battle_round` events from `MilitarySystem.resolve_battle()` via `socketio.emit()`.
- Client listens in `templates/military_battle.html` and appends each round to a live log panel.
- LLM commentary prompt: "In one sentence, narrate this battle round in a dramatic medieval style: [round_data]". Keep max_tokens low (60) for speed.
- Fall back to plain round log if LLM unavailable.

### P5 — Interactive canvas map (replaces Matplotlib PNGs)
**Why last:** largest scope; touches map_renderer, world_map.html, and all territory routes.

Replace the server-side Matplotlib PNG map with a browser-rendered interactive canvas (plain HTML5 Canvas or Leaflet.js with a custom tile layer).

- Territories are clickable polygons; clicking opens a sidebar with territory details.
- Army tokens are draggable (movement actions submitted via AJAX).
- Map data served as GeoJSON from a new route: `GET /game/<id>/map.geojson`.
- `visualization/map_renderer.py` is repurposed to generate the GeoJSON; PNG generation is removed.
- `templates/world_map.html` handles all rendering client-side.

---

## Coding Conventions

### Python Style
- Module-level docstrings on every file in `models/`.
- Class docstrings: one-liner summary, blank line, detail paragraph.
- Type hints used in `models/` (`List`, `Dict`, `Optional`, `Any` from `typing`); absent in `main_flask_app.py`.
- `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for module-level constants.
- DB model classes are suffixed `DB` (e.g. `DynastyDB`, `PersonDB`).

### LLM Prompts
- All prompt templates live in `utils/llm_prompts.py`. Never inline prompt strings in route handlers or model methods.
- Every prompt function signature: `def build_<name>_prompt(**kwargs) -> str`.
- Guard every LLM call: `if llm_model is None: return fallback_value`.
- Keep `max_tokens` as low as the task allows (chronicle: 150, advisor: 200, AI decision: 100, battle commentary: 60).

### Logging
- Each module acquires a logger: `logger = setup_logger('royal_succession.<module_name>')`
- `logger.debug` — routine tracing; `logger.info` — state changes and AI decisions; `logger.warning`/`logger.error` — problems.
- No bare `print()` statements.

### Database
- All models in `models/db_models.py`, SQLAlchemy declarative base via `db = SQLAlchemy()`.
- Explicit `__tablename__` on every model.
- Foreign keys use integer IDs; use `back_populates` (not `backref`) with explicit `foreign_keys=` when ambiguous.
- JSON fields stored as `db.Text` with `json.dumps`/`json.loads`.

### Flask Routes
- `@login_required` on all game actions.
- Flash messages use Bootstrap categories: `"success"`, `"danger"`, `"info"`, `"warning"`.
- Serialize data before passing to templates — never pass raw ORM objects.
- Wrap all DB writes in try/except with rollback:
  ```python
  try:
      db.session.commit()
  except Exception as e:
      db.session.rollback()
      logger.error(f"...: {e}")
      flash("An error occurred.", "danger")
  ```

### Subsystem Pattern
Every subsystem class takes `session: Session` as its only constructor arg and stores it as `self.session`. No Flask app context inside subsystems.

### SVG / Visualization
- All procedural SVG output (portraits, heraldry) must work in both light and dark mode.
- Use CSS variables for colours wherever SVG is embedded in HTML templates.
- Portrait and coat of arms SVGs are stored as strings in the DB, not as files.
- Heraldry SVGs must be self-contained (no external assets, no JS).

---

## Environment & Running

```bash
pip install -r requirements.txt
python main_flask_app.py          # dev server
python run_local_simulation.py    # headless simulation
pytest                            # run tests
pytest --cov=. --cov-report=term-missing

export FLASK_SECRET_KEY="your_secret"
export DATABASE_URL="sqlite:///instance/dynastysim.db"
export GOOGLE_API_KEY="your_key_here"   # enables LLM features
```

---

## Completed Features (Sprints 1–4)

All original roadmap items are done. See `STATUS.md` for full details.

- ✅ SQLAlchemy backref conflicts fixed (`back_populates` throughout)
- ✅ Auth Blueprint (`blueprints/auth.py`)
- ✅ Integration tests (143 passing)
- ✅ `AIController` — 4-phase personality-driven AI dynasties
- ✅ Living chronicle (`ChronicleEntryDB`, `/game/<id>/chronicle`)
- ✅ AI advisor (`/game/<id>/advisor`, dashboard panel)
- ✅ SVG coat of arms (`visualization/heraldry_renderer.py`)
- ✅ SVG character portraits (`visualization/portrait_renderer.py`)
- ✅ Naval combat + blockade (`/dynasty/<id>/naval_battle`)
- ✅ Real-time battle ticker (Flask-SocketIO + LLM commentary)
- ✅ Interactive HTML5 canvas map (replaces Matplotlib PNG)

---

## Active Roadmap — Sprints 5–8

### Sprint 5 — Playability (Current)

Make the game actually playable end-to-end before anything else.

| Task | Description | Priority |
|------|-------------|----------|
| 5A | **Audit + wire `AIController` into the turn loop** — verify `decide_diplomacy/military/economy/character` are called on every `advance_turn` for non-human dynasties. Fix any gaps. | Critical |
| 5B | **Fix 7 legacy test failures** + write full game-loop integration tests (create dynasty → advance turns → battle → succession) | High |
| 5C | **Turn-order enforcement** — server-side lock so players cannot submit actions out of turn | High |
| 5D | **`chronicle_entry` DB migration** — ensure table is created on startup; add pagination to all list endpoints | Medium |

### Sprint 6 — UI Overhaul

The CSS is ~100 lines and the interface is rough. This sprint makes the game look and feel like a real medieval strategy game.

| Task | Description |
|------|-------------|
| 6A | **Dark medieval CSS redesign** — full stylesheet rewrite using `frontend-design` + `ui-ux-pro-max` skills. Parchment textures, gothic fonts, dark sidebar nav. |
| 6B | **Game-specific UI panels** — character cards with portrait + traits, territory HUD with resource bars, diplomacy relation wheel, live battle screen layout. |
| 6C | **Art layer** — improve procedural SVGs (richer coat of arms charges, more portrait detail). Optionally wire `pixel-art-sprites` / `ai-game-art-generation` skills for AI-generated territory icons and unit tokens. |

### Sprint 7 — Blueprint Refactor

Extract the remaining 5 blueprints from `main_flask_app.py` one at a time. Run the full test suite after each extraction before moving to the next. Do NOT batch these.

| Order | Blueprint | Routes to extract |
|-------|-----------|-------------------|
| 1 | `blueprints/dynasty.py` | `/dynasty/create`, `/dynasty/<id>/view`, `/dynasty/<id>/advance_turn`, `/dynasty/<id>/delete` |
| 2 | `blueprints/military.py` | `/dynasty/<id>/military`, `/recruit_unit`, `/form_army`, `/army/<id>/battle`, `/dynasty/<id>/naval_battle` |
| 3 | `blueprints/economy.py` | `/dynasty/<id>/economy`, `/build`, `/upgrade`, `/repair`, `/develop_territory` |
| 4 | `blueprints/diplomacy.py` | `/dynasty/<id>/diplomacy`, `/diplomatic_action`, `/declare_war`, `/negotiate_peace` |
| 5 | `blueprints/map.py` | `/world/map`, `/game/<id>/map.geojson`, `/generate_initial_map` |

After all blueprints are extracted: add pagination to remaining list endpoints, replace any remaining `print()` with `logger.debug()`, fix circular FK cycle with `use_alter=True`.

### Sprint 8 — Audio & Advanced Features (Optional / Paid APIs)

These features require external API keys and incur per-call costs. Treat as an optional enhancement layer.

| Task | Requires | Description |
|------|----------|-------------|
| 8A | ElevenLabs API key | NPC narrator voice for chronicle entries and battle results (`elevenlabs-tts` skill) |
| 8B | ElevenLabs API key | Ambient medieval background music (`elevenlabs-music` skill) |
| 8C | — | Banking/loans system (economy depth) |
| 8D | — | Espionage / spy networks (diplomacy depth) |
| 8E | — | Court faction politics |

---

## Agent Instructions

- Always run tasks in parallel with sub-agents where tasks are independent.
- Always update `STATUS.md` after completing any task.
- Blueprint extraction (Sprint 7): test after each blueprint, never batch.
- LLM calls: guard with `if llm_model is None: return fallback`. Max tokens: chronicle 150, advisor 200, AI decision 100, battle commentary 60.
- Never inline prompt strings — all prompts live in `utils/llm_prompts.py`.
- Audio/art features (Sprint 8): check for API key before calling external service; degrade gracefully if absent.
