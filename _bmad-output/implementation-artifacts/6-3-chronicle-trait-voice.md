# Story 6-3: Chronicle Trait-Voice + Trait Tooltips + Player Docs

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player, I want the chronicle's narrative voice to reflect the reigning monarch's personality, the monarch's traits visible on hover, and a player-facing guide to what traits do — so the trait system (made mechanical in 6-1/6-2) is also legible and characterful. **Completes Epic 6.**

## Acceptance Criteria

1. **AC1 — Chronicle prompt receives monarch traits (`utils/llm_prompts.py`).** Add an optional `monarch_traits: Optional[list] = None` parameter to `build_chronicle_prompt(events, dynasty_name, year, ...)` (`:47`) AND to the live `build_turn_story_prompt(...)` (`:128`). When traits are provided, the prompt text instructs the chronicler to color the narrative voice to match them (e.g. "The reigning monarch is Brave and Wroth — let the telling reflect a bold, wrathful character."). Backward-compatible: omitted/None/empty → today's prompt unchanged. Keep within the 150-token chronicle budget. Deterministic fallbacks (`generate_*_fallback`) are unaffected.

2. **AC2 — Pass the active monarch's traits at the call site (`models/turn_processor.py`).** Where `build_turn_story_prompt(...)` is called (`~:310`), fetch the dynasty's living monarch (`PersonDB.is_monarch==True, death_year is None`) and pass `monarch_traits=monarch.get_traits()` (or `[]` if no monarch). LLM-guarded path unchanged; no monarch → no traits, prompt unchanged.

3. **AC3 — Surface traits in the monarch tooltip (`templates/world_map.html`).** The left-rail monarch portrait (`~:116`, currently `title="{{ monarch_name | trim }}"`) shows the monarch's traits on hover — extend the `title`/`aria-label` to include the trait list (e.g. `"Margaret, Queen of Anjou — Brave, Pious"`) when `current_monarch` traits are available. (Traits are already passed to the template / used by `_renderMonarchCard`.) The detail-panel monarch card's existing traits display stays intact. No backend route change needed if the monarch payload already carries traits; if it doesn't reach the rail, use what's available (`current_monarch`).

4. **AC4 — `docs/traits.md` (NEW, player-facing).** A concise markdown guide documenting all 8 canonical traits and their mechanical effects (sourced from `models/trait_effects.py` + Story 6-2): for each of **Brave, Craven, Cunning, Wroth, Patient, Pious, Greedy, Sickly** — a one-line description and its effects (combat / tax / diplomacy modifiers; Sickly's halved lifespan; note building gates and trait inheritance briefly). Player-readable tone.

5. **AC5 — No regressions.** Full suite green (baseline **395**; new tests additive). The chronicle/turn-story prompt changes are additive params with defaults, so existing prompt tests and the turn loop keep passing.

6. **AC6 — ≥4 new tests:**
   - `tests/unit/`: `build_chronicle_prompt`/`build_turn_story_prompt` with `monarch_traits=['Brave','Pious']` includes those trait names in the returned prompt string; with `None`/`[]` the prompt is unchanged from the no-traits form (and never errors).
   - `tests/integration/`: `/world/map` for a dynasty with a trait-bearing monarch renders the monarch's traits in the rail tooltip (assert the trait text appears in the monarch portrait `title`/`aria-label` region).
   - A test asserting `docs/traits.md` exists and names all 8 traits.

## Tasks / Subtasks
- [ ] Task 1 — Prompt trait-voice param + call-site wiring (`utils/llm_prompts.py`, `models/turn_processor.py`). [Agent A]
- [ ] Task 2 — Monarch trait tooltip + `docs/traits.md` (`templates/world_map.html`, `docs/traits.md`). [Agent B]
- [ ] Task 3 — Tests (unit prompt + integration tooltip + docs). [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `utils/llm_prompts.py` (add `monarch_traits` param to `build_chronicle_prompt` + `build_turn_story_prompt`) + `models/turn_processor.py` (pass living-monarch traits at the call site).
- **Agent B** — `templates/world_map.html` (monarch tooltip traits) + NEW `docs/traits.md`.
- **Agent C** — NEW test files only (`tests/unit/test_chronicle_trait_voice.py`, `tests/integration/test_trait_docs_and_tooltip.py` or similar).
- No shared files.

### FROZEN INTERFACE CONTRACT
- `build_chronicle_prompt(events, dynasty_name, year, monarch_traits=None)` and `build_turn_story_prompt(..., monarch_traits=None)` — when truthy, the returned prompt STRING contains the trait names and a voice instruction; None/empty → unchanged prompt; never raises.
- `turn_processor` passes `monarch_traits=<living monarch get_traits() or []>` to `build_turn_story_prompt`.
- `world_map.html` monarch rail tooltip (`title`/`aria-label`) includes the monarch's trait names when available.
- `docs/traits.md` exists and names all 8 traits (Brave, Craven, Cunning, Wroth, Patient, Pious, Greedy, Sickly) with effects.

### Reuse / project rules
- All prompt strings in `utils/llm_prompts.py`; keep the 150-token chronicle budget. Additive params with defaults (don't break existing callers/tests). `get_traits()` on PersonDB. No new deps. The monarch trait effects to document live in `models/trait_effects.py` (6-1) + the Sickly/inheritance rules (6-2).

### Out of scope / deferred
- No new mechanical effects (6-1/6-2 own those). 6-3 is voice + visibility + docs. After 6-3, **Epic 6 is complete**; `epic-6-retrospective` is optional.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool (Epic 5/6 ran clean). Agents default to plan mode → "EXECUTE NOW, pre-approved, no EnterPlanMode"; worktrees branch off `main`; contract inlined. Integrator verifies the main tree is clean before merging. `pytest` against an isolated temp DB rebuilt per run; reset it before a run for determinism. Baseline 395. Known `test_military_routes` flake.
- Tooltip is a `title` attribute (not a heavy visual feature) → a template-substring test suffices; no run-the-app screenshot needed.
- 6-1 = `trait_effects.py` + hooks; 6-2 = building gates + Sickly lifespan + trait inheritance.

## References
- `build_chronicle_prompt` / `build_turn_story_prompt`: `utils/llm_prompts.py:47`, `:128`; live caller `models/turn_processor.py:310`.
- Monarch rail tooltip: `templates/world_map.html:116`; detail-panel monarch card traits + `_renderMonarchCard` (`m.traits`).
- Trait effects to document: `models/trait_effects.py` (6-1 modifiers), 6-2 (Sickly lifespan, building gates, inheritance).
- Test fixtures: `tests/unit/` (prompt builders), `tests/integration/test_detail_panel_render.py:13-39`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool (run `wf_d4b2c14e-9e9`), + main-session integrator.

### Completion Notes List

- All ACs satisfied. `pytest -p no:randomly`: **402 tests** — 401 pass + 1 pre-existing shared-state ordering flake (`test_heir_turning_majority_age_triggers_interrupt_once`, which passes 12/12 in its file and 3/3 alone). Not a 6-3 regression.
- A `wt/6-3-prompt` (`5774999`): `monarch_traits=None` param on `build_chronicle_prompt` + `build_turn_story_prompt` (voice clause when truthy, byte-identical when None); call-site passes living-monarch `get_traits()`. B `wt/6-3-ui-docs` (`de88df5`): monarch rail tooltip `title`/`aria-label` includes traits; NEW `docs/traits.md` (all 8 traits + effects + building gates + inheritance). C `wt/6-3-tests` (`995b603`): 5 unit + 2 integration.
- **Integrator cleanup:** Agent B's Edit again leaked into the main working tree (uncommitted `world_map.html` + untracked `docs/traits.md`), which made the `wt/6-3-ui-docs` merge fail on a dirty tree. Discarded the leaked copies and merged the branch cleanly (its commit had the same content).
- Tooltip is a `title`/`aria-label` attribute (server-rendered Jinja from `current_monarch.traits`) → covered by the integration substring test; no heavy visual check needed.
- **Epic 6 (Traits & Buildings Matter) complete** (6-1…6-3).
- **Flagged tech-debt:** the shared-temp-DB test-isolation flake now intermittently fails the full-suite gate across several files — worth a dedicated Sprint-11 test-isolation fix (logged).

### File List

- `utils/llm_prompts.py` — MODIFIED (monarch_traits voice param)
- `models/turn_processor.py` — MODIFIED (pass monarch traits to the chronicle prompt)
- `templates/world_map.html` — MODIFIED (monarch trait tooltip)
- `docs/traits.md` — NEW (player-facing trait guide)
- `tests/unit/test_chronicle_trait_voice.py`, `tests/integration/test_trait_docs_and_tooltip.py` — NEW (7 tests)
- `_bmad-output/implementation-artifacts/{6-3-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED

### Change Log

| Date | Change |
|---|---|
| 2026-05-30 | spec(6-3); 3 worktree agents via Workflow; cleaned a leaked-edit merge; 401 pass + 1 isolation flake; Story 6-3 → done; Epic 6 complete |
