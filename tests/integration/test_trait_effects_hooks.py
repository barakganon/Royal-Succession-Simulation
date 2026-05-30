# tests/integration/test_trait_effects_hooks.py
# Story 6-1 (Trait effects on Combat / Tax / Diplomacy) — CONTRACT-FIRST
# integration tests written by Agent C in an isolated worktree.
#
# These pin the contract for how models/trait_effects.py is wired into the three
# subsystems via a dynasty's LIVING MONARCH's traits:
#
#   - MilitarySystem._resolve_battle multiplies EACH side's strength by
#     combat_modifier(that side's monarch traits). A Brave attacker therefore
#     wins an otherwise-even fight that a trait-less attacker loses.
#   - EconomySystem.calculate_territory_tax_income multiplies the result by
#     tax_modifier(controller's monarch traits). A Greedy monarch yields strictly
#     MORE tax than an identical trait-less baseline.
#   - DiplomacySystem.perform_diplomatic_action adds
#     diplomacy_modifier(actor's monarch traits) to the relation change. A Cunning
#     actor moves the relation score strictly MORE than a trait-less actor.
#   - No living monarch / no traits -> the hook is a no-op (baseline behaviour).
#
# Traits are set on a LIVING (death_year is None) is_monarch=True PersonDB via
# PersonDB.set_traits([...]). LLM is OFF in tests.
#
# Several of these tests WILL FAIL in this isolated worktree because
# trait_effects.py and the subsystem hooks do not yet exist (the backend agents
# build them). That is EXPECTED for a contract-first suite — do NOT weaken,
# stub, or skip them.

import pytest

from models.db_models import (
    db as _db,
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
)
from models.economy_system import EconomySystem
from models.diplomacy_system import DiplomacySystem
from models.military_system import MilitarySystem

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in test_succession.py / test_detail_panel_render.py)
# ---------------------------------------------------------------------------

def _make_dynasty(app, db, username, dynasty_name, wealth=1000, year=1230):
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
            current_wealth=wealth,
            start_year=1200,
            current_simulation_year=year,
            prestige=10,
            honor=50,
        )
        db.session.add(dynasty)
        db.session.commit()
        return dynasty.id


def _make_living_monarch(app, db, dynasty_id, traits=None, name="King",
                         birth_year=1180):
    """Add a LIVING (death_year None) reigning monarch with optional traits."""
    with app.app_context():
        monarch = PersonDB(
            dynasty_id=dynasty_id,
            name=name,
            surname="Traitsson",
            gender="MALE",
            birth_year=birth_year,
            death_year=None,
            is_monarch=True,
            is_noble=True,
            reign_start_year=1200,
        )
        if traits is not None:
            monarch.set_traits(traits)
        db.session.add(monarch)
        db.session.commit()
        return monarch.id


def _make_geography(app, db, controller_dynasty_id, terrain=TerrainType.PLAINS,
                    base_tax=10, development_level=1, population=1000):
    """Create Region -> Province -> Territory; return territory_id.

    The territory is owned by `controller_dynasty_id` and uses neutral PLAINS
    terrain with no fortification so battle math stays deterministic.
    """
    with app.app_context():
        region = Region(name="Trait Region", base_climate="temperate")
        db.session.add(region)
        db.session.commit()
        province = Province(name="Trait Province", region_id=region.id,
                            primary_terrain=terrain)
        db.session.add(province)
        db.session.commit()
        territory = Territory(
            province_id=province.id,
            name="Trait Field",
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
    """Create an Army with one LEVY_SPEARMEN unit (quality 1.0, no commander)."""
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
    """Create an active War (Battle.war_id is NOT NULL); return war_id."""
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


# ---------------------------------------------------------------------------
# 1. Economy hook — tax_modifier(controller monarch traits)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTaxTraitHook:
    def test_greedy_monarch_yields_more_tax_than_baseline(self, app, db, session):
        """A Greedy controller's territory yields strictly MORE tax than an
        identical territory whose controller has no traits."""
        greedy_did = _make_dynasty(app, db, "tr_user_greedy", "House Greed")
        plain_did = _make_dynasty(app, db, "tr_user_plain", "House Plain")
        _make_living_monarch(app, db, greedy_did, traits=["Greedy"], name="Midas")
        _make_living_monarch(app, db, plain_did, traits=[], name="Pauper")

        # Two identical territories (same base_tax/dev/pop), differing only in
        # which dynasty controls them.
        greedy_terr = _make_geography(app, db, greedy_did)
        plain_terr = _make_geography(app, db, plain_did)

        with app.app_context():
            econ = EconomySystem(db.session)
            greedy_tax = econ.calculate_territory_tax_income(greedy_terr)
            plain_tax = econ.calculate_territory_tax_income(plain_terr)

        assert plain_tax > 0, "baseline tax should be positive for the comparison"
        # Greedy applies tax_modifier 1.20 -> strictly more than the trait-less base.
        assert greedy_tax > plain_tax
        assert greedy_tax == pytest.approx(plain_tax * 1.20, rel=1e-6)

    def test_no_monarch_is_tax_noop(self, app, db, session):
        """A controller dynasty with NO monarch leaves tax at the baseline."""
        no_monarch_did = _make_dynasty(app, db, "tr_user_nomon", "House Void")
        plain_did = _make_dynasty(app, db, "tr_user_plain2", "House Plain2")
        _make_living_monarch(app, db, plain_did, traits=[], name="Plainface")
        # no_monarch_did deliberately has no PersonDB at all.

        nm_terr = _make_geography(app, db, no_monarch_did)
        plain_terr = _make_geography(app, db, plain_did)

        with app.app_context():
            econ = EconomySystem(db.session)
            nm_tax = econ.calculate_territory_tax_income(nm_terr)
            plain_tax = econ.calculate_territory_tax_income(plain_terr)

        # No monarch -> identity tax_modifier -> identical to the trait-less baseline.
        assert nm_tax == pytest.approx(plain_tax, rel=1e-6)


# ---------------------------------------------------------------------------
# 2. Diplomacy hook — diplomacy_modifier(actor monarch traits)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDiplomacyTraitHook:
    def test_cunning_actor_moves_relation_more_than_baseline(self, app, db, session):
        """A Cunning actor's diplomatic action moves the relation score strictly
        MORE than a trait-less actor performing the same action."""
        cunning_did = _make_dynasty(app, db, "tr_user_cunning", "House Cunning")
        plain_actor_did = _make_dynasty(app, db, "tr_user_plainact", "House PlainAct")
        target_a_did = _make_dynasty(app, db, "tr_user_tgt_a", "House TargetA")
        target_b_did = _make_dynasty(app, db, "tr_user_tgt_b", "House TargetB")

        _make_living_monarch(app, db, cunning_did, traits=["Cunning"], name="Schemer")
        _make_living_monarch(app, db, plain_actor_did, traits=[], name="Honest")
        # Targets need monarchs only insofar as the contract reads the ACTOR's
        # monarch; give them trait-less monarchs to keep both setups symmetric.
        _make_living_monarch(app, db, target_a_did, traits=[], name="TargA")
        _make_living_monarch(app, db, target_b_did, traits=[], name="TargB")

        action = "send_envoy"  # base effect +5, no honor/prestige edge cases here

        with app.app_context():
            diplo = DiplomacySystem(db.session)

            cunning_ok, _ = diplo.perform_diplomatic_action(
                cunning_did, target_a_did, action
            )
            plain_ok, _ = diplo.perform_diplomatic_action(
                plain_actor_did, target_b_did, action
            )
            assert cunning_ok is True and plain_ok is True

            cunning_rel = diplo.get_diplomatic_relation(cunning_did, target_a_did)
            plain_rel = diplo.get_diplomatic_relation(plain_actor_did, target_b_did)
            cunning_score = cunning_rel.relation_score
            plain_score = plain_rel.relation_score

        # Cunning adds +15 to the relation change on top of the same base.
        assert cunning_score > plain_score
        assert (cunning_score - plain_score) == 15

    def test_no_monarch_is_diplomacy_noop(self, app, db, session):
        """An actor dynasty with NO monarch applies the baseline relation change."""
        no_monarch_did = _make_dynasty(app, db, "tr_user_dipnomon", "House DipVoid")
        plain_actor_did = _make_dynasty(app, db, "tr_user_dipplain", "House DipPlain")
        target_a_did = _make_dynasty(app, db, "tr_user_diptgt_a", "House DTargetA")
        target_b_did = _make_dynasty(app, db, "tr_user_diptgt_b", "House DTargetB")

        # no_monarch_did has no PersonDB; plain actor gets a trait-less monarch.
        _make_living_monarch(app, db, plain_actor_did, traits=[], name="DipHonest")

        action = "send_envoy"

        with app.app_context():
            diplo = DiplomacySystem(db.session)
            diplo.perform_diplomatic_action(no_monarch_did, target_a_did, action)
            diplo.perform_diplomatic_action(plain_actor_did, target_b_did, action)

            nm_score = diplo.get_diplomatic_relation(
                no_monarch_did, target_a_did
            ).relation_score
            plain_score = diplo.get_diplomatic_relation(
                plain_actor_did, target_b_did
            ).relation_score

        # No monarch -> identity diplomacy_modifier -> equal to the trait-less baseline.
        assert nm_score == plain_score


# ---------------------------------------------------------------------------
# 3. Combat hook — combat_modifier(each side's monarch traits)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCombatTraitHook:
    def _run_even_battle(self, app, db, attacker_traits):
        """Run one battle on a neutral PLAINS field where attacker and defender
        field identical levy hosts; only the ATTACKER monarch's traits vary.

        Returns the winning dynasty_id. The territory is controlled by the
        ATTACKER so the defender earns no home-territory bonus, making an
        un-modified fight an exact tie (which _resolve_battle awards to the
        defender via its strict `attacker > defender` win check). A combat
        bonus on the attacker is therefore the ONLY thing that can flip the
        result to an attacker victory — a clean, assertable signal.
        """
        atk_did = _make_dynasty(app, db, f"tr_atk_{abs(hash(tuple(attacker_traits or [])))%99999}", "House Atk")
        def_did = _make_dynasty(app, db, f"tr_def_{abs(hash(tuple(attacker_traits or [])))%99999}", "House Def")

        _make_living_monarch(app, db, atk_did, traits=attacker_traits, name="AtkKing")
        _make_living_monarch(app, db, def_did, traits=[], name="DefKing")

        # Territory controlled by the attacker -> no defender home bonus.
        terr = _make_geography(app, db, atk_did)
        atk_army = _make_army(app, db, atk_did, terr, unit_size=1000)
        def_army = _make_army(app, db, def_did, terr, unit_size=1000)
        war_id = _make_war(app, db, atk_did, def_did)

        with app.app_context():
            mil = MilitarySystem(db.session)
            ok, _msg, battle = mil.initiate_battle(atk_army, def_army, terr, war_id=war_id)
            assert ok is True and battle is not None
            return battle.winner_dynasty_id, atk_did, def_did

    def test_baseline_attacker_does_not_win_even_fight(self, app, db, session):
        """Trait-less attacker vs trait-less defender on an even field: the
        attacker does NOT win (ties resolve to the defender)."""
        winner, atk_did, def_did = self._run_even_battle(app, db, attacker_traits=[])
        assert winner == def_did
        assert winner != atk_did

    def test_brave_attacker_wins_the_same_even_fight(self, app, db, session):
        """A Brave attacker (combat +0.15) wins the exact fight a trait-less
        attacker loses — proving combat_modifier is applied per-side."""
        winner, atk_did, def_did = self._run_even_battle(app, db, attacker_traits=["Brave"])
        assert winner == atk_did
        assert winner != def_did
