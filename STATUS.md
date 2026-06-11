# Royal Succession Simulation - Development Status
Last updated: 2026-06-11
Last commit: Story 11-4 — logging + SQLAlchemy 2.0 warnings cleanup (536 green). Epic 11 complete.

---

## Current State
**Tests:** 414 passed + 1 known heir-majority isolation flake (passes in isolation) · 0 skipped
**Epic 7 (Dynastic Marriages) — in progress.** 7-1 done: marriages now first seek an eligible unmarried noble in another dynasty (political match, both keep their house), stranger fallback only if none; added `MarriageOfferDB` scaffold for 7-2. Next: 7-2 (AI marriage acceptance + wedding chronicle), 7-3 (children-with-claims + UI). Epics 1–6 complete.
**Epic 6 (Traits & Buildings Matter) — COMPLETE.** 6-1 trait_effects + Military/Economy/Diplomacy hooks; 6-2 building gates + Sickly lifespan + trait inheritance; 6-3 monarch-trait chronicle voice + portrait tooltip + `docs/traits.md`. **Epics 1–6 all done.** Next: Epic 7 (Dynastic Marriages). ⚠ Tech-debt: a shared-temp-DB test-isolation flake intermittently fails the full-suite gate across a few files (passes in isolation) — worth a Sprint-11 test-isolation fix. Dev-server: launch with `MPLBACKEND=Agg`.
**Epic 6 (Traits & Buildings Matter) — in progress.** 6-1 done: `models/trait_effects.py` (8-trait modifier map) wired into combat (`_resolve_battle`), tax (`calculate_territory_tax_income`), and diplomacy (`perform_diplomatic_action`) — a Brave monarch fights better, Greedy taxes harder, Cunning negotiates better; no-op for trait-less/monarch-less. Also fixed a latent bug where `perform_diplomatic_action` returned None for non-special actions. Next: 6-2 (building gates + lifespan + trait inheritance), 6-3 (chronicle voice + trait docs).
**Epic 5 (Generational Interrupts + Succession Drama) — COMPLETE.** 5-1 succession modal on monarch death; 5-2 LLM candidate cards + coronation; 5-3 pretender mechanics (is_pretender/pretender_strength + accumulation, non-default heir flags a pretender); 5-4 civil-war interrupt (Fight/Negotiate/Abdicate modal + `/civil_war_resolve`) when a pretender's strength ≥ 50, and heir-majority interrupt at age 16 (`has_seen_majority`). AI dynasties auto-resolve/flag (never hang). Verified live (civil-war modal + negotiate resolve). Built via worktree-agent Workflows. **Epics 1–5 done.** Next: Epic 6 (Traits & Buildings Matter). Dev-server note: launch with `MPLBACKEND=Agg` to avoid a macOS matplotlib NSWindow crash.
**Epic 5 (Generational Interrupts + Succession Drama) — in progress.** 5-1: human monarch death halts the turn → succession modal to crown an heir (AI auto-crowns); End Turn blocked while kingless. 5-2: each candidate card now carries a 3-sentence LLM character sketch (deterministic trait-based fallback when LLM is off), and crowning writes a `coronation` chronicle line. Verified live (flavor on cards + coronation entry). Built via 3 worktree agents (5-2 orchestrated through the Workflow tool). Next: 5-3 (pretenders), 5-4 (civil war + heir-majority).
**Epic 4 (Free Actions Split) — complete.** 4-1: `POST /free_action` dispatcher (9 instant actions; diplomacy delegates to DiplomacySystem; +2 DynastyDB columns) that doesn't tick the turn. 4-2: each free action gets an LLM-narrated chronicle line (deterministic fallback); right-click menu now has a separated "Decisions" section (free_action_catalogue.json) alongside Projects; reversible actions (feast/tournament/pardon/name_heir/succession_law) can be undone before End Turn via a server session stack + `/free_action/undo` (war/treaty non-undoable). Verified live (menu screenshot + undo round-trip). Built via 3 worktree agents each. Next epic: Epic 5 (Generational Interrupts + Succession Drama).
**Story 3-5 (Animated turn pass + routing + delete action_phase):** done — branch `feature/animated-turn-routing-cleanup` (3 worktree agents: backend / frontend / tests). **Epic 3 (Map as Main View) complete** — stories 3-1…3-5 all done. End Turn now plays event toasts on the map then routes to the turn report; login lands on the map; `action_phase` route deleted (404).

**Correct-course fix (`fix/world-map-empty-render`):** running the app revealed the world map rendered **empty on real data** (every Epic 3 story had deferred visual verification). Root cause: `map_renderer` emits raw pixel coords as `col/row` but the canvas treated them as hex-grid indices (×48 off-screen). Fixed `hexCenter` + added `fitToView`; also wired a starting-map bootstrap into `create_dynasty` (gated on non-TESTING). Map now renders & fits-to-view; verified visually via headless Chrome. Logged follow-ups in `deferred-work.md`: **`pytest` wipes the dev DB** (conftest binds `:memory:` too late), borders need a tessellated layout, legacy AP panel still shown. Next epic: Epic 4 (Free actions split).
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
| 1-3 | Add years_advanced + interrupt_reason to turn report UI | templates/turn_report.html | Done — 212 tests pass |
| 1-4 | Update Chronicle prompt to receive years_advanced + interrupt_reason | utils/llm_prompts.py | TODO |

Branch: feature/turn-processor-extraction → merged to main ✅
Branch: feature/interrupt-driven-turn-loop → merged to main ✅
Branch: feature/turn-report-interrupt-ui → in progress

Task 1-4 remains (chronicle prompt update).

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
| flake | Eliminate order-dependent full-suite flake (autouse RNG seed + heir-majority test patches marriage/childbirth) — 415 green | Done |
| 7-1 | Marriage negotiation model + cross-dynasty matching (MarriageOfferDB) | Done |
| 7-2 | AI marriage acceptance (decide_marriage_response) + wedding chronicle | Done |
| 7-3 | Children-with-claims (ClaimDB on cross-dynasty birth) + Foreign-Court marriage-proposal UI (4 worktree agents) — 427 green | Done |
| 8-1 | Family-tree SVG renderer (pure-Python Reingold-Tilford) + DynastyDB.family_tree_svg column + migration (3 worktree agents) — 436 green | Done |
| 8-2 | Interactive family-tree page: pan/zoom/tooltip/show-deceased toggle/highlight-bloodline/search + person-JSON + raw-SVG routes (3 worktree agents) — 452 green | Done |
| 8-3 | Retire matplotlib family-tree plotter + inline SVG in view_dynasty (kept matplotlib for 5 other renderers; full removal deferred) (3 worktree agents) — 455 green. Epic 8 complete | Done |
| 9-1 | 5 event-flavor prompt builders + deterministic fallbacks (birth/death/battle/world-news/construction) (2 worktree agents) — 468 green | Done |
| 9-2 | Lifecycle event-flavor: birth/death/battle narrated via narrate_event + 9-1 prompts (fallback when LLM off) (3 worktree agents) — 474 green. Construction flavor descoped (pre-existing Building schema gap) | Done |
| 9-3 | World-news 'letters from afar' on AI war + async process_ai_turns offload (daemon thread when LLM-on + 5+ calls; sync path preserved) (3 worktree agents) — 482 green. Epic 9 complete | Done |
| 10-1 | Story-moment template library (9 vignettes) + precondition matcher + weighted trigger (2 worktree agents) — 509 green | Done |
| 10-2 | Story-moment turn interrupt + LLM prose + full-screen choice modal + choice route (record/dismiss; effects in 10-3) (4 worktree agents) — 530 green | Done |
| 10-3 | Story-moment effect applicator (prestige/wealth/infamy/trait; exile/relation narrative-only) + 25y (~5-turn) cooldown (3 worktree agents) — 542 green. Epic 10 complete | Done |
| 11-1 | Retire legacy simulation_engine + Person/FamilyTree/EconomyManager + dead routes/tests/junk (~1450 lines); repoint base.html nav to real routes — 536 green | Done |
| 11-2 | Flask-Migrate/Alembic adoption: baseline migration (24 tables, circular FKs via use_alter, render_as_batch); retired ad-hoc ALTER TABLE + db_version path; live DB stamped; CLAUDE.md migration workflow. Verified fresh-DB `flask db upgrade` == `create_all()` schema; app boots 8091 (Sonnet worktree agent; Opus verify+integrate) — 536 green | Done |
| 11-3 | Perf: composite indexes `ix_history_dynasty_year` + `ix_project_dynasty_status_completion` via Alembic migration (chained off baseline, hand-cleaned of SQLite autogen noise); memoized `get_dynasty_theme_config()`; turn_processor N+1 audit (no relationship traversal → no eager-load). Verified upgrade==create_all incl. indexes; live DB migrated to head; app boots 8091 — 536 green | Done |
| 11-4 | Logging + SQLAlchemy 2.0 warnings: RotatingFileHandler (5MB×3) for app log; conditional atexit (skip under pytest, kills test-exit noise); `.query.get()`/`session.query().get()` → `session.get()` (180+ sites); print()→logger (map_renderer); utcnow()→now(UTC). Warnings ~1982→0 (real fixes + narrowed message-specific SAWarning suppress for the unfixable circular-FK teardown). app boots 8091 (Sonnet subagent on live main — no worktree, to avoid stale-base conflicts; Opus verify+integrate) — 536 green. **Epic 11 complete** | Done |
