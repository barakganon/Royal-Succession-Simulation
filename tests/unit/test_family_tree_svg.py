# tests/unit/test_family_tree_svg.py
# Story 8-1 (Family-tree SVG renderer) — CONTRACT-FIRST unit tests written by
# Agent C in an isolated worktree.
#
# These tests pin the frozen interface contract for the NEW renderer
# visualization/family_tree_svg.py:
#
#   generate_family_tree_svg(dynasty_id: int, session,
#                            current_year: int | None = None,
#                            show_deceased: bool = True) -> str
#
#   - Mirrors visualization/map_renderer.py generate_geojson(dynasty_id, session):
#     queries via session.query(PersonDB)... (NOT bare PersonDB.query).
#   - Returns ONE complete SVG string: startswith '<svg', endswith '</svg>',
#     includes xmlns="http://www.w3.org/2000/svg".
#   - Deterministic (no random, or seeded by dynasty_id) => identical data
#     yields identical output.
#   - One <g data-person-id="{id}"> node per rendered person; crown mark for
#     is_monarch; marriage edge between spouses; DASHED edge (stroke-dasharray)
#     for a cross-dynasty spouse.
#   - show_deceased=False omits dead people; default True includes them.
#   - Empty dynasty => minimal valid SVG, never raises.
#
# The renderer does NOT exist in this worktree (the backend agent builds it),
# so these tests will fail to import / collect here. That is EXPECTED for a
# contract-first suite — do not weaken, stub, or skip them.

import pytest

from models.db_models import User, DynastyDB, PersonDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# A marriageable-age suitor in year 1230 is born in 1200 (age 30).
SUITOR_BIRTH_YEAR = 1200


# ---------------------------------------------------------------------------
# Helpers (mirror tests/integration/test_cross_dynasty_marriage.py)
# ---------------------------------------------------------------------------

def _import_renderer():
    """Import the renderer lazily so collection errors surface per-test rather
    than at module import (keeps the file syntactically importable even before
    the backend agent writes visualization/family_tree_svg.py)."""
    from visualization.family_tree_svg import generate_family_tree_svg
    return generate_family_tree_svg


def _create_user_and_dynasty(app, db, username, dynasty_name,
                             current_simulation_year=1230, is_ai=False):
    """Create a User + DynastyDB directly; return dynasty_id."""
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        dynasty = DynastyDB(
            user_id=user.id,
            name=dynasty_name,
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=500,
            start_year=1200,
            current_simulation_year=current_simulation_year,
            prestige=10,
            is_ai_controlled=is_ai,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


def _add_person(app, db, dynasty_id, name, gender="MALE",
                birth_year=SUITOR_BIRTH_YEAR, death_year=None, is_noble=True,
                is_monarch=False, spouse_sim_id=None, mother_sim_id=None,
                father_sim_id=None, surname="House"):
    """Add a PersonDB; return its id."""
    with app.app_context():
        person = PersonDB(
            dynasty_id=dynasty_id,
            name=name,
            surname=surname,
            gender=gender,
            birth_year=birth_year,
            death_year=death_year,
            is_noble=is_noble,
            is_monarch=is_monarch,
            spouse_sim_id=spouse_sim_id,
            mother_sim_id=mother_sim_id,
            father_sim_id=father_sim_id,
        )
        db.session.add(person)
        db.session.commit()
        return person.id


def _link_spouses(app, db, a_id, b_id):
    """Set spouse_sim_id both ways for a couple."""
    with app.app_context():
        a = db.session.get(PersonDB, a_id)
        b = db.session.get(PersonDB, b_id)
        a.spouse_sim_id = b_id
        b.spouse_sim_id = a_id
        db.session.commit()


def _render(app, db, dynasty_id, **kwargs):
    """Call the renderer inside an app context, passing the live session."""
    generate_family_tree_svg = _import_renderer()
    with app.app_context():
        return generate_family_tree_svg(dynasty_id, db.session, **kwargs)


# ---------------------------------------------------------------------------
# 1. Well-formed SVG envelope
# ---------------------------------------------------------------------------

class TestSvgEnvelope:
    def test_output_is_well_formed_svg(self, app, db, session):
        """Output starts with '<svg', ends with '</svg>', declares the SVG namespace."""
        did = _create_user_and_dynasty(app, db, "fts_env", "House Envelope")
        _add_person(app, db, did, "Founder", gender="MALE",
                    is_monarch=True, surname="Envelope")

        svg = _render(app, db, did)

        assert isinstance(svg, str)
        assert svg.startswith('<svg'), "SVG must start with '<svg'"
        assert svg.rstrip().endswith('</svg>'), "SVG must end with '</svg>'"
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert 'viewBox' in svg


# ---------------------------------------------------------------------------
# 2. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_two_calls_identical_data_identical_output(self, app, db, session):
        """Two renders of the same dynasty data produce byte-identical strings (no random)."""
        did = _create_user_and_dynasty(app, db, "fts_det", "House Determinism")
        dad = _add_person(app, db, did, "Father", gender="MALE",
                          is_monarch=True, surname="Determinism")
        mom = _add_person(app, db, did, "Mother", gender="FEMALE",
                          surname="Determinism")
        _link_spouses(app, db, dad, mom)
        _add_person(app, db, did, "Child", gender="MALE",
                    birth_year=1225, father_sim_id=dad, mother_sim_id=mom,
                    surname="Determinism")

        first = _render(app, db, did)
        second = _render(app, db, did)

        assert first == second, "renderer must be deterministic for identical data"


# ---------------------------------------------------------------------------
# 3. One node per living person
# ---------------------------------------------------------------------------

class TestOneNodePerPerson:
    def test_node_count_matches_person_count(self, app, db, session):
        """Each person's name appears and there is exactly one data-person-id per rendered person."""
        did = _create_user_and_dynasty(app, db, "fts_nodes", "House Nodes")
        dad = _add_person(app, db, did, "Aldric", gender="MALE",
                          is_monarch=True, surname="Nodes")
        mom = _add_person(app, db, did, "Beatrix", gender="FEMALE",
                          surname="Nodes")
        _link_spouses(app, db, dad, mom)
        _add_person(app, db, did, "Cedric", gender="MALE", birth_year=1224,
                    father_sim_id=dad, mother_sim_id=mom, surname="Nodes")
        _add_person(app, db, did, "Dahlia", gender="FEMALE", birth_year=1226,
                    father_sim_id=dad, mother_sim_id=mom, surname="Nodes")

        svg = _render(app, db, did)

        # All four living members are present.
        for nm in ("Aldric", "Beatrix", "Cedric", "Dahlia"):
            assert nm in svg, f"expected name {nm!r} in rendered SVG"

        # Exactly one node per rendered person (4 living persons).
        assert svg.count('data-person-id') == 4


# ---------------------------------------------------------------------------
# 4. Crown mark only for monarchs
# ---------------------------------------------------------------------------

class TestMonarchCrown:
    # The crown is rendered as a crown emoji <text> or a small gold polygon;
    # either way the gold crown palette colour distinguishes a monarch node.
    CROWN_MARKERS = ('\U0001F451', 'crown', 'Crown', '#d4af37', '#ffd700',
                     '#FFD700', '#gold', 'gold')

    def _has_crown(self, svg):
        return any(marker in svg for marker in self.CROWN_MARKERS)

    def test_monarch_dynasty_shows_crown(self, app, db, session):
        """A dynasty containing a monarch renders a crown mark."""
        did = _create_user_and_dynasty(app, db, "fts_crown", "House Crowned")
        _add_person(app, db, did, "King", gender="MALE",
                    is_monarch=True, surname="Crowned")

        svg = _render(app, db, did)
        assert self._has_crown(svg), "monarch node must carry a crown mark"

    def test_no_monarch_dynasty_omits_crown(self, app, db, session):
        """A dynasty with no monarch does NOT render the crown mark."""
        did = _create_user_and_dynasty(app, db, "fts_nocrown", "House Commoner")
        _add_person(app, db, did, "Peasant", gender="MALE",
                    is_monarch=False, surname="Commoner")
        _add_person(app, db, did, "Goodwife", gender="FEMALE",
                    is_monarch=False, surname="Commoner")

        svg = _render(app, db, did)
        assert not self._has_crown(svg), (
            "no crown mark should appear when the dynasty has no monarch")


# ---------------------------------------------------------------------------
# 5. Marriage edges (same-dynasty solid, cross-dynasty dashed)
# ---------------------------------------------------------------------------

class TestMarriageEdges:
    def test_same_dynasty_couple_draws_marriage_edge(self, app, db, session):
        """A married same-dynasty couple yields a marriage edge (a <line>/<path> connecting them)."""
        did = _create_user_and_dynasty(app, db, "fts_marr", "House Married")
        husband = _add_person(app, db, did, "Husband", gender="MALE",
                              is_monarch=True, surname="Married")
        wife = _add_person(app, db, did, "Wife", gender="FEMALE",
                           surname="Married")
        _link_spouses(app, db, husband, wife)

        svg = _render(app, db, did)

        # A marriage edge is drawn (line or path elements present beneath nodes).
        assert ('<line' in svg) or ('<path' in svg), (
            "a married couple must produce a marriage edge")

    def test_cross_dynasty_spouse_draws_dashed_edge(self, app, db, session):
        """A spouse in a DIFFERENT dynasty yields a DASHED marriage edge (stroke-dasharray)."""
        did_a = _create_user_and_dynasty(app, db, "fts_cd_a", "House CrossA")
        did_b = _create_user_and_dynasty(app, db, "fts_cd_b", "House CrossB")
        groom = _add_person(app, db, did_a, "Groom", gender="MALE",
                            is_monarch=True, surname="CrossA")
        bride = _add_person(app, db, did_b, "Bride", gender="FEMALE",
                            surname="CrossB")
        _link_spouses(app, db, groom, bride)

        # Render dynasty A: its monarch is married to a bride in dynasty B.
        svg = _render(app, db, did_a)

        assert 'stroke-dasharray' in svg, (
            "a cross-dynasty marriage edge must be dashed (stroke-dasharray)")


# ---------------------------------------------------------------------------
# 6. show_deceased toggling
# ---------------------------------------------------------------------------

class TestShowDeceased:
    def test_show_deceased_false_omits_dead_person(self, app, db, session):
        """show_deceased=False omits a dead person; default True includes them."""
        did = _create_user_and_dynasty(app, db, "fts_dead", "House Mortal")
        _add_person(app, db, did, "Livia", gender="FEMALE",
                    is_monarch=True, surname="Mortal")
        _add_person(app, db, did, "Mortimer", gender="MALE",
                    birth_year=1190, death_year=1225, surname="Mortal")

        shown = _render(app, db, did, show_deceased=True)
        hidden = _render(app, db, did, show_deceased=False)

        assert "Mortimer" in shown, "deceased person should appear when show_deceased=True"
        assert "Mortimer" not in hidden, "deceased person must be omitted when show_deceased=False"
        # The living monarch is present in both.
        assert "Livia" in shown
        assert "Livia" in hidden


# ---------------------------------------------------------------------------
# 7. Empty dynasty => minimal valid SVG, never raises
# ---------------------------------------------------------------------------

class TestEmptyDynasty:
    def test_empty_dynasty_returns_minimal_valid_svg(self, app, db, session):
        """A dynasty with no persons renders a minimal valid SVG without raising."""
        did = _create_user_and_dynasty(app, db, "fts_empty", "House Empty")

        svg = _render(app, db, did)

        assert isinstance(svg, str)
        assert svg.startswith('<svg')
        assert svg.rstrip().endswith('</svg>')
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert 'data-person-id' not in svg, "no person nodes for an empty dynasty"
