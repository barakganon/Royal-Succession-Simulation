# Story 6-1: Trait Effects System + Subsystem Hooks

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player whose rulers have personality traits,
I want those traits to actually change mechanical outcomes — a Brave monarch fights better, a Greedy one taxes harder, a Cunning one strikes better deals,
so that the trait/portrait flavor from earlier sprints becomes real strategy.

**Backend-only** (pure modifier module + additive hooks). No UI surface → tests are the verification.

## Acceptance Criteria

1. **AC1 — `models/trait_effects.py` (NEW, pure functions, no DB/session).** A module mapping the 8 canonical traits to mechanical modifiers and exposing pure helpers that take a `traits: list[str]` and return a number:
   - `TRAIT_MODIFIERS` dict: per trait, a dict of domain deltas. Suggested (tune as needed, keep deterministic):
     - `Brave`: combat +0.15
     - `Craven`: combat −0.15
     - `Wroth`: combat +0.10, diplomacy −10
     - `Patient`: combat +0.05 (steadiness), diplomacy +10
     - `Cunning`: diplomacy +15
     - `Pious`: diplomacy +10
     - `Greedy`: tax +0.20, diplomacy −5
     - `Sickly`: combat −0.05 (lifespan effect is Story 6-2; keep a small combat nudge only here)
   - `combat_modifier(traits) -> float` — returns a multiplier `1.0 + Σ combat deltas` (e.g. Brave+Wroth → 1.25). Unknown traits ignored.
   - `tax_modifier(traits) -> float` — multiplier `1.0 + Σ tax deltas`.
   - `diplomacy_modifier(traits) -> int` — additive `Σ diplomacy deltas` (relation/acceptance points).
   - All three: empty/None list → identity (1.0 / 1.0 / 0). Pure, side-effect-free, importable without a Flask app context.

2. **AC2 — Military hook (`models/military_system.py`).** In `_resolve_battle` (~:606), multiply each side's effective combat strength by `combat_modifier(<that army's controlling dynasty's living monarch traits>)`. Add a small private helper to fetch the monarch's traits for an army's `dynasty_id` (query `PersonDB` is_monarch + alive → `get_traits()`, default `[]`). Apply additively to the EXISTING strength computation (do not rewrite the battle math); a dynasty with no monarch/traits → modifier 1.0 (unchanged outcome). Keep the method's return shape unchanged.

3. **AC3 — Economy hook (`models/economy_system.py`).** In `calculate_territory_tax_income` (~:422) (or the dynasty-level tax aggregation if cleaner), multiply the computed tax income by `tax_modifier(<territory's controller dynasty's monarch traits>)`. No monarch/traits → 1.0. Keep return type (float) unchanged.

4. **AC4 — Diplomacy hook (`models/diplomacy_system.py`).** In `perform_diplomatic_action` (the relation-delta path), add `diplomacy_modifier(<actor dynasty's monarch traits>)` to the relation change (so a Cunning envoy improves relations more, a Wroth/Greedy one less). No monarch/traits → +0. Keep the `(ok, message)` return shape unchanged.

5. **AC5 — No regressions.** Full suite green (baseline **364**; new tests additive). All hooks are multiplicative/additive on top of existing logic and default to no-op when there's no monarch or no traits, so existing tests (which mostly use trait-less or monarch-less setups) keep passing. Don't rewrite the subsystems — extend via the modifier.

6. **AC6 — ≥6 new tests** split between unit and integration:
   - `tests/unit/test_trait_effects.py`: `combat_modifier`/`tax_modifier`/`diplomacy_modifier` for empty list (identity), single trait, multiple traits (additive), unknown trait (ignored). (Pure, no app context.)
   - `tests/integration/test_trait_effects_hooks.py`: a Brave monarch's army resolves with higher effective strength than an identical Craven/trait-less one (or wins where the baseline loses); a Greedy monarch's territory yields more tax than a trait-less baseline; a Cunning actor's diplomatic action moves relations more than a trait-less baseline. (Mock LLM; build dynasties/monarchs with set traits in `app.app_context()`.)

## Tasks / Subtasks
- [ ] Task 1 — `models/trait_effects.py` + military hook (`models/military_system.py`). [Agent A]
- [ ] Task 2 — economy hook (`models/economy_system.py`) + diplomacy hook (`models/diplomacy_system.py`). [Agent B]
- [ ] Task 3 — tests (`tests/unit/test_trait_effects.py` + `tests/integration/test_trait_effects_hooks.py`). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — NEW `models/trait_effects.py` (the pure module) + `models/military_system.py` (combat hook). Owns the trait_effects API.
- **Agent B** — `models/economy_system.py` (tax hook) + `models/diplomacy_system.py` (diplomacy hook). Imports `trait_effects` (created by A; absent in B's worktree — import is module-level but B can import inside the method/lazy to keep its isolated pytest importable, OR top-level since the hook only runs at call time; if a top-level import would break B's suite, use a lazy import inside the hooked method, mirroring the codebase's lazy-import pattern).
- **Agent C** — NEW test files only (`tests/unit/test_trait_effects.py`, `tests/integration/test_trait_effects_hooks.py`).
- No shared files. (A: trait_effects.py + military_system.py; B: economy_system.py + diplomacy_system.py; C: 2 new tests.)

### FROZEN INTERFACE CONTRACT
- `from models.trait_effects import combat_modifier, tax_modifier, diplomacy_modifier, TRAIT_MODIFIERS`.
- `combat_modifier(traits)->float` (1.0±), `tax_modifier(traits)->float` (1.0±), `diplomacy_modifier(traits)->int` (additive). Pure; empty/None → identity (1.0/1.0/0).
- Hooks fetch the relevant dynasty's LIVING monarch (`PersonDB.is_monarch==True, death_year is None`), use `monarch.get_traits()` (default `[]`), and apply the modifier on top of existing math. No monarch/traits → no-op. Subsystem return shapes unchanged.
- B should use a **lazy import** of `models.trait_effects` inside the hooked methods so `economy_system`/`diplomacy_system` still import in B's isolated worktree (where trait_effects.py is absent). It lands on integration with A.

### Reuse / project rules
- Do NOT rewrite `MilitarySystem`/`EconomySystem`/`DiplomacySystem` internals — extend via the modifier (project-context: subsystems are complete; extend via public/additive paths). Subsystem ctors take `session` only; the monarch-trait lookup uses `self.session`. `get_traits()` on PersonDB returns the trait list. No new deps.

### Out of scope / deferred
- Sickly → lifespan (`process_death_check`), building gates, trait inheritance → **Story 6-2**. Chronicle voice reflecting traits + player docs → **Story 6-3**. 6-1 is the modifier module + the 3 mechanical hooks only.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool (Epic 5 ran clean). Agents default to plan mode → "EXECUTE NOW, pre-approved, no EnterPlanMode"; worktrees branch off `main`; contract inlined. Integrator verifies the main tree is clean before merging (an agent's Edit can resolve against the main copy). `pytest` against an isolated temp DB rebuilt per run. Baseline 364. Known `test_military_routes` ordering flake (unrelated).
- Backend-only story → no run-the-app visual check needed.

## References
- `MilitarySystem._resolve_battle`: `models/military_system.py:606` (and `initiate_battle` :508).
- `EconomySystem.calculate_territory_tax_income`: `models/economy_system.py:422`.
- `DiplomacySystem.perform_diplomatic_action` + relation deltas: `models/diplomacy_system.py:198` (action-effect map ~:32).
- `PersonDB.get_traits()` / `is_monarch`: `models/db_models.py:232`, `:192`.
- Test fixtures: `tests/unit/` (pure), `tests/integration/test_detail_panel_render.py:13-39`.

## Dev Agent Record

### Agent Model Used

(to be filled by dev/integration)

### Debug Log References

### Completion Notes List

### File List
