# Epic 12 — Compile the Chronicle: Design Note

Date: 2026-06-12 · Author: Opus (design pass with Barakganon)
Status: design locked — ready to spec 12-1

## Goal
Stitch the dynasty's accumulated saga into a publishable, keepable **Chronicle book** (on-screen reader + PDF), organized by reign, with key events highlighted.

## Locked decisions (Project Lead)
1. **Prose source:** `ChronicleEntryDB` rows (structured per-turn: `game_id`=dynasty.id, `turn`, `year`, `text`). `epic_story_text` stays the live in-game saga view.
2. **Highlight scoring:** deterministic fixed `event_type → weight` table (no LLM). See table below.
3. **Highlight layout:** per-chapter "Key Events of the Reign" callout box, in narrative context.

## Data model (existing — no schema change needed for 12-1)
- `ChronicleEntryDB(game_id, turn, year, text)` — prose paragraphs.
- `HistoryLogEntryDB(dynasty_id, year, event_string, event_type, person1_sim_id, territory_id)` — highlight candidates (~30 event types).
- `PersonDB(is_monarch, reign_start_year, name, portrait_svg)` — chapter boundaries.
- `DynastyDB(coat_of_arms_svg, family_tree_svg, name, ...)` — book cover/back matter.

## Architecture

### 12-1 `models/chronicle_compiler.py`
`compile_chronicle(dynasty_id) -> ChronicleBook`:
1. Load chronicle paragraphs from `ChronicleEntryDB` filtered by `game_id=dynasty_id`, ordered by `year, turn`.
2. Build **chapters** from monarchs: query `PersonDB.is_monarch` ordered by `reign_start_year`; each chapter spans `[reign_start_year, next_reign_start_year)`; prepend a **"Founding"** chapter for any paragraph/event earlier than the first monarch's reign.
3. Bucket each paragraph into the chapter whose year-range contains `paragraph.year`.
4. Load `HistoryLogEntryDB` for the dynasty; score each event via the weight table; select **top-N (default 5)** per chapter as highlights (ties broken by year).
5. Assemble dataclasses (below). Foreword/epilogue left empty here — filled by 12-2.

```python
@dataclass
class ChronicleHighlight:
    year: int
    event_type: str
    text: str          # event_string
    weight: int

@dataclass
class ChronicleChapter:
    monarch_name: str          # "" for the Founding chapter
    portrait_svg: str | None
    start_year: int
    end_year: int | None       # None = still reigning
    paragraphs: list[str]
    highlights: list[ChronicleHighlight]

@dataclass
class ChronicleBook:
    dynasty_name: str
    coat_of_arms_svg: str
    family_tree_svg: str | None
    chapters: list[ChronicleChapter]
    foreword: str = ""         # filled by 12-2
    epilogue: str = ""         # filled by 12-2
```

### Proposed importance weight table (tune freely)
| Weight | Event types |
|---|---|
| 10 | succession_crisis, civil_war, successful_assassination, dynasty_founding |
| 8 | battle, siege_success, succession_end, natural_disaster |
| 6 | peace_treaty, siege_start, siege_failure, failed_assassination |
| 5 | marriage, death, foundation |
| 4 | birth, building_completed, army_formation |
| 2 | military_recruitment, commander_assignment, reparations_paid, reparations_received |
| 1 | military_maintenance, military_maintenance_failure, character_events, generic_event |
*(Unknown event_type → default weight 3.)*

### 12-2 prompts (in `utils/llm_prompts.py`, ≤200 tokens each, deterministic fallback)
- `build_foreword_prompt(dynasty, first_3_paragraphs)` → a short framing foreword.
- `build_epilogue_prompt(dynasty, last_5_paragraphs, current_state)` → a closing reflection.
- Fallbacks: deterministic prose assembled from dynasty name + founding/current year (LLM-off must still produce a readable book).

### 12-3 book + PDF
- `templates/chronicle_book.html` — paginated reader extending `base.html`; cover (coat of arms + title), foreword, chapters (prose + per-chapter highlight callout box + monarch portrait), embedded `family_tree_svg`, epilogue.
- PDF export route (uses the `pdf` skill) producing a downloadable book.
- **"Compile Chronicle"** button on the left rail — always available (not end-game only).

## Notes / pre-existing gotchas
- `ChronicleEntryDB.game_id` == dynasty id in the current single-dynasty-per-game model; filter by `game_id=dynasty_id`.
- Compiler is pure read + assembly (no writes) → unit-testable without HTTP; 12-1 needs a `tests/unit/` test (chapter bucketing, highlight selection, Founding-chapter edge case, empty-history dynasty).
- Any future `ChronicleBook` persistence (caching compiled books) would be a schema change → use the Alembic workflow (Epic 11-2).

## Next step
Create story **12-1** from this design (`create story 12-1`), then 12-2, then 12-3. Epic 12 flips to in-progress on first story creation.
