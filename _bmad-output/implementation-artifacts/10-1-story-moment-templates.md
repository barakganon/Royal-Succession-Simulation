# Story 10-1: Story-Moment Template Library + Trigger

Status: done

## Story

The data foundation for branching narrative vignettes ("story moments"): a pure module of ≥8 templates — each with preconditions, 2–3 mechanical choices, and per-choice effects — plus a weighted trigger that, given a snapshot of dynasty state, occasionally returns a fitting template (≈5% base, nudged by state). **10-1 is data + the pure trigger only** — the turn interrupt + modal UI is Story 10-2; the effect applicator + chronicle + cooldown is Story 10-3. No turn_processor / template / DB changes here.

## Acceptance Criteria

1. **AC1 — Template library (NEW `models/story_moments.py`).** A module-level `STORY_MOMENT_TEMPLATES: list[dict]` with **≥8** templates. Named keys to include (from the plan): `forbidden_love`, `council_whispers`, `dueling_lords`, `bonds_of_kin`, `fading_heir`, `letter_from_east`, plus 2+ more (e.g. `peasant_petition`, `pious_pilgrim`). Each template is a dict with EXACTLY these keys:
   - `key: str` (unique slug), `title: str`, `summary: str` (one-line, used for fallback prose),
   - `preconditions: dict` — simple, declarative constraints checked against `dynasty_state` (see AC3 for the matcher + supported keys; e.g. `{"min_prestige": 50}`, `{"at_war": True}`, `{"monarch_has_trait": "Brave"}`, `{"has_living_heir": True}`),
   - `weight: float` (relative likelihood once eligible; default 1.0),
   - `mechanical_choices: list[dict]` of **2–3** choices, each `{"key": str, "label": str, "description": str, "effects": dict}`. The `effects` dict uses a small declarative vocabulary (applied in 10-3, but DEFINED here): any of `prestige_delta:int`, `wealth_delta:int`, `add_trait_to_monarch:str`, `relation_delta:{"target":"...","amount":int}`, `infamy_delta:int`, `exile_person:bool`, plus a free-form `chronicle_note:str`. (10-1 only declares them; 10-3 applies.)
   - No two templates share a `key`; every template has 2–3 choices; every choice has a unique `key` within its template. Keep content medieval/dynastic and concise.

2. **AC2 — `maybe_trigger_story_moment` (same module).** `maybe_trigger_story_moment(dynasty_state: dict, rng=None) -> dict | None`:
   - Filter `STORY_MOMENT_TEMPLATES` to those whose `preconditions` all match `dynasty_state` (AC3 matcher).
   - With a **base 5%** chance (constant `BASE_TRIGGER_CHANCE = 0.05`) decide whether a moment fires at all; if it does, pick one eligible template weighted by `weight` (× optional state weighting — keep simple: just `weight`). Return the chosen template dict, else `None`.
   - `rng` defaults to the module `random`; accept an injected `random.Random` for deterministic tests. Never raises (bad/empty state → returns None). No eligible templates → None.
   - Also expose `eligible_templates(dynasty_state: dict) -> list[dict]` (the filtered list, no probability) for testing/10-2.

3. **AC3 — Precondition matcher.** A pure helper `_matches(preconditions: dict, dynasty_state: dict) -> bool` supporting at least: `min_prestige`/`max_prestige` (int vs `dynasty_state['prestige']`), `min_wealth`/`max_wealth` (vs `wealth`), `at_war` (bool vs `at_war`), `has_living_heir` (bool vs `has_living_heir`), `monarch_has_trait` (str in `dynasty_state['monarch_traits']`), `monarch_lacks_trait` (str NOT in monarch_traits), `min_year`/`max_year` (vs `year`). An empty `preconditions` → always matches. Unknown precondition keys are ignored (forward-compatible) — or treated as non-matching; pick **ignore-unknown** and document it. Missing `dynasty_state` keys → that precondition fails safe (no match) without raising.
   - **`dynasty_state` shape (the contract 10-2 will populate):** `{prestige:int, wealth:int, infamy:int, at_war:bool, has_living_heir:bool, heir_age:int|None, monarch_traits:list[str], year:int, relations:dict[str,int]}` (extra keys allowed/ignored). Document this dict at the top of the module.

4. **AC4 — Purity / no regressions.** `models/story_moments.py` is a **pure module** — no Flask/DB/genai/`current_app` imports (it operates on a plain `dynasty_state` dict and returns plain dicts). No `print()`; `logger = logging.getLogger('royal_succession.story_moments')` allowed but not required. Full suite green vs baseline **482 passed** (new tests additive). No new pip deps. Do NOT touch turn_processor, templates, or db_models.

5. **AC5 — Tests (NEW `tests/unit/test_story_moments.py`) — ≥8.**
   - `STORY_MOMENT_TEMPLATES` has ≥8 entries; all `key`s unique; each has a `title`, `summary`, `preconditions` (dict), `weight`, and 2–3 `mechanical_choices`; each choice has unique `key`, `label`, `description`, `effects` (dict). The named templates (`forbidden_love`, `council_whispers`, `dueling_lords`, `bonds_of_kin`, `fading_heir`, `letter_from_east`) are present.
   - `_matches`: empty preconditions matches anything; `min_prestige`/`at_war`/`monarch_has_trait`/`has_living_heir` each match & fail correctly; missing state key fails-safe (no raise); unknown precondition key is ignored (documented behavior).
   - `eligible_templates` returns only templates whose preconditions pass for a given state (construct a state that includes some and excludes others).
   - `maybe_trigger_story_moment`: with a seeded `random.Random` that forces the 5% roll to "fire", returns an eligible template (deterministic with the seed); with a roll that doesn't fire → None; with no eligible templates → None; never raises on `{}` / missing keys.
   - Determinism: same `dynasty_state` + same seeded rng → same template.

## Tasks / Subtasks
- [ ] Task 1 — `models/story_moments.py` (templates + matcher + trigger). [Agent A]
- [ ] Task 2 — `tests/unit/test_story_moments.py`. [Agent B]

## Dev Notes

### Multi-agent split (2 worktree agents + integrator) — ZERO file overlap
- **Agent A** — NEW `models/story_moments.py` ONLY.
- **Agent B** — NEW `tests/unit/test_story_moments.py` ONLY (CONTRACT below is authoritative; A's module absent in B's worktree).
- No shared files.

### FROZEN INTERFACE CONTRACT (authoritative)
- `STORY_MOMENT_TEMPLATES: list[dict]` — each: `{key, title, summary, preconditions: dict, weight: float, mechanical_choices: list[{key,label,description,effects:dict}]}` (2–3 choices). Includes the 6 named keys + ≥2 more (≥8 total).
- `BASE_TRIGGER_CHANCE = 0.05`.
- `maybe_trigger_story_moment(dynasty_state: dict, rng=None) -> dict | None` — eligible-filter → 5% gate → weighted pick; None otherwise; never raises; `rng` injectable (`random.Random`).
- `eligible_templates(dynasty_state: dict) -> list[dict]`.
- `_matches(preconditions: dict, dynasty_state: dict) -> bool` — supports min/max_prestige, min/max_wealth, at_war, has_living_heir, monarch_has_trait, monarch_lacks_trait, min/max_year; empty→True; unknown keys ignored; missing state keys fail-safe (no raise).
- `dynasty_state` shape: `{prestige, wealth, infamy, at_war, has_living_heir, heir_age, monarch_traits, year, relations}` (extra keys ignored).
- Effects vocabulary (declared in templates, APPLIED in 10-3): `prestige_delta, wealth_delta, add_trait_to_monarch, relation_delta:{target,amount}, infamy_delta, exile_person, chronicle_note`.

### Reuse / project rules
- Pure module — mirror the style of `models/trait_effects.py` (pure data + functions, no Flask/DB). Traits referenced should be real ones from the trait system (Brave, Craven, Cunning, Wroth, Patient, Pious, Greedy, Sickly — see `models/trait_effects.py` `TRAIT_MODIFIERS`). No new deps. Determinism via injectable `rng` (the suite seeds global `random` per-test, but injecting is cleaner — see the test-isolation memory).

### Out of scope / deferred
- The `story_moment` turn interrupt + full-screen modal (`templates/story_moment.html`) + LLM prose builder → **Story 10-2**. The effect applicator (mutating dynasty state per chosen choice) + chronicle entry per choice + 5-turn cooldown → **Story 10-3**. 10-1 only defines the data + the pure trigger.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool; "EXECUTE NOW, no plan mode"; write only inside the worktree root; contract inlined. Integrator: run the full suite before merge; signature drift bit 7-1/7-2 — frozen names above authoritative.
- Baseline **482 passed** (Epics 7+8+9 complete). Tests: isolated temp DB; `python -m pytest -p no:randomly -q`. Pure-module story → no app/visual check; unit tests are the contract. Inject `random.Random(seed)` for deterministic trigger tests rather than relying on the global-seed autouse fixture.
- Depends conceptually on Epic 6 (traits) + Epic 9 (LLM) but 10-1 itself is standalone data; the LLM prose + interrupt come in 10-2.

## References
- Pure-data/function module to mirror: `models/trait_effects.py` (`TRAIT_MODIFIERS`, pure helpers). Trait names: same file. Interrupt pattern (for 10-2 context): `models/turn_processor.py` interrupt loop (`INTERRUPT_REASONS`, ~line 40). DynastyDB fields for the future state map: `prestige`, `current_wealth`, `infamy`, monarch via PersonDB `is_monarch`+`get_traits()`.

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 2 worktree sub-agents via the Workflow tool + main-session integrator.
### Completion Notes List
- _pending_
### File List
- `models/story_moments.py` — NEW (templates + matcher + trigger)
- `tests/unit/test_story_moments.py` — NEW
- `_bmad-output/implementation-artifacts/{10-1-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(10-1); ready-for-dev; 2 worktree agents via Workflow; pure template library + trigger |
