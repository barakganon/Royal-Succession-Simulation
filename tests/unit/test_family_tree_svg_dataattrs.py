# tests/unit/test_family_tree_svg_dataattrs.py
# Story 8-2 (A) — Renderer data-* attributes.
#
# CONTRACT-FIRST unit tests written by Agent C in an isolated worktree.
#
# These tests pin the contract for the additive data-* attributes on the
# family-tree SVG renderer (visualization.family_tree_svg):
#   - EVERY person node <g> (including satellite in-married spouses) carries,
#     ALONGSIDE the existing data-person-id, the additional attributes
#     data-father-id, data-mother-id and data-spouse-id. The value is the id
#     when present, or an empty string ("") when the corresponding sim id is
#     None / absent.
#   - The change is purely additive: data-person-id and its count are unchanged,
#     so the number of 'data-person-id="' occurrences still equals the number of
#     persons rendered (monarch + spouse + child, etc.).
#
# Persons/dynasties are created directly via a real app/session using the shared
# app/db/session fixtures from tests/conftest.py, mirroring the person/dynasty
# creation in tests/integration/test_cross_dynasty_marriage.py.
#
# Some assertions WILL FAIL in this isolated worktree until the renderer is
# extended to emit data-father-id / data-mother-id / data-spouse-id (Agent A's
# work). That is EXPECTED and correct for a contract-first suite — do not weaken,
# stub, or skip them.

import re

import pytest

from models.db_models import User, DynastyDB, PersonDB
from visualization.family_tree_svg import generate_family_tree_svg

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror tests/integration/test_cross_dynasty_marriage.py)
# ---------------------------------------------------------------------------

def _create_user_and_dynasty(app, db, username, dynasty_name,
                             password="password123", is_ai=False):
    """Create a User + DynastyDB directly; return dynasty_id."""
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        dynasty = DynastyDB(
            user_id=user.id,
            name=dynasty_name,
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=500,
            start_year=1200,
            current_simulation_year=1230,
            prestige=10,
            is_ai_controlled=is_ai,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


def _add_person(app, db, dynasty_id, name, gender="MALE", birth_year=1200,
                death_year=None, is_noble=True, spouse_sim_id=None,
                father_sim_id=None, mother_sim_id=None, is_monarch=False,
                surname="House"):
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
            spouse_sim_id=spouse_sim_id,
            father_sim_id=father_sim_id,
            mother_sim_id=mother_sim_id,
            is_monarch=is_monarch,
        )
        db.session.add(person)
        db.session.commit()
        return person.id


def _set_person(app, db, person_id, **fields):
    """Update an existing PersonDB row in place."""
    with app.app_context():
        person = db.session.get(PersonDB, person_id)
        for key, value in fields.items():
            setattr(person, key, value)
        db.session.commit()


def _group_for(svg, person_id):
    """Return the opening <g ...> tag for the node carrying data-person-id={id}.

    The renderer emits each node as '<g data-person-id="{id}" ...>'; this finds
    that exact opening tag (up to the closing '>') so the data-* attributes on
    the same group can be asserted.
    """
    pattern = re.compile(r'<g\b[^>]*\bdata-person-id="' + str(person_id) + r'"[^>]*>')
    match = pattern.search(svg)
    assert match is not None, (
        f"no opening <g> with data-person-id=\"{person_id}\" found in SVG"
    )
    return match.group(0)


# ---------------------------------------------------------------------------
# A nuclear family inside ONE dynasty: monarch (father) + spouse (mother) +
# child. Used by several tests; returns the dynasty + person ids.
# ---------------------------------------------------------------------------

def _build_nuclear_family(app, db):
    did = _create_user_and_dynasty(app, db, "ftda_user", "House Tree")
    father_id = _add_person(app, db, did, "Father", gender="MALE",
                            birth_year=1180, is_monarch=True, surname="Tree")
    mother_id = _add_person(app, db, did, "Mother", gender="FEMALE",
                            birth_year=1185, surname="Tree")
    # Link the spouses to each other.
    _set_person(app, db, father_id, spouse_sim_id=mother_id)
    _set_person(app, db, mother_id, spouse_sim_id=father_id)
    # Child of both.
    child_id = _add_person(app, db, did, "Child", gender="MALE",
                           birth_year=1210, father_sim_id=father_id,
                           mother_sim_id=mother_id, surname="Tree")
    return did, father_id, mother_id, child_id


# ---------------------------------------------------------------------------
# 1. Output carries the three new data-* attribute names at all.
# ---------------------------------------------------------------------------

class TestDataAttrsPresent:
    def test_output_contains_all_three_data_attr_names(self, app, db, session):
        """Renderer output contains data-father-id, data-mother-id, data-spouse-id."""
        did, _, _, _ = _build_nuclear_family(app, db)
        with app.app_context():
            svg = generate_family_tree_svg(did, db.session)
        assert 'data-father-id' in svg
        assert 'data-mother-id' in svg
        assert 'data-spouse-id' in svg


# ---------------------------------------------------------------------------
# 2. A child's node carries its father/mother ids.
# ---------------------------------------------------------------------------

class TestChildParentAttrs:
    def test_child_group_has_parent_ids(self, app, db, session):
        """The child node's <g> carries data-father-id/data-mother-id matching its parents."""
        did, father_id, mother_id, child_id = _build_nuclear_family(app, db)
        with app.app_context():
            svg = generate_family_tree_svg(did, db.session)
        child_tag = _group_for(svg, child_id)
        assert f'data-father-id="{father_id}"' in child_tag, (
            f"child group missing father id; tag was: {child_tag}"
        )
        assert f'data-mother-id="{mother_id}"' in child_tag, (
            f"child group missing mother id; tag was: {child_tag}"
        )


# ---------------------------------------------------------------------------
# 3. A spouse's node carries data-spouse-id pointing at the partner.
# ---------------------------------------------------------------------------

class TestSpouseAttr:
    def test_spouse_group_has_partner_id(self, app, db, session):
        """Each spouse node has data-spouse-id set to the partner's id."""
        did, father_id, mother_id, _ = _build_nuclear_family(app, db)
        with app.app_context():
            svg = generate_family_tree_svg(did, db.session)
        father_tag = _group_for(svg, father_id)
        mother_tag = _group_for(svg, mother_id)
        assert f'data-spouse-id="{mother_id}"' in father_tag, (
            f"father group missing spouse id; tag was: {father_tag}"
        )
        assert f'data-spouse-id="{father_id}"' in mother_tag, (
            f"mother group missing spouse id; tag was: {mother_tag}"
        )

    def test_absent_parents_render_empty_string(self, app, db, session):
        """A root with no in-tree parents emits empty-string father/mother ids."""
        did, father_id, _, _ = _build_nuclear_family(app, db)
        with app.app_context():
            svg = generate_family_tree_svg(did, db.session)
        father_tag = _group_for(svg, father_id)
        # The monarch/root has no father_sim_id / mother_sim_id -> "".
        assert 'data-father-id=""' in father_tag, (
            f"root father group should have empty father id; tag was: {father_tag}"
        )
        assert 'data-mother-id=""' in father_tag, (
            f"root father group should have empty mother id; tag was: {father_tag}"
        )


# ---------------------------------------------------------------------------
# 4. Regression: data-person-id count == number of persons rendered.
# ---------------------------------------------------------------------------

class TestPersonIdCountRegression:
    def test_person_id_count_matches_rendered_persons(self, app, db, session):
        """Count of 'data-person-id="' equals the number of persons rendered.

        A single-dynasty nuclear family (monarch + spouse + child) renders all
        three persons as nodes, so the data-person-id count is exactly 3 — the
        additive data-* attrs must not change that count.
        """
        did, _, _, _ = _build_nuclear_family(app, db)
        with app.app_context():
            person_count = (
                db.session.query(PersonDB)
                .filter(PersonDB.dynasty_id == did)
                .count()
            )
            svg = generate_family_tree_svg(did, db.session)
        rendered = svg.count('data-person-id="')
        assert person_count == 3
        assert rendered == person_count, (
            f"expected {person_count} data-person-id occurrences, got {rendered}"
        )
