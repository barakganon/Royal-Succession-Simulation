# tests/unit/test_chronicle_compiler.py
"""Unit tests for models.chronicle_compiler."""
import uuid
import pytest
from models.db_models import db, DynastyDB, PersonDB, HistoryLogEntryDB, ChronicleEntryDB, User
from models.chronicle_compiler import compile_chronicle, MAX_HIGHLIGHTS_PER_CHAPTER


def _unique(base: str) -> str:
    return f"{base}_{uuid.uuid4().hex[:8]}"


def _make_dynasty(session, app, start_year: int = 1000) -> tuple[int, str]:
    """Create a minimal User + DynastyDB; return (dynasty_id, dynasty_name)."""
    with app.app_context():
        uname = _unique("cc_user")
        user = User(username=uname, email=f"{uname}@test.test")
        user.set_password("pw")
        session.add(user)
        session.flush()
        name = _unique("House")
        dynasty = DynastyDB(
            user_id=user.id,
            name=name,
            theme_identifier_or_json="medieval_europe",
            start_year=start_year,
            current_simulation_year=start_year,
        )
        session.add(dynasty)
        session.commit()
        return dynasty.id, dynasty.name


def _add_monarch(session, app, dynasty_id: int, dynasty_name: str, name: str,
                 reign_start: int, reign_end: int | None = None,
                 death_year: int | None = None) -> int:
    with app.app_context():
        person = PersonDB(
            dynasty_id=dynasty_id,
            name=name,
            surname=dynasty_name,
            gender='MALE',
            birth_year=reign_start - 20,
            is_noble=True,
            is_monarch=False,
            reign_start_year=reign_start,
            reign_end_year=reign_end,
            death_year=death_year,
        )
        session.add(person)
        session.commit()
        return person.id


def _add_chronicle_entry(session, app, dynasty_id: int, year: int, turn: int, text: str):
    with app.app_context():
        entry = ChronicleEntryDB(game_id=dynasty_id, turn=turn, year=year, text=text)
        session.add(entry)
        session.commit()


def _add_history_log(session, app, dynasty_id: int, year: int, event_type: str, text: str):
    with app.app_context():
        log = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=year,
            event_string=text,
            event_type=event_type,
        )
        session.add(log)
        session.commit()


@pytest.mark.unit
class TestCompileChronicleBasic:

    def test_nonexistent_dynasty_returns_none(self, session, app):
        with app.app_context():
            result = compile_chronicle(999999999)
        assert result is None

    def test_empty_history_dynasty_no_crash(self, session, app):
        """Dynasty with monarchs but no chronicle/history entries returns book with empty lists."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1100)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Alfred", reign_start=1100)
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        assert book.dynasty_name == dynasty_name
        assert len(book.chapters) >= 1
        for ch in book.chapters:
            assert ch.paragraphs == []
            assert ch.highlights == []

    def test_multi_monarch_chapter_count(self, session, app):
        """Three monarchs → three chapters (no founding chapter if no early prose)."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000, reign_end=1020)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Bertram", reign_start=1020, reign_end=1045)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Cecily", reign_start=1045)
        # Chronicle entry starting at first reign — no founding chapter
        _add_chronicle_entry(session, app, dynasty_id, 1000, 1, "The dynasty rises.")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        assert len(book.chapters) == 3
        names = [ch.monarch_name for ch in book.chapters]
        assert any("Aldric" in n for n in names)
        assert any("Bertram" in n for n in names)
        assert any("Cecily" in n for n in names)

    def test_paragraph_bucketed_into_correct_chapter(self, session, app):
        """Chronicle entries are bucketed into the monarch chapter that covers their year."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000, reign_end=1019)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Bertram", reign_start=1020)
        _add_chronicle_entry(session, app, dynasty_id, 1005, 1, "Aldric's tale.")
        _add_chronicle_entry(session, app, dynasty_id, 1025, 2, "Bertram's tale.")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        ch0 = next(ch for ch in book.chapters if "Aldric" in ch.monarch_name)
        ch1 = next(ch for ch in book.chapters if "Bertram" in ch.monarch_name)
        assert "Aldric's tale." in ch0.paragraphs
        assert "Bertram's tale." in ch1.paragraphs
        assert "Bertram's tale." not in ch0.paragraphs
        assert "Aldric's tale." not in ch1.paragraphs


@pytest.mark.unit
class TestYearlessHistoryLog:

    def test_yearless_history_log_excluded_without_crash(self, session, app):
        """HistoryLogEntryDB.year is nullable (system messages); such events must be
        skipped as highlights, not crash with a None < int comparison."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000)
        _add_history_log(session, app, dynasty_id, None, "generic_event", "A system message.")
        _add_history_log(session, app, dynasty_id, 1005, "battle", "A real battle.")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        all_highlights = [h for ch in book.chapters for h in ch.highlights]
        texts = [h.text for h in all_highlights]
        assert "A real battle." in texts
        assert "A system message." not in texts


@pytest.mark.unit
class TestFoundingChapter:

    def test_founding_chapter_emitted_when_early_prose_exists(self, session, app):
        """If chronicle entries predate first monarch's reign, a founding chapter is prepended."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1010)
        _add_chronicle_entry(session, app, dynasty_id, 1005, 1, "Before the reign.")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        assert len(book.chapters) == 2
        founding = book.chapters[0]
        assert founding.monarch_name == ""
        assert founding.start_year == 1000
        assert founding.end_year == 1009
        assert "Before the reign." in founding.paragraphs

    def test_founding_chapter_omitted_when_no_early_prose(self, session, app):
        """If no chronicle entries predate first monarch's reign, no founding chapter."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000)
        _add_chronicle_entry(session, app, dynasty_id, 1000, 1, "The reign begins.")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        assert len(book.chapters) == 1
        assert book.chapters[0].monarch_name != ""


@pytest.mark.unit
class TestHighlightRanking:

    def test_highlights_capped_at_max(self, session, app):
        """More than MAX highlights in a chapter → only top MAX kept."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000)
        for i in range(MAX_HIGHLIGHTS_PER_CHAPTER + 3):
            _add_history_log(session, app, dynasty_id, 1000 + i, "birth", f"Event {i}")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        assert len(book.chapters) >= 1
        for ch in book.chapters:
            assert len(ch.highlights) <= MAX_HIGHLIGHTS_PER_CHAPTER

    def test_high_weight_events_kept_over_low_weight(self, session, app):
        """civil_war (weight 10) beats military_maintenance (weight 1) under cap."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000)
        for i in range(MAX_HIGHLIGHTS_PER_CHAPTER + 2):
            _add_history_log(session, app, dynasty_id, 1001, "military_maintenance", f"Maintenance {i}")
        _add_history_log(session, app, dynasty_id, 1002, "civil_war", "Civil war erupts!")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        chapter = book.chapters[0]
        highlight_types = [h.event_type for h in chapter.highlights]
        assert "civil_war" in highlight_types

    def test_highlights_sorted_by_year_ascending(self, session, app):
        """Kept highlights are returned sorted by year ascending."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000)
        _add_history_log(session, app, dynasty_id, 1010, "battle", "Late battle")
        _add_history_log(session, app, dynasty_id, 1001, "battle", "Early battle")
        _add_history_log(session, app, dynasty_id, 1005, "marriage", "Mid marriage")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        chapter = book.chapters[0]
        years = [h.year for h in chapter.highlights]
        assert years == sorted(years)

    def test_highlight_weight_assignment(self, session, app):
        """Verify weights: civil_war=10, battle=8, unknown defaults to 3."""
        dynasty_id, dynasty_name = _make_dynasty(session, app, start_year=1000)
        _add_monarch(session, app, dynasty_id, dynasty_name, "Aldric", reign_start=1000)
        _add_history_log(session, app, dynasty_id, 1001, "civil_war", "Civil war")
        _add_history_log(session, app, dynasty_id, 1002, "battle", "Battle")
        _add_history_log(session, app, dynasty_id, 1003, "unknown_custom", "Custom event")
        with app.app_context():
            book = compile_chronicle(dynasty_id)
        assert book is not None
        chapter = book.chapters[0]
        weights_by_type = {h.event_type: h.weight for h in chapter.highlights}
        assert weights_by_type.get("civil_war") == 10
        assert weights_by_type.get("battle") == 8
        assert weights_by_type.get("unknown_custom") == 3
