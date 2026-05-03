# Story 1-3: Turn Report Interrupt UI

Status: review

## Story

As a player,
I want the turn report to tell me WHY the turn ended and HOW MANY years passed,
so that I can immediately understand whether the world changed because of a crisis, a completion, or a peaceful span of time — rather than seeing a generic "Years 1300–1305" heading with no context.

## Acceptance Criteria

1. **AC1 — Interrupt banner is displayed.** `turn_report.html` renders a prominent banner immediately below the header `<hr>` that conveys the interrupt reason in plain language (e.g., "Your monarch has died" / "Five quiet years have passed"). The banner is always visible, never hidden.

2. **AC2 — Years-passed pill is displayed.** The stat row includes a "Years Passed" tile that reads `summary.years_advanced` (e.g., "1" or "5"). The tile replaces or supplements an existing stat so total stat tiles remain 4.

3. **AC3 — Four interrupt classes are visually distinct.**

   | `interrupt_reason` value | Visual style | Banner text |
   |---|---|---|
   | `monarch_death` | Red background, skull icon | "Your monarch has died — a new reign begins" |
   | `project_complete` | Green background, check icon | "A great work has been completed" |
   | `war_declared` or `attack_received` | Orange background, sword icon | "War has come to your realm" |
   | `quiet_period` (default) | Muted / blue-grey, dove icon | "N quiet year(s) passed without incident" |

4. **AC4 — Missing `interrupt_reason` handled gracefully.** The template uses `summary.interrupt_reason | default('quiet_period')` so it renders correctly even if the key is absent (e.g., old sessions without the new key).

5. **AC5 — Header years reflect actual years.** The existing `"The Years {{ summary.start_year }} — {{ summary.end_year }}"` line already uses the correct keys; verify it still renders correctly after the new blocks are added (no regression).

6. **AC6 — Existing tests still pass.** `test_advance_turn_shows_flash` checks for `b'Chronicles'` in the HTTP response — this must still pass. 211 tests pass, 0 fail.

7. **AC7 — No Python or route changes.** The story is template-only. No changes to `models/turn_processor.py`, `blueprints/dynasty.py`, or any test files.

## Tasks / Subtasks

- [x] Task 1: Add interrupt banner block to `templates/turn_report.html` (AC1, AC3, AC4)
  - [x] Place it immediately after the `<hr class="section-divider">` inside the header `<div>`, before the stat row
  - [x] Use a `{% set %}` block to derive banner text, CSS class, and icon from `summary.interrupt_reason | default('quiet_period')`
  - [x] Four branches: `monarch_death`, `project_complete`, `war_declared`/`attack_received` (share one branch), `quiet_period`

- [x] Task 2: Update stat row to show "Years Passed" (AC2)
  - [x] Replace the fourth stat tile (currently "Current Year") with a "Years Passed" tile showing `summary.years_advanced | default(5)`
  - [x] Keep the other three tiles unchanged: Events This Turn, Living Members, Treasury

- [x] Task 3: Verify header years (AC5)
  - [x] Confirm `summary.start_year` and `summary.end_year` are present and render correctly
  - [x] No change to the line itself — just confirm no regression after new blocks

- [x] Task 4: Run `pytest` — confirm 212 passed, 0 failed (AC6, AC7)

- [x] Task 5: Create feature branch, commit, push, update STATUS.md

## Dev Notes

### Primary file: `templates/turn_report.html`

This is the ONLY file that changes. No Python, route, or test modifications.

### Current state of `turn_report.html`

The file is 199 lines. Key sections:

**Header block (lines 8–19):** Renders dynasty coat of arms, `<h1>` title, and the subtitle `"The Years {{ summary.start_year }} — {{ summary.end_year }}"` followed by `<hr class="section-divider">`. No interrupt mention.

**Stat row (lines 22–47):** Four `turn-report-stat` tiles:
1. `summary.events | length` — "Events This Turn"
2. `summary.living_count` — "Living Members"
3. `summary.current_wealth` — "Treasury (Gold)"
4. `dynasty.current_simulation_year` — "Current Year"

**Chronicle card (lines 50–104):** Left column, event list with per-type icons and colors. Already has good `{% if t == 'death' %}` branching.

**World News card (lines 106–150):** Right column, AI dynasty events.

**Event breakdown legend (lines 153–183):** Deaths/births/marriages count, shown only if any present.

**Actions (lines 186–195):** "Continue to Dynasty" and "Dashboard" buttons.

### `turn_summary` keys available from Story 1-2

As confirmed by `models/turn_processor.py` lines 233–249 and the Story 1-2 completion notes:

```python
turn_summary = {
    'start_year': int,           # e.g. 1300
    'end_year': int,             # dynasty.current_simulation_year after loop — actual end year
    'years_advanced': int,       # 1–5, actual years processed (not always 5)
    'interrupt_reason': str,     # one of INTERRUPT_REASONS — always present
    'events': list[dict],        # each: {'type': str, 'year': int, 'text': str}
    'living_count': int,
    'current_wealth': int,
    'new_story_paragraph': str,
}
```

All keys are populated by `process_dynasty_turn`. Use `| default(...)` for defensive rendering only.

### Interrupt class → visual style mapping

```jinja2
{% set reason = summary.interrupt_reason | default('quiet_period') %}
{% if reason == 'monarch_death' %}
    {% set banner_class = 'alert-danger' %}
    {% set banner_icon = '&#9760;' %}
    {% set banner_text = 'Your monarch has died — a new reign begins' %}
{% elif reason == 'project_complete' %}
    {% set banner_class = 'alert-success' %}
    {% set banner_icon = '&#10003;' %}
    {% set banner_text = 'A great work has been completed' %}
{% elif reason == 'war_declared' or reason == 'attack_received' %}
    {% set banner_class = 'alert-warning' %}
    {% set banner_icon = '&#9876;' %}
    {% set banner_text = 'War has come to your realm' %}
{% else %}
    {% set banner_class = 'alert-secondary' %}
    {% set banner_icon = '&#128375;' %}
    {% set banner_text = (summary.years_advanced | default(5)) ~ ' quiet year' ~ ('s' if (summary.years_advanced | default(5)) != 1 else '') ~ ' passed without incident' %}
{% endif %}
```

Then render the banner:

```html
<div class="alert {{ banner_class }} text-center mb-3" role="alert"
     style="font-family:'Cinzel',serif;font-size:1.05rem;border-radius:6px;">
  <span style="font-size:1.3rem;margin-right:.5rem;">{{ banner_icon | safe }}</span>
  {{ banner_text }}
</div>
```

The `alert-*` classes are Bootstrap 4 utility classes already present in the project's base theme. They provide the colored background and border without custom CSS.

### Stat row change: replace tile 4

**Current tile 4 (lines 43–47):**
```html
<div class="col-6 col-md-3">
  <div class="turn-report-stat">
    <div class="turn-stat-value">{{ dynasty.current_simulation_year }}</div>
    <div class="turn-stat-label">Current Year</div>
  </div>
</div>
```

**Target tile 4:**
```html
<div class="col-6 col-md-3">
  <div class="turn-report-stat">
    <div class="turn-stat-value">{{ summary.years_advanced | default(5) }}</div>
    <div class="turn-stat-label">Years Passed</div>
  </div>
</div>
```

Rationale: "Current Year" is redundant — it already appears in the header subtitle `"The Years {{ summary.start_year }} — {{ summary.end_year }}"`. "Years Passed" directly communicates the variable-turn information and is the more interesting stat after the Story 1-2 engine change.

### Where to insert the banner in the template

Insert between line 18 (`<hr class="section-divider">`) and line 21 (`</div>` that closes the header block):

```html
  <hr class="section-divider">

  {# ── Interrupt banner ── #}
  {% set reason = summary.interrupt_reason | default('quiet_period') %}
  ... (set block for banner_class / banner_icon / banner_text) ...
  <div class="alert {{ banner_class }} text-center mb-3" role="alert" ...>
    ...
  </div>

</div><!-- end header div -->
```

### `project_complete` stub handling

`project_complete` is a valid `INTERRUPT_REASONS` value (Sprint 2 will wire it), but no logic fires it yet. The template handles it with the green success banner. If it does appear in a session (e.g., from a future sprint), it will display gracefully. If it never appears in the current sprint, the code is dead but harmless.

### Test impact analysis

The only test that exercises the turn report template directly is `test_advance_turn_shows_flash` in `tests/integration/test_game_loop.py`, which checks `b'Chronicles'` appears in the response. The word "Chronicles" comes from the `<h1>` in the header block (`Chronicles of House {{ dynasty.name }}`), which is unchanged. The new banner block is additive — no existing text is removed.

No new test file is required for this story. The existing integration test suite provides adequate coverage for a template-only change. If any test fails after the change, it will be due to a Jinja2 syntax error in the new block, not a logic regression.

### CSS note

The project uses Bootstrap 4 via `base.html`. `alert`, `alert-danger`, `alert-success`, `alert-warning`, `alert-secondary` are all available out of the box. No custom CSS additions are needed.

### Scope boundaries

- **In scope:** `templates/turn_report.html` only
- **Out of scope (Story 1-4):** `utils/llm_prompts.py` — `build_turn_story_prompt` receiving `years_advanced` and `interrupt_reason` for narrative pacing
- **Out of scope (Sprint 2):** `project_complete` interrupt wiring in `models/turn_processor.py`
- **Out of scope (Sprint 5):** `heir_majority`, `civil_war` interrupt banners

### Exact insertion point summary

| Section | Change |
|---|---|
| After `<hr class="section-divider">` on line 18 | Insert `{% set %}` block + `<div class="alert ...">` banner |
| Stat tile 4 (lines 43–47) | Replace `dynasty.current_simulation_year` / "Current Year" with `summary.years_advanced` / "Years Passed" |
| Everything else | Unchanged |

### Branch and commit plan

- Branch name: `feature/epic-story-panel` (per CLAUDE.md Sprint 10 branch map — Story 10A was "Chronicles panel in view_dynasty.html" but the branch exists already for the turn-report work from the sprint map. Check if branch already exists; if not, create `feature/turn-report-interrupt-ui`)
- Commit 1: `feat(turn-report): add interrupt banner and years-passed stat to turn_report.html`

### References

- Primary file: `templates/turn_report.html` (199 lines, read completely above)
- `turn_summary` source: `models/turn_processor.py` lines 233–251
- `INTERRUPT_REASONS` constant: `models/turn_processor.py` lines 38–47
- Route variables passed to template: `blueprints/dynasty.py` lines 371–376 (`dynasty`, `summary`, `ai_news`)
- Previous story dev notes: `_bmad-output/implementation-artifacts/1-2-interrupt-driven-turn-loop.md`
- Master plan Sprint 1 task: `review_documents/8_master_plan_2026.md` line 136 ("Update `turn_report.html` to show `interrupt.reason` prominently")
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story 1-3 comment block

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Completion Notes

- AC1/AC3/AC4: Interrupt banner inserted after `<hr class="section-divider">` at line 18 of `turn_report.html`. Uses `{% set %}` block with `summary.interrupt_reason | default('quiet_period')` to derive `banner_class`, `banner_icon`, and `banner_text`. All four interrupt classes implemented: `monarch_death` (alert-danger, skull), `project_complete` (alert-success, check), `war_declared`/`attack_received` (alert-warning, sword), default `quiet_period` (alert-secondary, dove). Banner always visible — no conditional.
- AC2: Stat tile 4 replaced — `dynasty.current_simulation_year` / "Current Year" → `summary.years_advanced | default(5)` / "Years Passed". Other three tiles unchanged.
- AC5: `summary.start_year` and `summary.end_year` on line 16 are untouched; confirmed present after template edit.
- AC6/AC7: 212 tests pass, 0 fail. No Python, route, or test file changes.

### File List

- `templates/turn_report.html` — interrupt banner block + years-passed stat tile
- `STATUS.md` — Story 1-3 marked done, test count updated to 212
- `_bmad-output/implementation-artifacts/1-3-turn-report-interrupt-ui.md` — tasks checked, status → review
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story 1-3 status → review
