# models/military_system.py
"""
Military system for the multi-agent strategic game.
Handles unit recruitment, army management, battles, and sieges.
"""

import random
import math
import datetime
import logging
import traceback
from typing import List, Dict, Tuple, Optional, Union, Any
from sqlalchemy.orm import Session
from models.db_models import (
    db, DynastyDB, PersonDB, Territory, TerrainType, Settlement,
    MilitaryUnit, UnitType, Army, Battle, Siege, War, WarGoal,
    HistoryLogEntryDB
)
from models.map_system import MovementSystem

# Import logging configuration if available, otherwise set up basic logging
try:
    from utils.logging_config import setup_logger, log_performance
    logger = setup_logger('royal_succession.military_system')
except ImportError:
    # Fallback logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('royal_succession.military_system')
    
    def log_performance(operation, duration, details=None):
        """Fallback performance logging function"""
        details_str = f" ({details})" if details else ""
        logger.info(f"Performance: {operation} took {duration:.6f}s{details_str}")

class MilitarySystem:
    """
    Core military system that handles unit recruitment, army management,
    battles, and sieges.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the military system.
        
        Args:
            session: SQLAlchemy database session
        """
        logger.info("Initializing MilitarySystem")
        """
        self.session = session
        self.movement_system = MovementSystem(session)
        
        # Unit recruitment costs and stats
        self.unit_costs = {
            UnitType.LEVY_SPEARMEN: {"gold": 10, "iron": 5, "manpower": 100},
            UnitType.PROFESSIONAL_SWORDSMEN: {"gold": 25, "iron": 15, "manpower": 100},
            UnitType.ELITE_GUARDS: {"gold": 50, "iron": 30, "manpower": 100},
            UnitType.ARCHERS: {"gold": 20, "iron": 10, "manpower": 100},
            UnitType.LIGHT_CAVALRY: {"gold": 30, "iron": 15, "manpower": 100},
            UnitType.HEAVY_CAVALRY: {"gold": 50, "iron": 30, "manpower": 100},
            UnitType.HORSE_ARCHERS: {"gold": 40, "iron": 20, "manpower": 100},
            UnitType.KNIGHTS: {"gold": 75, "iron": 40, "manpower": 100},
            UnitType.BATTERING_RAM: {"gold": 100, "timber": 50, "manpower": 50},
            UnitType.SIEGE_TOWER: {"gold": 150, "timber": 75, "manpower": 75},
            UnitType.CATAPULT: {"gold": 200, "timber": 50, "iron": 25, "manpower": 50},
            UnitType.TREBUCHET: {"gold": 300, "timber": 75, "iron": 50, "manpower": 75},
            UnitType.TRANSPORT_SHIP: {"gold": 150, "timber": 100, "manpower": 50},
            UnitType.WAR_GALLEY: {"gold": 250, "timber": 150, "manpower": 100},
            UnitType.HEAVY_WARSHIP: {"gold": 400, "timber": 200, "iron": 50, "manpower": 150},
            UnitType.FIRE_SHIP: {"gold": 300, "timber": 150, "manpower": 75}
        }
        
        # Unit base stats
        self.unit_stats = {
            UnitType.LEVY_SPEARMEN: {
                "attack": 3, "defense": 5, "morale": 3, "speed": 1.0,
                "maintenance_gold": 1, "maintenance_food": 1.0
            },
            UnitType.PROFESSIONAL_SWORDSMEN: {
                "attack": 6, "defense": 6, "morale": 5, "speed": 1.0,
                "maintenance_gold": 2, "maintenance_food": 1.0
            },
            UnitType.ELITE_GUARDS: {
                "attack": 8, "defense": 8, "morale": 8, "speed": 1.0,
                "maintenance_gold": 4, "maintenance_food": 1.0
            },
            UnitType.ARCHERS: {
                "attack": 7, "defense": 3, "morale": 4, "speed": 1.0,
                "maintenance_gold": 2, "maintenance_food": 1.0
            },
            UnitType.LIGHT_CAVALRY: {
                "attack": 6, "defense": 4, "morale": 5, "speed": 1.5,
                "maintenance_gold": 3, "maintenance_food": 1.5
            },
            UnitType.HEAVY_CAVALRY: {
                "attack": 10, "defense": 7, "morale": 6, "speed": 1.2,
                "maintenance_gold": 5, "maintenance_food": 1.5
            },
            UnitType.HORSE_ARCHERS: {
                "attack": 8, "defense": 3, "morale": 5, "speed": 1.5,
                "maintenance_gold": 4, "maintenance_food": 1.5
            },
            UnitType.KNIGHTS: {
                "attack": 12, "defense": 10, "morale": 8, "speed": 1.3,
                "maintenance_gold": 7, "maintenance_food": 2.0
            },
            UnitType.BATTERING_RAM: {
                "attack": 2, "defense": 2, "morale": 3, "speed": 0.5,
                "maintenance_gold": 2, "maintenance_food": 0.5,
                "siege_bonus": 5
            },
            UnitType.SIEGE_TOWER: {
                "attack": 1, "defense": 3, "morale": 3, "speed": 0.4,
                "maintenance_gold": 3, "maintenance_food": 0.5,
                "siege_bonus": 7
            },
            UnitType.CATAPULT: {
                "attack": 8, "defense": 1, "morale": 4, "speed": 0.6,
                "maintenance_gold": 4, "maintenance_food": 0.5,
                "siege_bonus": 10
            },
            UnitType.TREBUCHET: {
                "attack": 12, "defense": 1, "morale": 4, "speed": 0.4,
                "maintenance_gold": 6, "maintenance_food": 0.5,
                "siege_bonus": 15
            },
            UnitType.TRANSPORT_SHIP: {
                "attack": 1, "defense": 3, "morale": 4, "speed": 1.0,
                "maintenance_gold": 3, "maintenance_food": 1.0,
                "transport_capacity": 500
            },
            UnitType.WAR_GALLEY: {
                "attack": 6, "defense": 5, "morale": 5, "speed": 1.2,
                "maintenance_gold": 5, "maintenance_food": 1.5
            },
            UnitType.HEAVY_WARSHIP: {
                "attack": 10, "defense": 8, "morale": 6, "speed": 0.8,
                "maintenance_gold": 8, "maintenance_food": 2.0
            },
            UnitType.FIRE_SHIP: {
                "attack": 15, "defense": 2, "morale": 3, "speed": 1.0,
                "maintenance_gold": 6, "maintenance_food": 1.5
            }
        }
        
        # Training time in days for each unit type
        self.training_times = {
            UnitType.LEVY_SPEARMEN: 30,
            UnitType.PROFESSIONAL_SWORDSMEN: 60,
            UnitType.ELITE_GUARDS: 90,
            UnitType.ARCHERS: 45,
            UnitType.LIGHT_CAVALRY: 60,
            UnitType.HEAVY_CAVALRY: 90,
            UnitType.HORSE_ARCHERS: 75,
            UnitType.KNIGHTS: 120,
            UnitType.BATTERING_RAM: 45,
            UnitType.SIEGE_TOWER: 60,
            UnitType.CATAPULT: 75,
            UnitType.TREBUCHET: 90,
            UnitType.TRANSPORT_SHIP: 60,
            UnitType.WAR_GALLEY: 90,
            UnitType.HEAVY_WARSHIP: 120,
            UnitType.FIRE_SHIP: 75
        }
    
    def recruit_unit(self, dynasty_id: int, unit_type: UnitType, size: int,
                    territory_id: Optional[int] = None, name: Optional[str] = None) -> Tuple[bool, str, Optional[MilitaryUnit]]:
        """
        Recruit a new military unit for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty recruiting the unit
            unit_type: Type of unit to recruit
            size: Size of the unit (number of troops)
            territory_id: ID of the territory to recruit in (optional)
            name: Custom name for the unit (optional)
            
        Returns:
            Tuple of (success, message, unit)
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return False, f"Dynasty with ID {dynasty_id} not found", None
        
        # Check if unit type is valid
        if unit_type not in self.unit_costs:
            return False, f"Invalid unit type: {unit_type}", None
        
        # Calculate total cost
        unit_cost = self.unit_costs[unit_type]
        total_gold_cost = unit_cost.get("gold", 0) * size / 100
        
        # Check if dynasty has enough gold
        if dynasty.current_wealth < total_gold_cost:
            return False, f"Not enough gold. Required: {total_gold_cost}, Available: {dynasty.current_wealth}", None
        
        # Check territory if provided
        territory = None
        if territory_id:
            territory = self.session.query(Territory).get(territory_id)
            if not territory:
                return False, f"Territory with ID {territory_id} not found", None
            
            # Check if territory is controlled by dynasty
            if territory.controller_dynasty_id != dynasty_id:
                return False, "Cannot recruit in territory not controlled by dynasty", None
            
            # Check if territory has enough manpower
            manpower_required = unit_cost.get("manpower", 0) * size / 100
            if territory.base_manpower < manpower_required:
                return False, f"Not enough manpower in territory. Required: {manpower_required}, Available: {territory.base_manpower}", None
        
        # Create the unit
        unit_stats = self.unit_stats[unit_type]
        new_unit = MilitaryUnit(
            dynasty_id=dynasty_id,
            unit_type=unit_type,
            name=name if name else f"{dynasty.name} {unit_type.value.replace('_', ' ').title()}",
            size=size,
            quality=1.0,  # Base quality
            experience=0.0,  # No experience initially
            morale=1.0,  # Full morale
            territory_id=territory_id,
            maintenance_cost=unit_stats["maintenance_gold"] * size / 100,
            food_consumption=unit_stats["maintenance_food"] * size / 100,
            created_year=dynasty.current_simulation_year
        )
        
        # Deduct costs
        dynasty.current_wealth -= total_gold_cost
        
        # Deduct manpower from territory if applicable
        if territory:
            manpower_required = unit_cost.get("manpower", 0) * size / 100
            territory.base_manpower -= manpower_required
        
        # Add to database
        self.session.add(new_unit)
        self.session.commit()
        
        # Create history log entry
        log_entry = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=dynasty.current_simulation_year,
            event_string=f"Recruited {size} {unit_type.value.replace('_', ' ').title()} troops",
            event_type="military_recruitment",
            territory_id=territory_id
        )
        self.session.add(log_entry)
        self.session.commit()
        
        return True, f"Successfully recruited {size} {unit_type.value.replace('_', ' ').title()} troops", new_unit
    
    def form_army(self, dynasty_id: int, unit_ids: List[int], name: str, 
                 commander_id: Optional[int] = None) -> Tuple[bool, str, Optional[Army]]:
        """
        Form a new army from individual units.
        
        Args:
            dynasty_id: ID of the dynasty forming the army
            unit_ids: List of unit IDs to include in the army
            name: Name for the army
            commander_id: ID of the person to command the army (optional)
            
        Returns:
            Tuple of (success, message, army)
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return False, f"Dynasty with ID {dynasty_id} not found", None
        
        # Check if units exist and belong to dynasty
        units = []
        for unit_id in unit_ids:
            unit = self.session.query(MilitaryUnit).get(unit_id)
            if not unit:
                return False, f"Unit with ID {unit_id} not found", None
            if unit.dynasty_id != dynasty_id:
                return False, f"Unit with ID {unit_id} does not belong to dynasty", None
            if unit.army_id:
                return False, f"Unit with ID {unit_id} is already part of an army", None
            units.append(unit)
        
        if not units:
            return False, "No valid units provided", None
        
        # Check if all units are in the same territory
        territory_id = units[0].territory_id
        for unit in units[1:]:
            if unit.territory_id != territory_id:
                return False, "All units must be in the same territory to form an army", None
        
        # Check commander if provided
        commander = None
        if commander_id:
            commander = self.session.query(PersonDB).get(commander_id)
            if not commander:
                return False, f"Person with ID {commander_id} not found", None
            if commander.dynasty_id != dynasty_id:
                return False, f"Person with ID {commander_id} does not belong to dynasty", None
            if not commander.can_lead_army():
                return False, f"{commander.name} {commander.surname} cannot lead an army", None
        
        # Create the army
        new_army = Army(
            dynasty_id=dynasty_id,
            name=name,
            territory_id=territory_id,
            commander_id=commander_id,
            is_active=True,
            is_sieging=False,
            created_year=dynasty.current_simulation_year
        )
        self.session.add(new_army)
        self.session.flush()  # Get ID without committing
        
        # Add units to army
        for unit in units:
            unit.army_id = new_army.id
        
        # Commit changes
        self.session.commit()
        
        # Create history log entry
        log_entry = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=dynasty.current_simulation_year,
            event_string=f"Formed army '{name}' with {len(units)} units",
            event_type="army_formation",
            territory_id=territory_id
        )
        self.session.add(log_entry)
        self.session.commit()
        
        return True, f"Successfully formed army '{name}' with {len(units)} units", new_army
    
    def assign_commander(self, army_id: int, commander_id: int) -> Tuple[bool, str]:
        """
        Assign a commander to an army.
        
        Args:
            army_id: ID of the army
            commander_id: ID of the person to command the army
            
        Returns:
            Tuple of (success, message)
        """
        # Get army
        army = self.session.query(Army).get(army_id)
        if not army:
            return False, f"Army with ID {army_id} not found"
        
        # Get commander
        commander = self.session.query(PersonDB).get(commander_id)
        if not commander:
            return False, f"Person with ID {commander_id} not found"
        
        # Check if commander belongs to same dynasty as army
        if commander.dynasty_id != army.dynasty_id:
            return False, f"Commander must belong to the same dynasty as the army"
        
        # Check if commander can lead army
        if not commander.can_lead_army():
            return False, f"{commander.name} {commander.surname} cannot lead an army"
        
        # Assign commander
        army.commander_id = commander_id
        self.session.commit()
        
        # Create history log entry
        log_entry = HistoryLogEntryDB(
            dynasty_id=army.dynasty_id,
            year=self.session.query(DynastyDB).get(army.dynasty_id).current_simulation_year,
            event_string=f"{commander.name} {commander.surname} was assigned to command the army '{army.name}'",
            event_type="commander_assignment",
            person1_sim_id=commander.id
        )
        self.session.add(log_entry)
        self.session.commit()
        
        return True, f"Successfully assigned {commander.name} {commander.surname} as commander of army '{army.name}'"
    
    def calculate_maintenance(self, dynasty_id: int) -> Dict[str, float]:
        """
        Calculate the total maintenance cost for all military units of a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Dictionary with maintenance costs
        """
        # Get all units belonging to dynasty
        units = self.session.query(MilitaryUnit).filter_by(dynasty_id=dynasty_id).all()
        
        # Calculate costs
        total_gold = 0
        total_food = 0
        
        for unit in units:
            unit_stats = self.unit_stats.get(unit.unit_type, {})
            gold_cost = unit_stats.get("maintenance_gold", 1) * unit.size / 100
            food_cost = unit_stats.get("maintenance_food", 1) * unit.size / 100
            
            total_gold += gold_cost
            total_food += food_cost
        
        return {
            "gold": total_gold,
            "food": total_food
        }
    
    def apply_maintenance(self, dynasty_id: int) -> Tuple[bool, str, Dict[str, float]]:
        """
        Apply maintenance costs to a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Tuple of (success, message, costs)
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return False, f"Dynasty with ID {dynasty_id} not found", {}
        
        # Calculate maintenance costs
        costs = self.calculate_maintenance(dynasty_id)
        
        # Check if dynasty has enough gold
        if dynasty.current_wealth < costs["gold"]:
            # Not enough gold, reduce morale of units
            units = self.session.query(MilitaryUnit).filter_by(dynasty_id=dynasty_id).all()
            for unit in units:
                unit.morale = max(0.1, unit.morale - 0.2)  # Reduce morale by 20%, minimum 10%
            
            self.session.commit()
            
            # Create history log entry
            log_entry = HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=dynasty.current_simulation_year,
                event_string=f"Unable to pay military maintenance. Troops' morale has decreased.",
                event_type="military_maintenance_failure"
            )
            self.session.add(log_entry)
            self.session.commit()
            
            return False, "Not enough gold for military maintenance. Troops' morale has decreased.", costs
        
        # Deduct maintenance costs
        dynasty.current_wealth -= costs["gold"]
        self.session.commit()
        
        # Create history log entry
        log_entry = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=dynasty.current_simulation_year,
            event_string=f"Paid {costs['gold']} gold for military maintenance.",
            event_type="military_maintenance"
        )
        self.session.add(log_entry)
        self.session.commit()
        
        return True, f"Successfully paid military maintenance: {costs['gold']} gold", costs
    
    def initiate_battle(self, attacker_army_id: int, defender_army_id: int, 
                       territory_id: int, war_id: Optional[int] = None) -> Tuple[bool, str, Optional[Battle]]:
        """
        Initiate a battle between two armies.
        
        Args:
            attacker_army_id: ID of the attacking army
            defender_army_id: ID of the defending army
            territory_id: ID of the territory where the battle takes place
            war_id: ID of the war this battle is part of (optional)
            
        Returns:
            Tuple of (success, message, battle)
        """
        # Get armies
        attacker_army = self.session.query(Army).get(attacker_army_id)
        defender_army = self.session.query(Army).get(defender_army_id)
        
        if not attacker_army:
            return False, f"Attacker army with ID {attacker_army_id} not found", None
        if not defender_army:
            return False, f"Defender army with ID {defender_army_id} not found", None
        
        # Check if armies are in the same territory
        if attacker_army.territory_id != territory_id or defender_army.territory_id != territory_id:
            return False, "Both armies must be in the specified territory", None
        
        # Get territory
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return False, f"Territory with ID {territory_id} not found", None
        
        # Get dynasties
        attacker_dynasty = self.session.query(DynastyDB).get(attacker_army.dynasty_id)
        defender_dynasty = self.session.query(DynastyDB).get(defender_army.dynasty_id)
        
        if not attacker_dynasty or not defender_dynasty:
            return False, "Could not find dynasties for armies", None
        
        # Create battle
        battle = Battle(
            war_id=war_id,
            territory_id=territory_id,
            year=attacker_dynasty.current_simulation_year,
            attacker_dynasty_id=attacker_dynasty.id,
            defender_dynasty_id=defender_dynasty.id,
            attacker_army_id=attacker_army.id,
            defender_army_id=defender_army.id
        )
        self.session.add(battle)
        self.session.flush()  # Get ID without committing
        
        # Resolve battle
        winner_id, attacker_casualties, defender_casualties, battle_details = self._resolve_battle(
            attacker_army, defender_army, territory
        )
        
        # Update battle with results
        battle.winner_dynasty_id = winner_id
        battle.attacker_casualties = attacker_casualties
        battle.defender_casualties = defender_casualties
        battle.set_details(battle_details)
        
        # Apply casualties to units
        self._apply_battle_casualties(attacker_army, attacker_casualties)
        self._apply_battle_casualties(defender_army, defender_casualties)
        
        # Update war score if part of a war
        if war_id:
            war = self.session.query(War).get(war_id)
            if war:
                war.calculate_war_score()
        
        # Commit changes
        self.session.commit()
        
        # Create history log entry
        winner_name = attacker_dynasty.name if winner_id == attacker_dynasty.id else defender_dynasty.name
        loser_name = defender_dynasty.name if winner_id == attacker_dynasty.id else attacker_dynasty.name
        
        log_entry = HistoryLogEntryDB(
            dynasty_id=attacker_dynasty.id,
            year=attacker_dynasty.current_simulation_year,
            event_string=f"Battle of {territory.name}: {winner_name} defeated {loser_name}. Casualties: {attacker_casualties} attackers, {defender_casualties} defenders.",
            event_type="battle",
            territory_id=territory_id,
            battle_id=battle.id,
            war_id=war_id
        )
        self.session.add(log_entry)
        
        # Also add to defender's history
        defender_log = HistoryLogEntryDB(
            dynasty_id=defender_dynasty.id,
            year=defender_dynasty.current_simulation_year,
            event_string=f"Battle of {territory.name}: {winner_name} defeated {loser_name}. Casualties: {attacker_casualties} attackers, {defender_casualties} defenders.",
            event_type="battle",
            territory_id=territory_id,
            battle_id=battle.id,
            war_id=war_id
        )
        self.session.add(defender_log)
        self.session.commit()
        
        return True, f"Battle resolved. {winner_name} was victorious.", battle
    
    def _resolve_battle(self, attacker_army: Army, defender_army: Army,
                       territory: Territory) -> Tuple[int, int, int, Dict[str, Any]]:
        """
        Resolve a battle between two armies.
                
                Args:
                    attacker_army: Attacking army
                    defender_army: Defending army
                    territory: Territory where the battle takes place
                    
            
        Returns:
            Tuple of (winner_dynasty_id, attacker_casualties, defender_casualties, battle_details)
        """
        # Calculate initial strengths
        attacker_strength = attacker_army.calculate_total_strength(territory.terrain_type)
        defender_strength = defender_army.calculate_total_strength(territory.terrain_type)
        
        # Apply terrain bonuses for defender
        if territory.controller_dynasty_id == defender_army.dynasty_id:
            defender_strength *= 1.2  # 20% bonus for defending controlled territory
        
        # Apply fortification bonus if territory has fortifications
        if territory.fortification_level > 0:
            defender_strength *= (1 + territory.fortification_level * 0.1)  # 10% per fortification level
        
        # Calculate total troops
        attacker_troops = sum(unit.size for unit in attacker_army.units)
        defender_troops = sum(unit.size for unit in defender_army.units)
        
        # Battle simulation
        rounds = []
        attacker_remaining = attacker_troops
        defender_remaining = defender_troops
        
        # Initial round
        initial_round = {
            "round": 0,
            "attacker_strength": attacker_strength,
            "defender_strength": defender_strength,
            "attacker_troops": attacker_troops,
            "defender_troops": defender_troops
        }
        rounds.append(initial_round)
        
        # Simulate up to 5 rounds of combat
        for round_num in range(1, 6):
            # Calculate casualties based on strength ratio
            attacker_casualties_this_round = int(defender_strength / attacker_strength * random.uniform(0.05, 0.15) * attacker_remaining)
            defender_casualties_this_round = int(attacker_strength / defender_strength * random.uniform(0.05, 0.15) * defender_remaining)
            
            # Apply casualties
            attacker_remaining -= attacker_casualties_this_round
            defender_remaining -= defender_casualties_this_round
            
            # Ensure non-negative
            attacker_remaining = max(0, attacker_remaining)
            defender_remaining = max(0, defender_remaining)
            
            # Update strengths
            attacker_strength = attacker_strength * (attacker_remaining / attacker_troops) if attacker_troops > 0 else 0
            defender_strength = defender_strength * (defender_remaining / defender_troops) if defender_troops > 0 else 0
            
            # Record round
            round_data = {
                "round": round_num,
                "attacker_casualties": attacker_casualties_this_round,
                "defender_casualties": defender_casualties_this_round,
                "attacker_remaining": attacker_remaining,
                "defender_remaining": defender_remaining,
                "attacker_strength": attacker_strength,
                "defender_strength": defender_strength
            }
            rounds.append(round_data)
            
            # Check for decisive victory
            if attacker_remaining <= attacker_troops * 0.2 or defender_remaining <= defender_troops * 0.2:
                break
        
        # Determine winner
        attacker_casualty_ratio = (attacker_troops - attacker_remaining) / attacker_troops if attacker_troops > 0 else 1
        defender_casualty_ratio = (defender_troops - defender_remaining) / defender_troops if defender_troops > 0 else 1
        
        winner_dynasty_id = None
        if attacker_remaining <= 0:
            winner_dynasty_id = defender_army.dynasty_id
        elif defender_remaining <= 0:
            winner_dynasty_id = attacker_army.dynasty_id
        elif attacker_casualty_ratio > defender_casualty_ratio * 1.5:
            winner_dynasty_id = defender_army.dynasty_id
        elif defender_casualty_ratio > attacker_casualty_ratio * 1.5:
            winner_dynasty_id = attacker_army.dynasty_id
        else:
            # No clear winner, determine based on remaining strength
            if attacker_strength > defender_strength:
                winner_dynasty_id = attacker_army.dynasty_id
            else:
                winner_dynasty_id = defender_army.dynasty_id
        
        # Calculate total casualties
        attacker_casualties = attacker_troops - attacker_remaining
        defender_casualties = defender_troops - defender_remaining
        
        # Create battle details
        battle_details = {
            "rounds": rounds,
            "initial_attacker_strength": initial_round["attacker_strength"],
            "initial_defender_strength": initial_round["defender_strength"],
            "final_attacker_strength": attacker_strength,
            "final_defender_strength": defender_strength,
            "attacker_casualty_ratio": attacker_casualty_ratio,
            "defender_casualty_ratio": defender_casualty_ratio
        }
        
        return winner_dynasty_id, attacker_casualties, defender_casualties, battle_details
    
    def _apply_battle_casualties(self, army: Army, total_casualties: int) -> None:
        """
        Apply casualties to units in an army.
        
        Args:
            army: The army that suffered casualties
            total_casualties: Total number of casualties to distribute
        """
        if total_casualties <= 0:
            return
        
        # Get all units in the army
        units = list(army.units)
        if not units:
            return
        
        # Calculate total troops
        total_troops = sum(unit.size for unit in units)
        if total_troops <= 0:
            return
        
        # Calculate casualty ratio
        casualty_ratio = total_casualties / total_troops
        
        # Apply casualties to each unit proportionally
        remaining_casualties = total_casualties
        for unit in units:
            # Calculate unit casualties
            unit_casualties = int(unit.size * casualty_ratio)
            
            # Ensure we don't exceed total casualties
            unit_casualties = min(unit_casualties, remaining_casualties)
            
            # Apply casualties
            unit.size -= unit_casualties
            remaining_casualties -= unit_casualties
            
            # Ensure unit size is at least 1 or remove the unit
            if unit.size < 1:
                self.session.delete(unit)
            else:
                # Reduce morale based on casualties
                unit_casualty_ratio = unit_casualties / (unit.size + unit_casualties)
                unit.morale = max(0.1, unit.morale - unit_casualty_ratio * 0.5)
                
                # Increase experience for survivors
                unit.experience = min(1.0, unit.experience + 0.05)
        
        # If there are still casualties to distribute, apply them to the largest unit
        if remaining_casualties > 0:
            units.sort(key=lambda u: u.size, reverse=True)
            for unit in units:
                if unit.size > remaining_casualties:
                    unit.size -= remaining_casualties
                    break
    
    def initiate_siege(self, army_id: int, territory_id: int, 
                      war_id: Optional[int] = None) -> Tuple[bool, str, Optional[Siege]]:
        """
        Initiate a siege of a territory by an army.
        
        Args:
            army_id: ID of the army conducting the siege
            territory_id: ID of the territory being sieged
            war_id: ID of the war this siege is part of (optional)
            
        Returns:
            Tuple of (success, message, siege)
        """
        # Get army
        army = self.session.query(Army).get(army_id)
        if not army:
            return False, f"Army with ID {army_id} not found", None
        
        # Get territory
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return False, f"Territory with ID {territory_id} not found", None
        
        # Check if army is in the territory
        if army.territory_id != territory_id:
            return False, "Army must be in the territory to initiate a siege", None
        
        # Check if territory is controlled by another dynasty
        if not territory.controller_dynasty_id:
            return False, "Territory is not controlled by any dynasty", None
        if territory.controller_dynasty_id == army.dynasty_id:
            return False, "Cannot siege own territory", None
        
        # Get defender dynasty
        defender_dynasty = self.session.query(DynastyDB).get(territory.controller_dynasty_id)
        if not defender_dynasty:
            return False, "Defender dynasty not found", None
        
        # Check if army is already sieging
        if army.is_sieging:
            return False, "Army is already conducting a siege", None
        
        # Create siege
        siege = Siege(
            war_id=war_id,
            territory_id=territory_id,
            attacker_dynasty_id=army.dynasty_id,
            defender_dynasty_id=territory.controller_dynasty_id,
            attacker_army_id=army_id,
            start_year=self.session.query(DynastyDB).get(army.dynasty_id).current_simulation_year,
            progress=0.0,
            is_active=True,
            successful=False
        )
        self.session.add(siege)
        
        # Mark army as sieging
        army.is_sieging = True
        
        # Commit changes
        self.session.commit()
        
        # Create history log entry
        attacker_dynasty = self.session.query(DynastyDB).get(army.dynasty_id)
        log_entry = HistoryLogEntryDB(
            dynasty_id=army.dynasty_id,
            year=attacker_dynasty.current_simulation_year,
            event_string=f"Army '{army.name}' began a siege of {territory.name}, controlled by {defender_dynasty.name}.",
            event_type="siege_start",
            territory_id=territory_id,
            war_id=war_id
        )
        self.session.add(log_entry)
        
        # Also add to defender's history
        defender_log = HistoryLogEntryDB(
            dynasty_id=territory.controller_dynasty_id,
            year=defender_dynasty.current_simulation_year,
            event_string=f"{attacker_dynasty.name}'s army '{army.name}' began a siege of {territory.name}.",
            event_type="siege_start",
            territory_id=territory_id,
            war_id=war_id
        )
        self.session.add(defender_log)
        self.session.commit()
        
        return True, f"Siege of {territory.name} initiated by army '{army.name}'.", siege
    
    def update_siege(self, siege_id: int) -> Tuple[bool, str, Optional[Siege]]:
        """
        Update the progress of a siege.
        
        Args:
            siege_id: ID of the siege to update
            
        Returns:
            Tuple of (success, message, siege)
        """
        # Get siege
        siege = self.session.query(Siege).get(siege_id)
        if not siege:
            return False, f"Siege with ID {siege_id} not found", None
        
        # Check if siege is active
        if not siege.is_active:
            return False, "Siege is no longer active", None
        
        # Get army and territory
        army = self.session.query(Army).get(siege.attacker_army_id)
        territory = self.session.query(Territory).get(siege.territory_id)
        
        if not army or not territory:
            return False, "Army or territory not found", None
        
        # Check if army is still in the territory
        if army.territory_id != territory.id:
            # End siege if army has moved
            siege.is_active = False
            siege.end_year = self.session.query(DynastyDB).get(siege.attacker_dynasty_id).current_simulation_year
            self.session.commit()
            return False, "Siege ended because army is no longer in the territory", siege
        
        # Calculate siege progress increment
        base_progress = 0.05  # Base 5% progress per update
        
        # Adjust for fortification level
        if territory.fortification_level > 0:
            base_progress /= (1 + territory.fortification_level * 0.2)  # Reduce progress by 20% per fortification level
        
        # Adjust for siege equipment
        siege_bonus = 0
        for unit in army.units:
            if unit.unit_type in [UnitType.BATTERING_RAM, UnitType.SIEGE_TOWER, UnitType.CATAPULT, UnitType.TREBUCHET]:
                unit_stats = self.unit_stats.get(unit.unit_type, {})
                siege_bonus += unit_stats.get("siege_bonus", 0) * unit.size / 100
        
        # Apply siege bonus
        progress_increment = base_progress * (1 + siege_bonus * 0.1)
        
        # Update siege progress
        siege.progress = min(1.0, siege.progress + progress_increment)
        
        # Check if siege is successful
        if siege.progress >= 1.0:
            siege.is_active = False
            siege.successful = True
            siege.end_year = self.session.query(DynastyDB).get(siege.attacker_dynasty_id).current_simulation_year
            
            # Transfer control of territory
            territory.controller_dynasty_id = siege.attacker_dynasty_id
            
            # Reset army siege status
            army.is_sieging = False
            
            # Update war score if part of a war
            if siege.war_id:
                war = self.session.query(War).get(siege.war_id)
                if war:
                    war.calculate_war_score()
            
            # Create history log entries
            attacker_dynasty = self.session.query(DynastyDB).get(siege.attacker_dynasty_id)
            defender_dynasty = self.session.query(DynastyDB).get(siege.defender_dynasty_id)
            
            log_entry = HistoryLogEntryDB(
                dynasty_id=siege.attacker_dynasty_id,
                year=attacker_dynasty.current_simulation_year,
                event_string=f"Siege of {territory.name} successful. Territory captured from {defender_dynasty.name}.",
                event_type="siege_success",
                territory_id=territory.id,
                war_id=siege.war_id
            )
            self.session.add(log_entry)
            
            defender_log = HistoryLogEntryDB(
                dynasty_id=siege.defender_dynasty_id,
                year=defender_dynasty.current_simulation_year,
                event_string=f"{territory.name} has fallen to {attacker_dynasty.name} after a siege.",
                event_type="siege_failure",
                territory_id=territory.id,
                war_id=siege.war_id
            )
            self.session.add(defender_log)
            
            self.session.commit()
            return True, f"Siege of {territory.name} successful. Territory captured.", siege
        
        # Siege continues
        self.session.commit()
        return True, f"Siege of {territory.name} continues. Progress: {siege.progress:.1%}", siege
        return True, f"Battle resolved. {winner_name} was victorious.", battle