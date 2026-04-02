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

## Current State (as of Sprint 9 complete)

- **187 tests pass, 0 failures, 0 skipped**
- All Flask routes extracted into 6 blueprints (`auth`, `dynasty`, `military`, `economy`, `diplomacy`, `map`)
- `main_flask_app.py` is ~290 lines (app setup + blueprint registration only)
- Medieval dark theme applied to all 27 templates (Cinzel/Crimson Text fonts, CSS variables)
- AI controller wired into every `advance_turn`; LLM or rule-based fallback
- SVG coat of arms + character portraits procedurally generated
- Real-time battle ticker via Flask-SocketIO
- Interactive HTML5 canvas map (hex grid, click to select, hover tooltip)
- Action Phase: 3 AP decision screen before every turn
- Full-viewport Travian-style hex world map
- Victory conditions + endgame screen (`templates/victory.html`)
- Player onboarding panel + milestone progress bars on dashboard
- Epic Story Chronicle: per-turn LLM fantasy paragraph appended to dynasty saga

---

## Active Sprint: Sprint 10 — Polish & Depth

Sprint 8 and 9 are complete. The game has player agency, a hex map, victory conditions, and an epic chronicle. Sprint 10 adds depth and polish.

### Sprint 10 Task List

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 10A | Chronicles panel in `view_dynasty.html` (scrollable epic story card) | `templates/view_dynasty.html` | TODO |
| 10B | Banking / loans subsystem (borrow gold vs. interest, repay) | `models/economy_system.py`, `blueprints/economy.py`, new template | TODO |
| 10C | Espionage system (spy missions: assassinate, sabotage, intel) | new `models/espionage_system.py`, `blueprints/espionage.py`, template | TODO |
| 10D | ElevenLabs TTS narrator for turn events (requires `ELEVENLABS_API_KEY`) | `utils/tts_narrator.py`, wired into turn_report | TODO |

**Do tasks in order. Run `pytest` after each task. Each task on its own branch.**


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
- Run `pytest` after every change — must stay at 187 passed, 0 failed
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

## Completed Sprints (reference)

| Sprint | Key deliverables | Tests |
|--------|-----------------|-------|
| 8 | Action phase (3 AP screen), full-viewport hex map | 163 passed |
| 9 | Epic story chronicle, victory conditions, onboarding, fix all 17 skipped tests | 187 passed |

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


---

## Git Workflow — Mandatory for All Agents

> This section is enforced. A task is NOT done until the branch is pushed and STATUS.md is updated.
> Claude Code agents must follow this workflow exactly — no exceptions.

---

### Branch naming convention

```
feature/<short-description>     # new feature
fix/<short-description>         # bug fix
infra/<short-description>       # infrastructure, Docker, config
refactor/<short-description>    # code cleanup, no behavior change
test/<short-description>        # adding or fixing tests
chore/<short-description>       # deps, config, docs, CLAUDE.md updates
```

Examples:
```
feature/action-phase-ui
feature/hex-map-travian-style
fix/circular-fk-use-alter
test/fix-skipped-gamemanager-tests
chore/update-sprint8-status
refactor/blueprint-map-cleanup
```

---

### Workflow every agent MUST follow

#### 1. Before starting any work
```bash
cd /Users/barakganon/personal_projects/Royal-Succession-Simulation
git checkout main
git pull origin main
git checkout -b <branch-name>
# Example: git checkout -b feature/action-phase-ui
```

#### 2. Commit frequently — after every logical unit of work
Do NOT batch everything into one commit at the end.
Each of these warrants its own commit:
- New route created and working
- New template created
- Existing template redesigned
- Tests added and passing
- Bug fixed
- CSS changes for a specific component

```bash
git add <specific-files>   # never: git add .  — always be explicit
git commit -m "<type>(<scope>): <what and why>"
```

#### 3. Commit message format (Conventional Commits)
```
<type>(<scope>): <imperative description>

[optional body: why this change, what problem it solves]
```

Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`, `infra`

Good examples:
```
feat(action-phase): add action_phase route with 3 AP spending UI
feat(map): replace polygon GeoJSON with hex grid rendering
feat(map): add hover tooltip with territory details
fix(fk): add use_alter=True to fix dynasty/person circular FK cycle
test(gamemanager): rewrite skipped tests against create_new_game() API
refactor(map): remove dead placeholder routes from blueprints/map.py
chore(css): add game-viewport layout classes for full-screen map
docs(claude): mark Sprint 8A and 8B complete in STATUS.md
```

Bad examples (do not use):
```
update stuff        ← too vague
fix                 ← which fix?
wip                 ← never commit WIP
changes             ← meaningless
```

#### 4. Push branch after each meaningful milestone
```bash
git push origin <branch-name>
```

After pushing, append to STATUS.md:
```
Branch: feature/action-phase-ui → pushed to origin ✅
```

#### 5. When fully complete: merge to main
```bash
git checkout main
git pull origin main
git merge --no-ff <branch-name> -m "Merge branch '<branch-name>': <one-line summary>"
git push origin main
git branch -d <branch-name>
```

Always use `--no-ff` — this preserves branch history in the graph.
Always run `pytest` before merging. Must stay at 187 passed, 0 failed.

---

### Commit frequency targets

| Task type | Minimum commits |
|-----------|----------------|
| New route + template | 1 commit each (2 total minimum) |
| CSS changes | 1 commit per component/section |
| New blueprint extraction | 1 commit (route file + test update) |
| Test file | 1 commit when tests pass |
| Bug fix | 1 commit with description of root cause |
| Multi-task sprint | Minimum 1 commit per sprint task |

Target: **at least 10–20 commits per sprint**. Sprint 8 has 10 tasks — that means minimum 10 commits, ideally 15–20.

---

### Sprint 10 branch map

Each Sprint 10 task on its own branch:

```
main
  ├── feature/epic-story-panel      ← Task 10A (Chronicles panel in view_dynasty.html)
  ├── feature/banking-system        ← Task 10B (loans subsystem)
  ├── feature/espionage-system      ← Task 10C (spy missions)
  └── feature/tts-narrator          ← Task 10D (ElevenLabs TTS)
```

---

### What NOT to do with git

- Never `git add .` — always stage specific files
- Never commit `.env` or `instance/dynastysim.db`
- Never force push to main
- Never commit `__pycache__/`, `*.pyc`, `logs/`, `visualizations/`
- Never merge without running `pytest` first
- Never finish a task without pushing the branch
- Never commit with a vague message

---

### Quick reference

```bash
# Start new task
git checkout main && git pull origin main
git checkout -b feature/my-feature

# Save progress (do this after each working piece)
git add blueprints/dynasty.py templates/action_phase.html
git commit -m "feat(action-phase): add action_phase route with AP spending logic"

# Push branch
git push origin feature/my-feature

# Merge when done (run pytest first!)
pytest  # must be 187 passed, 0 failed
git checkout main && git pull origin main
git merge --no-ff feature/my-feature -m "Merge branch 'feature/my-feature': add action phase"
git push origin main
git branch -d feature/my-feature
```

