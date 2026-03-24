# Royal Succession Simulation — Development Status

Last updated: 2026-03-24

---

## Current Phase: Sprint 2 (AI & LLM Features) — Agent D still running

---

## Sprint 1 — Stability ✅ COMPLETE

| # | Task | Status | Commit |
|---|------|--------|--------|
| A | SQLAlchemy backref conflicts + error handling + print→logger | ✅ Merged | `63f0a41` |
| B | Auth Blueprint (`blueprints/auth.py`) | ✅ Merged | `3f52553` |
| C | Integration tests (107 tests, 98 pass, 9 skip) | ✅ Merged | — |

**Achievements:**
- All `backref=` conflicts replaced with `back_populates=` + `foreign_keys=`
- `War.history_entries` SAWarning fixed post-merge
- `diplomacy_view.html` template bug fixed (missing `war_id` in `url_for`)
- Auth routes extracted to `blueprints/auth.py`; all 7 templates updated
- `tests/conftest.py` updated for Flask-SQLAlchemy 3.x (removed `create_scoped_session`)
- 107 new integration tests added across 5 files
- **Test suite**: 112 passed, 7 failed (pre-existing in old test files), 17 skipped

---

## Sprint 2 — AI & LLM Features 🔄 IN PROGRESS

| # | Task | Status |
|---|------|--------|
| D | AI player (`models/ai_controller.py`) | 🔄 Running |
| E | Living chronicle (`ChronicleEntryDB`, `/game/<id>/chronicle`) | ✅ Done, pending merge |
| F | AI advisor (`/game/<id>/advisor`, dashboard panel) | ✅ Done, pending merge |

**`utils/llm_prompts.py` functions (no name conflicts):**
- D → `build_ai_decision_prompt`
- E → `build_chronicle_prompt`, `generate_chronicle_fallback`
- F → `build_advisor_prompt`, `generate_advisor_fallback`

---

## Sprint 3 — Visual Layer 🔲 Not started

| # | Task | Status |
|---|------|--------|
| G | SVG coat of arms (`visualization/heraldry_renderer.py`) | 🔲 Pending |
| H | SVG character portraits (`visualization/portrait_renderer.py`) | 🔲 Pending |

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
| Circular FK cycle dynasty/person_db/territory on DROP | Medium | `use_alter=True` needed on FKs |
| 7 pre-existing test failures in old test files | Low | Wrong expected strings / URLs — legacy tests |
| `main_flask_app.py` still monolith (~3000+ lines) | High | Auth done; 5 more blueprints remaining |
| Turn-order enforcement missing | High | Sprint 4+ |
| No pagination on list endpoints | Medium | Post-MVP |
| Naval combat units exist but no combat mechanics | Medium | Sprint 4 |
| Banking/loans, espionage, court politics not implemented | Low | Post-MVP |

---

## Test Suite History

| Milestone | Passed | Failed | Skipped |
|-----------|--------|--------|---------|
| Baseline (pre-Sprint 1) | 13 | 7 | 9 |
| Sprint 1 complete | 112 | 7 | 17 |
| Sprint 2 complete | TBD | — | — |

---

## Architecture Notes

- Auth Blueprint: `url_for('auth.login')`, `url_for('auth.dashboard')`, etc.
- All LLM prompts centralised in `utils/llm_prompts.py` — never inline in routes
- LLM guard: `if llm_model is None: return fallback_value`
- DB models: `back_populates` + `foreign_keys=`, never `backref=`
- Loggers: `logger = setup_logger('royal_succession.<module_name>')`
- Chronicle: `ChronicleEntryDB` with FK to `dynasty.id`
- Advisor: result cached in Flask session by `(dynasty_id, turn)` key
