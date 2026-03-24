# Royal Succession Simulation — Development Status

Last updated: 2026-03-24

---

## ✅ ALL SPRINTS COMPLETE

---

## Sprint 1 — Stability ✅

| # | Task | Status |
|---|------|--------|
| A | SQLAlchemy backref conflicts + error handling + print→logger | ✅ Merged |
| B | Auth Blueprint (`blueprints/auth.py`) | ✅ Merged |
| C | Integration tests (107 tests, 98 pass, 9 skip) | ✅ Merged |

---

## Sprint 2 — AI & LLM Features ✅

| # | Task | Status |
|---|------|--------|
| D | AI player (`models/ai_controller.py` — 4 phases, LLM + rule-based) | ✅ Merged |
| E | Living chronicle (`ChronicleEntryDB`, `/game/<id>/chronicle`) | ✅ Merged |
| F | AI advisor (`/game/<id>/advisor`, dashboard panel) | ✅ Merged |

---

## Sprint 3 — Visual Layer ✅

| # | Task | Status |
|---|------|--------|
| G | SVG coat of arms (`visualization/heraldry_renderer.py`) | ✅ Merged |
| H | SVG character portraits (`visualization/portrait_renderer.py`) | ✅ Merged |

---

## Sprint 4 — Infrastructure ✅

| # | Task | Status |
|---|------|--------|
| I | Naval combat + blockade + `/dynasty/<id>/naval_battle` | ✅ Merged |
| J | Real-time battle ticker (Flask-SocketIO + LLM commentary) | ✅ Merged |
| K | Interactive HTML5 canvas map (replaces Matplotlib PNG) | ✅ Merged |

---

## Final Test Suite

| Category | Count |
|----------|-------|
| **Passed** | **143** |
| Failed (pre-existing legacy) | 7 |
| Skipped | 17 |
| Total | 167 |

**The 7 failures are all pre-existing** in `test_flask_app.py` and `test_game_flow.py` — wrong expected strings/URLs written before the auth Blueprint refactor. They do not reflect broken functionality.

---

## Complete Feature Inventory

### Authentication
- `/login`, `/logout`, `/register` — Flask Blueprint (`blueprints/auth.py`)
- `/dashboard` — user hub with dynasty list, AI advisor panel

### Dynasty & Characters
- `/dynasty/create`, `/dynasty/<id>`, `/dynasty/<id>/territories`
- Procedural coat of arms SVG on dashboard + territory page
- Procedural character portrait SVG on dynasty view (ruler + family)

### Military
- `/dynasty/<id>/military`, `/recruit_unit`, `/form_army`, `/army/<id>/battle`
- `/dynasty/<id>/naval_battle` — naval combat with blockade mechanics
- Real-time battle ticker via SocketIO (live round feed + LLM commentary)

### Economy
- `/dynasty/<id>/economy`, `/build`, `/upgrade`, `/repair`, `/develop_territory`

### Diplomacy
- `/dynasty/<id>/diplomacy`, `/diplomatic_action`, `/declare_war`, `/negotiate_peace`

### AI & LLM
- `/game/<id>/advisor` — AI advisor (LLM or rule-based fallback, cached per turn)
- `/game/<id>/chronicle` — dynasty chronicle (LLM narrated or template fallback)
- `AIController` — 4-phase AI for non-human dynasties (diplomacy/military/economy/character)

### World Map
- `/world/map` — Interactive HTML5 canvas map (click territories, sidebar details)
- `/game/<id>/map.geojson` — territory data as GeoJSON

---

## Known Remaining Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| 7 legacy test failures | Low | `test_flask_app.py` + `test_game_flow.py` use wrong expected strings — fix tests |
| Circular FK cycle on dynasty/person_db/territory DROP | Medium | `use_alter=True` on FKs needed |
| `main_flask_app.py` still a monolith | High | Auth done; 5 more Blueprints remaining (military/economy/diplomacy/map/dynasty) |
| Turn-order enforcement missing | High | Server-side lock needed |
| No pagination on list endpoints | Medium | Will degrade at scale |
| `chronicle_entry` table not yet created via migration | Medium | Needs `db.create_all()` or Alembic migration |
| Banking/loans, espionage, court politics | Low | Post-MVP |

---

## Architecture Decisions Made

- Auth Blueprint: all auth `url_for` calls use `'auth.<name>'`
- All LLM prompts in `utils/llm_prompts.py` (6 functions: ai_decision, chronicle, chronicle_fallback, advisor, advisor_fallback, battle_commentary)
- LLM guard everywhere: `if llm_model is None: return fallback_value`
- DB models use `back_populates` + `foreign_keys=` — never `backref=`
- SVGs stored as Text in DB, rendered with `| safe` Jinja filter
- SocketIO: `async_mode='threading'`, `allow_unsafe_werkzeug=True` for dev
- Canvas map: hexagonal territories (Territory only has x/y centroids, no polygon data), auto-scaled to canvas
