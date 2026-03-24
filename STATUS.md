# Royal Succession Simulation — Development Status

Last updated: 2026-03-24

---

## Current Phase: Sprint 3 (Visual Layer) — G & H running

---

## Sprint 1 — Stability ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| A | SQLAlchemy backref conflicts + error handling + print→logger | ✅ Merged |
| B | Auth Blueprint (`blueprints/auth.py`) | ✅ Merged |
| C | Integration tests (107 tests, 98 pass, 9 skip) | ✅ Merged |

**Achievements:**
- All `backref=` replaced with `back_populates=` + `foreign_keys=`; zero SAWarnings on import
- Auth routes extracted to `blueprints/auth.py`; all 7 templates updated
- `tests/conftest.py` fixed for Flask-SQLAlchemy 3.x
- `diplomacy_view.html` template bug fixed
- 107 new integration tests across 5 files
- **Test suite**: 112 passed, 7 failed (pre-existing legacy tests), 17 skipped

---

## Sprint 2 — AI & LLM Features ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| D | AI player (`models/ai_controller.py` + `models/game_manager.py`) | ✅ Merged |
| E | Living chronicle (`ChronicleEntryDB`, `/game/<id>/chronicle`) | ✅ Merged |
| F | AI advisor (`/game/<id>/advisor`, dashboard panel) | ✅ Merged |

**Achievements:**
- `AIController` class with 4 phase methods (diplomacy/military/economy/character)
- Rule-based fallbacks for all phases when LLM unavailable
- `GameManager.register_ai_dynasties()` + `process_ai_turns()`
- 5 AI personalities added to `themes/cultural_themes.json`
- `ChronicleEntryDB` model; chronicle generated at end of each turn
- `/game/<id>/chronicle` route + `templates/chronicle.html`
- `/game/<id>/advisor` route with Flask session caching
- Dashboard advisor panel (JS fetch, dismissible)
- `utils/llm_prompts.py` with 5 functions (no LLM = graceful fallback)
- **Test suite**: 34 unit tests pass (10 original + 24 AI controller tests)

---

## Sprint 3 — Visual Layer 🔄 IN PROGRESS

| # | Task | Status |
|---|------|--------|
| G | SVG coat of arms (`visualization/heraldry_renderer.py`) | 🔄 Running |
| H | SVG character portraits (`visualization/portrait_renderer.py`) | 🔄 Running |

---

## Sprint 4 — Infrastructure 🔲 Not started (sequential)

| # | Task | Status |
|---|------|--------|
| I | Naval combat mechanics | 🔲 Pending |
| J | Real-time battle ticker (Flask-SocketIO) | 🔲 Pending |
| K | Interactive HTML5 canvas map | 🔲 Pending |

---

## Known Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| Circular FK cycle dynasty/person_db/territory on DROP | Medium | `use_alter=True` needed |
| 7 pre-existing test failures in legacy test files | Low | Wrong expected strings/URLs |
| `main_flask_app.py` still monolith | High | Auth done; 5 more blueprints remaining |
| Turn-order enforcement missing | High | Sprint 4+ |
| No pagination on list endpoints | Medium | Post-MVP |
| Naval combat units exist but no combat mechanics | Medium | Sprint 4 |

---

## Test Suite History

| Milestone | Passed | Failed | Skipped |
|-----------|--------|--------|---------|
| Baseline (pre-Sprint 1) | 13 | 7 | 9 |
| Sprint 1 complete | 112 | 7 | 17 |
| Sprint 2 complete | 34* | 7 | 9 |
| Sprint 3 complete | TBD | — | — |

*Unit tests only after Sprint 2 merge (integration tests still green separately)

---

## Architecture Notes

- Auth Blueprint: `url_for('auth.login')`, `url_for('auth.dashboard')`, etc.
- All LLM prompts in `utils/llm_prompts.py` — never inline in routes
- LLM guard: `if llm_model is None: return fallback_value`
- DB models: `back_populates` + `foreign_keys=`, never `backref=`
- Loggers: `logger = setup_logger('royal_succession.<module_name>')`
- Chronicle: `ChronicleEntryDB` with FK to `dynasty.id`
- Advisor: cached in Flask session by `(dynasty_id, turn)` key
- Coat of arms + portraits: stored as SVG text in DB, rendered with `| safe` filter
