---
project_name: 'Royal-Succession-Simulation'
user_name: 'Barakganon'
date: '2026-05-01'
sections_completed:
  ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
status: 'complete'
rule_count: 52
optimized_for_llm: true
---

# Project Context for AI Agents

_Critical rules and patterns for implementing code in this project. Focuses on unobvious details agents might otherwise miss._

---

## Technology Stack & Versions

- **Python** — Flask backend, blueprint-based routing
- **Flask** — `Flask-SQLAlchemy`, `Flask-Login`, `Flask-WTF`, `Flask-SocketIO ≥5.3.0`, `simple-websocket ≥0.9.0`
- **SQLite** — dev/prod database at `instance/dynastysim.db`; tests use in-memory `:memory:`
- **Google Generative AI** — `google-generativeai` package; key via env `GOOGLE_API_KEY`
- **matplotlib + networkx** — visualization only (not in web request path)
- **pytest 7.4.0** — `pytest-flask`, `pytest-cov 4.1.0`, `pytest-mock 3.11.1`, `coverage 7.3.0`
- **Jinja2** — templating via Flask; all templates in `templates/`, all extend `base.html`
- **Flask-SocketIO** — real-time battle ticker; `async_mode='threading'`

---

## Critical Implementation Rules

### Language-Specific Rules

- **Logger setup**: Every module must use `logger = logging.getLogger('royal_succession.<module_name>')`. Use `from utils.logging_config import setup_logger` in models. Never use `print()`.
- **DB error handling**: All DB writes must be wrapped in `try/except` with `db.session.rollback()` and `flash("...", "danger")` — no silent failures.
- **LLM guard pattern**: Every LLM call must check `if llm_model is None: return fallback_value` before invoking. Never call the model without this guard.
- **Prompt strings**: All LLM prompt strings live in `utils/llm_prompts.py` only. Never inline prompt text in routes, blueprints, or model classes.
- **Subsystem constructors**: All subsystem classes (`MilitarySystem`, `EconomySystem`, etc.) take `session: Session` as their only constructor argument.
- **DB model naming**: DB-backed model classes are always suffixed `DB` (e.g. `DynastyDB`, `PersonDB`). Never name a DB model without the suffix.
- **SQLAlchemy relationships**: Always use `back_populates=`, never `backref=`. Use explicit `foreign_keys=` when there is any ambiguity (circular FKs).
- **Circular FK fix**: Add `use_alter=True, name='fk_<descriptive_name>'` to `db.ForeignKey(...)` calls that create circular references — required to avoid SQLAlchemy metadata ordering errors.
- **Flash categories**: Only four valid values — `"success"`, `"danger"`, `"info"`, `"warning"`. No other strings accepted.
- **Config access**: Always use `current_app.config.get('KEY')` — never hardcode API keys or reference `os.environ` directly inside blueprints or models.
- **LLM token budgets** (hard limits — never exceed):

  | Use case | max_tokens |
  |---|---|
  | Chronicle narration | 150 |
  | AI advisor | 200 |
  | AI dynasty decision | 100 |
  | Battle commentary | 60 |

### Framework-Specific Rules

- **All routes require auth**: Every game route must have `@login_required`. Auth routes (`/login`, `/register`) are the only exceptions.
- **Blueprint registration only in `main_flask_app.py`**: Do not import or register blueprints anywhere else. Keep `main_flask_app.py` ≤ ~300 lines — app setup only.
- **`url_for` always**: Always use `url_for('blueprint_name.function_name')`. Never hardcode URL strings in templates or redirects.
- **Turn processing guard**: Routes that mutate dynasty state must check `dynasty.is_turn_processing` and block/redirect if True. Use the `@block_if_turn_processing` decorator from `blueprints/dynasty.py`.
- **Serialize before template**: Pass only serialized primitives (dicts, lists, strings) to templates — never raw SQLAlchemy ORM objects.
- **SVG rendering**: SVG strings from DB are rendered with `{{ svg_string | safe }}`. Do not add escaping.
- **Flash in base.html**: `get_flashed_messages(with_categories=true)` is already in `base.html`. Never re-render flash in individual templates.
- **SocketIO scope**: Use `socketio.emit()` for battle ticker only. All SocketIO event handlers must be thread-safe (`async_mode='threading'`).
- **Templates**: Every template must start with `{% extends 'base.html' %}`. Never override base font or CSS variables.

### Testing Rules

- **Target**: 187 tests must pass, 0 failures, 0 skipped after every change. Run `pytest` before every merge.
- **Test locations**:
  - `tests/unit/` — pure logic, no HTTP, no DB
  - `tests/integration/` — full Flask routes with in-memory SQLite
  - `tests/functional/` — end-to-end flows
- **New route** → at least one integration test in `tests/integration/`
- **New game mechanic** → at least one unit test in `tests/unit/`
- **Never skip** a test without an inline comment explaining exactly why.
- **Fixture scoping**:
  - `app` — session-scoped (one Flask app per session)
  - `db` — session-scoped (schema created once)
  - `session` — function-scoped (drops and recreates all tables per test — this is the correct isolation mechanism)
- **In-memory only**: Never reference `instance/dynastysim.db` in tests.
- **Auth in integration tests**: Create users inside `with app.app_context():`, log in via `client.post('/login', ...)`, use `follow_redirects=True` on form submissions.
- **Theme key**: Use `VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'` for all test dynasty creation.
- **No real DB mocks**: Do not mock the SQLAlchemy session in integration tests — use the real in-memory DB.
- **Always mock LLM**: `google-generativeai` calls must be mocked via `mocker.patch()` at the call site in the module under test.

### Code Quality & Style Rules

- **Naming**:
  - DB models: suffixed `DB` — `DynastyDB`, `PersonDB`
  - Blueprint objects: `<name>_bp` — `dynasty_bp`, `economy_bp`
  - Loggers: `'royal_succession.<module_name>'`
  - Prompt builders: `build_<name>_prompt(**kwargs) -> str`
  - Fallback generators: `generate_<name>_fallback(...)`, co-located in `utils/llm_prompts.py`
- **No `print()`** anywhere — use `logger.debug/info/warning/error`.
- **No inline prompt strings** — all LLM prompts in `utils/llm_prompts.py`.
- **No raw ORM objects in templates** — serialize to dict/list before `render_template()`.
- **No hardcoded URLs** — always `url_for(...)`.
- **No new dependencies** without updating `requirements.txt`.
- **No API keys in source** — always `current_app.config.get('KEY')`.
- **Comments**: Default to none. Only add when the WHY is non-obvious. No multi-line docstrings for obvious methods.
- **`main_flask_app.py`**: Must stay ≤ ~300 lines. No route handlers, no business logic, no prompt strings.

### Development Workflow Rules

- **Branch naming**:

  | Type | Pattern |
  |---|---|
  | Feature | `feature/<short-description>` |
  | Bug fix | `fix/<short-description>` |
  | Infrastructure | `infra/<short-description>` |
  | Refactor | `refactor/<short-description>` |
  | Tests | `test/<short-description>` |
  | Chores/docs | `chore/<short-description>` |

- **Commit format** (Conventional Commits): `<type>(<scope>): <imperative description>`
  - Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`, `infra`
  - Good: `feat(banking): add loan repayment route with interest calculation`
  - Bad: `update stuff`, `fix`, `wip`, `changes`
- **Commit frequency**: After every logical unit of work. Minimum 1 commit per sprint task; target 15–20 per sprint. Never batch everything into one end-of-task commit.
- **Never `git add .`** — always stage specific files by name.
- **Never commit**: `__pycache__/`, `*.pyc`, `logs/`, `instance/dynastysim.db`, `.env`.
- **Merge protocol**: `git merge --no-ff` always. Run `pytest` immediately before merging. Update `STATUS.md` after every completed task. Delete branch locally after merge.

### Critical Don't-Miss Rules

- **Circular FK between `DynastyDB` ↔ `PersonDB`**: Any new FK between these two tables MUST use `use_alter=True, name='fk_<name>'` on the `db.ForeignKey(...)` call.
- **Never `backref=`**: Always `back_populates=` with explicit relationship on both sides.
- **Explicit `foreign_keys=`**: Required on any relationship where SQLAlchemy cannot infer the join condition (multiple FKs between same tables).
- **Schema changes require migration**: Never alter DB models without updating `models/db_initialization.py`. Do not rely on `db.create_all()` for schema evolution.
- **`__tablename__` always explicit**: Every DB model class must declare `__tablename__`.
- **Do not rewrite working subsystems**: `MilitarySystem`, `EconomySystem`, `DiplomacySystem`, `AIController`, `GameManager`, `MapGenerator`, `TerritoryManager`, `BorderSystem`, `TimeSystem`, and all `visualization/` renderers are complete and tested. Extend via public API; never rewrite internals.
- **LLM must always have a fallback**: The app must be fully functional when `GOOGLE_API_KEY` is absent. Every LLM code path needs a working non-LLM fallback.
- **Security**:
  - `@login_required` on every route except `/login`, `/logout`, `/register`, `/`
  - Never expose raw SQLAlchemy objects via `jsonify()` — serialize to dict first
  - `{{ svg_string | safe }}` is safe only for server-side SVG from DB — never use `| safe` on user input
  - No SQL string interpolation — always use SQLAlchemy ORM or parameterized queries

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — especially DB, LLM, and test rules
- When in doubt, prefer the more restrictive option
- Never rewrite a working subsystem — extend it

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack or conventions change
- Remove rules that become obvious over time

_Last Updated: 2026-05-01_
