# Royal Succession Simulation — Development Status

Last updated: 2026-03-24

---

## Current Development Phase: Sprint 1 (Stability) — Merging

---

## Sprint 1 — Stability ✅ (Agents complete, pending merge)

| # | Task | Agent | Branch | Status |
|---|------|-------|--------|--------|
| A | Fix SQLAlchemy backref conflicts + error handling + print→logger | Subagent A | `worktree-agent-ad7ca9e0` | ✅ Committed |
| B | Extract auth routes into Flask Blueprint | Subagent B | `worktree-agent-a445a07f` | ✅ Committed |
| C | Integration tests for working routes | Subagent C | `worktree-agent-a3074fc5` | ❌ Quota exhausted — needs re-run |

### Sprint 1 Deliverables
- [x] SQLAlchemy `backref=` conflicts resolved with `back_populates=` on both sides
- [x] Explicit `foreign_keys=` added for ambiguous relationships (`War.target_territory`, `Battle.battle_territory`, `Battle.winner`, `Siege.siege_territory`)
- [x] `print()` replaced with `logger.debug()` across all production modules
- [x] `try/except` with `db.session.rollback()` added to bare error routes
- [x] Auth routes (`/login`, `/logout`, `/register`, `/dashboard`) extracted to `blueprints/auth.py`
- [x] All `url_for('login')` → `url_for('auth.login')` updated across templates
- [ ] Integration tests — re-run needed (quota exhausted)

---

## Sprint 2 — AI & LLM Features 🔲 (Not started)

| # | Task | Agent | Branch | Status |
|---|------|-------|--------|--------|
| D | Personality-driven AI player (`models/ai_controller.py`) | — | `feature/ai-player` | 🔲 Pending |
| E | Living chronicle (`models/chronicle.py`, `templates/chronicle.html`) | — | `feature/chronicle` | 🔲 Pending |
| F | In-game AI advisor (`/game/<id>/advisor`) | — | `feature/advisor` | 🔲 Pending |

---

## Sprint 3 — Visual Layer 🔲 (Not started)

| # | Task | Agent | Branch | Status |
|---|------|-------|--------|--------|
| G | Procedural SVG coat of arms (`visualization/heraldry_renderer.py`) | — | `feature/coat-of-arms` | 🔲 Pending |
| H | Procedural SVG character portraits (`visualization/portrait_renderer.py`) | — | `feature/portraits` | 🔲 Pending |

---

## Sprint 4 — Infrastructure 🔲 (Not started, sequential)

| # | Task | Agent | Branch | Status |
|---|------|-------|--------|--------|
| I | Naval combat mechanics | — | `feature/naval-combat` | 🔲 Pending |
| J | Real-time battle ticker (Flask-SocketIO) | — | `feature/battle-ticker` | 🔲 Pending |
| K | Interactive HTML5 canvas map | — | `feature/canvas-map` | 🔲 Pending |

---

## Backlog / Known Issues

| Issue | Priority | Notes |
|-------|----------|-------|
| `tests/conftest.py` `session` fixture uses removed `db.create_scoped_session` | High | Fixed in working tree; needs committed |
| `main_flask_app.py` still ~3300 lines — needs Blueprint refactor beyond auth | High | Auth done; military/economy/diplomacy/map/dynasty remain |
| AI player logic absent — game unplayable without human opponent | Critical | Sprint 2 target |
| Turn-order enforcement missing | High | Sprint 4+ |
| No pagination on list endpoints | Medium | — |
| Naval combat units exist but no combat mechanics | Medium | Sprint 4 |
| Banking/loans, espionage, court politics not implemented | Low | Post-MVP |

---

## Test Suite Baseline (pre-Sprint 1 merge)

```
10 passed, 9 skipped, 17 warnings   (unit tests — main branch)
7 failed, 13 passed                 (integration/functional — pre-existing failures)
```

---

## Architecture Notes

- All prompt templates must live in `utils/llm_prompts.py` — never inline in routes
- Every LLM call must be guarded: `if llm_model is None: return fallback_value`
- DB models use `back_populates` (not `backref`) with explicit `foreign_keys=` when ambiguous
- Loggers: `logger = setup_logger('royal_succession.<module_name>')`
- Blueprint-qualified `url_for`: `url_for('auth.login')`, `url_for('auth.dashboard')`, etc.
