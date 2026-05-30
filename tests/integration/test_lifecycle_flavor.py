# tests/integration/test_lifecycle_flavor.py
# Story 9-2 (LLM-narrated lifecycle event flavor + deterministic fallback) —
# CONTRACT-FIRST integration tests written by Agent C in an isolated worktree.
#
# Story 9-1 added flavor prompt builders + deterministic fallbacks in
# utils/llm_prompts.py. Story 9-2 wires each lifecycle log site so that
# HistoryLogEntryDB.event_string is set from a guarded LLM narration
# (utils.llm_narration.narrate_event) that FALLS BACK to the deterministic
# 9-1 fallback whenever the LLM is unavailable / errors / times out.
#
# The test environment runs LLM-OFF (no GOOGLE_API_KEY, no Flask app config
# flag), so narrate_event ALWAYS returns its fallback argument. Therefore every
# lifecycle event_string in these tests must equal the corresponding
# generate_*_fallback(...) output verbatim — NOT the old static strings.
#
# These tests WILL FAIL in this isolated worktree because the wiring
# (utils/llm_narration.py + the four log-site edits) does not yet exist (the
# backend agents build it). That is EXPECTED and correct for a contract-first
# suite — do NOT weaken, stub, or skip them.

from unittest.mock import patch

import pytest

from models.db_models import (
    User,
    DynastyDB,
    PersonDB,
    Region,
    Province,
    Territory,
    TerrainType,
    UnitType,
    MilitaryUnit,
    Army,
    War,
    WarGoal,
    Building,
    BuildingType,
    HistoryLogEntryDB,
)
from models import turn_processor as tp
from models.economy_system import EconomySystem
from models.military_system import MilitarySystem
from utils.llm_prompts import (
    generate_birth_flavor_fallback,
    generate_death_flavor_fallback,
    generate_battle_flavor_fallback,
    generate_construction_complete_fallback,
)
from utils.theme_manager import get_theme

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_cross_dynasty_marriage.py /
# test_civil_war_majority.py / test_trait_effects_hooks.py)
# ---------------------------------------------------------------------------

def _create_user_and_dynasty(app, db, username, dynasty_name,
                             password="password123", is_ai=False, year=1230,
                             wealth=2000):
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
            current_wealth=wealth,
            start_year=1200,
            current_simulation_year=year,
            prestige=10,
            is_ai_controlled=is_ai,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


def _add_person(app, db, dynasty_id, name, gender="MALE", birth_year=1200,
                death_year=None, is_noble=True, is_monarch=False,
                spouse_sim_id=None, surname="House", traits=None):
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
        )
        if traits is not None:
            person.set_traits(traits)
        db.session.add(person)
        db.session.commit()
        return person.id


def _make_geography(app, db, controller_dynasty_id, terrain=TerrainType.PLAINS,
                    base_tax=10, development_level=1, population=1000,
                    name="Flavor Field"):
    """Create Region -> Province -> Territory; return territory_id."""
    with app.app_context():
        region = Region(name="Flavor Region", base_climate="temperate")
        db.session.add(region)
        db.session.commit()
        province = Province(name="Flavor Province", region_id=region.id,
                            primary_terrain=terrain)
        db.session.add(province)
        db.session.commit()
        territory = Territory(
            province_id=province.id,
            name=name,
            terrain_type=terrain,
            x_coordinate=0.0,
            y_coordinate=0.0,
            base_tax=base_tax,
            base_manpower=1000,
            development_level=development_level,
            population=population,
            fortification_level=0,
            controller_dynasty_id=controller_dynasty_id,
        )
        db.session.add(territory)
        db.session.commit()
        return territory.id


def _make_army(app, db, dynasty_id, territory_id, unit_size=1000, year=1230):
    """Create an Army with one LEVY_SPEARMEN unit; return army_id."""
    with app.app_context():
        army = Army(dynasty_id=dynasty_id, name="Host", territory_id=territory_id,
                    created_year=year, is_active=True)
        db.session.add(army)
        db.session.commit()
        unit = MilitaryUnit(
            dynasty_id=dynasty_id,
            unit_type=UnitType.LEVY_SPEARMEN,
            name="Levy",
            size=unit_size,
            quality=1.0,
            experience=0.0,
            morale=1.0,
            territory_id=territory_id,
            army_id=army.id,
            maintenance_cost=1,
            food_consumption=1.0,
            created_year=year,
        )
        db.session.add(unit)
        db.session.commit()
        return army.id


def _make_war(app, db, attacker_dynasty_id, defender_dynasty_id, year=1230):
    """Create an active War; return war_id."""
    with app.app_context():
        war = War(
            attacker_dynasty_id=attacker_dynasty_id,
            defender_dynasty_id=defender_dynasty_id,
            war_goal=WarGoal.CONQUEST,
            start_year=year,
            is_active=True,
        )
        db.session.add(war)
        db.session.commit()
        return war.id


def _theme():
    return get_theme(VALID_THEME_KEY) or {}


def _latest_log(app, db, dynasty_id, event_type):
    """Return the most-recent HistoryLogEntryDB of the given type for a dynasty."""
    with app.app_context():
        return (
            db.session.query(HistoryLogEntryDB)
            .filter_by(dynasty_id=dynasty_id, event_type=event_type)
            .order_by(HistoryLogEntryDB.id.desc())
            .first()
        )


# ---------------------------------------------------------------------------
# 1. BIRTH — surviving-child birth_log uses the flavored fallback
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestBirthFlavor:
    def test_birth_event_string_is_flavored_fallback(self, app, db, session):
        """A guaranteed conception+survival drives process_childbirth_check; the
        birth HistoryLogEntryDB.event_string equals the deterministic 9-1 birth
        fallback (LLM off), naming the child + parents + house + year, and is NOT
        the old 'was born to' static string."""
        # 9-2: event_string now flavored
        year = 1230
        did = _create_user_and_dynasty(app, db, "lf_birth_user", "House Birthwell",
                                       year=year)
        # A married couple; the mother is of childbearing age (30 in 1230).
        father_id = _add_person(app, db, did, "Fatherly", gender="MALE",
                                birth_year=1200, surname="Birthwell")
        mother_id = _add_person(app, db, did, "Motherly", gender="FEMALE",
                                birth_year=1200, surname="Birthwell",
                                spouse_sim_id=father_id)
        with app.app_context():
            mom = db.session.get(PersonDB, mother_id)
            mom.spouse_sim_id = father_id
            db.session.commit()

        with app.app_context():
            dynasty = db.session.get(DynastyDB, did)
            woman = db.session.get(PersonDB, mother_id)
            spouse = db.session.get(PersonDB, father_id)
            # random.random() < 0.4 pregnancy_chance -> conceives;
            # random.random() < 0.30 trait-inherit roll passes (harmless);
            # random.random() < 0.15 child-mortality -> 0.16 FAILS -> child SURVIVES.
            with patch('models.turn_processor.random.random', return_value=0.16):
                result = tp.process_childbirth_check(dynasty, woman, year, _theme())
            db.session.commit()

            assert result is True
            woman_name = woman.name
            spouse_name = spouse.name
            house = dynasty.name

        log = _latest_log(app, db, did, "birth")
        assert log is not None, "a birth HistoryLogEntryDB must be written"

        with app.app_context():
            child = db.session.get(PersonDB, log.person1_sim_id)
            assert child is not None
            assert child.death_year is None, "child must survive the mortality roll"
            child_name = child.name
            expected = generate_birth_flavor_fallback(
                child_name, woman_name, spouse_name, house, year
            )

        assert log.event_string == expected
        # event_string is now the flavored fallback (equals generate_birth_flavor_fallback
        # above), not the old static "{child} {surname} was born to {mother} and {father}."
        # NOTE: the 9-1 fallback legitimately uses the words "was born to" as natural
        # prose, so we assert equality with the fallback (above) rather than a brittle
        # substring-absence check.
        assert child_name in log.event_string
        assert str(year) in log.event_string


# ---------------------------------------------------------------------------
# 2. DEATH — death_log uses the flavored fallback (commoner + monarch variants)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDeathFlavor:
    def test_death_event_string_is_flavored_fallback(self, app, db, session):
        """A forced death drives process_death_check; the death
        HistoryLogEntryDB.event_string equals the deterministic 9-1 death
        fallback (LLM off), naming the person + age + year, and is NOT the old
        'passed away at the age of' static string."""
        # 9-2: event_string now flavored
        year = 1255
        did = _create_user_and_dynasty(app, db, "lf_death_user", "House Mortis",
                                       year=year)
        # Born 1200 -> age 55 in 1255; not a monarch.
        pid = _add_person(app, db, did, "Doomed", gender="MALE",
                          birth_year=1200, surname="Mortis", is_monarch=False)

        with app.app_context():
            person = db.session.get(PersonDB, pid)
            # random.random() == 0.0 < base_mortality -> guaranteed death.
            with patch('models.turn_processor.random.random', return_value=0.0):
                died = tp.process_death_check(person, year, _theme())
            db.session.commit()
            assert died is True
            age = year - 1200
            dynasty = db.session.get(DynastyDB, did)
            expected = generate_death_flavor_fallback(
                f"{person.name} {person.surname}", dynasty.name, age, year,
                person.is_monarch,
            )

        log = _latest_log(app, db, did, "death")
        assert log is not None, "a death HistoryLogEntryDB must be written"
        assert log.event_string == expected
        assert "passed away at the age of" not in log.event_string
        assert "Doomed" in log.event_string
        assert str(year) in log.event_string

    def test_monarch_death_variant_differs_from_commoner(self, app, db, session):
        """A monarch's death fallback references the crown/ended reign and so
        differs from the commoner phrasing; the logged event_string equals the
        monarch fallback."""
        # 9-2: event_string now flavored
        year = 1255
        did = _create_user_and_dynasty(app, db, "lf_kdeath_user", "House Regis",
                                       year=year)
        pid = _add_person(app, db, did, "OldKing", gender="MALE",
                          birth_year=1185, surname="Regis", is_monarch=True)

        with app.app_context():
            person = db.session.get(PersonDB, pid)
            with patch('models.turn_processor.random.random', return_value=0.0):
                died = tp.process_death_check(person, year, _theme())
            db.session.commit()
            assert died is True
            age = year - 1185
            dynasty = db.session.get(DynastyDB, did)
            monarch_expected = generate_death_flavor_fallback(
                f"{person.name} {person.surname}", dynasty.name, age, year, True
            )
            commoner_expected = generate_death_flavor_fallback(
                f"{person.name} {person.surname}", dynasty.name, age, year, False
            )

        log = _latest_log(app, db, did, "death")
        assert log is not None
        assert log.event_string == monarch_expected
        assert monarch_expected != commoner_expected, \
            "monarch death flavor must differ from the commoner variant"


# ---------------------------------------------------------------------------
# 3. BATTLE — initiate_battle log uses the flavored fallback
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestBattleFlavor:
    def test_battle_event_string_is_flavored_fallback(self, app, db, session):
        """MilitarySystem.initiate_battle between two armies writes a battle
        HistoryLogEntryDB whose event_string equals the deterministic 9-1 battle
        fallback (LLM off), naming both combatants + the victor + year, and is
        NOT the old 'Battle of ... defeated ... Casualties' static string."""
        # 9-2: event_string now flavored
        year = 1230
        atk_did = _create_user_and_dynasty(app, db, "lf_atk_user", "House Atticus",
                                           year=year)
        def_did = _create_user_and_dynasty(app, db, "lf_def_user", "House Defenrir",
                                           year=year)
        terr = _make_geography(app, db, atk_did)
        atk_army = _make_army(app, db, atk_did, terr, unit_size=1000, year=year)
        def_army = _make_army(app, db, def_did, terr, unit_size=1000, year=year)
        war_id = _make_war(app, db, atk_did, def_did, year=year)

        with app.app_context():
            mil = MilitarySystem(db.session)
            ok, _msg, battle = mil.initiate_battle(atk_army, def_army, terr,
                                                   war_id=war_id)
            assert ok is True and battle is not None
            winner_id = battle.winner_dynasty_id
            atk_dyn = db.session.get(DynastyDB, atk_did)
            def_dyn = db.session.get(DynastyDB, def_did)
            winner_name = (atk_dyn.name if winner_id == atk_did else def_dyn.name)
            expected = generate_battle_flavor_fallback(
                atk_dyn.name, def_dyn.name, winner_name, year
            )

        # The attacker's history carries the battle line.
        log = _latest_log(app, db, atk_did, "battle")
        assert log is not None, "a battle HistoryLogEntryDB must be written"
        assert log.event_string == expected
        # Old static phrasing must be gone.
        assert "Battle of" not in log.event_string
        assert "defeated" not in log.event_string
        assert "Casualties" not in log.event_string
        assert "House Atticus" in log.event_string
        assert "House Defenrir" in log.event_string
        assert str(year) in log.event_string


# ---------------------------------------------------------------------------
# 4. CONSTRUCTION flavor — DESCOPED from Story 9-2.
#
# The construction-completion narration (build_construction_complete_prompt /
# generate_construction_complete_fallback) was intended here, but the underlying
# construction subsystem is pre-existingly broken: EconomySystem.construct_building
# constructs Building(..., completion_year=..., is_under_construction=True) and the
# completion branch reads building.is_under_construction / .completion_year, yet the
# Building model (models/db_models.py) defines NEITHER column. construct_building
# therefore raises TypeError and the completion branch is dead code. Wiring (and
# testing) construction flavor requires first adding those columns + a migration,
# which is out of scope for 9-2 (flavor wiring). Deferred to a dedicated story that
# fixes the Building schema; the build_construction_complete_prompt builder already
# exists (Story 9-1) and is ready to wire in once the columns land.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 5. narrate_event unit — pure fallback with no Flask app context, never raises
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNarrateEventHelper:
    def test_narrate_event_returns_fallback_without_app_context(self):
        """utils.llm_narration.narrate_event returns its fallback verbatim when
        there is no Flask application context / no API key configured, and never
        raises — this is the LLM-OFF path every lifecycle test relies on."""
        from utils.llm_narration import narrate_event
        result = narrate_event("anything", "FB")
        assert result == "FB"

    def test_narrate_event_never_raises_on_arbitrary_input(self):
        """narrate_event swallows all errors and returns the fallback for any
        input, so a narration failure can never abort a turn/battle/economy
        update."""
        from utils.llm_narration import narrate_event
        # Various odd inputs; must always return the provided fallback string.
        assert narrate_event("", "fallback-A") == "fallback-A"
        assert narrate_event("a very long prompt " * 100, "fallback-B",
                             max_tokens=10, timeout_s=1) == "fallback-B"
