"""Chronicle compiler: assembles a ChronicleBook from DB data for a dynasty."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from models.db_models import db, DynastyDB, PersonDB, HistoryLogEntryDB, ChronicleEntryDB

logger = logging.getLogger('royal_succession.chronicle_compiler')

MAX_HIGHLIGHTS_PER_CHAPTER = 5

EVENT_WEIGHTS: dict[str, int] = {
    # weight 10
    'succession_crisis': 10,
    'civil_war': 10,
    'successful_assassination': 10,
    'dynasty_founding': 10,
    # weight 8
    'battle': 8,
    'siege_success': 8,
    'succession_end': 8,
    'natural_disaster': 8,
    # weight 6
    'peace_treaty': 6,
    'siege_start': 6,
    'siege_failure': 6,
    'failed_assassination': 6,
    # weight 5
    'marriage': 5,
    'death': 5,
    'foundation': 5,
    # weight 4
    'birth': 4,
    'building_completed': 4,
    'army_formation': 4,
    # weight 2
    'military_recruitment': 2,
    'commander_assignment': 2,
    'reparations_paid': 2,
    'reparations_received': 2,
    # weight 1
    'military_maintenance': 1,
    'military_maintenance_failure': 1,
    'character_events': 1,
    'generic_event': 1,
}

DEFAULT_WEIGHT = 3


@dataclass
class ChronicleHighlight:
    year: int
    event_type: str
    text: str
    weight: int


@dataclass
class ChronicleChapter:
    monarch_name: str
    portrait_svg: str | None
    start_year: int
    end_year: int | None
    paragraphs: list[str] = field(default_factory=list)
    highlights: list[ChronicleHighlight] = field(default_factory=list)


@dataclass
class ChronicleBook:
    dynasty_name: str
    coat_of_arms_svg: str
    family_tree_svg: str | None
    chapters: list[ChronicleChapter] = field(default_factory=list)
    foreword: str = ""
    epilogue: str = ""


def _year_in_chapter(year: int, chapter: ChronicleChapter) -> bool:
    """Return True if year falls within [chapter.start_year, chapter.end_year] (inclusive)."""
    if year < chapter.start_year:
        return False
    if chapter.end_year is None:
        return True
    return year <= chapter.end_year


def compile_chronicle(dynasty_id: int) -> ChronicleBook | None:
    """Compile a ChronicleBook for the given dynasty, or None if dynasty not found."""
    dynasty = db.session.get(DynastyDB, dynasty_id)
    if dynasty is None:
        logger.warning("compile_chronicle: dynasty %s not found", dynasty_id)
        return None

    # --- Build monarch chapters ---
    monarchs = (
        PersonDB.query
        .filter(
            PersonDB.dynasty_id == dynasty_id,
            PersonDB.reign_start_year.isnot(None),
        )
        .order_by(PersonDB.reign_start_year, PersonDB.id)
        .all()
    )

    chapters: list[ChronicleChapter] = []
    for m in monarchs:
        end_year = m.reign_end_year if m.reign_end_year is not None else m.death_year
        chapters.append(ChronicleChapter(
            monarch_name=f"{m.name} {m.surname}".strip() if m.surname else m.name,
            portrait_svg=m.portrait_svg if hasattr(m, 'portrait_svg') else None,
            start_year=m.reign_start_year,
            end_year=end_year,
        ))

    # --- Prose (ChronicleEntryDB) ---
    entries = (
        ChronicleEntryDB.query
        .filter_by(game_id=dynasty_id)
        .order_by(ChronicleEntryDB.year, ChronicleEntryDB.turn)
        .all()
    )

    # Determine whether a Founding chapter is needed
    first_reign_start = monarchs[0].reign_start_year if monarchs else None
    needs_founding = first_reign_start is not None and any(
        e.year < first_reign_start for e in entries
    )

    if needs_founding:
        founding_end = first_reign_start - 1 if first_reign_start is not None else None
        founding = ChronicleChapter(
            monarch_name="",
            portrait_svg=None,
            start_year=dynasty.start_year,
            end_year=founding_end,
        )
        chapters = [founding] + chapters

    # Bucket prose into chapters
    for entry in entries:
        for chapter in chapters:
            if _year_in_chapter(entry.year, chapter):
                chapter.paragraphs.append(entry.text)
                break
        else:
            # Doesn't fit any chapter — append to last if available
            if chapters:
                chapters[-1].paragraphs.append(entry.text)

    # --- Highlights (HistoryLogEntryDB) ---
    history_logs = HistoryLogEntryDB.query.filter_by(dynasty_id=dynasty_id).all()

    # Collect all highlights per chapter index
    chapter_highlight_candidates: list[list[ChronicleHighlight]] = [[] for _ in chapters]

    for log in history_logs:
        weight = EVENT_WEIGHTS.get(log.event_type or '', DEFAULT_WEIGHT)
        highlight = ChronicleHighlight(
            year=log.year,
            event_type=log.event_type or '',
            text=log.event_string,
            weight=weight,
        )
        for idx, chapter in enumerate(chapters):
            if _year_in_chapter(log.year, chapter):
                chapter_highlight_candidates[idx].append(highlight)
                break
        else:
            if chapters:
                chapter_highlight_candidates[-1].append(highlight)

    # Keep top MAX_HIGHLIGHTS_PER_CHAPTER per chapter, then sort by year ascending
    for idx, chapter in enumerate(chapters):
        candidates = chapter_highlight_candidates[idx]
        # Sort descending by weight, then by year desc, then by id desc (tie-break)
        candidates.sort(key=lambda h: (h.weight, h.year), reverse=True)
        top = candidates[:MAX_HIGHLIGHTS_PER_CHAPTER]
        # Sort kept highlights by year ascending
        top.sort(key=lambda h: h.year)
        chapter.highlights = top

    coat_of_arms = dynasty.coat_of_arms_svg or ""
    family_tree = getattr(dynasty, 'family_tree_svg', None)

    logger.info(
        "compile_chronicle: compiled %d chapters for dynasty %s (%s)",
        len(chapters), dynasty_id, dynasty.name,
    )
    return ChronicleBook(
        dynasty_name=dynasty.name,
        coat_of_arms_svg=coat_of_arms,
        family_tree_svg=family_tree,
        chapters=chapters,
    )
