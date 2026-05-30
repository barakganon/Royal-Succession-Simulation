# tests/integration/test_building_gates.py
# Story 6-2 — CONTRACT-FIRST tests (Agent C / TESTS).
#
# Three contracts under test (built by sibling agents A and B):
#   1. Building gate: ProjectSystem.start_project for a project whose catalogue
#      entry has requires_building set (e.g. 'recruit_cavalry' → 'Stables') is
#      REJECTED unless the dynasty controls a Territory with the required
#      Building. Rejection = no Project row created AND cost not charged.
#      Non-gated projects (recruit_infantry / build_farm) start regardless.
#   2. Sickly lifespan: process_death_check halves max_age (~42) and doubles
#      base_mortality for a 'Sickly' person. A Sickly person aged ~50 dies;
#      an identical non-Sickly person aged 50 (random.random patched high)
#      survives.
#   3. Trait inheritance: process_childbirth_check gives the child up to 3
#      inherited parent traits (each at <0.30 prob) + 1 themed random trait.
#
# These tests are EXPECTED TO FAIL in isolation until the gate / Sickly effect /
# inheritance logic ships. They must collect cleanly and exercise the real
# contract — no stubs, no skips, no weakening.

import pytest

from models.db_models import (
    Building, BuildingType, DynastyDB, PersonDB,
    Project, Region, Province, Territory, TerrainType, User,
)
from models.project_system import ProjectSystem, InsufficientResourcesError
from models import turn_processor as tp
from utils.theme_manager import get_theme

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# State builders — all run inside an app.app_context() supplied by the caller.
# ---------------------------------------------------------------------------
def _make_user(db, username):
    user = User(username=username, email=f"{username}@example.com")
    user.set_password("bgpass123")
    db.session.add(user)
    db.session.commit()
    return user


def _make_dynasty_monarch_territory(db, user, *, start_year=1300,
                                    wealth=500, iron=200, timber=200):
    """Create a dynasty with a living monarch and one controlled territory."""
    dynasty = DynastyDB(
        user_id=user.id,
        name="House Gate",
        theme_identifier_or_json=VALID_THEME_KEY,
        current_wealth=wealth,
        current_iron=iron,
        current_timber=timber,
        start_year=start_year,
        current_simulation_year=start_year,
    )
    db.session.add(dynasty)
    db.session.commit()

    monarch = PersonDB(
        dynasty_id=dynasty.id, name="Aldric", surname="Gate",
        gender="MALE", birth_year=start_year - 30,
        is_noble=True, is_monarch=True, reign_start_year=start_year,
    )
    db.session.add(monarch)

    region = Region(name="Gate Region", description="x")
    db.session.add(region)
    db.session.commit()
    province = Province(
        region_id=region.id, name="Gate Province",
        primary_terrain=TerrainType.PLAINS,
    )
    db.session.add(province)
    db.session.commit()
    territory = Territory(
        province_id=province.id, name="Gate Hold",
        terrain_type=TerrainType.PLAINS,
        x_coordinate=0.0, y_coordinate=0.0,
        controller_dynasty_id=dynasty.id,
        development_level=2,
    )
    db.session.add(territory)
    db.session.commit()
    return dynasty.id, monarch.id, territory.id


def _add_stables(db, territory_id):
    """Attach a Stables building to a territory.

    Built with BOTH BuildingType.STABLE and name='Stables' so the gate can
    match on either the enum type or the catalogue's 'Stables' label.
    """
    stables = Building(
        territory_id=territory_id,
        building_type=BuildingType.STABLE,
        name='Stables',
        level=1,
        condition=1.0,
        construction_year=1300,
    )
    db.session.add(stables)
    db.session.commit()
    return stables.id


# ===========================================================================
# Contract 1 — building gate on start_project
# ===========================================================================
class TestBuildingGate:
    def test_recruit_cavalry_rejected_without_stables(self, app, db, session):
        """recruit_cavalry is rejected when no controlled territory has Stables."""
        with app.app_context():
            user = _make_user(db, "bg_user_cav_no")
            dynasty_id, _, territory_id = _make_dynasty_monarch_territory(db, user)
            wealth_before = db.session.get(DynastyDB, dynasty_id).current_wealth
            iron_before = db.session.get(DynastyDB, dynasty_id).current_iron

            ps = ProjectSystem(db.session)
            with pytest.raises((ValueError, InsufficientResourcesError)):
                ps.start_project(
                    dynasty_id, 'recruit_cavalry', started_year=1300,
                    target_territory_id=territory_id, params={'size': 50},
                )

            # No Project row created and no resources spent.
            projects = db.session.query(Project).filter_by(
                dynasty_id=dynasty_id, project_type='recruit_cavalry',
            ).all()
            assert projects == []
            d = db.session.get(DynastyDB, dynasty_id)
            assert d.current_wealth == wealth_before
            assert d.current_iron == iron_before

    def test_recruit_cavalry_succeeds_with_stables(self, app, db, session):
        """recruit_cavalry succeeds when a controlled territory has Stables."""
        with app.app_context():
            user = _make_user(db, "bg_user_cav_yes")
            dynasty_id, _, territory_id = _make_dynasty_monarch_territory(db, user)
            _add_stables(db, territory_id)

            ps = ProjectSystem(db.session)
            project = ps.start_project(
                dynasty_id, 'recruit_cavalry', started_year=1300,
                target_territory_id=territory_id, params={'size': 50},
            )
            assert project is not None
            assert project.status == 'active'
            projects = db.session.query(Project).filter_by(
                dynasty_id=dynasty_id, project_type='recruit_cavalry',
            ).all()
            assert len(projects) == 1

    def test_recruit_infantry_starts_without_any_building(self, app, db, session):
        """A non-gated project (recruit_infantry) starts with no building."""
        with app.app_context():
            user = _make_user(db, "bg_user_inf")
            dynasty_id, _, territory_id = _make_dynasty_monarch_territory(db, user)

            ps = ProjectSystem(db.session)
            project = ps.start_project(
                dynasty_id, 'recruit_infantry', started_year=1300,
                target_territory_id=territory_id, params={'size': 100},
            )
            assert project is not None
            assert project.status == 'active'
            projects = db.session.query(Project).filter_by(
                dynasty_id=dynasty_id, project_type='recruit_infantry',
            ).all()
            assert len(projects) == 1

    def test_build_farm_starts_without_any_building(self, app, db, session):
        """A non-gated build project (build_farm) starts with no building."""
        with app.app_context():
            user = _make_user(db, "bg_user_farm")
            dynasty_id, _, territory_id = _make_dynasty_monarch_territory(db, user)

            ps = ProjectSystem(db.session)
            project = ps.start_project(
                dynasty_id, 'build_farm', started_year=1300,
                target_territory_id=territory_id,
            )
            assert project is not None
            assert project.status == 'active'
            projects = db.session.query(Project).filter_by(
                dynasty_id=dynasty_id, project_type='build_farm',
            ).all()
            assert len(projects) == 1


# ===========================================================================
# Contract 2 — Sickly halves lifespan / doubles mortality
# ===========================================================================
class TestSicklyLifespan:
    def _make_person(self, db, *, traits, birth_year=1250):
        user = _make_user(db, f"bg_user_sick_{abs(hash(tuple(traits))) % 100000}")
        dynasty = DynastyDB(
            user_id=user.id, name="House Sick",
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=100, current_iron=0, current_timber=0,
            start_year=1300, current_simulation_year=1300,
        )
        db.session.add(dynasty)
        db.session.commit()
        person = PersonDB(
            dynasty_id=dynasty.id, name="Edmund", surname="Sick",
            gender="MALE", birth_year=birth_year, is_noble=True,
        )
        person.set_traits(traits)
        db.session.add(person)
        db.session.commit()
        return person

    def test_sickly_person_aged_50_dies(self, app, db, session, monkeypatch):
        """A Sickly person aged ~50 → process_death_check returns True."""
        with app.app_context():
            theme_config = get_theme(VALID_THEME_KEY) or {}
            # Born 1250, checked in 1300 → age 50. Sickly halves max_age to ~42,
            # so 50 > 42 → guaranteed death regardless of the (low) roll.
            person = self._make_person(db, traits=['Sickly'], birth_year=1250)
            monkeypatch.setattr(tp.random, 'random', lambda: 0.5)
            assert tp.process_death_check(person, 1300, theme_config) is True
            assert person.death_year == 1300

    def test_non_sickly_person_aged_50_survives(self, app, db, session, monkeypatch):
        """An identical non-Sickly person aged ~50 survives a high roll."""
        with app.app_context():
            theme_config = get_theme(VALID_THEME_KEY) or {}
            # Same age 50, no Sickly trait → normal max_age (85), low base
            # mortality. A high roll (0.99) must not trip even doubled mortality.
            person = self._make_person(db, traits=['Just'], birth_year=1250)
            monkeypatch.setattr(tp.random, 'random', lambda: 0.99)
            assert tp.process_death_check(person, 1300, theme_config) is False
            assert person.death_year is None


# ===========================================================================
# Contract 3 — child trait inheritance
# ===========================================================================
class TestTraitInheritance:
    def _make_couple(self, db, *, mother_traits, father_traits,
                     mother_birth=1280, current_year=1305):
        """Married noble couple; mother of childbearing age at current_year."""
        user = _make_user(db, f"bg_user_inh_{abs(hash((tuple(mother_traits), tuple(father_traits)))) % 100000}")
        dynasty = DynastyDB(
            user_id=user.id, name="House Inherit",
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=100, current_iron=0, current_timber=0,
            start_year=1300, current_simulation_year=current_year,
        )
        db.session.add(dynasty)
        db.session.commit()

        father = PersonDB(
            dynasty_id=dynasty.id, name="Roderick", surname="Inherit",
            gender="MALE", birth_year=mother_birth - 2, is_noble=True,
        )
        father.set_traits(father_traits)
        db.session.add(father)

        mother = PersonDB(
            dynasty_id=dynasty.id, name="Adela", surname="Inherit",
            gender="FEMALE", birth_year=mother_birth, is_noble=True,
        )
        mother.set_traits(mother_traits)
        db.session.add(mother)
        db.session.commit()

        mother.spouse_sim_id = father.id
        father.spouse_sim_id = mother.id
        db.session.commit()
        return dynasty, mother, father

    def _get_child(self, db, mother_id, father_id):
        return (
            db.session.query(PersonDB)
            .filter(
                (PersonDB.mother_sim_id == mother_id)
                | (PersonDB.father_sim_id == mother_id)
            )
            .filter(PersonDB.birth_year == 1305)
            .first()
        )

    def test_inheritance_low_roll_inherits_capped_parent_traits(self, app, db, session, monkeypatch):
        """random.random->0.0: child inherits parent traits (capped at 3) plus 1 themed."""
        with app.app_context():
            theme_config = get_theme(VALID_THEME_KEY) or {}
            # 4 distinct parent traits → inheritance cap of 3 must apply.
            dynasty, mother, father = self._make_couple(
                db,
                mother_traits=['Pious', 'Ambitious'],
                father_traits=['Valiant', 'Learned'],
            )
            parent_traits = set(['Pious', 'Ambitious', 'Valiant', 'Learned'])
            # 0.0 forces: pregnancy fires, every inheritance roll (<0.30) fires,
            # and the infant-mortality roll (<0.15) would fire too — so child
            # dies but is still created with its inherited traits. Patch choice
            # so the +1 themed trait is one OUTSIDE the parent set to make the
            # "+1 themed" component observable.
            monkeypatch.setattr(tp.random, 'random', lambda: 0.0)
            monkeypatch.setattr(tp.random, 'choice', _cycling_choice(['MALE', 'Roland', 'Cruel']))
            # Return the TAIL of the population so a 1-trait themed sample over
            # common_traits yields 'Diplomatic' (a NON-parent trait) — keeping
            # the themed component distinct from any inherited parent trait
            # regardless of whether the impl uses random.choice or random.sample.
            monkeypatch.setattr(tp.random, 'sample', lambda pop, k: list(pop)[-k:])

            assert tp.process_childbirth_check(dynasty, mother, 1305, theme_config) is True
            child = self._get_child(db, mother.id, father.id)
            assert child is not None
            child_traits = set(child.get_traits())
            inherited = child_traits & parent_traits
            # Capped at 3 inherited parent traits.
            assert 1 <= len(inherited) <= 3
            # Plus at least one themed trait that is not a parent trait.
            assert len(child_traits - parent_traits) >= 1

    def test_inheritance_high_roll_only_themed_trait(self, app, db, session, monkeypatch):
        """random.random->1.0 (after birth fires): child has only the themed trait, no parent traits."""
        with app.app_context():
            theme_config = get_theme(VALID_THEME_KEY) or {}
            dynasty, mother, father = self._make_couple(
                db,
                mother_traits=['Pious', 'Ambitious'],
                father_traits=['Valiant', 'Learned'],
            )
            parent_traits = set(['Pious', 'Ambitious', 'Valiant', 'Learned'])
            # First random.random call (pregnancy gate) must succeed; every
            # subsequent call (inheritance rolls, infant mortality) must fail.
            monkeypatch.setattr(tp.random, 'random', _first_low_then_high())
            monkeypatch.setattr(tp.random, 'choice', _cycling_choice(['MALE', 'Roland', 'Cruel']))
            # Return the TAIL of the population so a 1-trait themed sample over
            # common_traits yields 'Diplomatic' (a NON-parent trait) — keeping
            # the themed component distinct from any inherited parent trait
            # regardless of whether the impl uses random.choice or random.sample.
            monkeypatch.setattr(tp.random, 'sample', lambda pop, k: list(pop)[-k:])

            assert tp.process_childbirth_check(dynasty, mother, 1305, theme_config) is True
            child = self._get_child(db, mother.id, father.id)
            assert child is not None
            child_traits = set(child.get_traits())
            # No parent traits inherited (every inheritance roll failed).
            assert child_traits & parent_traits == set()
            # Exactly the single themed trait remains.
            assert len(child_traits) == 1


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------
def _cycling_choice(values):
    """A random.choice replacement that pops from `values`, then repeats last."""
    state = {'i': 0}
    def _choice(seq):
        v = values[min(state['i'], len(values) - 1)]
        state['i'] += 1
        # If the requested value is not in the sequence, fall back to seq[0]
        # so name/gender choices over arbitrary theme lists still work.
        return v if v in seq else seq[0]
    return _choice


def _first_low_then_high():
    """random.random side_effect: 0.0 for the first call, 1.0 thereafter.

    The first call is the pregnancy gate (must pass: 0.0 < pregnancy_chance);
    every later call (per-trait inheritance < 0.30, infant mortality < 0.15)
    must fail so the child ends up with only the +1 themed trait.
    """
    state = {'first': True}
    def _r():
        if state['first']:
            state['first'] = False
            return 0.0
        return 1.0
    return _r
