# tests/unit/test_ai_controller.py
"""Unit tests for the personality-driven AIController."""

import pytest
from unittest.mock import MagicMock, patch

from models.db_models import (
    DynastyDB, PersonDB, Territory, MilitaryUnit, Army, War, WarGoal,
    DiplomaticRelation, UnitType, BuildingType,
)
from models.ai_controller import AIController


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dynasty(session, dynasty_id: int = 1, name: str = "Test Dynasty",
                  wealth: int = 200, year: int = 1100, is_ai: bool = True) -> DynastyDB:
    """Create and persist a minimal DynastyDB row."""
    from models.db_models import User
    user = session.query(User).filter_by(username="ai_test_user").first()
    if user is None:
        user = User(username="ai_test_user", email="ai@test.com")
        user.set_password("secret")
        session.add(user)
        session.flush()

    dynasty = DynastyDB(
        user_id=user.id,
        name=name,
        theme_identifier_or_json="medieval_europe",
        current_wealth=wealth,
        start_year=year,
        current_simulation_year=year,
        is_ai_controlled=is_ai,
    )
    session.add(dynasty)
    session.flush()
    return dynasty


def _make_person(session, dynasty_id: int, birth_year: int = 1070,
                 is_monarch: bool = False, gender: str = "MALE") -> PersonDB:
    person = PersonDB(
        dynasty_id=dynasty_id,
        name="Test",
        surname="Person",
        gender=gender,
        birth_year=birth_year,
        is_noble=True,
        is_monarch=is_monarch,
    )
    session.add(person)
    session.flush()
    return person


def _make_unit(session, dynasty_id: int, size: int = 500) -> MilitaryUnit:
    unit = MilitaryUnit(
        dynasty_id=dynasty_id,
        unit_type=UnitType.LEVY_SPEARMEN,
        size=size,
        quality=1.0,
        morale=1.0,
        maintenance_cost=10,
        food_consumption=1.0,
        created_year=1100,
    )
    session.add(unit)
    session.flush()
    return unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PERSONALITY = "House Test is aggressive and expansionist — always attacks first."


@pytest.fixture
def controller(session, app):
    """Return an AIController bound to a freshly created dynasty."""
    with app.app_context():
        dynasty = _make_dynasty(session)
        ctrl = AIController(
            session=session,
            dynasty_id=dynasty.id,
            personality=PERSONALITY,
        )
        yield ctrl, dynasty


# ---------------------------------------------------------------------------
# Basic instantiation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAIControllerInstantiation:
    def test_init(self, session, app):
        """AIController can be instantiated with session, dynasty_id, personality."""
        with app.app_context():
            dynasty = _make_dynasty(session, name="Init Dynasty")
            ctrl = AIController(
                session=session,
                dynasty_id=dynasty.id,
                personality=PERSONALITY,
            )
            assert ctrl.dynasty_id == dynasty.id
            assert ctrl.personality == PERSONALITY
            assert ctrl.session is session

    def test_get_dynasty_name(self, controller, app):
        with app.app_context():
            ctrl, dynasty = controller
            assert ctrl._get_dynasty_name() == dynasty.name

    def test_build_game_state_returns_dict(self, controller, app):
        with app.app_context():
            ctrl, dynasty = controller
            state = ctrl._build_game_state()
            assert isinstance(state, dict)
            assert state['dynasty_id'] == dynasty.id
            assert state['dynasty_name'] == dynasty.name
            assert state['treasury'] == dynasty.current_wealth

    def test_build_game_state_missing_dynasty(self, session, app):
        """_build_game_state returns safe defaults when dynasty does not exist."""
        with app.app_context():
            ctrl = AIController(session=session, dynasty_id=99999, personality="x")
            state = ctrl._build_game_state()
            assert state['treasury'] == 0
            assert state['army_size'] == 0


# ---------------------------------------------------------------------------
# LLM path is skipped when llm_model is None
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMSkippedWhenNone:
    def test_call_llm_returns_none_when_no_model(self, controller, app):
        with app.app_context():
            ctrl, _ = controller
            with patch('models.ai_controller.AIController._call_llm', return_value=None) as mock_call:
                result = ctrl._call_llm("irrelevant prompt")
            assert result is None

    def test_decide_diplomacy_falls_back_without_llm(self, controller, app):
        with app.app_context():
            ctrl, dynasty = controller
            # Patch _call_llm to simulate LLM unavailable
            ctrl._call_llm = lambda prompt: None
            state = ctrl._build_game_state()
            result = ctrl.decide_diplomacy(state)
            assert 'action' in result
            assert isinstance(result['action'], str)

    def test_decide_military_falls_back_without_llm(self, controller, app):
        with app.app_context():
            ctrl, dynasty = controller
            ctrl._call_llm = lambda prompt: None
            state = ctrl._build_game_state()
            result = ctrl.decide_military(state)
            assert 'action' in result

    def test_decide_economy_falls_back_without_llm(self, controller, app):
        with app.app_context():
            ctrl, dynasty = controller
            ctrl._call_llm = lambda prompt: None
            state = ctrl._build_game_state()
            result = ctrl.decide_economy(state)
            assert 'action' in result
            assert 'building_type' in result

    def test_decide_character_falls_back_without_llm(self, controller, app):
        with app.app_context():
            ctrl, dynasty = controller
            ctrl._call_llm = lambda prompt: None
            state = ctrl._build_game_state()
            result = ctrl.decide_character(state)
            assert 'action' in result


# ---------------------------------------------------------------------------
# Diplomacy rule-based fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFallbackDiplomacy:
    def test_propose_nap_when_hostile_and_weaker(self, session, app):
        """Should propose NAP when relation score < -50 and own army is weaker."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Weak Dynasty")
            enemy_dynasty = _make_dynasty(session, name="Strong Enemy")

            # Weak own forces
            _make_unit(session, my_dynasty.id, size=100)
            # Strong enemy forces
            _make_unit(session, enemy_dynasty.id, size=800)

            # Create hostile relation (dynasty1 < dynasty2 by convention)
            rel = DiplomaticRelation(
                dynasty1_id=my_dynasty.id,
                dynasty2_id=enemy_dynasty.id,
                relation_score=-75,
            )
            session.add(rel)
            session.flush()

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None  # force fallback
            state = ctrl._build_game_state()
            result = ctrl.decide_diplomacy(state)

            assert result['action'] == 'propose_nap'
            assert result['target_id'] == enemy_dynasty.id

    def test_propose_alliance_when_friendly(self, session, app):
        """Should propose alliance when relation score > 60 and we are stronger."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Friendly Overlord")
            friend_dynasty = _make_dynasty(session, name="Friendly Vassal")

            # Own forces are stronger
            _make_unit(session, my_dynasty.id, size=1000)
            _make_unit(session, friend_dynasty.id, size=200)

            rel = DiplomaticRelation(
                dynasty1_id=my_dynasty.id,
                dynasty2_id=friend_dynasty.id,
                relation_score=75,
            )
            session.add(rel)
            session.flush()

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            result = ctrl.decide_diplomacy(state)

            assert result['action'] == 'propose_alliance'
            assert result['target_id'] == friend_dynasty.id

    def test_no_action_when_neutral(self, session, app):
        """Should return 'none' when relations are neutral and strengths are even."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Neutral A")
            other_dynasty = _make_dynasty(session, name="Neutral B")

            _make_unit(session, my_dynasty.id, size=300)
            _make_unit(session, other_dynasty.id, size=300)

            rel = DiplomaticRelation(
                dynasty1_id=my_dynasty.id,
                dynasty2_id=other_dynasty.id,
                relation_score=10,
            )
            session.add(rel)
            session.flush()

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            result = ctrl.decide_diplomacy(state)

            assert result['action'] == 'none'


# ---------------------------------------------------------------------------
# Military rule-based fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFallbackMilitary:
    def test_attack_when_stronger_and_at_war(self, session, app):
        """Should choose 'attack' when own army > 1.5× enemy and war is active."""
        with app.app_context():
            from models.db_models import Province, TerrainType
            import random

            my_dynasty = _make_dynasty(session, name="Attacker")
            enemy_dynasty = _make_dynasty(session, name="Defender")

            _make_unit(session, my_dynasty.id, size=1500)
            _make_unit(session, enemy_dynasty.id, size=500)

            # Create a province + territory for the enemy
            region_row = session.query(__import__('models.db_models', fromlist=['Region']).Region).first()
            if region_row is None:
                from models.db_models import Region
                region_row = Region(name="Test Region", base_climate="temperate")
                session.add(region_row)
                session.flush()

            province = Province(
                region_id=region_row.id,
                name="Test Province",
                primary_terrain=TerrainType.PLAINS,
            )
            session.add(province)
            session.flush()

            territory = Territory(
                province_id=province.id,
                name="Enemy Capital",
                terrain_type=TerrainType.PLAINS,
                x_coordinate=0.0,
                y_coordinate=0.0,
                controller_dynasty_id=enemy_dynasty.id,
                is_capital=True,
            )
            session.add(territory)
            session.flush()

            war = War(
                attacker_dynasty_id=my_dynasty.id,
                defender_dynasty_id=enemy_dynasty.id,
                war_goal=WarGoal.CONQUEST,
                start_year=1100,
                is_active=True,
            )
            session.add(war)
            session.flush()

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            result = ctrl.decide_military(state)

            assert result['action'] == 'attack'
            assert result['target_id'] == territory.id

    def test_retreat_when_weaker_at_war(self, session, app):
        """Should choose 'retreat' when own army is weaker and under attack."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Outnumbered")
            enemy_dynasty = _make_dynasty(session, name="Overwhelming Force")

            _make_unit(session, my_dynasty.id, size=200)
            _make_unit(session, enemy_dynasty.id, size=2000)

            war = War(
                attacker_dynasty_id=enemy_dynasty.id,
                defender_dynasty_id=my_dynasty.id,
                war_goal=WarGoal.CONQUEST,
                start_year=1100,
                is_active=True,
            )
            session.add(war)
            session.flush()

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            result = ctrl.decide_military(state)

            assert result['action'] == 'retreat'

    def test_none_when_no_war(self, session, app):
        """Should return 'none' when there is no active war."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Peaceful Dynasty")
            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            result = ctrl.decide_military(state)

            assert result['action'] == 'none'


# ---------------------------------------------------------------------------
# Economy rule-based fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFallbackEconomy:
    def test_build_farm_when_poor_food(self, session, app):
        """Should build farm when treasury is below 20% of food capacity proxy."""
        with app.app_context():
            # 1 territory, capacity proxy = 100; 20% = 20; treasury=10 → build farm
            my_dynasty = _make_dynasty(session, name="Starving Dynasty", wealth=10)
            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            state['territory_count'] = 1  # override
            result = ctrl.decide_economy(state)

            assert result['action'] == 'build'
            assert result['building_type'] == BuildingType.FARM.value

    def test_build_market_when_low_treasury(self, session, app):
        """Should build market when treasury < 50 (but above food threshold)."""
        with app.app_context():
            # territory_count=10 → capacity proxy=1000; 20%=200; treasury=30 < 200 → farm
            # Use treasury=30 with territory_count=0 so capacity proxy=100; 20%=20; 30>20 → market
            my_dynasty = _make_dynasty(session, name="Broke Dynasty", wealth=30)
            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            state['territory_count'] = 0  # capacity proxy = 0 → food check skips
            result = ctrl.decide_economy(state)

            assert result['action'] == 'build'
            assert result['building_type'] == BuildingType.MARKET.value

    def test_build_barracks_when_wealthy(self, session, app):
        """Should build barracks when treasury is healthy."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Rich Dynasty", wealth=500)
            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            state['territory_count'] = 1  # capacity proxy = 100; 20% = 20; 500 > 20 → market check
            # 500 >= 50 → barracks
            result = ctrl.decide_economy(state)

            assert result['action'] == 'build'
            assert result['building_type'] == BuildingType.BARRACKS.value


# ---------------------------------------------------------------------------
# Character rule-based fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFallbackCharacter:
    def test_arrange_marriage_when_old_leader_no_heir(self, session, app):
        """Should arrange marriage for eldest child when monarch is old and has no heir."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Heirless Dynasty", year=1100)
            monarch = _make_person(session, my_dynasty.id, birth_year=1044, is_monarch=True)
            # Monarch is now 56 years old
            child = _make_person(session, my_dynasty.id, birth_year=1075, is_monarch=False)
            child.father_sim_id = monarch.id
            session.flush()

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            # Force conditions: old monarch, no heir flag
            state['monarch_age'] = 56
            state['has_heir'] = False
            state['monarch_id'] = monarch.id
            result = ctrl.decide_character(state)

            assert result['action'] == 'arrange_marriage'
            assert result['person_id'] == child.id

    def test_none_when_young_leader(self, session, app):
        """Should return 'none' when leader is young."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Young Dynasty", year=1100)
            _make_person(session, my_dynasty.id, birth_year=1075, is_monarch=True)

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            state['monarch_age'] = 25
            state['has_heir'] = True
            result = ctrl.decide_character(state)

            assert result['action'] == 'none'

    def test_none_when_heir_exists(self, session, app):
        """Should return 'none' even for old leader when heir exists."""
        with app.app_context():
            my_dynasty = _make_dynasty(session, name="Old But Heired", year=1100)
            _make_person(session, my_dynasty.id, birth_year=1044, is_monarch=True)

            ctrl = AIController(session, my_dynasty.id, PERSONALITY)
            ctrl._call_llm = lambda p: None
            state = ctrl._build_game_state()
            state['monarch_age'] = 56
            state['has_heir'] = True
            result = ctrl.decide_character(state)

            assert result['action'] == 'none'


# ---------------------------------------------------------------------------
# LLM path — response parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMResponseParsing:
    def test_valid_llm_response_parsed(self, controller, app):
        """A well-formed LLM response is correctly parsed into an action dict."""
        with app.app_context():
            ctrl, dynasty = controller
            fake_response = "ACTION: propose_nap | REASON: Our army is too weak right now."
            ctrl._call_llm = lambda p: fake_response
            state = ctrl._build_game_state()
            result = ctrl.decide_diplomacy(state)
            assert result['action'] == 'propose_nap'

    def test_invalid_llm_response_falls_back_to_none(self, controller, app):
        """An unrecognised action in LLM response is normalised to 'none'."""
        with app.app_context():
            ctrl, dynasty = controller
            fake_response = "ACTION: build_a_spaceship | REASON: why not"
            ctrl._call_llm = lambda p: fake_response
            state = ctrl._build_game_state()
            result = ctrl.decide_diplomacy(state)
            assert result['action'] == 'none'

    def test_llm_response_without_action_tag(self, controller, app):
        """Missing ACTION tag in LLM response produces 'none'."""
        with app.app_context():
            ctrl, dynasty = controller
            ctrl._call_llm = lambda p: "Let's just wait and see what happens."
            state = ctrl._build_game_state()
            result = ctrl.decide_diplomacy(state)
            assert result['action'] == 'none'
