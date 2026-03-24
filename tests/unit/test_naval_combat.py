"""Unit tests for MilitarySystem.resolve_naval_battle."""

from unittest.mock import MagicMock, patch
import pytest

from models.db_models import UnitType
from models.military_system import MilitarySystem, NAVAL_UNIT_TYPES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unit(unit_type: UnitType, size: int = 100) -> MagicMock:
    """Return a mock MilitaryUnit with a working calculate_strength()."""
    unit = MagicMock()
    unit.unit_type = unit_type
    unit.size = size
    unit.calculate_strength.return_value = float(size)
    return unit


def _make_army(army_id: int, dynasty_id: int, units) -> MagicMock:
    """Return a mock Army with the given units list."""
    army = MagicMock()
    army.id = army_id
    army.dynasty_id = dynasty_id
    army.units = units
    return army


def _make_military_system(armies: dict) -> MilitarySystem:
    """Return a MilitarySystem whose session.query(Army).get() resolves from *armies*."""
    session = MagicMock()

    # Make session.query(Army).get(x) return armies[x]
    def _get(army_id):
        return armies.get(army_id)

    session.query.return_value.get.side_effect = _get

    # Also mock DynastyDB query to return None (no winter season)
    ms = MilitarySystem.__new__(MilitarySystem)
    ms.session = session
    return ms


# ---------------------------------------------------------------------------
# Test: blockade — attacker has no naval units
# ---------------------------------------------------------------------------

class TestNavalBlockadeAttackerNoNavy:
    def test_attacker_no_naval_units_returns_blockade_win_for_defender(self):
        land_unit = _make_unit(UnitType.LEVY_SPEARMEN, size=200)
        naval_unit = _make_unit(UnitType.WAR_GALLEY, size=150)

        army1 = _make_army(army_id=1, dynasty_id=10, units=[land_unit])   # no naval
        army2 = _make_army(army_id=2, dynasty_id=20, units=[naval_unit])  # has naval

        ms = _make_military_system({1: army1, 2: army2})
        result = ms.resolve_naval_battle(1, 2)

        assert result["is_blockade"] is True
        assert result["winner_army_id"] == 2
        assert result["loser_army_id"] == 1
        assert result["rounds"] == 0
        assert result["attacker_losses"] == 0
        assert result["defender_losses"] == 0
        assert any("Blockade" in line for line in result["battle_log"])


# ---------------------------------------------------------------------------
# Test: blockade — defender has no naval units
# ---------------------------------------------------------------------------

class TestNavalBlockadeDefenderNoNavy:
    def test_defender_no_naval_units_returns_blockade_win_for_attacker(self):
        naval_unit = _make_unit(UnitType.HEAVY_WARSHIP, size=200)
        land_unit = _make_unit(UnitType.PROFESSIONAL_SWORDSMEN, size=150)

        army1 = _make_army(army_id=1, dynasty_id=10, units=[naval_unit])  # has naval
        army2 = _make_army(army_id=2, dynasty_id=20, units=[land_unit])   # no naval

        ms = _make_military_system({1: army1, 2: army2})
        result = ms.resolve_naval_battle(1, 2)

        assert result["is_blockade"] is True
        assert result["winner_army_id"] == 1
        assert result["loser_army_id"] == 2
        assert result["rounds"] == 0
        assert result["attacker_losses"] == 0
        assert result["defender_losses"] == 0
        assert any("Blockade" in line for line in result["battle_log"])


# ---------------------------------------------------------------------------
# Test: blockade — neither side has naval units
# ---------------------------------------------------------------------------

class TestNavalNoUnitsEitherSide:
    def test_no_naval_units_on_either_side_returns_no_battle(self):
        army1 = _make_army(army_id=1, dynasty_id=10, units=[_make_unit(UnitType.ARCHERS)])
        army2 = _make_army(army_id=2, dynasty_id=20, units=[_make_unit(UnitType.HEAVY_CAVALRY)])

        ms = _make_military_system({1: army1, 2: army2})
        result = ms.resolve_naval_battle(1, 2)

        assert result["is_blockade"] is False
        assert result["winner_army_id"] is None
        assert result["loser_army_id"] is None
        assert result["rounds"] == 0
        assert any("No naval units" in line for line in result["battle_log"])


# ---------------------------------------------------------------------------
# Test: normal naval combat — attacker wins (much stronger)
# ---------------------------------------------------------------------------

class TestNavalCombatAttackerWins:
    def test_attacker_wins_with_overwhelming_force(self):
        # Attacker has a fleet that is far superior to defender
        naval_attacker = _make_unit(UnitType.HEAVY_WARSHIP, size=1000)
        naval_attacker.calculate_strength.return_value = 1000.0

        naval_defender = _make_unit(UnitType.TRANSPORT_SHIP, size=10)
        naval_defender.calculate_strength.return_value = 10.0

        army1 = _make_army(army_id=1, dynasty_id=10, units=[naval_attacker])
        army2 = _make_army(army_id=2, dynasty_id=20, units=[naval_defender])

        ms = _make_military_system({1: army1, 2: army2})
        result = ms.resolve_naval_battle(1, 2)

        assert result["is_blockade"] is False
        assert result["winner_army_id"] == 1, "Overwhelming attacker should win"
        assert result["loser_army_id"] == 2
        assert result["rounds"] > 0
        assert len(result["battle_log"]) > 0


# ---------------------------------------------------------------------------
# Test: normal naval combat — defender wins (attacker stalemates)
# ---------------------------------------------------------------------------

class TestNavalCombatDefenderWins:
    def test_defender_wins_stalemate_when_equal_strength(self):
        # Equal-strength fleets => stalemate => defender wins by default
        naval_attacker = _make_unit(UnitType.WAR_GALLEY, size=100)
        naval_attacker.calculate_strength.return_value = 100.0

        naval_defender = _make_unit(UnitType.WAR_GALLEY, size=100)
        naval_defender.calculate_strength.return_value = 100.0

        army1 = _make_army(army_id=1, dynasty_id=10, units=[naval_attacker])
        army2 = _make_army(army_id=2, dynasty_id=20, units=[naval_defender])

        ms = _make_military_system({1: army1, 2: army2})
        result = ms.resolve_naval_battle(1, 2)

        assert result["is_blockade"] is False
        # Equal fleets should exhaust 10 rounds without decisive victory → defender wins
        assert result["winner_army_id"] == 2
        assert result["rounds"] == 10


# ---------------------------------------------------------------------------
# Test: NAVAL_UNIT_TYPES constant contains the expected enum members
# ---------------------------------------------------------------------------

class TestNavalUnitTypesConstant:
    def test_constant_contains_all_four_naval_types(self):
        expected = {
            UnitType.TRANSPORT_SHIP,
            UnitType.WAR_GALLEY,
            UnitType.HEAVY_WARSHIP,
            UnitType.FIRE_SHIP,
        }
        assert expected == NAVAL_UNIT_TYPES

    def test_land_unit_not_in_naval_types(self):
        assert UnitType.LEVY_SPEARMEN not in NAVAL_UNIT_TYPES
        assert UnitType.HEAVY_CAVALRY not in NAVAL_UNIT_TYPES
        assert UnitType.TREBUCHET not in NAVAL_UNIT_TYPES
