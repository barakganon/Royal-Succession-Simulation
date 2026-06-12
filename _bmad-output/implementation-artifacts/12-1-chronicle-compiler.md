# Story 12-1: Chronicle Compiler

Status: ready-for-dev

## Story
As a **player who has built a dynasty saga over many turns**,
I want **the accumulated narrative and events compiled into a structured, reign-by-reign Chronicle book object**,
so that **it can be rendered as a keepable on-screen book and PDF (Stories 12-2/12-3).**

## Context
The per-turn LLM narration already accumulates as `ChronicleEntryDB` rows (and the mirrored `DynastyDB.epic_story_text`). Structured events accumulate as `HistoryLogEntryDB`. This story adds a **pure read + assembly** module that turns those into a `ChronicleBook` dataclass organized into chapters by monarch reign, with weighted event highlights per chapter. No LLM, no DB writes, no schema change. Design locked in `_bmad-output/implementation-artifacts/epic-12-design.md` (prose ← ChronicleEntryDB; deterministic weighted highlights; per-chapter callout layout).

## Acceptance Criteria

1. **AC1 — Module + dataclasses.** Create `models/chronicle_compiler.py` with three dataclasses and one public function:
   ```python
   @dataclass
   class ChronicleHighlight:
       year: int
       event_type: str
       text: str          # from HistoryLogEntryDB.event_string
       weight: int

   @dataclass
   class ChronicleChapter:
       monarch_name: str          # "" for the Founding chapter
       portrait_svg: str | None
       start_year: int
       end_year: int | None       # None = monarch still reigning / open chapter
       paragraphs: list[str]
       highlights: list[ChronicleHighlight]

   @dataclass
   class ChronicleBook:
       dynasty_name: str
       coat_of_arms_svg: str
       family_tree_svg: str | None
       chapters: list[ChronicleChapter]
       foreword: str = ""         # filled by Story 12-2
       epilogue: str = ""         # filled by Story 12-2

   def compile_chronicle(dynasty_id: int) -> ChronicleBook | None: ...
   ```
   Returns `None` if the dynasty doesn't exist (load via `db.session.get(DynastyDB, dynasty_id)`).

2. **AC2 — Chapters from reigns (critical gotcha).** Build chapters from **all monarchs past and present** by querying `PersonDB.query.filter(PersonDB.dynasty_id == dynasty_id, PersonDB.reign_start_year.isnot(None)).order_by(PersonDB.reign_start_year)`. **Do NOT filter on `is_monarch == True`** — `is_monarch` means *currently* reigning, so it returns only one person and would drop every past chapter. Each monarch → one `ChronicleChapter` with `start_year = reign_start_year`, `end_year = reign_end_year` (may be None for the sitting monarch). If two monarchs share/overlap years, order by `reign_start_year` then `id`.

3. **AC3 — Founding chapter.** Prepend a chapter with `monarch_name = ""`, `portrait_svg = None`, `start_year = dynasty.start_year`, `end_year =` (first monarch's `reign_start_year` − 1, or None if no monarchs) for any paragraphs/events dated before the first monarch's `reign_start_year`. If nothing predates the first reign, omit the Founding chapter (don't emit an empty one).

4. **AC4 — Prose bucketing.** Load paragraphs from `ChronicleEntryDB.query.filter_by(game_id=dynasty_id).order_by(ChronicleEntryDB.year, ChronicleEntryDB.turn)` (note: the column is `game_id`, which equals the dynasty id in this single-dynasty-per-game model). Assign each paragraph's `text` to the chapter whose `[start_year, end_year]` range contains `paragraph.year` (a paragraph at/after the last open chapter's start goes to that chapter). Every paragraph must land in exactly one chapter (no drops, no dupes).

5. **AC5 — Weighted highlights.** Load `HistoryLogEntryDB.query.filter_by(dynasty_id=dynasty_id)`. Score each by an `event_type → weight` table (module constant `EVENT_WEIGHTS`); unknown type → default weight 3. Assign events to chapters by `year` (same bucketing as paragraphs), then keep the **top 5 per chapter** by weight (tie-break: higher year first, then id). Each kept event → `ChronicleHighlight(year, event_type, text=event_string, weight)`, sorted within the chapter by `year` ascending for display. Make the top-N a module constant `MAX_HIGHLIGHTS_PER_CHAPTER = 5`.
   - `EVENT_WEIGHTS` (from the design note — keep as a tunable dict):
     `10`: succession_crisis, civil_war, successful_assassination, dynasty_founding ·
     `8`: battle, siege_success, succession_end, natural_disaster ·
     `6`: peace_treaty, siege_start, siege_failure, failed_assassination ·
     `5`: marriage, death, foundation ·
     `4`: birth, building_completed, army_formation ·
     `2`: military_recruitment, commander_assignment, reparations_paid, reparations_received ·
     `1`: military_maintenance, military_maintenance_failure, character_events, generic_event.

6. **AC6 — Book assembly.** Populate `ChronicleBook` with `dynasty.name`, `dynasty.coat_of_arms_svg or ""`, `dynasty.family_tree_svg` (may be None), and the ordered chapters (Founding first if present, then reigns by start_year). `foreword`/`epilogue` left `""` (Story 12-2). No DB writes anywhere in this module.

7. **AC7 — Unit tests.** `tests/unit/test_chronicle_compiler.py` covering: (a) multi-monarch dynasty → correct chapter count + paragraph/highlight bucketing by year; (b) Founding-chapter emitted when early paragraphs predate first reign, and omitted when they don't; (c) top-N highlight cap + weight ordering (e.g. a `civil_war` outranks `military_maintenance`); (d) empty-history dynasty (no chronicle entries, no events) → book with chapters but empty paragraphs/highlights, no crash; (e) `compile_chronicle(nonexistent_id)` → None. Use the existing unit-test fixtures/patterns; no HTTP.

8. **AC8 — No regressions.** Full suite green (baseline **536 passed, 0 failed, 0 skipped**) plus the new tests. `python -c "import main_flask_app"` clean. No new dependencies, no schema change, no migration.

## Tasks
- [ ] Task 1 — `models/chronicle_compiler.py`: dataclasses + `EVENT_WEIGHTS`/`MAX_HIGHLIGHTS_PER_CHAPTER` constants (AC1, AC5).
- [ ] Task 2 — `compile_chronicle()`: load dynasty (`session.get`), build reign chapters (AC2) + Founding (AC3).
- [ ] Task 3 — bucket prose (AC4) and weighted highlights (AC5) into chapters; assemble book (AC6).
- [ ] Task 4 — `tests/unit/test_chronicle_compiler.py` (AC7).
- [ ] Task 5 — `pytest` 536+new green; import clean (AC8).

## Dev Notes
- **Pure read + assembly module** — module-level functions (mirrors `models/turn_processor.py`), NOT a session-taking subsystem class. No `db.session.add/commit/delete` anywhere.
- **SA 2.0 conventions (Epic 11):** use `db.session.get(DynastyDB, dynasty_id)` for PK loads and `Model.query.filter_by(...)` for collections. Do not use legacy `Query.get()`/`get_or_404` (none needed here anyway).
- **Logger:** `logger = logging.getLogger('royal_succession.chronicle_compiler')`. No `print()`.
- **The reign gotcha (AC2) is the #1 mistake to avoid:** `is_monarch` is "currently reigning" — past monarchs have `is_monarch == False` but non-null `reign_start_year`/`reign_end_year`. Chapter source = `reign_start_year IS NOT NULL`, not `is_monarch`.
- **`ChronicleEntryDB.game_id`** is the dynasty id here (FK → dynasty.id; "one per turn per game"; single dynasty per game). Filter `game_id=dynasty_id`.
- Imports available from `models.db_models`: `db, DynastyDB, PersonDB, HistoryLogEntryDB, ChronicleEntryDB`.
- This is a self-contained backend story → implement as a **single Sonnet subagent on live `main` (no worktree)** per the Epic 11 retro policy.
- Out of scope: foreword/epilogue prompts (12-2), book template + PDF + left-rail button (12-3), any caching/persistence of compiled books (would be a schema change → Alembic).

## References
- Design: `_bmad-output/implementation-artifacts/epic-12-design.md`.
- `models/db_models.py`: `ChronicleEntryDB` (game_id, turn, year, text), `HistoryLogEntryDB` (dynasty_id, year, event_string, event_type), `PersonDB` (is_monarch, reign_start_year, reign_end_year, name, portrait_svg), `DynastyDB` (name, start_year, coat_of_arms_svg, family_tree_svg).
- Existing query pattern: `blueprints/map.py:857` (`ChronicleEntryDB.query.filter_by(game_id=dynasty_id)`).
- Event types observed across `models/` + `blueprints/` (the ~30 in `EVENT_WEIGHTS`).

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-12 | spec(12-1); chronicle compiler — reign chapters + weighted highlights (ready-for-dev) |
