# Royal Succession Simulation — Development Status

Last updated: 2026-03-24

---

## Current Phase: Sprint 4 (Infrastructure) — Agent I running (sequential)

---

## Sprint 1 — Stability ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| A | SQLAlchemy backref conflicts + error handling + print→logger | ✅ Merged |
| B | Auth Blueprint (`blueprints/auth.py`) | ✅ Merged |
| C | Integration tests (107 tests, 98 pass, 9 skip) | ✅ Merged |

**Test suite after Sprint 1**: 112 passed, 7 failed (pre-existing legacy tests), 17 skipped

---

## Sprint 2 — AI & LLM Features ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| D | AI player (`models/ai_controller.py` + `models/game_manager.py`) | ✅ Merged |
| E | Living chronicle (`ChronicleEntryDB`, `/game/<id>/chronicle`) | ✅ Merged |
| F | AI advisor (`/game/<id>/advisor`, dashboard panel) | ✅ Merged |

**Test suite after Sprint 2**: 34 unit tests pass (10 original + 24 AI controller)

---

## Sprint 3 — Visual Layer ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| G | SVG coat of arms (`visualization/heraldry_renderer.py`) | ✅ Merged |
| H | SVG character portraits (`visualization/portrait_renderer.py`) | ✅ Merged |

**Visible changes**: Heraldic shields on dashboard + territory pages; character faces on dynasty view

**Test suite after Sprint 3**: 34 unit tests pass, no SAWarnings on import

---

## Sprint 4 — Infrastructure 🔄 IN PROGRESS (sequential)

| # | Task | Status | Notes |
|---|------|--------|-------|
| I | Naval combat + `/game/<id>/naval_battle` | 🔄 Running | Depends on: nothing |
| J | Real-time battle ticker (Flask-SocketIO) | 🔲 Pending | Depends on: I |
| K | Interactive HTML5 canvas map | 🔲 Pending | Depends on: I,J merged |

---

## Known Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| Circular FK cycle dynasty/person_db/territory on DROP | Medium | `use_alter=True` needed |
| 7 pre-existing test failures in legacy test files | Low | Wrong expected strings/URLs |
| `main_flask_app.py` still monolith | High | Auth done; 5 more blueprints remaining |
| Turn-order enforcement missing | High | Sprint 4+ |
| No pagination on list endpoints | Medium | Post-MVP |

---

## Full Feature Inventory (what's live)

### Working routes
- `/login`, `/logout`, `/register`, `/dashboard` (auth Blueprint)
- `/dynasty/create`, `/dynasty/<id>`, `/dynasty/<id>/territories`
- `/dynasty/<id>/military`, `/recruit_unit`, `/form_army`, `/army/<id>/battle`
- `/dynasty/<id>/economy`, `/build`, `/upgrade`, `/repair`
- `/dynasty/<id>/diplomacy`, `/diplomatic_action`, `/declare_war`, `/negotiate_peace`
- `/game/<id>/chronicle` ← NEW Sprint 2
- `/game/<id>/advisor` ← NEW Sprint 2
- `/game/<id>/naval_battle` ← NEW Sprint 4I (pending)

### New visualizations
- Procedural heraldic shield SVG per dynasty (stored in DB)
- Procedural character portrait SVG per person (stored in DB, trait/age-driven)

### AI systems
- `AIController` — 4 phases, LLM + rule-based fallback
- `ChronicleEntryDB` — per-turn narrative entries

---

## Test Suite History

| Milestone | Unit | Integration | Failed | Skipped |
|-----------|------|-------------|--------|---------|
| Baseline | 10 | 13 | 7 | 9 |
| Sprint 1 | 10 | 112 total | 7 | 17 |
| Sprint 2 | 34 | — | 7 | 9 |
| Sprint 3 | 34 | — | 7 | 9 |
| Sprint 4 | TBD | — | — | — |
