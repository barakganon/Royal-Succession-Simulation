# Deferred Work Log

## Deferred from: code review of sprint01-task01-turn-processor-extraction (2026-05-02)

All items below are pre-existing issues in `blueprints/dynasty.py` surfaced during the Sprint 1 Task 1 refactor review. None were introduced by this PR.

- **2-tuple early exits in `process_dynasty_turn`** [`models/turn_processor.py:72,85`] — `return False, "Dynasty not found"` and `return False, "Invalid theme configuration"` are 2-tuples; docstring promises 3-tuple. Callers guard with `len(result)==3` so no live bug. Harden the contract in Sprint 1 Task 1-2 when the function signature changes anyway.

- **`FLASK_APP_GOOGLE_API_KEY` config key** [`models/turn_processor.py:182`] — `current_app.config.get("FLASK_APP_GOOGLE_API_KEY")` always returns `None` because the app only sets `FLASK_APP_GOOGLE_API_KEY_PRESENT` (bool). The `os.environ.get("GOOGLE_API_KEY")` fallback makes it work. Clean this up in Sprint 11 config audit.

- **`max_output_tokens: 300` violates 150-token chronicle budget** [`models/turn_processor.py:196`] — CLAUDE.md mandates 150 for chronicle narration; this uses 300. Address when refactoring the epic story generation in Sprint 9 (LLM storytelling spine).

- **`current_simulation_year` advances outside per-year `try/except`** [`models/turn_processor.py:138`] — A year that raises an exception still advances the clock, silently losing that year's lifecycle events. Sprint 1 Task 1-2 (interrupt-driven loop) will restructure this loop and can fix it then.

- **Sibling NULL FK query** [`models/turn_processor.py:510`] — `PersonDB.father_sim_id == deceased_monarch.father_sim_id` is vacuously false when father is NULL, so founders skip the sibling path and fall straight to "any living noble." Low impact (succession still works via fallback). Sprint 5 succession drama is the right fix point.

- **`_llm_available()` asymmetry** [`blueprints/dynasty.py:37`] — dynasty.py version has no try/except; will raise `RuntimeError` if called outside a Flask app context. Not a current bug (only called in request handlers). Consolidate into a shared util in Sprint 11 cleanup.

- **Double `DynastyDB.query.get` after commit** [`models/turn_processor.py:213`] — `dynasty_obj = DynastyDB.query.get(dynasty_id)` re-queries the same object already in session. Extra round-trip, plus silent `None` fallback. Fix in Sprint 11 N+1 query pass.

- **`monarch_title` NameError if `titles` is empty** [`models/turn_processor.py:566`] — `monarch_title` assigned inside `if titles:` but used unconditionally in an f-string below. Mitigated by `theme_config.get(title_key, ["Leader"])` default (list always has ≥1 item in practice). Harden in Sprint 5 succession drama work.

- **`BankingSystem.accrue_interest` post-commit rollback gap** [`models/turn_processor.py:153`] — Called after `db.session.commit()` with only a log on failure; partial writes could be orphaned. Address in Sprint 10B follow-on or Sprint 11 transaction audit.

## Deferred from: code review of 1-2-interrupt-driven-turn-loop (2026-05-03)

- **`years_advanced` incremented unconditionally after exception** [`models/turn_processor.py:148-152`] — a year whose `try` block throws still increments `years_advanced` and `current_simulation_year`, counting it as processed even though no events were generated. Pre-existing behavior made explicit by the new `years_advanced` variable; same clock-advance-on-exception semantics as the original `for` loop. Fix in Sprint 11 logging & warnings pass.
- **`quiet_period` interrupt tuple stores count, not year** [`models/turn_processor.py:155`] — `interrupt = ('quiet_period', years_advanced)` uses a count as the second element; `monarch_death` uses `current_year` (absolute). Internal inconsistency; `interrupt[1]` is not surfaced in `turn_summary` so no external impact today. Normalize both interrupts to use absolute year when `interrupt[1]` is first consumed (Story 1-3 or later).
## Deferred from: code review of 1-3-turn-report-interrupt-ui (2026-05-03)

- **`alert-warning` (yellow) used for war/attack interrupt banner instead of orange** [`templates/turn_report.html:31`] — AC3 specifies "Orange background" but Dev Notes say `alert-warning`; internal contradiction resolved in favor of Dev Notes. Add `style="background-color:#fd7e14;border-color:#e35d06;color:#fff;"` override if visual orange is desired in Sprint 11 polish.
- **Unknown INTERRUPT_REASONS fall into quiet_period else branch** [`templates/turn_report.html:34-38`] — `heir_majority`, `major_world_event`, `story_moment` are in `INTERRUPT_REASONS` but have no banner branch; they silently render as "N quiet years passed." Add branches in the sprint that wires each interrupt type (Sprints 5, 6, 10).
- **Double `| default(5)` evaluation in pluralisation expression** [`templates/turn_report.html:37`] — `summary.years_advanced | default(5)` called twice independently; simplify with `{% set yrs = summary.years_advanced | default(5) %}` in Sprint 11 cleanup.

- **`living_persons` snapshot excludes newly-created persons** [`models/turn_processor.py:99-102`] — persons created by `process_marriage_check` or `process_childbirth_check` are never added to the in-loop snapshot; new spouses and children receive no lifecycle processing in the same turn they're created. Pre-existing simulation accuracy gap; fix when rewriting lifecycle iteration in Sprint 6 or later.

## Deferred from: code review of 3-1-world-map-panel-rebuild (2026-05-17)

- **Inline `onclick=` / `onkeydown=` attributes in world_map.html** — CSP-hostile (forces `unsafe-inline`). Pre-existing codebase pattern; consider extracting to event listeners + data-attributes when CSP is enforced in Sprint 11.
- **`window.currentDetailContext` / `window.openDetailPanel` / `window.closeDetailPanel` pollute global namespace** [`templates/world_map.html`] — required because the inline `onclick=` attributes can't reach IIFE-scoped functions. Same fix-point as the CSP item above.
- **SVG strings rendered with `| safe`** [`templates/world_map.html`] — `coat_of_arms_svg` and `portrait_svg` are server-generated; if any future feature lets a user submit SVG, this is an XSS vector. Sprint 11 security pass.
- **z-index `50` magic number on `.game-detail-panel`** [`static/style.css`] — no documented stacking-context contract. Add a constants comment block when more overlays land.
- **`:` width 320px on detail panel may overflow narrow viewports** [`static/style.css`] — mobile responsiveness not in scope until a dedicated mobile sprint.
- **`.game-left-rail` `overflow-y: auto` produces a Windows-style scrollbar that eats half the 60px column** [`static/style.css`] — add `scrollbar-width: thin` when this surfaces in cross-platform QA.
- **No focus trap inside `.game-detail-panel`** [`templates/world_map.html`] — only the close button is focusable in the stub; Story 3-3 must add a focus trap when it wires real content with multiple focusable children.
- **Test count of `'game-project-slot is-empty'` substrings is class-order-brittle** [`tests/integration/test_world_map_panels.py`] — works today because the template emits a stable class order; revisit if the slot template grows conditional classes.
- **`projects.sort(key=lambda p: p.started_year)` no `or 0` fallback** [`blueprints/map.py:world_map`] — `started_year` is `nullable=False` per Story 2-1; unreachable in practice.
- **No assertion that `active_projects` filtering is dynasty-scoped beyond `get_active_projects(dynasty_id)`** [`blueprints/map.py:world_map`] — `get_active_projects` already filters by `dynasty_id`; defense-in-depth would re-check at the route, but is redundant.
- **Lazy `from models.project_system import ProjectSystem` inside the route** [`blueprints/map.py:world_map`] — matches existing lazy-import pattern in the same file (Story 1-3 used the same convention for `EconomySystem`).
- **`projects[:3]` cap not surfaced as a constant** [`blueprints/map.py:world_map`, `templates/world_map.html` `range(3)`] — two hard-codes for "3 slots". Lift to `PROJECT_SLOT_COUNT` constant when Sprint 4 introduces the free-action split.
- **No test for the populated-slot case (active_projects has 1/2/3 entries)** [`tests/integration/test_world_map_panels.py`] — would require building a real Project row in the test setup; Story 3-3 will exercise this path more naturally when it fills the detail body.
- **`project_type[:2] | upper` slice may render `BU` for `build_farm` rather than the more semantic `BF` or `FA`** [`templates/world_map.html`] — Story 3-3 should wire `_PROJECT_LABELS` from Story 2-4 for human-readable abbreviations.
- **No "missing assets" fallback if SVG strings are empty but non-null** [`templates/world_map.html`] — `{% if ... and dynasty.coat_of_arms_svg %}` covers None; doesn't cover empty-string SVG. Rare; defer.

## Deferred from: code review of 2-4-multi-generation-story-hook (2026-05-17)

- **`_llm_available()` duplicated in `models/project_system.py` and `models/turn_processor.py`** — intentional to avoid a circular import (turn_processor already imports project_system). Sprint 11 cleanup should lift both into `utils/llm_guard.py`.
- **Bare `except Exception` in `_llm_available()` silently returns False on config bugs** [`models/project_system.py`] — matches pre-existing pattern; a misconfigured Flask app context masquerades as "LLM unavailable" with no warning.
- **Inline `genai.configure()` + hardcoded `"gemini-1.5-flash"` model name** [`models/project_system.py:_chronicle_multigen_completion`] — matches `turn_processor.py` pattern. Centralize when Sprint 11 introduces a shared LLM client wrapper.
- **No LLM timeout configured** [`models/project_system.py`] — `model.generate_content` will hang indefinitely if the API stalls; pre-existing pattern. Sprint 11 LLM hardening.
- **Three different config key names for the Google API key** — `FLASK_APP_GOOGLE_API_KEY_PRESENT`, `FLASK_APP_GOOGLE_API_KEY`, `GOOGLE_API_KEY`. Already on the deferred list from Story 1-4 (`turn_processor.py:200`).
- **Network errors / rate-limit / quota collapse into one warning** [`models/project_system.py`] — no retry, no circuit breaker. Sprint 11 LLM hardening.
- **`max_output_tokens=100` paired with "Write exactly 2-3 sentences" instruction may truncate** [`models/project_system.py`, `utils/llm_prompts.py:build_multigen_project_completion_prompt`] — intentional safety under 150-token chronicle budget; revisit if truncation observed in practice.
- **`_PROJECT_LABELS` is module-level mutable dict** [`utils/llm_prompts.py`] — convention in this codebase. Freeze with `MappingProxyType` in Sprint 11 if needed.
- **No prompt-injection sanitization on monarch / dynasty names** [`utils/llm_prompts.py`, `models/project_system.py`] — a user-controlled dynasty name with `"Ignore previous instructions and ..."` flows straight into the LLM. Real concern; Sprint 11 security pass should sanitize across all prompt builders.
- **Hardcoded `'project_completed_multigen'` event_type string** [`models/project_system.py`, `tests/unit/test_project_system.py`] — no constant / enum; typo risk. Sprint 11 introduces an EventType enum.
- **Fallback ignores `dynasty_name` parameter** [`utils/llm_prompts.py:generate_multigen_project_completion_fallback`] — true but harmless; master plan template doesn't use it. Remove or use.
- **Hook fires before commit; the "queued" INFO log overstates if commit fails** [`models/project_system.py`] — cosmetic; outer commit failure produces its own warning.
- **No fractional-year refund / partial-progress tests for ProjectSystem** — Story 2-3 deferred; not introduced by 2-4 but worth restating.

## Deferred from: code review of 2-3-wire-projects-and-migrate-actions (2026-05-17)

- **`Building.is_under_construction` referenced in `economy_system.py` but never declared on the Building model** [`models/db_models.py:Building`, `models/economy_system.py:639,748,784,815`] — pre-existing inconsistency surfaced during Story 2-3. Either the column was added via manual DB migration and the model is out of date, OR `economy_system.construct_building` has been silently erroring. Add the column declaration to the model OR remove the legacy `is_under_construction` machinery entirely (the project-completion path no longer needs it). Sprint 11 cleanup candidate.
- **No territory ownership check in `start_project`** [`models/project_system.py:start_project`] — accepts any `target_territory_id`. Pre-existing pattern from legacy `submit_actions`; tighten in Sprint 4 free-action validation or Sprint 11 cleanup.
- **No ownership check at project completion** [`models/project_system.py:_effect_*`] — territory may have changed hands mid-project; gameplay exploit. Defer to Sprint 5 succession drama / war-system rework.
- **`_effect_recruit_infantry` hardcodes `UnitType.LEVY_SPEARMEN`, quality=1.0, morale=1.0, maintenance_cost=1, food_consumption=1** [`models/project_system.py`] — old `MilitarySystem.recruit_unit` had similar simplifications; fold in real military balance in Sprint 11.
- **No upper bound on `development_level` in `_effect_develop_territory`** [`models/project_system.py`] — old `develop_territory` was also unbounded; cap when designing development tier rewards.
- **5 catalogue entries reachable via routes but still NO-OP at completion** [`models/project_system.py:EFFECT_DISPATCHER`] — `recruit_cavalry`, `build_walls`, `build_cathedral`, `envoy_mission`, `march_army_cross_realm` complete with `[stub]` logs. Wire effects when gameplay decisions land (Sprint 4+).
- **No resource refund / pause-vs-cancel semantics on stall** [`models/project_system.py:tick_projects`] — stalled rows just sit there; UX for resume/cancel is Sprint 3 (Epic 3 UI).
- **`stalled_project_ids` always present in `turn_summary`** [`models/turn_processor.py`] — even on non-stall turns. Harmless; callers check `interrupt_reason` first.
- **`_BUILDING_TYPE_TO_PROJECT_TYPE` / `_UNIT_TYPE_TO_PROJECT_TYPE` defined inside `submit_actions`** [`blueprints/dynasty.py`] — module-level constants would be cleaner; Sprint 11 cleanup.
- **`construction_year` semantics differ between effects** [`models/project_system.py:_effect_recruit_infantry,_effect_build_farm`] — `_effect_build_farm` uses `started_year`, `_effect_recruit_infantry` uses `completion_year`. Both arguably correct (a building was started THEN; a unit came into being AT completion) but document the convention.
- **`test_complete_sets_status_and_invokes_dispatcher` switched to `envoy_mission`** [`tests/unit/test_project_system.py`] — fragile to a future real-effect wiring of envoy_mission. Replace caplog string-match with a mock dispatcher when Sprint 11 test cleanup runs.
- **`_make_territory` helper duplicates Region/Province creation** [`tests/unit/test_project_system.py`] — lift to a shared conftest helper if more tests need it.
- **Bare `except Exception` in turn_processor tick/completion wiring** [`models/turn_processor.py`] — matches existing file pattern; tighten when Sprint 11 logging pass runs.

## Deferred from: code review of 2-2-project-system-logic (2026-05-17)

- **`requires_building` field in catalogue not enforced by `start_project`** [`models/project_system.py:PROJECT_TYPE_CATALOGUE`] — Story 2-3 owns building-gate enforcement; until then `recruit_cavalry` can start without Stables.
- **`slot` field in catalogue not consumed by `start_project`** [`models/project_system.py:PROJECT_TYPE_CATALOGUE`] — Sprint 3 (UI) surfaces the 3-project-slot constraint; backend currently allows unlimited active projects.
- **`start_project` accepts arbitrary kwargs (no whitelist)** [`models/project_system.py:start_project`] — typos like `target_territoy_id` silently swallowed. Sprint 11 type-strict kwargs cleanup.
- **`start_project` doesn't pre-validate `target_*` FK existence** [`models/project_system.py:start_project`] — DB FK rejects on commit but error is opaque. Story 2-3 may add eager validation for nicer UX.
- **No history-log entries from tick/complete/cancel** [`models/project_system.py`] — Story 2-4 (chronicle hook) owns multi-monarch completion line; Story 2-3 wires the chronicle for tick/stall events.
- **No `resume_project` method — stalled is permanent** [`models/project_system.py`] — intentional for now; Sprint 5 succession drama or Sprint 11 economy fixes may add resume.
- **All-or-nothing affordability (no partial-pay)** [`models/project_system.py:tick_projects`] — game-design decision; revisit if telemetry shows it's frustrating.
- **Affordability uses `<` (no buffer)** [`models/project_system.py:start_project,tick_projects`] — dynasty with exactly year-1 cost can start a project that immediately drains to zero. Sprint 11 if economy balance needs a buffer.
- **`build_walls` / `build_cathedral` are gold-only** [`models/project_system.py:PROJECT_TYPE_CATALOGUE`] — placeholder until Sprint 6 wires a stone resource on DynastyDB.
- **`tick_projects` iteration order is DB-insertion order** [`models/project_system.py:tick_projects`] — non-deterministic fairness across SQLite/Postgres if dynasty has multiple projects competing for last resources. Story 2-3 may add `ORDER BY started_year` (FIFO).
- **`cancel_project` doesn't emit a chronicle line** [`models/project_system.py:cancel_project`] — Story 2-4 chronicle hook will add a cancel-line variant.
- **No fractional-year refund tests** [`tests/unit/test_project_system.py`] — e.g. cancel after 3 of 5 ticks of a 100g/yr project = 150g refund. Add when Story 2-3 wires cancel into UI.
- **`PROJECT_TYPE_CATALOGUE` returns mutable dict by reference** [`models/project_system.py`] — no `MappingProxyType` / freeze. Constants in this codebase aren't frozen by convention; caller responsibility.
- **No `ProjectSystemError` base class** [`models/project_system.py`] — premature abstraction; revisit when a 2nd exception type is needed.
- **No method-level docstrings on ProjectSystem methods** [`models/project_system.py`] — Sprint 11 documentation pass.
- **`caplog`-based dispatcher test is fragile to log format** [`tests/unit/test_project_system.py:test_complete_sets_status_and_invokes_dispatcher`] — replace with mock dispatcher in Sprint 11 test cleanup.
- **`_make_monarch` always `gender='MALE'`** [`tests/unit/test_project_system.py`] — extend when Sprint 5 succession drama needs female-monarch coverage.
- **Monarch-succession test simulates inheritance manually** [`tests/unit/test_project_system.py:test_complete_sets_completed_by_to_current_monarch_not_initiator`] — acceptable until Sprint 5 wires the real flow into a fixture.
- **Multi-dynasty isolation not explicitly tested in 2-2** [`tests/unit/test_project_system.py`] — only one dynasty per test; partial coverage via `get_active_projects` filter. Full multi-dynasty integration in Story 2-3.
- **`completion_year = started_year + duration_years` semantic (1-year project finishes in `started_year+1`)** [`models/project_system.py:start_project`] — pinned by tests; not changing. Could be confusing for game balance docs.
- **No `pytest.xfail` on `test_tick_ignores_food_cost`** [`tests/unit/test_project_system.py`] — documented design choice (food is forward-compat); Sprint 6 will replace with real food-drain assertions.

## Deferred from: code review of 2-1-project-db-model (2026-05-16)

- **`project_type` and `status` as free-form strings, not `db.Enum`** [`models/db_models.py:Project`] — typos like `'build_wals'` or `'actve'` will persist silently. Define `ProjectType` / `ProjectStatus` enums when Story 2-2 finalizes the catalogue.
- **No `ondelete='SET NULL'` on `target_*` and monarch FKs** [`models/db_models.py:Project`] — deleting a target territory/dynasty/person leaves stale FKs. Story 2-2's `tick_projects` should defensively skip / cancel projects whose target is gone; alternatively add `ondelete='SET NULL'` to the FK definitions in 2-2.
- **No `CheckConstraint` for `completion_year >= started_year`, non-negative costs, or year bounds** [`models/db_models.py:Project`] — app-level validation in Story 2-2's `start_project()` is the planned guard. DB-level constraints would be belt-and-braces.
- **`yearly_cost_*` columns `nullable=True` with Python `default=0`** [`models/db_models.py:Project`] — raw SQL inserts could write NULL; subsequent arithmetic in `tick_projects` would raise `TypeError`. Tighten to `nullable=False` + `server_default='0'` in Story 2-2 when those columns are actively read.
- **`get_params`/`set_params` lacks malformed-JSON guard and `None` handling** [`models/db_models.py:Project`] — caller responsibility; corruption is an exceptional path. Add try/except + logging in Sprint 11 cleanup if it surfaces in practice.
- **No composite index on `(dynasty_id, status)` / `(status, completion_year)`** [`models/db_models.py:Project`] — already on the deferred list at `11-3-performance-optimizations`. Will become important once Story 2-2's `tick_projects` scans active projects every year for every dynasty.
- **No `created_at`/`updated_at` timestamps on Project** [`models/db_models.py:Project`] — every other late-added model (Chronicle, Loan, Building) has them. Sprint 11 cleanup normalization.
- **No DB-level `ondelete='CASCADE'` on `Project.dynasty_id`** [`models/db_models.py:Project.dynasty_id`] — ORM `cascade='all, delete-orphan'` covers normal session-mediated deletes; a raw SQL `DELETE FROM dynasty` would orphan. Add at the same time as the other ondelete tightening.
- **No reverse `back_populates` on `Territory`, `PersonDB`, `DynastyDB.target_*` sides** [`models/db_models.py:Project`] — intentional one-way for now (Story 2-2 only walks Project → target). Add inverse collections when navigation in the other direction is actually needed (Sprint 3 UI may need `territory.active_projects`).
- **No app-level guard against `dynasty_id == target_dynasty_id` self-targeting** [`models/db_models.py:Project`] — Story 2-2's `start_project` should reject self-envoys / self-marriages with a domain validation error.
- **Migration test covers only the "table missing" branch** [`tests/unit/test_db_models.py`] — the "table already exists" branch is also worth exercising once Sprint 11 introduces Alembic and the lazy-create pattern goes away anyway.
- **`Project` imported top-level in `db_initialization.py` while `Loan` is lazy-imported** [`models/db_initialization.py`] — inconsistent. Normalize when Sprint 11 introduces Alembic (Story 11-2).
- **No file-end trailing newline on `test_db_models.py`** [`tests/unit/test_db_models.py`] — pre-existing. Trivial cleanup at any time.
- **No test for "Project pointing at deleted `target_*` row continues to exist"** [`tests/unit/test_db_models.py`] — Story 2-2 will need this coverage once `tick_projects` walks target relationships.

## Deferred from: code review of 1-4-chronicle-prompt-years-and-interrupt (2026-05-16)

- **`monarch_death` fallback branch ignores `start_year`/`end_year`** [`utils/llm_prompts.py:151-163`] — Intentional per spec Dev Notes (uses `years_advanced` + `monarch_name` instead of explicit date range), but creates an inconsistency with the other two branches in the same function. Possible future polish: include "in the years X to Y" phrasing in the monarch-death sentence too.
- **No unit test for unknown `interrupt_reason` value** [`tests/unit/test_llm_prompts.py`] — closed-set invariant from `INTERRUPT_REASONS` makes this low priority, but defensive coverage would catch a future expansion mistake. Add when wiring new interrupt types (Epics 5, 6, 10).
- **`start_year == end_year` produces "from 1300 to 1300"** [`utils/llm_prompts.py:175`] — happens only when `years_advanced==1`; awkward but not broken. Address with `"year 1300"` vs `"years 1300 to 1304"` branching when polishing prose in Sprint 12 (chronicle compiler).
- **`pacing_hint` if/elif chain rather than dict lookup** [`utils/llm_prompts.py:138-143`] — premature abstraction for the current 2-branch case; revisit when a 3rd interrupt class needs differentiated pacing copy. Sprint 5 succession drama is the likely trigger.
- **Test `_call` helper duplicated across two test classes** [`tests/unit/test_llm_prompts.py`] — minor style; could lift to module-level fixture. Cosmetic, Sprint 11 cleanup.
- **Inconsistent parameter typing** [`utils/llm_prompts.py:128,148`] — only new params have type hints, existing positional args untyped. Sprint 11 logging/warnings pass should add types module-wide.
- **Magic defaults `years_advanced=5` / `interrupt_reason='quiet_period'`** [`utils/llm_prompts.py:128,148`] — documented in Dev Notes for backward compatibility; move to a `constants.py` module so turn-length and default-interrupt aren't scattered. Sprint 11.
- **`pacing_hint` meta-instruction may bleed into LLM narrative output** [`utils/llm_prompts.py:136-143`] — speculative; the prompt instructs "ONE paragraph (4-6 sentences)" but the literal interrupt-reason text could echo into the model's output. Cannot be asserted in unit tests; observe in Sprint 9 LLM storytelling spine when wiring real-LLM smoke tests.

## Deferred from: adversarial review post-Story-1-3 (2026-05-05)

- **`INTERRUPT_REASONS` Python constant has 6 unimplemented values** [`models/turn_processor.py:40-49`] — `heir_majority`, `project_complete`, `war_declared`, `attack_received`, `major_world_event`, `story_moment` are listed in `INTERRUPT_REASONS` but no code path ever sets them. The constant is aspirational documentation masquerading as a live contract. (The template-side fallthrough for unknown reasons is separately logged above.) Remove or annotate the constant to make the unimplemented status explicit; complete the list as each Epic wires its interrupt type (Epics 3, 5, 6, 10). Sprint 11 cleanup at minimum.

- **Succession crisis produces no interrupt** [`models/turn_processor.py:590-598`] — when `eligible_heirs` is empty, a crisis log is written but `interrupt` is never set. The turn continues advancing years as if nothing happened; the player sees the "quiet years" banner despite a dynasty-ending event. Fix in Story 5-1 (monarch death interrupt + succession UI) when the interrupt machinery for succession is wired end-to-end.

- **Test mock `process_death_check` is over-broad** [`tests/integration/test_game_loop.py`, `tests/functional/test_game_flow.py`] — `patch('models.turn_processor.process_death_check', return_value=False)` suppresses ALL deaths to guarantee deterministic year counts. This means patched tests produce dynasties with zero deaths, so no succession, marriage-after-spouse-death, or depleted-court interaction is ever exercised. Refine to a targeted mock (kill/spare specific persons by ID) when Story 5-1 rewrites the succession test suite.

- **`flask_session.pop` makes turn report single-use** [`blueprints/dynasty.py:340`] — `summary = flask_session.pop('last_turn_summary', None)` discards the report on first load. A player who presses Back and reloads the turn report URL gets silently redirected to `view_dynasty` with no explanation. Fix in Story 3-5 (animated turn pass + routing cleanup) when the turn report flow is replaced by the in-map event ticker; or persist the last summary to the DB as a fallback in Sprint 11.

## Deferred from: code review of 3-2-right-click-context-menu (2026-05-18)

- **`.cannot-afford` rows still fire click handler** [`templates/world_map.html`] — visually dimmed + `aria-disabled`, but the click handler is not short-circuited. Story 3-2 doesn't actually start projects (AC7 — only sets `window.lastChosenAction`), so safe today. Story 3-5 (animated turn pass + project starts) must add `if (cannotAfford) return;` before any `start_project` POST is wired.
- **Catalogue cache (`window.__projectCatalogue`) never invalidates** [`templates/world_map.html`] — fine while catalogue is fully static (Sprint 3 has no per-dynasty unlocks). Sprint 6 (building gates) may introduce dynamic gating; revisit then.
- **Wealth values baked into JS at template render time** [`templates/world_map.html`] — `var gold = {{ dynasty.current_wealth }}` is interpolated at page render, then re-used per right-click. If wealth changes mid-page (Sprint 4 free actions or AJAX-driven updates), the affordability badge goes stale. Refresh path or full reload required; address in Sprint 4 when free actions land.
- **`requires_building` text shown but not actually validated against player's buildings** [`templates/world_map.html`] — UI shows "Requires: Stables" but the row isn't disabled when the dynasty has no Stables. Pre-existing limitation; gating is Sprint 6 work (Story 6-2 building gates).
- **No drift test between `PROJECT_TYPE_CATALOGUE` keys and `canonical_order` list** [`blueprints/map.py::project_catalogue`] — new project types added to the catalogue but not to canonical_order silently disappear from the menu. Add assertion `set(canonical_order).issubset(PROJECT_TYPE_CATALOGUE.keys())` in tests, or log warning at startup. Sprint 11 chore.
- **Negative wealth from Sprint 10B loans renders ugly `(have -50)`** [`templates/world_map.html`] — numerically correct, visually clumsy. Polish when banking UI is revisited.
- **No user feedback on `project_catalogue.json` fetch failure** [`templates/world_map.html`] — silently shows empty menu, only logs to console. Add a toast/inline error in Sprint 11 polish.
- **Test `assert b"addEventListener('contextmenu'" in response.data` is string-brittle** [`tests/integration/test_world_map_context_menu.py`] — works today, but tied to literal text in template. Acceptable per Story 3-1 precedent (substring checks for stubs).
- **No assertion that `march_army_cross_realm` is excluded from menu** [`tests/integration/test_world_map_context_menu.py`] — spec says omit it; endpoint omits it; test doesn't verify. One-line addition possible.
- **CSS `::before` content `'⛔ '` is an emoji** [`static/style.css`] — repo policy bans emoji in source unless user-requested; CSS-rendered glyph for UI marker is arguably different category. Flag for style audit, replace with text symbol or background-image if policy hardens.
- **404 vs 403 leaks dynasty existence to attackers** [`blueprints/map.py::project_catalogue`] — `query.get_or_404` returns 404 for missing IDs; 403 for foreign-owned IDs. Distinguishable. Acceptable per existing codebase pattern; revisit in Sprint 11 security pass.
- **No focus-trap / keyboard navigation between rows** [`templates/world_map.html`] — rows have `tabindex="0"` but no arrow-key navigation. Acceptable for stub; Story 3-3 will expand the panel and may want full keyboard support.

## Deferred from: code review of 3-3-detail-panel-and-geojson (2026-05-25)

- **Unscoped `Building` / `MilitaryUnit` / `Project` table scans in `generate_geojson`** [`visualization/map_renderer.py`] — pre-aggregation queries fetch every row of those tables on every world-map page load, ignoring dynasty/territory scoping. Fine at sprint-level data sizes; will degrade silently as the DB grows. Sprint 11 (perf) should add `.filter(...).all()` scoped to the rendered territory ids and the player's dynasty.
- **N+1 `DynastyDB.query.get(...)` for `active_wars` attacker/defender names** [`blueprints/map.py::world_map`] — 2 queries per active war. Active wars are few; safe today. Use `joinedload` or the `War.attacker` / `War.defender` relationship in Sprint 11 cleanup.
- **Project tie-breaker by `(started_year, id)` not enforced** [`visualization/map_renderer.py` active_project aggregation] — when two active projects target the same territory in the same year, the first-returned row wins (SQLite row order = arbitrary). Visual: gold-shaded hex may flicker between projects across reloads. Add `.order_by(Project.started_year.asc(), Project.id.asc())` to make it deterministic.
- **Stale globals (`window.__activeProjectsById`, `__monarchData`, `__recentEvents`, `__activeWars`, `currentSimYear`) baked at page load** [`templates/world_map.html`] — fine while End Turn is a full nav. Sprint 3-5 (animated turn pass) introduces in-place state changes; revisit the seeding pattern then.
- **Unclaimed-hex hostile classification** [`visualization/map_renderer.py`] — units on territories with no controller all count toward `hostile_garrison_total`, painting unclaimed hexes red on the Threats overlay even when only friendly units are present. Designer call; revisit when threat overlay UX is reviewed.
- **Garrison list includes size-0 units** [`blueprints/map.py::territory_details`] — no `MilitaryUnit.size > 0` filter. Stale/zero units clutter the per-territory garrison list. Add filter when garrison detail gets more polish.
- **Projects overlay produces no visual when no hex has an active project** [`templates/world_map.html` `drawAll`] — falls back to terrain color, visually identical to the terrain overlay. Add a low-alpha grey wash or surface a toast when zero projects exist.
- **`.detail-list` lacks `max-height` / `overflow-y`** [`static/style.css`] — long building/garrison lists scroll the entire panel body (title scrolls off). Minor cosmetic; mobile sprint can address.
- **`_renderProjectSlot(ctx)` ignores `ctx.index`** [`templates/world_map.html`] — renders the generic "Empty Slot" card for slot 1, 2, and 3 identically. Acceptable until slots get per-index semantics (Sprint 4).
- **`_renderTerritoryCard` does not surface `Building.condition`** [`templates/world_map.html`] — endpoint emits it, panel ignores it. Add a "Condition" pill (% colored green→red) when building damage / siege state matters in Sprint 6.
- **Test isolation flake on `test_develop_action_raises_development_level`** [`tests/integration/test_project_turn_lifecycle.py:150`] — pre-existing intermittent failure under pytest-randomly ordering; passes in isolation and under `-p no:randomly`. Unrelated to Story 3-3. Sprint 11 test-isolation pass should kill the shared-state cause.
- **Completed-project staleness in `__activeProjectsById`** [`templates/world_map.html`] — a project that completes between page load and a click still shows as active (years_remaining clamped to 0). Sprint 3-5 (animated turn pass) will refresh the page state and obviate this.
- **`is_player_owned` route does linear scan of user dynasties per request** [`blueprints/map.py::territory_details`] — 1 query for the dynasties + a `set` membership check. Multi-dynasty users (rare) handled. Cache in `g` if it becomes hot.

## Deferred from: integration review of 3-4-borders-panzoom-overlays (2026-05-29)

- **`drawBorders()` is O(N²) per frame and rebuilds its data every `drawAll()`** [`templates/world_map.html`] — for each of N hexes it walks 6 edges and runs `nearestCentreFeature` (a linear scan over all N centres), and it rebuilds the `centres` array on every `drawAll()`. Since `drawAll()` now fires on every pan `mousemove` and every wheel tick, border cost is paid every frame. Fine at sprint-level map sizes; will visibly lag pan/zoom on large maps. Fix: precompute a per-hex neighbour adjacency map ONCE on GeoJSON load (keyed by col/row or by nearest-centre), and have `drawBorders` consume it. Sprint 11 perf pass (alongside the existing `generate_geojson` table-scan defer).
- **`byColRow` built but never read in `drawBorders`** [`templates/world_map.html`] — the `(col,row)->feature` lookup is constructed but the neighbour match uses the centre list instead, leaving `byColRow` dead. Remove it, or switch neighbour detection to use it (an O(1) col/row adjacency lookup would also resolve the perf item above). Trivial cleanup.
- **Border neighbour geometry is approximate under the non-standard hex layout** [`templates/world_map.html:drawBorders`] — `hexCenter` uses a pointy-top-style odd-row offset while `hexPath` vertices are at `PI/3*i`; the `C + 2*(M - C)` candidate + `R*0.6` tolerance is empirically tuned, not exact. Visual-only; verify borders render on realm boundaries during the manual `/world/map` check. If edges are missed/spurious, widen the tolerance or derive neighbours from a true axial mapping.

## Deferred from: integration review of 3-5-animated-turn-routing-cleanup (2026-05-29)

- **`advance_turn` is a GET with side effects (now also returns JSON for XHR)** [`blueprints/dynasty.py:231`] — processing a turn mutates state on a GET, which 3-5 extended with an XHR/JSON branch rather than fixing. Should be a POST (with CSRF) so reloads/prefetch can't re-trigger a turn. Pre-existing since the original form-based flow; convert to POST in Sprint 4 (free-action endpoints) or the Sprint 11 cleanup.
- **`turn_report` summary is single-use (`flask_session.pop`)** [`blueprints/dynasty.py`] — the animated End Turn navigates to `turn_report` exactly once, which is fine, but a manual reload of `/turn_report` still falls back to `view_dynasty` (the previously-logged item from the post-Story-1-3 review). Persist last summary to the DB if reload-resilience is wanted. Unchanged by 3-5.
- **Project-start POST wiring + `.cannot-afford` click guard remain unwired** [`templates/world_map.html`] — right-click still only sets `window.lastChosenAction` (Story 3-2). 3-5 deliberately kept to animated-turn + routing scope; actual project starts from the map are Sprint 4 (free actions) work. Re-stated here so it isn't lost now that Epic 3 is complete.

## Correct-course: world map rendered empty on real data (fix/world-map-empty-render, 2026-05-29)

Found by actually running the app (`/world/map`) against a real generated game — every Epic 3 story had deferred visual verification, so this shipped "tests-green but blank".

**Fixed in this branch:**
- **Empty map (root cause).** `visualization/map_renderer.generate_geojson` emits `col=int(x_coordinate)`, `row=int(y_coordinate)` — i.e. raw pixel positions on the generated map plane (≈74–800). But `world_map.html`'s `hexCenter(col,row)` multiplied them by `R·√3` / `R·1.5` as if they were compact hex-grid indices, exploding coords ~48× off-screen → blank canvas. Fix: `hexCenter` now returns the raw pixel position, plus a new `fitToView()` computes an initial scale+pan so the whole plane fills the canvas on load.
- **UI dynasty-create seeded no map.** `create_dynasty` only made a founder; the map model lives in `GameManager.create_new_game`, which the form never called → a normal new player got an empty map regardless. Fix: `create_dynasty` now bootstraps a small procedural map and assigns ~6 starting territories (1 capital) to the new dynasty, **gated on `not TESTING`** (so the 24 test create-calls are unaffected) and wrapped in try/except.

**Still open (logged, not fixed here):**
- **🔴 Running `pytest` destroys the dev DB.** `tests/integration/conftest.py` sets `SQLALCHEMY_DATABASE_URI=':memory:'` AFTER `main_flask_app` import has already bound the SQLAlchemy engine to `instance/dynastysim.db`; the override doesn't rebind, so per-test `db.drop_all()` wipes the real file. This is why the dev DB keeps coming back empty. Fix: bind the test engine to in-memory *before* `db.init_app` (e.g. a `create_app(testing=True)` factory or set the URI via env before import), or point tests at a throwaay temp file. High value — protects dev data and is a correctness smell.
- **🟡 Borders don't render on the point-map layout.** `MapGenerator` scatters territories as points in a plane (not a tessellated hex grid), so hexes don't share edges and Story 3-4's edge-based `drawBorders` rarely draws. Realm borders need either a tessellated grid layout or a region-outline/Delaunay approach — a map-model design choice, separate from this render fix.
- **🟡 `create_dynasty` map bootstrap is minimal** — grabs the first 6 unclaimed territories (no AI neighbours, no contiguity guarantee). It overlaps conceptually with `GameManager.create_new_game`; a proper "new game from the UI" story should unify them.
- **🟡 Legacy AP/action-queue side panel** still renders on `/world/map` alongside the Story-3-3 detail panel (superseded by the Epic 2 project model). Master plan wanted it gone; never removed.
