# Story 10-2: Story-Moment Interrupt + Choice Modal

Status: ready-for-dev

## Story

Wire the Story 10-1 template library into the turn loop: on a human dynasty's turn, occasionally a story moment **interrupts** the turn; the player sees a full-screen modal with LLM-narrated prose and 2–3 choice cards, picks one, and the turn resolves. **10-2 delivers the interrupt + prose + modal + a choice route that records & dismisses the moment** (writes a chronicle/history line). **Mechanical effect application + 5-turn cooldown is Story 10-3** — so after 10-2, choosing dismisses cleanly with a narrative note but does not yet mutate prestige/traits/etc.

## Acceptance Criteria

1. **AC1 — `story_moment` interrupt (`models/turn_processor.py`).** Add `'story_moment'` to `INTERRUPT_REASONS` (~line 39). In the per-year loop, AFTER the existing detections (monarch_death → civil_war → heir_majority) and only when `interrupt is None` AND `not dynasty.is_ai_controlled`: build a `dynasty_state` dict (see AC2) and call `story_moments.maybe_trigger_story_moment(dynasty_state)`. If it returns a template, set `interrupt = ('story_moment', current_year)`, stash the chosen template (e.g. local `triggered_moment = template`), and `break` the per-person loop / halt like the other human interrupts. Lazy-import `from models import story_moments`. Story moments fire ONLY for human dynasties (AI never interrupts — mirrors civil_war/heir_majority). No cooldown yet (10-3).

2. **AC2 — `dynasty_state` builder + prose into `turn_summary` (`models/turn_processor.py`).** Build the state dict the 10-1 matcher expects: `{prestige: dynasty.prestige or 0, wealth: dynasty.current_wealth or 0, infamy: getattr(dynasty,'infamy',0) or 0, at_war: <any active War for this dynasty>, has_living_heir: <a living non-monarch noble exists>, heir_age: <or None>, monarch_traits: <current monarch get_traits() or []>, year: current_year, relations: {}}`. When the interrupt is `story_moment`, add to `turn_summary` a `story_moment` dict: `{ 'key': template['key'], 'title': template['title'], 'prose': <narrated>, 'choices': [ {'key':c['key'],'label':c['label'],'description':c['description']} for c in template['mechanical_choices'] ] }`. `prose` = `narrate_event(build_story_moment_prompt(template['title'], template['summary'], monarch_name, monarch_traits, recent_event_texts, current_year), generate_story_moment_fallback(template['title'], template['summary'], current_year), max_tokens=200)` (guarded; fallback when LLM off). Lazy-import `narrate_event` + the new builders. Other interrupts' summaries unchanged.

3. **AC3 — Prose prompt + fallback (`utils/llm_prompts.py`).** `build_story_moment_prompt(title, summary, monarch_name, monarch_traits, recent_events, year) -> str` (≤200 tok; second-person, medieval, sets up the dilemma described by `summary`, references the monarch + traits; does NOT enumerate the choices — those are shown as cards) and `generate_story_moment_fallback(title, summary, year) -> str` (deterministic, non-empty, names the title + year, uses `summary`). Mirror the existing builder/fallback house style; handle empty/None traits.

4. **AC4 — Modal (NEW `templates/story_moment.html`) + wiring (`templates/world_map.html`).**
   - `templates/story_moment.html`: a `hidden` full-screen modal `id="story-moment-modal"` (mirror the `succession-modal`/`civil-war-modal` markup + classes) with `id="story-moment-title"`, a prose paragraph `id="story-moment-prose"`, and a choices container `id="story-moment-choices"` (cards injected by JS). Role=dialog. No inline data — JS populates from the turn summary.
   - `templates/world_map.html`: `{% include 'story_moment.html' %}` near the other modals; in the turn-result JS dispatch (~line 521-551, where `reason === 'civil_war'` etc.), add `if (reason === 'story_moment') { _restoreEndTurnBtn(); openStoryMomentModal(summary.story_moment); return; }`. Implement `openStoryMomentModal(sm)`: set title + prose, render one button per `sm.choices` (each with `data-choice-key` + `data-template-key=sm.key`), wire each to POST JSON `{template: sm.key, choice: <choice key>}` to `url_for('dynasty.story_moment_choice', dynasty_id=...)`, then on success `window.location.reload()` (or redirect to the turn report). Match the medieval modal styling already used.

5. **AC5 — Choice route (`blueprints/dynasty.py`).** `@dynasty_bp.route('/dynasty/<int:dynasty_id>/story_moment_choice', methods=['POST'])` → `story_moment_choice(dynasty_id)`, `@login_required` (+ `@block_if_turn_processing` like the other resolve routes), ownership-guarded (403 JSON if not owner). Read `template` + `choice` from JSON/form. Validate the template key exists in `STORY_MOMENT_TEMPLATES` and the choice key exists in that template's `mechanical_choices` (else `{"ok": False, "message": ...}`, 400). **10-2 behavior:** record a `HistoryLogEntryDB(dynasty_id, year=current, event_type='story_moment', event_string=<the chosen choice's description or chronicle_note>)` and return `{"ok": True, "message": <chosen choice label>}`. **Do NOT apply mechanical effects yet** (10-3). try/except + rollback.

6. **AC6 — No regressions / safety.** Full suite green vs baseline **509 passed**. With LLM off (tests), the story_moment interrupt still fires (prose = fallback) — but note: turn-processing tests that assume a `quiet_period`/specific interrupt could now occasionally see `story_moment`. To keep them deterministic, story-moment-driving tests inject a forced trigger; and the trigger uses the global `random` (5% — seeded per-test via the autouse fixture) so most existing tests won't flip. **If any existing turn test becomes flaky/failing because a story moment fired, gate it**: those tests should `patch('models.turn_processor.story_moments.maybe_trigger_story_moment', return_value=None)` (document why). The integrator must run the full suite and apply this patch to any test that flips. No new deps.

7. **AC7 — Tests (NEW files only) — ≥6.**
   - Prose unit (`tests/unit/test_story_moment_prompt.py`): `build_story_moment_prompt(...)` contains the title + monarch name; `generate_story_moment_fallback('A Forbidden Love','...',1300)` is non-empty + contains the title + '1300'.
   - Interrupt integration (`tests/integration/test_story_moment_interrupt.py`): with `maybe_trigger_story_moment` patched to return a known template, `process_dynasty_turn` for a human dynasty halts with `interrupt_reason == 'story_moment'` and `turn_summary['story_moment']` has `key/title/prose/choices` (choices length 2–3, prose non-empty = fallback). With `maybe_trigger_story_moment` patched to `None`, no story_moment interrupt. An AI-controlled dynasty NEVER gets a story_moment interrupt (patch trigger to a template, assert it doesn't fire for AI).
   - Route (`tests/integration/test_story_moment_choice.py`): POST a valid `{template, choice}` to `story_moment_choice` (owner) → 200 `ok True`, a `story_moment` HistoryLogEntryDB written; invalid template/choice → 400 `ok False`; non-owner → 403. (No mechanical effect assertions — that's 10-3.)
   - world_map.html contains `story-moment-modal` + `openStoryMomentModal` + the `story_moment` dispatch branch.

## Tasks / Subtasks
- [ ] Task 1 — Interrupt + dynasty_state + prose-into-summary (turn_processor) + prose builder/fallback (llm_prompts). [Agent A]
- [ ] Task 2 — `story_moment_choice` route (record+dismiss; effects in 10-3). [Agent B]
- [ ] Task 3 — `story_moment.html` modal + world_map.html include/JS. [Agent C]
- [ ] Task 4 — Tests. [Agent D]

## Dev Notes

### Multi-agent split (4 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `models/turn_processor.py` (interrupt + state + summary) + `utils/llm_prompts.py` (prose builder + fallback). Lazy-import `story_moments`/`narrate_event`.
- **Agent B** — `blueprints/dynasty.py` (`story_moment_choice` route only). Lazy-import `STORY_MOMENT_TEMPLATES` from `models.story_moments`.
- **Agent C** — NEW `templates/story_moment.html` + `templates/world_map.html` (include + JS).
- **Agent D** — NEW test files only.
- No shared files.

### FROZEN INTERFACE CONTRACT (authoritative)
- `INTERRUPT_REASONS` gains `'story_moment'`. Fires only for human dynasties, lowest priority, no cooldown (10-3 adds it).
- `turn_summary['story_moment'] = {key, title, prose, choices:[{key,label,description}]}` when interrupted.
- `build_story_moment_prompt(title, summary, monarch_name, monarch_traits, recent_events, year) -> str`; `generate_story_moment_fallback(title, summary, year) -> str`.
- Route `dynasty.story_moment_choice` POST `/dynasty/<id>/story_moment_choice`, body `{template, choice}` → `{ok, message}`; validates against `STORY_MOMENT_TEMPLATES`; writes a `story_moment` HistoryLogEntryDB; **no mechanical effects in 10-2**.
- DOM: modal `id="story-moment-modal"`, `story-moment-title`, `story-moment-prose`, `story-moment-choices`; JS `openStoryMomentModal(sm)`; dispatch branch on `reason === 'story_moment'`.
- 10-1 (frozen): `models.story_moments.maybe_trigger_story_moment(dynasty_state, rng=None)`, `STORY_MOMENT_TEMPLATES`, template/choice/effects shape.

### Reuse / project rules
- Mirror interrupt detections + halt at `models/turn_processor.py:199-235`; turn_summary build `:345-362`. Modal markup + JS dispatch: `templates/world_map.html:341-380` (modals), `:516-551` (dispatch), `:699-770` (civil-war modal JS to mirror). Choice route pattern: `blueprints/dynasty.py:1355` (`civil_war_resolve`) — `@block_if_turn_processing`, ownership 403, JSON `{ok,message}`. `narrate_event`: `utils/llm_narration.py`. Builders live only in `utils/llm_prompts.py`. War check: query active `War` for the dynasty. `@login_required`; flash categories; no `print()`; SVG/prose via `| safe` only where needed (prose is plain text — escape in JS via textContent).

### Out of scope / deferred
- **Mechanical effect application** (prestige/wealth/trait/relation/exile per the chosen choice's `effects`) + the richer per-choice chronicle prose + **5-turn cooldown** between story moments → **Story 10-3** (will enhance `story_moment_choice` + add a cooldown gate to the trigger call). 10-2 only displays the moment and records the choice.

## Previous Story Intelligence
- Worktree contract-first via the Workflow tool; "EXECUTE NOW, no plan mode"; write only inside the worktree root; contract inlined. Integrator: verify where edits landed; **run the full suite — the new interrupt can make turn tests that assumed quiet_period flip to story_moment; patch `maybe_trigger_story_moment`→None in any such test** (5% × seeded global random — most won't flip, but check). Signature drift bit 7-1/7-2 — frozen names authoritative. UI story → **run-the-app visual check** at integration (advance a turn until a moment fires, or temporarily force the trigger, and confirm the modal renders prose + choice cards and a choice dismisses).
- Baseline **509 passed** (Epics 7+8+9 + 10-1 done). Tests: temp DB; `python -m pytest -p no:randomly -q`. 10-1 merged `885958c`.

## References
- 10-1: `models/story_moments.py` (`maybe_trigger_story_moment`, `STORY_MOMENT_TEMPLATES`). Interrupts: `models/turn_processor.py:39` (`INTERRUPT_REASONS`), `:199-262` (detections + quiet fallback), `:345-364` (summary). advance_turn JSON: `blueprints/dynasty.py:445-464`. Modal+JS: `templates/world_map.html:341-380,516-551,699-770`. Resolve route: `blueprints/dynasty.py:1355`. narrate_event: `utils/llm_narration.py`. Prompt builders: `utils/llm_prompts.py`.

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 4 worktree sub-agents via the Workflow tool + main-session integrator.
### Completion Notes List
- _pending_
### File List
- `models/turn_processor.py` — MODIFIED (story_moment interrupt + state + summary)
- `utils/llm_prompts.py` — MODIFIED (prose builder + fallback)
- `blueprints/dynasty.py` — MODIFIED (story_moment_choice route)
- `templates/story_moment.html` — NEW (modal)
- `templates/world_map.html` — MODIFIED (include + JS)
- `tests/unit/test_story_moment_prompt.py`, `tests/integration/test_story_moment_interrupt.py`, `tests/integration/test_story_moment_choice.py` — NEW
- `_bmad-output/implementation-artifacts/{10-2-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED
### Change Log
| Date | Change |
|---|---|
| 2026-05-31 | spec(10-2); ready-for-dev; 4 worktree agents; interrupt+prose+modal (effects/cooldown → 10-3) |
