# Royal Succession Simulation - Development Status
Last updated: 2026-05-03
Last commit: feat(turn-processor): interrupt-driven while loop + INTERRUPT_REASONS (Story 1-2)

---

## Current State
**Tests:** 211 passed · 0 skipped · 0 failed
**App:** imports cleanly, all 6 blueprints registered
**main_flask_app.py:** 290 lines — app setup + blueprint registration only

---

## Feature Inventory (What Works)

### Auth - blueprints/auth.py
- Register, login, logout (Flask-Login + Werkzeug hashing)
- Dashboard: dynasty list paginated 20/page, AI advisor panel

### Dynasty - blueprints/dynasty.py
- Create dynasty (predefined themes or LLM-generated from user story)
- View dynasty: ruler card with SVG portrait, family grid, event timeline, coat of arms
- Advance turn (5 years): births, deaths, marriages, succession
- Turn report page: stat row, Your Chronicle event timeline, World News from AI dynasties
- Delete dynasty
- Double-submit protection (is_turn_processing lock + block_if_turn_processing decorator)
- Procedural SVG coat of arms (10+ charges, quartered shields, border treatments)
- Procedural SVG character portraits (4 age tiers, 7+ trait to visual mappings)
- Family tree PNG generation
- EPIC STORY CHRONICLE: each turn appends one AI-generated fantasy paragraph to a cumulative saga stored on the dynasty; fallback prose generated rule-based when LLM unavailable

### Military - blueprints/military.py (18 routes)
- 16 unit types, army formation, assign commander
- Land battles, siege resolution
- Naval combat + blockade
- Real-time battle ticker via SocketIO + LLM commentary
- Army / battle / siege detail pages

### Economy - blueprints/economy.py (16 routes)
- Resources: food, timber, stone, iron, gold
- Build, upgrade, repair buildings
- Develop territories, establish/cancel trade routes
- World economy overview, territory economy detail
- **Banking/Loans:** borrow gold (100–2000, max 3 loans), 15% compound interest per turn, repay, default penalty (infamy +20, honor −20 when debt ≥ 5000 gold)

### Diplomacy - blueprints/diplomacy.py (7 routes)
- Relation scores (color-coded with progress bars), prestige/honor/infamy
- Create/break treaties, send envoys
- Declare war, negotiate peace

### Map and Time - blueprints/map.py (18 routes)
- Interactive HTML5 canvas world map (click territories for sidebar detail)
- GeoJSON endpoint (/game/<id>/map.geojson)
- Territory detail, dynasty territories list
- Seasonal map, time view, timeline, advance time, schedule/cancel events
- Chronicle page: LLM-narrated entries or template fallback
- AI advisor: LLM or rule-based, cached per turn

### AI and LLM
- AIController: 4-phase per-turn decisions (diplomacy, military, economy, character)
- Wired into every advance_turn for all non-human dynasties
- Rule-based fallbacks when GOOGLE_API_KEY absent
- All prompts centralised in utils/llm_prompts.py
- build_turn_story_prompt() + generate_turn_story_fallback() added to utils/llm_prompts.py

### UI
- Full medieval dark theme: all 27 templates styled
- Cinzel (headings) + Crimson Text (body) fonts
- CSS custom properties, Bootstrap 4 overrides, gold timeline, webkit scrollbars

---

## Known Issues
| Issue | Severity | Fix |
|-------|----------|-----|
| 2 dead placeholder routes in blueprints/map.py | Low | `create_dynasty_placeholder`, `view_dynasty_placeholder` — delete |
| `print()` statements in some model files | Low | Replace with `logger.debug()` |
| Banking, espionage, court politics | Low | Post-MVP |

---

## Sprint 8 - Make It Feel Like a Game (COMPLETE)
| # | Task | Files | Status |
|---|------|-------|--------|
| 8A | action_phase route | blueprints/dynasty.py | Done |
| 8B | submit_actions route | blueprints/dynasty.py | Done |
| 8C | templates/action_phase.html | new file | Done |
| 8D | Take Actions button in view_dynasty | templates/view_dynasty.html | Done |
| 8E | Full-viewport hex world map | templates/world_map.html | Done |
| 8F | generate_geojson hex_mode=True | visualization/map_renderer.py, blueprints/map.py | Done |

Result: Players have a decision screen (3 AP across 5 action types) before each turn. The world map is a full-viewport Travian-style hex canvas. Tests held at 163 passed, 0 failed.

---

## Sprint 9A - Epic Story Chronicle (COMPLETE)
| # | Task | Files | Status |
|---|------|-------|--------|
| 9A-1 | Add epic_story_text TEXT column to DynastyDB model | models/db_models.py | Done |
| 9A-2 | Column-migration check in DatabaseInitializer (ALTER TABLE if missing) | models/db_initialization.py | Done |
| 9A-3 | build_turn_story_prompt() + generate_turn_story_fallback() | utils/llm_prompts.py | Done |
| 9A-4 | Generate + append one epic paragraph per process_dynasty_turn() | blueprints/dynasty.py | Done |
| 9A-5 | Import new prompt helpers in dynasty blueprint | blueprints/dynasty.py | Done |
| 9A-6 | Expose new_story_paragraph in turn_summary dict | blueprints/dynasty.py | Done |
| 9A-7 | Add Chronicles panel to dynasty view template | templates/view_dynasty.html | Done |

Design: Each turn Claude (or rule-based fallback) writes one 4-6 sentence high-fantasy paragraph weaving that turn events into a living saga. Paragraphs are appended to dynasty.epic_story_text separated by blank lines. Over 10-20 turns the player accumulates a full fantasy chapter about their dynasty history.

---

## Sprint 10 — Polish & Depth (IN PROGRESS)
| # | Task | Files | Status |
|---|------|-------|--------|
| 10A | Chronicles panel in view_dynasty.html | templates/view_dynasty.html | Done (branch merged) |
| 10B | Banking / loans subsystem | models/banking_system.py, blueprints/economy.py, templates/banking.html | Done — 211 tests pass |
| 10C | Espionage / spy networks | models/espionage_system.py, blueprints/espionage.py | TODO |
| 10D | ElevenLabs TTS narrator (requires API key) | utils/tts_narrator.py | TODO |

## Sprint 1 — Turn Cadence Rework (IN PROGRESS)
| # | Task | Files | Status |
|---|------|-------|--------|
| 1-1 | Extract lifecycle functions into models/turn_processor.py | models/turn_processor.py, blueprints/dynasty.py | Done — 211 tests pass |
| 1-2 | Interrupt-driven turn loop (monarch_death, heir_majority, etc.) | models/turn_processor.py, tests/ | Done — 211 tests pass |
| 1-3 | Add years_advanced + interrupt_reason to turn report UI | templates/turn_report.html | TODO |
| 1-4 | Update Chronicle prompt to receive years_advanced + interrupt_reason | utils/llm_prompts.py | TODO |

Branch: feature/turn-processor-extraction → merged to main ✅
Branch: feature/interrupt-driven-turn-loop → in progress

Tasks 1-3 and 1-4 remain (turn report UI and chronicle prompt).

## Next Steps
| # | Task | Effort |
|---|------|--------|
| 1-2 | Interrupt-driven turn loop | Medium |
| 10C | Espionage / spy networks | High |
| 10D | ElevenLabs TTS narrator (requires API key) | Low |

---

## Architecture
| Concern | Decision |
|---------|----------|
| Routing | 6 Flask Blueprints: auth, dynasty, military, economy, diplomacy, map |
| url_for() | Always blueprint.function (e.g. dynasty.view_dynasty) |
| LLM prompts | All in utils/llm_prompts.py: never inline |
| LLM guard | if llm_model is None: return fallback_value everywhere |
| DB models | back_populates + foreign_keys=: never backref= |
| SVG storage | Stored as Text in DB, rendered with safe Jinja filter |
| SocketIO | async_mode=threading, allow_unsafe_werkzeug=True for dev |
| Canvas map | Hexagonal territories using x/y centroids, auto-scaled |
| Turn summary | Stored in flask_session between advance_turn and turn_report redirect |
| Logging | Module loggers: logging.getLogger(royal_succession.<module>) |
| Epic story | Cumulative Text field on DynastyDB; one LLM paragraph appended per turn; fallback prose always available |

---

## Sprint History
| Sprint | What | Result |
|--------|------|--------|
| 1 | SQLAlchemy fixes, auth Blueprint, integration tests | Done |
| 2 | AIController, living chronicle, AI advisor | Done |
| 3 | SVG coat of arms, SVG character portraits | Done |
| 4 | Naval combat, SocketIO battle ticker, HTML5 canvas map | Done |
| 5A | Wire AIController into every advance_turn | Done |
| 5B | Fix 7 legacy test failures, add 13 game-loop integration tests | Done |
| 5C | Turn-order enforcement (is_turn_processing lock) | Done |
| 5D | Chronicle table migration, dashboard pagination | Done |
| 6A | Full medieval dark CSS theme, base.html rewrite | Done |
| 6B | UI overhaul: view_dynasty, dashboard, military_view, economy_view | Done |
| 6C | Enhanced heraldry renderer, enhanced portrait renderer | Done |
| 6.5 | Turn report page, style remaining 5 templates | Done |
| 7 | Blueprint refactor: 5 blueprints extracted, main_flask_app 3300 to 290 lines | Done |
| 8 | Action phase screen, full-viewport hex world map | Done |
| 9A | Epic Story Chronicle: per-turn LLM fantasy narrative, DB column, migration, prompts, blueprint wiring | Done |
| 9B | Fix all 17 skipped tests (GameManager, SimulationEngine, diplomacy fixtures, circular FK) | Done |
| 9C | Victory conditions + endgame screen (`templates/victory.html`) | Done |
| 9D | Player onboarding panel + milestone progress bars on dashboard | Done |
| 8J | Integration tests for action_phase + submit_actions routes | Done |
