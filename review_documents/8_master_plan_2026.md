# Royal Succession Simulation — Master Implementation Plan
*Compiled May 2026. Combines the architecture review, the turn-cadence redesign, the map-as-main-view UI overhaul, the family tree replacement, and the LLM storytelling spine into a single sequenced plan.*

---

## Vision in one paragraph

A grand-strategy dynasty game that lives **on the map** as its primary surface, where time advances at the natural pulse of the world (year-by-year, pausing only when the player needs to decide), where actions are **multi-year projects** that span generations, and where every event — births, deaths, wars, harvests, marriages — is woven by an LLM into a single coherent saga that the player can compile into a published Chronicle at game's end. The mechanical systems (traits, buildings, diplomacy, succession) all feed into and are colored by the narrative; the narrative, in turn, is rooted in real game state, not flavor text. Travian's tactical satisfaction + Crusader Kings' generational drama + a personalized storybook the player wants to keep.

---

## Three pillars to hold in mind through every sprint

1. **The map is the game.** Every action originates from a hex click. The dashboard is a fallback list view, not the primary surface.
2. **Turns end at meaningful moments, not at fixed intervals.** A "turn" is the gap between the last decision and the next one that requires the player.
3. **The LLM is the connective tissue.** Every mechanical event has a narrative hook. Names and numbers become characters and stakes.

If a feature can't be justified against at least one of these, defer it.

---

## Architecture: the target end-state

```
    ┌──────────────────────────────────────────────────────────┐
    │                     world_map.html                       │
    │  (the main view — all play happens here)                 │
    │                                                          │
    │  ┌──────────────┐  ┌─────────────────────┐  ┌──────────┐ │
    │  │  LEFT RAIL   │  │   HEX CANVAS         │ │  RIGHT   │ │
    │  │  - Dynasty   │  │   right-click → ctx  │ │  PANEL   │ │
    │  │  - Resources │  │   click → select     │ │  (slides │ │
    │  │  - 3 Projects│  │   overlays: terrain  │ │  in on   │ │
    │  │  - Ruler     │  │           armies     │ │  click)  │ │
    │  │  - Chronicle │  │           threats    │ │          │ │
    │  └──────────────┘  └─────────────────────┘  └──────────┘ │
    │                                                          │
    │                    [End Turn] ▶                          │
    └──────────────────────────────────────────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │  TURN ENGINE (interrupt-driven)     │
              │  ticks year-by-year up to N years   │
              │  stops when:                        │
              │  - project completes                │
              │  - monarch dies → succession UI     │
              │  - heir comes of age                │
              │  - war declared / attacked          │
              │  - story moment triggers            │
              │  - 5 quiet years pass               │
              └─────────────────────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │  TURN REPORT                         │
              │  - what happened (events list)       │
              │  - LLM-narrated chronicle paragraph  │
              │  - succession or story-moment UI     │
              │    if interrupt requires decision    │
              └─────────────────────────────────────┘

Single source of truth: PersonDB / DynastyDB / Territory / Project (new)
Lifecycle logic in: models/turn_processor.py (extracted from blueprints)
LLM prompts: utils/llm_prompts.py (centralised, with fallbacks)
Story rendering: visualization/family_tree_svg.py + chronicle_compiler.py
```

---

## Sprint plan overview

| # | Sprint | Goal | Effort |
|---|---|---|---|
| 1 | Turn cadence rework | Variable turn length, interrupt-driven | 1–2 wk |
| 2 | Project model | Multi-year projects replace instant actions | 2 wk |
| 3 | Map as main view | UI overhaul, kill action_phase | 2 wk |
| 4 | Free actions split | Decisions vs commitments | 1 wk |
| 5 | Generational interrupts + succession drama | Monarch deaths become decisions | 2 wk |
| 6 | Traits & buildings matter | Wire systems together | 2 wk |
| 7 | Dynastic marriages | Cross-dynasty politics | 1–2 wk |
| 8 | Family tree replacement | SVG-based, dark-theme, dead ancestors visible | 1 wk |
| 9 | LLM storytelling spine | Narrative integrated into every event | 2 wk |
| 10 | Story moment events | Branching vignettes with LLM choices | 2 wk |
| 11 | Code cleanup | Delete duplicates, Alembic, log rotation | 1 wk |
| 12 | Compile the Chronicle | The dynasty book — exportable PDF saga | 1 wk |

**Total: ~16–20 weeks of evening work.** Sprints 1–4 are tightly coupled and should ship together; the rest can ship independently.

---

# Sprint 1 — Turn cadence rework

**Goal:** Stop forcing 5-year turns. End turns when something interesting happens.

**Why first:** Every sprint after this depends on the new turn engine. The 5-year fixed turn is the root cause of the "5 years for what?" problem you identified.

## The new turn loop

```python
# models/turn_processor.py  (NEW FILE)

INTERRUPT_REASONS = [
    'monarch_death',      # opens succession UI
    'heir_majority',      # one-shot when first child of monarch turns 16
    'project_complete',   # something the player started has finished
    'war_declared',       # foreign power declares war on us
    'attack_received',    # we are physically attacked this year
    'major_world_event',  # plague, famine, royal wedding abroad
    'story_moment',       # LLM-triggered branching vignette (Sprint 10)
    'quiet_period',       # 5 years passed without anything else
]

def process_dynasty_turn(dynasty_id, max_years=5):
    interrupt = None
    years_advanced = 0
    while years_advanced < max_years and interrupt is None:
        year = dynasty.current_simulation_year + 1
        tick_projects(dynasty_id, year)        # may set interrupt
        process_lifecycle(dynasty, year)       # may set interrupt
        process_world_events(dynasty, year)    # may set interrupt
        check_external_attacks(dynasty, year)  # may set interrupt
        years_advanced += 1
        dynasty.current_simulation_year = year
    if not interrupt:
        interrupt = ('quiet_period', years_advanced)
    return build_turn_summary(dynasty, years_advanced, interrupt)
```

## Tasks

- [ ] Create `models/turn_processor.py`
- [ ] Move `process_death_check`, `process_marriage_check`, `process_childbirth_check`, `process_succession`, `process_world_events` out of `blueprints/dynasty.py` into `turn_processor.py`
- [ ] Each lifecycle function returns `Optional[Interrupt]` instead of just `True/False`
- [ ] `process_dynasty_turn` becomes the interrupt-driven loop above
- [ ] Update `turn_report.html` to show `interrupt.reason` prominently ("⚠ Your monarch has died" / "✓ Walls of Riverlands completed" / "🕊 Five quiet years passed")
- [ ] Add `years_advanced` to the turn summary so the UI can say "2 years passed" or "5 years passed"
- [ ] Update the Chronicle prompt builder to receive `years_advanced` and `interrupt_reason` so the narrative can pace itself

## Acceptance criteria

- 211 tests still pass.
- A turn that contains a monarch death now stops at the year of death, not 5 years later.
- A turn with no events advances exactly 5 years and is summarized as "five quiet years."
- Turn report visually distinguishes the four interrupt classes (death / completion / war / quiet).

## Files affected

`models/turn_processor.py` (new), `blueprints/dynasty.py` (shrinks dramatically), `templates/turn_report.html`, `utils/llm_prompts.py`

---

# Sprint 2 — Project model

**Goal:** Replace instant actions with multi-year projects. Three "project slots" replace three AP.

**Why now:** Combined with Sprint 1, this delivers the entire turn-feel transformation. Without projects, variable turn length still has empty turns.

## New schema

```python
# models/db_models.py — add Project
class Project(db.Model):
    id = Column(Integer, primary_key=True)
    dynasty_id = Column(ForeignKey('dynasty.id'), nullable=False, index=True)
    project_type = Column(String, nullable=False)
    # 'recruit_unit', 'build_farm', 'build_walls', 'build_cathedral',
    # 'develop_territory', 'march_army', 'arrange_marriage', 'envoy_mission'

    target_territory_id = Column(ForeignKey('territory.id'), nullable=True)
    target_dynasty_id   = Column(ForeignKey('dynasty.id'), nullable=True)
    target_person_id    = Column(ForeignKey('person.id'), nullable=True)
    params_json         = Column(Text)  # unit_type, building_type, etc.

    started_year     = Column(Integer, nullable=False)
    completion_year  = Column(Integer, nullable=False)

    # Yearly drain (validated at project start; if treasury runs out,
    # project goes into 'stalled' status and reports a turn interrupt)
    yearly_cost_gold   = Column(Integer, default=0)
    yearly_cost_food   = Column(Integer, default=0)
    yearly_cost_iron   = Column(Integer, default=0)
    yearly_cost_timber = Column(Integer, default=0)

    status = Column(String, default='active')
    # 'active', 'completed', 'cancelled', 'failed', 'stalled'

    initiated_by_monarch_id = Column(ForeignKey('person.id'))
    completed_by_monarch_id = Column(ForeignKey('person.id'), nullable=True)
    # Set when completed — for chronicle: "Begun by Aldric I, finished by his
    # grandson Eldred III, the Cathedral of the Saints stood at last."
```

## Project type catalogue (proposed durations)

| Project | Duration | Slot | Cost (per year) | Notes |
|---|---|---|---|---|
| Recruit infantry x100 | 1 yr | yes | -50g, -100mp | |
| Recruit cavalry x50 | 2 yr | yes | -80g, -50mp, -10 iron | needs Stables |
| Recruit heavy infantry | 2 yr | yes | -120g, -50mp, -20 iron | needs Barracks |
| Build farm | 2 yr | yes | -30g, -20 timber | |
| Build market | 3 yr | yes | -80g, -30 timber | |
| Build walls (level 1) | 5 yr | yes | -100g, -50 stone | huge defense bonus |
| Build cathedral | 15 yr | yes | -100g, -30 stone | +prestige, multi-gen |
| Develop territory | 3 yr | yes | -40g/yr | raises dev level |
| March army (cross-realm) | 1 yr | yes | -10g, -20 food/yr | |
| March army (adjacent) | 0 yr | **no** | one-shot | free instant |
| Arrange dynastic marriage | 1–2 yr | yes | -20g/yr | depends on relations |
| Envoy mission | 1 yr | yes | -10g/yr | |

The 3 slots represent your dynasty's bandwidth. Cathedrals occupy a slot for 15 years — that's the whole point. Cancel one to free a slot, lose 50% of resources spent.

## Tasks

- [ ] Add `Project` model + migration
- [ ] Create `models/project_system.py` with: `start_project()`, `tick_projects()`, `complete_project()`, `cancel_project()`, `get_active_projects()`
- [ ] In `tick_projects`, drain yearly cost; if dynasty can't pay, set status to `stalled` and emit interrupt
- [ ] On completion: apply the project's effect (spawn the unit, mark the building built, transfer the army, register the marriage)
- [ ] Wire into `process_dynasty_turn` — projects tick before lifecycle each year
- [ ] Migrate the 6 actions from `submit_actions` into project starters
- [ ] Replace `Building.is_under_construction` machinery: a building under construction is just an active `Project` of type `build_*`
- [ ] Story hook: when a project completes under a different monarch than started it, generate a chronicle line: "What [original_monarch] began, [current_monarch] finished — the [project_name] stands."

## Acceptance criteria

- Starting a 5-year project, then advancing 2 turns (each = 5 quiet years), shows the project completing at the right calendar year.
- Cancelling a half-built project refunds 50% of resources spent.
- A project started by a monarch who dies before completion shows both names in the completion chronicle entry.

## Files affected

`models/db_models.py`, `models/project_system.py` (new), `models/turn_processor.py`, `blueprints/dynasty.py` (submit_actions becomes project-starter dispatcher)

---

# Sprint 3 — Map as main view

**Goal:** Make `world_map.html` the single play surface. Kill `action_phase.html`. Make every action originate from clicking a hex.

**Why now:** Sprint 1+2 produce a great underlying engine but the form-based UI undermines it. This sprint is where the player FEELS the redesign.

## Core UX principles

1. **Right-click for actions, left-click to inspect.** Universal grand-strategy convention.
2. **The map is full-viewport. No competing surfaces.**
3. **Three-panel layout** that compresses on smaller screens:

```
┌──────────────────────────────────────────────────────────────────────┐
│  ⚔ DYNASTY · YEAR 1247 · 🪙340 🌾120 ⚒80 🪵150 ⚔420            [End Turn] │
├──────┬──────────────────────────────────────────────────────┬────────┤
│      │                                                      │        │
│      │                                                      │        │
│ LEFT │              HEX MAP CANVAS                           │ DETAIL │
│ RAIL │           (overlays: terrain | armies | threats)     │ PANEL  │
│      │                                                      │ (slide │
│ 60px │                                                      │  in)   │
│      │                                                      │  340px │
│      │                                                      │        │
├──────┴──────────────────────────────────────────────────────┴────────┤
│  [terrain] [armies] [threats] [projects]   ← overlay tabs            │
│  Status: "Margaret Loop, Queen of Anjou, age 34"                     │
└──────────────────────────────────────────────────────────────────────┘
```

## The Left Rail (60px wide collapsible to 40px)

A vertical strip of icon-only widgets. No text labels except on hover. Mirrors a modern game's HUD.

```
┌────────┐
│ [CoA]  │  ← Dynasty coat of arms (click → dynasty info panel)
│        │
│  🪙   │  ← Resource pills, vertical stack
│  340   │     hover for breakdown (income/upkeep)
│        │
│  🌾   │
│  120   │
│        │
├────────┤
│        │
│  ⚙ 1  │  ← Project slots (3 of them, each a vertical pill)
│  ▓▓░  │     showing icon + progress bar
│        │     click → project detail panel (right side)
│  ⚙ 2  │     empty slot has a + icon
│  ▓░░  │
│        │
│  ⚙ 3  │
│   +    │
├────────┤
│        │
│  👑   │  ← Current monarch portrait (32px, generated SVG)
│        │     click → ruler bio panel
├────────┤
│        │
│  📜   │  ← Chronicle button (opens overlay with the saga)
│        │
│  🌍   │  ← World tab (other dynasties' news)
│        │
│  ⚔   │  ← Wars tab (only visible if at war)
│        │
└────────┘
```

## The Hex Map (center, takes ~70% of width)

Visual upgrades over current implementation:

1. **Layered hex rendering**:
   - Base: terrain texture (parchment-style fill instead of flat hex color)
   - Mid: dynasty color overlay (semi-transparent — terrain still shows through)
   - Icons stacked on hex:
     - 👑 Capital (gold ring, exists already — keep)
     - 🏰 Walls (small castle icon, color = level)
     - 🌾 Farm / ⚒ Mine / 🪵 Lumber mill (tiny resource icons clustered)
     - ⚔ Army token (red/blue based on owner; size = unit count)
     - 🚧 Active project marker (pulsing yellow icon with "3/5y" badge)

2. **Borders**: draw thicker ink-style strokes between territories of different controllers, creating visible realm boundaries (CK3 does this beautifully).

3. **Overlay tabs** at the bottom, switching the recolor:
   - **Terrain** (default) — biome colors
   - **Armies** — friendly green / neutral grey / enemy red
   - **Threats** — red gradient based on enemy proximity, gold for opportunities
   - **Projects** — territories with active projects glow

4. **Animations**:
   - When a turn ticks forward, subtly animate years passing in the topbar (1247 → 1248 → ...)
   - When a project completes, the icon flashes and floats a "✓ Walls Complete" toast over the hex
   - When a monarch dies, the screen briefly desaturates and the bell icon tolls (audio optional)
   - When an army marches, draw an arc from origin to destination over 1–2s

5. **Pan/zoom**: middle-drag pan, scroll-wheel zoom, double-click to recenter on territory.

6. **Right-click context menu** on a hex:

```
┌────────────────────────────────┐
│ Riverlands                     │
│ Population 2,400 · Plains      │
├────────────────────────────────┤
│ ⚔  Recruit unit here         ▶ │
│ 🏰 Build structure           ▶ │
│ 🛠  Develop territory         │
│ 📜 Issue local edict         ▶ │
├────────────────────────────────┤
│ Inspect detail                 │
└────────────────────────────────┘
```

The submenu shows project type with cost preview and duration:
- "Build farm — 2 years, -60g, -40 timber"
- "Build walls — 5 years, -500g, -250 stone — DEFENSE"

This is where the cost/risk preview from the original review lives. Player sees the trade-off before committing.

## The Right Detail Panel (340px, slides in)

Triggered by left-click on hex, monarch, project slot, etc. Always shows context for the selected entity.

For a **territory** click:
```
┌─ RIVERLANDS ──────────────────────────┐
│ Population 2,400 · Development 3      │
│ Controller: House Anjou (you)         │
│ Capital ⓒ                             │
│                                       │
│ ── Buildings ──                       │
│  🌾 Farm (level 2)                    │
│  🏰 Walls (level 1)                   │
│  🚧 Cathedral 3/15 yr ───────░░░     │
│                                       │
│ ── Garrison ──                        │
│  Royal Guard · 100 inf · loyalty 95   │
│  Northern Levy · 200 inf · loyalty 60 │
│                                       │
│ ── Recent events ──                   │
│  1244 Walls completed                 │
│  1242 Cathedral begun                 │
│                                       │
│ [Recruit ▶] [Build ▶] [Develop]      │
└───────────────────────────────────────┘
```

For a **project slot** click: progress detail, resources committed, completion year, option to cancel.

For the **monarch portrait** click: ruler bio with traits, current age, reign length, recent events, succession heir preview.

## Tasks

- [ ] Audit `world_map.html` — keep the canvas + tooltip code, rebuild the side panel as the left rail + right detail panel
- [ ] Implement right-click context menu (vanilla JS, no dependencies needed)
- [ ] Build the cost-preview submenu — shows project resource cost and duration before commit
- [ ] Add right detail panel as a slide-in `<aside>` element with conditional templates per entity type
- [ ] Update `/game/<id>/map.geojson` to include per-hex: building list, garrison summary, active project
- [ ] Add overlay modes (threats, projects) to the canvas renderer
- [ ] Border-drawing pass: after rendering hexes, draw thicker strokes on edges where neighboring hexes have different `controller_dynasty_id`
- [ ] Pan/zoom: implement via canvas transform matrix
- [ ] Animated turn pass: on End Turn click, fetch the turn summary, then play events as toasts with delays before redirecting to turn_report
- [ ] Redirect `auth.dashboard` → `world_map` for users with at least one active dynasty (dashboard becomes secondary, only used to switch dynasties or create new)
- [ ] **Delete `templates/action_phase.html`** and the `action_phase` route — its functionality is now distributed between right-click menus and the right detail panel
- [ ] **Delete `templates/view_dynasty.html`** OR keep as a "dynasty stats" sub-page (linked from left rail's CoA click)

## Acceptance criteria

- Logging in goes straight to the map.
- Right-clicking a hex shows actions with cost preview.
- Clicking a hex opens the detail panel.
- The action_phase.html route returns 404.
- All 6 action types from the old submit_actions are reachable from the map.

---

# Sprint 4 — Free actions split

**Goal:** Distinguish *decisions* (instant, unlimited) from *commitments* (project, slot-consuming).

**Why now:** Sprint 3 introduced cost previews; this sprint formalizes the second category — actions that don't take time but DO have consequences.

## Free actions catalogue

These don't consume project slots, don't take game-time, but DO have real effects (relations, treasury, infamy, future event triggers):

| Free action | Effect | UI access |
|---|---|---|
| Declare war | Opens war state, registers casus belli | Right-click a foreign hex |
| Propose treaty (NAP / Alliance / Trade) | Sends offer; AI responds next turn | Right-click foreign capital |
| Send envoy with gift | -50g, +10 relations | Right-click foreign capital |
| Issue ultimatum | -10 relations now, +20 infamy if rejected | Right-click foreign capital |
| Arrange marriage offer | Initiates negotiation project (Sprint 7) | Click character → context menu |
| Name an heir | Override default succession | Click monarch → context |
| Adopt new succession law | Future deaths use new law (-prestige once) | Dynasty info panel |
| Hold a feast | -100g, +5 to all noble loyalty | Dynasty info panel |
| Hold a tournament | -200g, +10 prestige, generates 1 story | Dynasty info panel |
| Pardon a vassal | reverses an infamy gain | Vassal context menu |

## Tasks

- [ ] Create `POST /dynasty/<id>/free_action` endpoint with `action_type` + params dispatcher
- [ ] Free actions are validated, applied, and a chronicle line is appended — but they don't tick the turn
- [ ] LLM hook: each free action triggers a flavor line. "Sent envoy" → LLM writes "Sir Aldwin rides north under banner of truce, bearing chests of silver…" appended to the chronicle but not yet a story moment
- [ ] Update right-click menus to include free actions (separated visually from projects)

## Acceptance criteria

- Declaring war is instant and doesn't end the turn.
- Each free action produces an LLM-flavored (or fallback) chronicle line.
- Free actions are reversible up until End Turn (player can undo a declaration before clicking End Turn).

---

# Sprint 5 — Generational interrupts + succession drama

**Goal:** Monarch death stops the world. Player chooses heir. Heirs have personality. Pretenders exist.

**Why now:** This is what transforms the game from "watch your dynasty drift" into "shepherd your dynasty's legacy." It's the single highest-impact feature for emotional engagement.

## The succession decision flow

When a monarch dies during a turn loop:

1. Turn loop halts immediately, year is captured.
2. Eligible heirs are calculated under the active succession law.
3. Player is shown a **succession panel** (full-screen modal):

```
┌──────────────────────────────────────────────────────────────┐
│   THE KING IS DEAD                                           │
│   ────────────────                                            │
│   Aldric I of Anjou has passed in his sleep, aged 67,        │
│   having ruled for 31 winters. Three claimants stand          │
│   ready to wear the iron crown.                              │
│                                                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│   │ [portrait]│  │ [portrait]│  │ [portrait]│                  │
│   │  ELDRED   │  │   BRAN    │  │  EMERIC   │                  │
│   │  age 28   │  │  age 26   │  │  age 14   │                  │
│   │ ─────────│  │ ─────────│  │ ─────────│                  │
│   │  Eldest   │  │  Brave    │  │  Cunning  │                  │
│   │  Lawful   │  │  Soldier  │  │  Sickly   │                  │
│   │           │  │           │  │           │                  │
│   │ "Beloved  │  │ "The army │  │ "His mind │                  │
│   │  by the   │  │  follows  │  │  is sharp │                  │
│   │  bishops" │  │  him"     │  │  but body │                  │
│   │           │  │           │  │  weak"    │                  │
│   │           │  │           │  │           │                  │
│   │ Default   │  │           │  │           │                  │
│   │ heir under│  │ +Army     │  │ Regency   │                  │
│   │ male prim │  │ loyalty   │  │ required  │                  │
│   │           │  │ -Bishop   │  │ -10 prest │                  │
│   │           │  │  loyalty  │  │           │                  │
│   │           │  │           │  │           │                  │
│   │ [Crown]   │  │ [Crown]   │  │ [Crown]   │                  │
│   └──────────┘  └──────────┘  └──────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

4. The "story" cards under each portrait are LLM-generated based on each candidate's actual traits, age, position in the family, and recent events. Fallback to template strings.
5. Choosing a non-default heir (e.g. picking Bran when male primogeniture would crown Eldred) triggers a **pretender flag** — Eldred has a 30% chance to revolt within 5 years.
6. After choice, an LLM-narrated coronation chronicle is appended. Then the turn report shows.

## Heir-coming-of-age interrupt

First time a monarch's eldest child turns 16: turn pauses. LLM writes 3-sentence vignette ("Lady Margaret comes of age in the spring of 1247, and the court takes notice…"). Player can issue one free action right now: arrange a marriage / send to a foreign court / appoint to a household role.

## Pretender mechanic

A flagged pretender silently accumulates support over years. If their supporting trait + dynasty discontent + foreign sponsorship crosses a threshold, they trigger a **civil war interrupt**: turn pauses, pretender publicly claims the throne, player must respond (negotiate / fight / abdicate).

## Tasks

- [ ] Add `monarch_death` interrupt to turn processor (already covered in Sprint 1)
- [ ] Build `/dynasty/<id>/succession_choice` endpoint + modal template
- [ ] LLM prompt: `build_succession_card_prompt(candidate, monarch, recent_events)` — generates flavor for each candidate
- [ ] Fallback templates for the candidate cards (using traits)
- [ ] Add `is_pretender`, `pretender_strength` fields to PersonDB
- [ ] Pretender accumulation logic in lifecycle tick
- [ ] `civil_war` interrupt type — opens a modal similar to succession but with "Fight / Negotiate / Abdicate" choices
- [ ] Heir-of-age interrupt: tracks `has_seen_majority` flag on PersonDB to fire only once per character

## Acceptance criteria

- A monarch's death always pauses the turn and shows the succession modal.
- Picking a non-default heir creates a pretender record on the bypassed candidate.
- Eldest child's 16th birthday triggers the once-per-character vignette.
- LLM generates per-candidate flavor when API is available; falls back to trait-templated text otherwise.

---

# Sprint 6 — Traits and buildings actually matter

**Goal:** Wire the existing trait/building/relation systems together so they affect outcomes.

**Why now:** Without this, all the new turn machinery sits on top of a shallow simulation. Players need to feel that *who their monarch is* and *what they've built* changes outcomes.

## Trait → effect map (start with 8)

| Trait | Effect |
|---|---|
| Brave | +10% combat strength when monarch leads army |
| Craven | -15% combat strength when monarch leads; -5 prestige |
| Cunning | +15% espionage success; +10% diplomatic offer success |
| Wroth (irascible) | +5 infamy from any war declaration; +5% combat |
| Patient | +1 to relation gain per turn from envoys |
| Sickly | -50% lifespan; can't lead armies |
| Pious | +5 relations with allied religion dynasties; -5 with others |
| Greedy | +10% tax income; -1 noble loyalty per turn |

Each trait should be checked at exactly the moments it matters:
- Combat resolution (`MilitarySystem.resolve_battle`)
- Tax tick (in EconomySystem)
- Diplomatic action acceptance
- Lifespan calculation (turn_processor's death_check)
- Chronicle flavor selection (LLM gets the trait list as context)

## Building → effect map (gate things)

| Building | Effect |
|---|---|
| Farm | +50 food/yr, +200 manpower max (territory) |
| Market | +20g/yr, enables trade routes from this territory |
| Walls (level 1) | siege duration ×2, defender combat +25% |
| Walls (level 2) | siege duration ×3, defender combat +50% |
| Barracks | unlocks heavy_infantry recruit project here |
| Stables | unlocks cavalry / heavy_cavalry recruit project here |
| Lumber mill | +30 timber/yr |
| Mine | +20 iron/yr |
| Cathedral | +5 prestige/yr while standing, +10 relations with religious dynasties |

## Trait inheritance

When a child is born, inherit ~30% from each parent trait pool (cap at 3 starting traits) plus 1 random trait from the theme's common pool. As they age, additional traits can be acquired through events.

## Tasks

- [ ] Build `models/trait_effects.py` — centralised mapping of trait → modifier function
- [ ] Hook trait effects into MilitarySystem, EconomySystem, DiplomacySystem
- [ ] Update `process_death_check` in turn_processor to apply lifespan modifiers
- [ ] Lock recruit-project starts behind the appropriate building check
- [ ] Trait inheritance in `process_childbirth_check`
- [ ] LLM prompt update: `build_chronicle_prompt` now receives the active monarch's traits so the narrative voice reflects them
- [ ] Document traits in `docs/traits.md` (player-facing) and surface them in tooltips on the trait badges

## Acceptance criteria

- A Brave monarch leading an army wins a battle they would otherwise have narrowly lost.
- Recruiting heavy infantry in a territory without a Barracks is rejected with a clear error.
- A child of a Cunning + Pious mother shows roughly the inherited trait probabilities over 100 simulated births.

---

# Sprint 7 — Dynastic marriages

**Goal:** Marriages become political instruments between actual dynasties, not stranger-generation.

**Why now:** This is the most "Crusader Kings" feature you can add and it relies on Sprint 6's trait inheritance to feel meaningful.

## The marriage pipeline

1. Player initiates a marriage offer as a free action: `propose_marriage(my_person, target_dynasty, target_person?)`
2. If `target_person` not specified, the AI picks the highest-prestige unmarried noble of the right gender.
3. The offer creates a `marriage_negotiation` project (1–2 years) on the player's slot.
4. AI accepts/rejects based on relative prestige, relations, religion, traits.
5. On acceptance, both characters become spouses, a chronicle entry fires ("Lady Elsa of Vane weds Lord Bran of Anjou in the great hall of Riverlands, sealing peace between the two houses…"), and:
   - Relations between the two dynasties: +30
   - Either side can call the other into wars (alliance pull)
   - Children of the marriage have claims on both dynasties (future succession spice)

## Tasks

- [ ] Add `MarriageOffer` model OR fold into `Project` with `project_type='marriage_negotiation'`
- [ ] Replace the stranger-generation in `process_marriage_check` with: first try cross-dynasty, fall back to stranger only if no candidates
- [ ] AI dynasty marriage acceptance logic in AIController (new `decide_marriage_response` method)
- [ ] Wedding chronicle entry — LLM-narrated using both spouse traits
- [ ] Children-with-claims: when a child is born to a cross-dynasty couple, register a `Claim` row linking that child to a potential title in the maternal dynasty
- [ ] Right-click on a foreign character → "Propose marriage to my [son/daughter]"

## Acceptance criteria

- A successful marriage between two player-created dynasties creates the alliance pull effect (when one is attacked, the other gets a "join war?" decision).
- Children of cross-dynasty marriages appear as potential heirs in BOTH dynasties' succession panels.

---

# Sprint 8 — Family tree replacement (kill the PNG)

**Goal:** Replace the matplotlib PNG family tree with a beautiful interactive SVG that fits the medieval dark aesthetic.

**Why now:** The current PNG (one isolated green circle on white canvas, no parent-child lines) is the worst-looking artifact in the game. It's visible from the dynasty page, and it screams "early prototype." Replacing it is small effort, huge perceived quality jump.

## What's wrong with the current PNG

1. White Bootstrap-light background fights the dark theme
2. Default matplotlib aesthetic — doesn't feel medieval
3. Living-nobles-only filter strips away parents/grandparents → you see disconnected leaves with no tree
4. Random scatter layout instead of generation-based hierarchy
5. Crude colored circles — you have beautiful procedural portraits already, why aren't you using them?
6. Static — no interaction, no zoom, no detail-on-hover
7. PNG file regeneration on every turn — 99 files in `visualizations/` already

## The replacement

A pure SVG renderer following the same pattern as `heraldry_renderer.py` and `portrait_renderer.py`. Lives at `visualization/family_tree_svg.py` and produces an SVG string stored in or rendered from the dynasty's HTML template.

### Layout

Hierarchical, generations as horizontal rows. Top row = founding ancestors. Each subsequent row = one generation down. Widows/widowers/spouses-from-outside on the same row as their partner, slightly offset.

```
Generation 0:   [👑Aldric I†] ══ [Margaret†]
                       │
                       ├─────────────┬────────┐
Generation 1:   [Eldred I†]══[Helga]    [Bran†]══[Aelfwyn]    [Emeric†]
                    │                       │
            ┌───────┴────┐              ┌───┴────┐
Generation 2: [👑Eldred II]══[Sigrid]    [Theodric] [Branwyn]══[Foreign Lord]
                    │                                    │
Generation 3:    [Roland]                          [Mira]──── (cross-dynasty link)
```

### Visual conventions

- **Node = portrait + name + dates + crown if monarch**
  - Living: full color portrait
  - Deceased: portrait desaturated and tinted slate-blue, dagger icon for assassinated, sword for killed-in-battle, cross for natural
  - Currently reigning: gold ring around portrait + 👑 above
- **Edges**:
  - Solid vertical lines for parent-child (drop down from midpoint between parents)
  - Double horizontal line `══` for marriages (your existing convention is fine)
  - Dashed line for cross-dynasty links (to spouses' originating dynasties shown as ghost nodes at edges)
- **Color palette**: ink-on-parchment — `--gold` for monarch ring, `--text-light` for living text, `--text-muted` for dead, `--dark-border` for edges
- **Font**: Cinzel for names, Crimson Text for dates (mirror the rest of the UI)

### Interactivity (HTML5/SVG inline, no PNG)

- Hover: tooltip with full info (full name, all titles, all traits, parents, spouse, cause of death)
- Click: opens a character bio panel on the right (re-uses Sprint 3's right detail panel)
- Pan/zoom for large dynasties
- "Show deceased" toggle (default ON — the dead are the WHOLE point of a dynasty)
- "Highlight bloodline" — click any character, all their descendants and ancestors light up, the rest fade
- Search box: type a name, jump to that node

### Generation algorithm

```python
# visualization/family_tree_svg.py
def generate_family_tree_svg(dynasty_id, options=None):
    """Build an SVG family tree from PersonDB.

    Returns: SVG string, ready to embed in template with `{{ ... | safe }}`.
    """
    persons = PersonDB.query.filter_by(dynasty_id=dynasty_id).all()
    # 1. Build child-of relationships
    children_of = defaultdict(list)
    for p in persons:
        if p.father_sim_id: children_of[p.father_sim_id].append(p)
        if p.mother_sim_id: children_of[p.mother_sim_id].append(p)
    # 2. Compute generation depth via BFS from founders (no parents in dynasty)
    generations = bfs_assign_generations(persons, children_of)
    # 3. Order within each generation: leftmost = eldest, by birth_year
    # 4. Compute X positions using a tree-walking algorithm (Reingold-Tilford
    #    or simpler centered-children layout)
    # 5. Emit SVG: <g class="generation"> per row, <g class="person"> per node,
    #    embed each person's portrait_svg inline (or via <use> reference)
    # 6. Draw edges: parent midpoint → child top
    return svg_string
```

### Rendering hook

Replace `generate_family_tree_visualization()` (the matplotlib PNG generator) with a function that just stores the SVG string in `dynasty.family_tree_svg` (new TEXT column on DynastyDB). The view template embeds `{{ dynasty.family_tree_svg | safe }}`. Updated only when the family changes (new birth/death) — not every turn.

## Tasks

- [ ] Build `visualization/family_tree_svg.py`
- [ ] Add `family_tree_svg` Text column to DynastyDB (migration)
- [ ] Implement Reingold-Tilford layout (~80 lines of Python) or use the lighter "centered children" heuristic
- [ ] Pan/zoom JS in the family tree page (vanilla, ~50 LoC)
- [ ] Search-and-highlight JS
- [ ] Delete `visualization/plotter.py` (the matplotlib renderer)
- [ ] Delete `visualizations/family_tree_*.png` (all 99 files)
- [ ] Add `*.png` to `.gitignore` for the `visualizations/` directory (already mostly there)
- [ ] Update `view_dynasty.html` to render the new SVG inline

## Acceptance criteria

- Opening a dynasty shows a family tree with deceased ancestors visible (greyed out).
- Tree fits the dark medieval theme.
- Hover on a portrait → tooltip with details.
- Click on a portrait → right detail panel opens with full bio.
- 500-person dynasty renders in under 500ms.

---

# Sprint 9 — LLM storytelling spine

**Goal:** Use the LLM as the connective tissue across all events. Names and numbers become characters and stakes.

**Why now:** All previous sprints created the mechanical hooks. This sprint plugs the narrative engine into them.

## Where LLM should now be present

| Event | Current | Target |
|---|---|---|
| Birth | "Eldred Anjou was born to Margaret and Aldric." | "In the bitter winter of 1227, Margaret labors three days. The midwives murmur of an ill star, but the boy emerges squalling — Eldred, named for his great-uncle who died on the Red Field." |
| Death | "Aldric died at age 67." | "The old king's breath stilled before dawn. He had ruled thirty-one winters. The bell of the chapel tolled until sunset." |
| Marriage | "X and Y married." | (already partial — extend with LLM) |
| Build complete | "Walls completed." | "After five years of stonecutting, the walls of Riverlands rise dark against the western sky." |
| Battle won | "Battle won, 200 casualties." | "The line held at the river's bend. Two hundred fell in the rushes, but the banner of Anjou stood at sundown." |
| Tournament held | (not present) | "Knights from four realms answered the call. Sir Aldwin unhorsed three Vane champions in succession before falling to a Pius blow…" |
| Foreign dynasty action | "House Vane declared war on House Pius." | "Word arrives by hooded courier: Lord Aldwin of Vane has flung his banners against the Pius bastion at Hollowford. The cause? Old grievances unburied." |

## Architecture

Keep the centralised prompt pattern. Add new prompt builders to `utils/llm_prompts.py`:

```python
def build_birth_flavor_prompt(child, mother, father, recent_events): ...
def build_death_flavor_prompt(deceased, age, recent_events, monarch_traits): ...
def build_battle_flavor_prompt(battle_result, attacker, defender): ...
def build_world_news_prompt(foreign_event, our_dynasty_state): ...
def build_succession_card_prompt(candidate, monarch, recent_events): ...  # (Sprint 5)
def build_coronation_prompt(new_monarch, predecessor, succession_method): ...
def build_construction_complete_prompt(project, territory, dynasty): ...
```

Each has a deterministic fallback. Each is called from the lifecycle/turn_processor immediately after the mechanical event resolves, BEFORE the chronicle paragraph is generated. Result: the chronicle paragraph (one per turn) draws on a rich pool of already-narrated micro-events.

## Token budget

| Event class | max_tokens | Frequency |
|---|---|---|
| Birth flavor | 60 | Common (~3-5/turn) |
| Death flavor | 80 | Less common |
| Build complete | 50 | Less common |
| Battle flavor | 100 | Rare |
| World news | 80 | 1-2/turn |
| Coronation | 120 | Rare (every ~5 turns) |
| Story moment | 200 | Rare (Sprint 10) |
| Per-turn chronicle | 150 | Always |

A typical turn now spends 300-600 LLM tokens instead of 150. Players who want narrative depth pay the API cost; players without an API key still get the deterministic fallback for everything.

## Tasks

- [ ] Add 7 new prompt builders to `utils/llm_prompts.py` with fallbacks
- [ ] Each lifecycle function in turn_processor.py adds a call to the relevant flavor function, results stored as event_string on HistoryLogEntryDB
- [ ] World news: when an AI dynasty does something significant, generate a "letter from the east" entry on the player's chronicle
- [ ] Cache invariants: per-event LLM calls should not block the turn — fire and store, with a fallback if it times out (>3s)
- [ ] Async LLM calls via background thread for any single turn that would make 5+ calls (perf optimization)

## Acceptance criteria

- A turn that contains 1 birth + 1 death + 1 project completion produces 4+ LLM-flavored chronicle entries plus the synthesized turn paragraph.
- Game remains fully playable without GOOGLE_API_KEY (all fallbacks fire).

---

# Sprint 10 — Story moment events

**Goal:** Occasional turns deliver a fully-rendered narrative vignette with 2-3 player choices that branch the simulation.

**Why now:** This is the deepest narrative feature and depends on Sprints 6 (traits matter) and 9 (LLM hooked in). Without them, story moments would feel generic.

## What a story moment looks like

```
┌────────────────────────────────────────────────────────────────┐
│   THE COURTSHIP OF LADY MARGARET                               │
│   ────────────────────────                                     │
│                                                                │
│   Lady Margaret, your eldest daughter, has been spending        │
│   long hours in the kitchen. The chamberlain, much disturbed,   │
│   has reported that she has formed an attachment to one of      │
│   the under-cooks — a quiet boy named Tomas, son of nobody.     │
│   She came to you yesterday, eyes blazing, and asked your       │
│   blessing for the match.                                       │
│                                                                │
│   The court watches. The bishops watch. The rival houses        │
│   are already laughing.                                         │
│                                                                │
│   ┌─────────────────────────────────────────────────────────┐ │
│   │ ▶ Allow the marriage. Love will not be commanded.       │ │
│   │   −20 prestige, +30 relationship with Margaret,         │ │
│   │   Tomas joins the dynasty as a minor noble (Romantic    │ │
│   │   trait propagates to descendants)                      │ │
│   ├─────────────────────────────────────────────────────────┤ │
│   │ ▶ Forbid it. The realm comes first.                     │ │
│   │   +5 prestige with the bishops, Margaret gains          │ │
│   │   "Embittered" trait, Tomas exiled to a frontier garrison│ │
│   ├─────────────────────────────────────────────────────────┤ │
│   │ ▶ Have Tomas killed quietly. Solve the problem.         │ │
│   │   +10 prestige with the old guard, −20 with reformers,  │ │
│   │   Margaret gains "Vengeful" trait, +5% chance of        │ │
│   │   parricide event when you grow old                     │ │
│   └─────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## Trigger conditions

Story moments fire on a low base probability (~5% per turn) but are heavily weighted by current state:

- A young heir is +Cunning → "The Council Whispers" plot moment
- Two of your nobles have hostile relations → "Dueling Lords" plot moment
- A foreign dynasty has declared war but you have a marriage tie → "The Bonds of Kin" plot moment
- A child of the monarch has fallen ill → "The Fading Heir" plot moment
- A long-standing alliance is fraying → "The Letter From The East" plot moment

The LLM prompt receives:
- Active monarch's traits and recent decisions
- Current relationships between key characters
- Recent dynasty events
- Available choices (mechanical templates the engine knows how to apply)

It generates the prose AND selects the best 3 choices from a larger pool.

## Architecture

```python
# models/story_moments.py
STORY_MOMENT_TEMPLATES = [
    {
        'id': 'forbidden_love',
        'preconditions': lambda state: any(
            p.is_unmarried and 16 <= p.age <= 25 and p.is_noble
            for p in state.monarch_children
        ),
        'mechanical_choices': ['allow', 'forbid', 'eliminate'],
        'effects': {
            'allow':     {'prestige': -20, 'relationship_delta': {'subject': +30}, 'add_character': 'commoner_spouse'},
            'forbid':    {'prestige': +5,  'add_trait': {'subject': 'Embittered'}, 'exile_npc': True},
            'eliminate': {'prestige': +10, 'add_trait': {'subject': 'Vengeful'}, 'parricide_risk': +5},
        },
    },
    # ... ~12 templates to start
]

def maybe_trigger_story_moment(dynasty_state):
    candidates = [t for t in STORY_MOMENT_TEMPLATES if t['preconditions'](dynasty_state)]
    if not candidates: return None
    if random.random() > BASE_TRIGGER_CHANCE: return None
    template = random.choice(candidates)
    prose = build_story_moment_prose_via_llm(template, dynasty_state)
    return StoryMoment(template_id=template['id'], prose=prose, choices=template['mechanical_choices'])
```

## Tasks

- [ ] `models/story_moments.py` with template library (start with 8 templates)
- [ ] `story_moment` interrupt in turn_processor
- [ ] Modal template `templates/story_moment.html`
- [ ] LLM prompt builder for prose generation per template
- [ ] Effect applicator that mutates dynasty state per chosen choice
- [ ] Each chosen choice creates a chronicle entry with the LLM's prose + the choice description
- [ ] Story moments respect cooldown (no two within 5 turns)

## Acceptance criteria

- Over a 50-turn dynasty, at least 3 story moments fire.
- Each story moment shows different prose (LLM not template).
- Chosen effects propagate (Embittered trait actually appears on the character).

---

# Sprint 11 — Code cleanup

**Goal:** Pay down all the technical debt from the other sprints and from the original review.

**Why now:** Putting it last lets us delete `action_phase.html`, `simulation_engine.py.bak`, `models/economy.py`, `models/person.py`, and `models/family_tree.py` without breaking anything — all the code that depended on them has been replaced.

## Deletions

- [ ] `simulation_engine.py.bak` — dead code
- [ ] `models/economy.py` — superseded by `economy_system.py`
- [ ] `models/person.py` — Person/FamilyTree layer no longer needed (Sprint 8 ported visualizer to PersonDB)
- [ ] `models/family_tree.py` — same
- [ ] `visualization/plotter.py` — matplotlib family tree, replaced by SVG
- [ ] `templates/action_phase.html` — replaced by map (Sprint 3)
- [ ] All 99 `visualizations/family_tree_*.png` — no longer generated
- [ ] `cookies.txt` — should not be in repo
- [ ] `flask_app.log` from project root — move to `logs/`
- [ ] Two dead placeholder routes in `blueprints/map.py` (noted in STATUS.md)

Roughly 1,800-2,200 lines of deletion. The codebase should drop from ~22K LoC to ~20K.

## Migrations

- [ ] Adopt **Flask-Migrate / Alembic**. Replace ad-hoc ALTER TABLE in `db_initialization.py`.
- [ ] Initial migration captures current schema; subsequent sprints (the ones above) generate proper migrations.

## Performance

- [ ] Add `joinedload(PersonDB.spouse, PersonDB.father, PersonDB.mother)` to the turn-processor's initial person fetch — kills the N+1 queries
- [ ] Cache `theme_config` per dynasty in app.config (re-read on dynasty save)
- [ ] Index `HistoryLogEntryDB(dynasty_id, year)` — used heavily by the chronicle queries
- [ ] Index `Project(dynasty_id, status, completion_year)` — used every turn-tick

## Logging hygiene

- [ ] `RotatingFileHandler` with `maxBytes=5MB`, `backupCount=3`
- [ ] Replace remaining `print()` statements with `logger.debug/info`
- [ ] Conditional atexit handler (skip during pytest) to fix the "I/O on closed file" warnings

## Warnings

- [ ] SQLAlchemy 2.0 deprecations — switch `.query.get(id)` to `db.session.get(Model, id)`
- [ ] `datetime.utcnow()` → `datetime.now(datetime.UTC)`
- [ ] Aim: 1094 warnings → <50

## Acceptance criteria

- 211+ tests still pass (some new tests added in earlier sprints).
- `pytest -W error` passes (no warnings treated as errors break the suite — at least filter the unavoidable third-party ones).
- Total Python LoC reduced by ~10%.

---

# Sprint 12 — Compile the Chronicle

**Goal:** The pay-off feature. Stitch the entire dynasty's saga into a publishable book the player wants to keep.

**Why last:** This is what happens AFTER the player has lived through 30+ turns of richly narrated events. Without all the narrative depth from Sprints 9 and 10, this would be a thin compilation. With them, it's the artifact the player will share.

## What it produces

A single document — `The Chronicle of House [Name]` — assembled from:

1. The dynasty's accumulated `epic_story_text` (the per-turn paragraphs)
2. Selected highlight events (births of monarchs, coronations, major battles, story moments, deaths)
3. The cumulative coats of arms
4. A final family tree SVG embedded
5. An LLM-written "Foreword" (200 tokens) that frames the whole saga
6. An LLM-written "Epilogue" (200 tokens) that comments on the dynasty's character

Available as:
- An on-screen reader page (paginated)
- An exported PDF (use the existing PDF tools / pdf skill)
- An exported epub (stretch)

## The compile flow

```python
def compile_chronicle(dynasty_id):
    dynasty = DynastyDB.query.get(dynasty_id)
    paragraphs = dynasty.epic_story_text.split('\n\n')
    highlights = select_highlight_events(dynasty_id)  # ~20 milestones
    tree_svg = dynasty.family_tree_svg
    foreword = generate_foreword_llm(dynasty, paragraphs[:3])
    epilogue = generate_epilogue_llm(dynasty, paragraphs[-5:], current_state)
    return ChronicleBook(
        title=f"The Chronicle of House {dynasty.name}",
        chapters=group_paragraphs_by_monarch(paragraphs, highlights),
        foreword=foreword,
        epilogue=epilogue,
        family_tree=tree_svg,
        coat_of_arms=dynasty.coat_of_arms_svg,
        period=f"{dynasty.start_year} – {dynasty.current_simulation_year}",
    )
```

## Available at any point

The player can compile the chronicle at any turn — even mid-dynasty — to read what's accumulated. It's not a "game over" feature; it's a "look at what we've built" feature, available always.

## Tasks

- [ ] `models/chronicle_compiler.py` with the compile flow above
- [ ] Highlight selection algorithm (top events by importance score)
- [ ] Group paragraphs into chapters by reigning monarch
- [ ] Foreword + epilogue prompts in `utils/llm_prompts.py`
- [ ] `templates/chronicle_book.html` — paginated reader
- [ ] PDF export route — use the existing pdf skill, render the HTML to PDF
- [ ] Family tree embedded as SVG in the book
- [ ] "Compile Chronicle" button on the left rail, always available

## Acceptance criteria

- A 30-turn dynasty produces a chronicle of at least 8 chapters.
- PDF export renders cleanly with embedded portraits, coat of arms, and family tree.
- The chronicle reads as a coherent narrative, not a log dump.

---

# Cross-cutting: how the LLM threads through everything

To address your concern that "all of this needs to compose a great story in the end" — here's how the LLM hooks layer through all 12 sprints, in order of insertion:

| Sprint | LLM hook |
|---|---|
| 1 | Chronicle prompt receives `years_advanced` + `interrupt_reason` |
| 2 | Project completion under a new monarch generates handoff narrative |
| 3 | (UI sprint — no new LLM hooks) |
| 4 | Each free action generates a flavor line (envoy, gift, ultimatum…) |
| 5 | Succession candidate cards + coronation narrative |
| 6 | Chronicle prompt receives active monarch's traits, narrative voice reflects them |
| 7 | Wedding chronicle uses both spouse traits |
| 8 | (Visualization — no new LLM hooks) |
| 9 | **The big one — birth/death/build/battle/world-news flavor everywhere** |
| 10 | **Story moments — full vignettes with branching** |
| 11 | (Cleanup — no new LLM hooks) |
| 12 | Foreword + epilogue + chapter compilation |

By Sprint 12, every event in the game has been narrated. The Chronicle compiler doesn't have to invent narrative — it just has to select and arrange what's already there.

---

# Risk and mitigation

| Risk | Mitigation |
|---|---|
| LLM cost / latency | Token budgets per call type; async background generation; full deterministic fallback; cache per-character flavor for reuse |
| Schema migrations break existing saves | Use Alembic from Sprint 11; for users with current saves, ship a one-time data migration script |
| Sprint 3 (UI overhaul) breaks too much at once | Ship behind a feature flag; old `view_dynasty.html` still reachable until Sprint 11 deletion |
| Story moments feel too random / break immersion | Cooldown (no two in 5 turns); only fire when preconditions match dynasty state; LLM prompt explicitly grounds in current characters |
| Family tree doesn't scale to 200+ persons | Implement as virtualized SVG (only render visible nodes); cap default view at 6 generations; "expand ancestors" button for older |

---

# Sequencing summary (for sticking on the wall)

```
PHASE 1 — Foundation (Sprints 1-4, 6-7 weeks)
   1. Variable turn → 2. Projects → 3. Map UI → 4. Free actions
   At end: the game FEELS right

PHASE 2 — Drama (Sprints 5-7, 5-6 weeks)
   5. Succession → 6. Traits/buildings → 7. Marriages
   At end: every monarch matters, every choice has weight

PHASE 3 — Beauty (Sprint 8, 1 week)
   8. SVG family tree
   At end: the game LOOKS right

PHASE 4 — Story (Sprints 9-10, 4 weeks)
   9. LLM everywhere → 10. Story moments
   At end: every dynasty tells a different story

PHASE 5 — Polish + Pay-off (Sprints 11-12, 2 weeks)
   11. Cleanup → 12. Compile the Chronicle
   At end: the dynasty becomes a book the player wants to keep
```

---

# Where to start tomorrow

Sprint 1, Task 1: create `models/turn_processor.py` and move the lifecycle functions out of `blueprints/dynasty.py`. That single refactor unlocks Sprints 1, 2, 5, 6, and 9. It can land in a single afternoon.

After that, the project model in Sprint 2 is the next domino. Once those two are in place, the game's pulse is right and every other sprint is incremental polish on a working foundation.

—

*This document supersedes review_documents/1-7. Update STATUS.md after each sprint completion.*
