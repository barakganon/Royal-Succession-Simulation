# Story 10-3: Story-Moment Effect Applicator + Cooldown

Status: done

## Story

Make story-moment choices *matter*: when the player picks a choice, apply its declared `effects` to dynasty state (prestige / wealth / infamy / a new monarch trait), record the outcome in the chronicle, and enforce a **cooldown** so story moments don't fire every turn. This completes the Epic-10 loop (10-1 templates → 10-2 interrupt+modal → 10-3 consequences).

## Acceptance Criteria

1. **AC1 — Effect applicator (`blueprints/dynasty.py`, in `story_moment_choice`).** After 10-2's validation (template+choice found) and BEFORE/with the existing `story_moment` HistoryLogEntryDB write, apply the chosen choice's `effects` dict to the dynasty via a helper `_apply_story_moment_effects(dynasty, effects: dict) -> None` (module-level in `blueprints/dynasty.py`). Supported effects (the real vocabulary used by the 10-1 templates):
   - `prestige_delta: int` → `dynasty.prestige = max(0, (dynasty.prestige or 0) + delta)`
   - `wealth_delta: int` → `dynasty.current_wealth = max(0, (dynasty.current_wealth or 0) + delta)`
   - `infamy_delta: int` → `dynasty.infamy = max(0, (dynasty.infamy or 0) + delta)`
   - `add_trait_to_monarch: str` → find the living monarch (`PersonDB.query.filter_by(dynasty_id=dynasty.id, is_monarch=True, death_year=None).first()`); if found and the trait isn't already present, `traits = monarch.get_traits(); traits.append(trait); monarch.set_traits(traits)`.
   - `chronicle_note: str` → already used as the `event_string` (10-2) — keep that behavior (prefer `chronicle_note` over the choice `description` for the logged text).
   - `exile_person: bool` and `relation_delta: {target, amount}` → **narrative-only for now** (no concrete person/dynasty is bound to a generic vignette): do NOT mutate state for these; they remain conveyed via the chronicle note. Document this explicitly in the helper (a future story can bind persons/dynasties to moments). Unknown effect keys are ignored (forward-compatible).
   - Each effect applied defensively (guard None/missing); a single bad effect must not abort the others or the route. The route still returns `{"ok": True, "message": <choice label>}` and commits once.

2. **AC2 — Chronicle outcome entry.** The `story_moment` `HistoryLogEntryDB` (written in 10-2) stands as the chronicle record of the choice (event_type `story_moment`, text = `chronicle_note` or the choice description). 10-3 keeps exactly one such entry per resolved choice (no duplicates). (Optional: prepend the choice label — keep it simple; the existing entry suffices.)

3. **AC3 — Cooldown (`models/turn_processor.py`).** Add `STORY_MOMENT_COOLDOWN_YEARS = 25` (≈5 turns at 5 years/turn). Before calling `maybe_trigger_story_moment` in the turn loop (the 10-2 gate), check the dynasty's most recent resolved story moment: query the latest `HistoryLogEntryDB` for this dynasty with `event_type == 'story_moment'`; if one exists and `current_year - that_entry.year < STORY_MOMENT_COOLDOWN_YEARS`, **skip** triggering (no story moment this turn). Otherwise proceed as in 10-2. Keep it cheap (one ordered-limit-1 query); guard exceptions (on error, just proceed without cooldown). This prevents back-to-back story moments.

4. **AC4 — No regressions.** Full suite green vs baseline **530 passed**. The 10-2 suppression fixtures in `test_game_loop.py` / `test_game_flow.py` still apply (story moments stay off in those mechanics tests). With LLM off, effect application is deterministic. No new pip deps. No schema change (cooldown derives from existing HistoryLogEntryDB rows — no new column).

5. **AC5 — Tests (NEW `tests/integration/test_story_moment_effects.py`) — ≥6.**
   - `_apply_story_moment_effects` / the route applies `prestige_delta` (assert dynasty.prestige changed by the delta, clamped ≥0), `wealth_delta`, `infamy_delta`.
   - `add_trait_to_monarch` adds the trait to the living monarch's `get_traits()` (and is idempotent — applying twice doesn't duplicate).
   - POST a real `{template, choice}` (pick a template+choice whose effects include a `prestige_delta`) to `story_moment_choice` (owner) → 200, the dynasty's prestige reflects the delta AND exactly one `story_moment` HistoryLogEntryDB exists for that choice.
   - `exile_person` / `relation_delta` choices apply WITHOUT error and do NOT crash (narrative-only) — the route still returns ok.
   - Cooldown: with a recent `story_moment` HistoryLogEntryDB (year within `STORY_MOMENT_COOLDOWN_YEARS` of the turn) AND `maybe_trigger_story_moment` patched to return a template, `process_dynasty_turn` does NOT fire a `story_moment` interrupt (cooldown suppresses it); with the entry far in the past (or none), it fires. (Patch the trigger to a template so only the cooldown gate decides.)

## Tasks / Subtasks
- [ ] Task 1 — Cooldown gate + `STORY_MOMENT_COOLDOWN_YEARS` (turn_processor). [Agent A]
- [ ] Task 2 — `_apply_story_moment_effects` + wire into `story_moment_choice` (blueprints/dynasty). [Agent B]
- [ ] Task 3 — Tests. [Agent C]

## Dev Notes

### Multi-agent split (3 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `models/turn_processor.py` ONLY (cooldown constant + gate around the existing `maybe_trigger_story_moment` call).
- **Agent B** — `blueprints/dynasty.py` ONLY (`_apply_story_moment_effects` helper + call it in `story_moment_choice` before the commit).
- **Agent C** — NEW `tests/integration/test_story_moment_effects.py` ONLY.
- No shared files.

### FROZEN INTERFACE CONTRACT (authoritative)
- `models/turn_processor.py`: `STORY_MOMENT_COOLDOWN_YEARS = 25`; the trigger gate skips `maybe_trigger_story_moment` when the latest `event_type='story_moment'` HistoryLogEntryDB for the dynasty has `year > current_year - STORY_MOMENT_COOLDOWN_YEARS`.
- `blueprints/dynasty.py`: `_apply_story_moment_effects(dynasty, effects: dict) -> None` applies prestige_delta/wealth_delta/infamy_delta (clamped ≥0) + add_trait_to_monarch (idempotent, living monarch); exile_person/relation_delta are narrative-only no-ops; unknown keys ignored; never raises. `story_moment_choice` calls it on the chosen choice's `effects`, keeps the single `story_moment` HistoryLogEntryDB, commits once, returns `{ok, message}`.
- 10-1/10-2 frozen: `STORY_MOMENT_TEMPLATES` (effects vocabulary: prestige_delta, wealth_delta, infamy_delta, add_trait_to_monarch, chronicle_note, exile_person, relation_delta); `story_moment_choice` route; `maybe_trigger_story_moment`.

### Reuse / project rules
- DynastyDB has `prestige`, `current_wealth`, `infamy` (game_manager uses `dynasty.infamy += 10`). Living monarch: `PersonDB.query.filter_by(dynasty_id=…, is_monarch=True, death_year=None).first()`; traits via `get_traits()`/`set_traits()`. Trait names: `models/trait_effects.py`. The 10-2 route + cooldown gate are the integration points (read them first). DB writes try/except + rollback; `@login_required` preserved; no `print()`. No schema change.
- Cooldown query: `HistoryLogEntryDB.query.filter_by(dynasty_id=dynasty.id, event_type='story_moment').order_by(HistoryLogEntryDB.year.desc()).first()` (or `.recorded_at`). Inside `process_dynasty_turn` the dynasty + current_year are in scope at the trigger site.

### Out of scope / deferred
- Binding concrete persons/dynasties to vignettes so `exile_person` / `relation_delta` mutate real state → future story. Tuning `BASE_TRIGGER_CHANCE`/cooldown/weights. Epic-10 retrospective (optional) after 10-3.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool; "EXECUTE NOW, no plan mode"; write only inside the worktree root; contract inlined. Integrator: run the full suite (the 10-2 suppression fixtures keep mechanics tests deterministic; the new cooldown test patches the trigger to isolate the gate). Signature drift bit 7-1/7-2 — frozen names authoritative.
- Baseline **530 passed** (Epics 7+8+9 + 10-1 + 10-2 done). Tests: temp DB; `python -m pytest -p no:randomly -q`. Backend-only (effects + cooldown) → no run-the-app check needed; the integration tests are the contract. 10-2 merged `815b71f`.
- The 10-2 `story_moment_choice` route currently records+dismisses; 10-3 adds effect application to it. The 10-2 turn_processor trigger has no cooldown; 10-3 adds the gate.

## References
- 10-2 route: `blueprints/dynasty.py` `story_moment_choice` (search it). Trigger gate: `models/turn_processor.py` (the `maybe_trigger_story_moment` call added in 10-2, after heir_majority detection). Templates/effects: `models/story_moments.py`. Trait names: `models/trait_effects.py`. DynastyDB fields: `models/db_models.py` (prestige/current_wealth/infamy). HistoryLogEntryDB: `models/db_models.py:288`.

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 3 worktree sub-agents via the Workflow tool + main-session integrator.
### Completion Notes List
- _pending_
### File List
- `models/turn_processor.py` — MODIFIED (cooldown gate + constant)
- `blueprints/dynasty.py` — MODIFIED (`_apply_story_moment_effects` + wire into route)
- `tests/integration/test_story_moment_effects.py` — NEW
- `_bmad-output/implementation-artifacts/{10-3-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(10-3); ready-for-dev; 3 worktree agents; effect applicator + 25-year (≈5-turn) cooldown; exile/relation narrative-only |
