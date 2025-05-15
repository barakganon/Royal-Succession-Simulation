# models/time_system.py
"""
Time synchronization system for the multi-agent strategic game.
Handles turn-based game progression, event scheduling and processing,
synchronization between multiple players, time-based events and triggers,
season and weather effects, and historical event logging and timeline.
"""

import random
import datetime
import enum
import json
from typing import List, Dict, Tuple, Optional, Union, Any, Set
from sqlalchemy.orm import Session
from models.db_models import (
    db, DynastyDB, PersonDB, Territory, TerrainType, Settlement,
    Resource, ResourceType, TerritoryResource, Building, BuildingType,
    MilitaryUnit, Army, Battle, Siege, War, DiplomaticRelation, Treaty,
    HistoryLogEntryDB, Region, Province
)

class Season(enum.Enum):
    """Enumeration of seasons."""
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

class EventPriority(enum.Enum):
    """Enumeration of event priorities."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3

class EventType(enum.Enum):
    """Enumeration of event types."""
    DIPLOMATIC = "diplomatic"
    MILITARY = "military"
    ECONOMIC = "economic"
    CHARACTER = "character"
    NATURAL = "natural"
    SCHEDULED = "scheduled"
    CONDITIONAL = "conditional"

class GamePhase(enum.Enum):
    """Enumeration of game phases within a turn."""
    PLANNING = "planning"
    DIPLOMATIC = "diplomatic"
    MILITARY = "military"
    ECONOMIC = "economic"
    CHARACTER = "character"
    RESOLUTION = "resolution"

class TimeSystem:
    """
    Core time system that handles turn-based game progression, event scheduling
    and processing, synchronization between multiple players, time-based events
    and triggers, season and weather effects, and historical event logging and timeline.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the time system.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        
        # Scheduled events queue
        self.scheduled_events = []
        
        # Season effects on production and movement
        self.season_production_modifiers = {
            Season.SPRING: {
                ResourceType.FOOD: 1.2,
                ResourceType.TIMBER: 1.1,
                "movement_cost": 1.1,  # Slightly increased due to rain
                "population_growth": 1.2
            },
            Season.SUMMER: {
                ResourceType.FOOD: 1.5,
                ResourceType.TIMBER: 1.0,
                ResourceType.STONE: 1.2,
                ResourceType.IRON: 1.2,
                "movement_cost": 0.8,  # Reduced cost
                "population_growth": 1.0
            },
            Season.AUTUMN: {
                ResourceType.FOOD: 1.3,
                ResourceType.TIMBER: 1.2,
                ResourceType.STONE: 1.0,
                ResourceType.IRON: 1.0,
                "movement_cost": 1.0,  # Normal cost
                "population_growth": 0.9
            },
            Season.WINTER: {
                ResourceType.FOOD: 0.5,
                ResourceType.TIMBER: 0.7,
                ResourceType.STONE: 0.6,
                ResourceType.IRON: 0.7,
                "movement_cost": 1.5,  # Increased cost
                "population_growth": 0.7
            }
        }
        
        # Weather probabilities by season
        self.weather_probabilities = {
            Season.SPRING: {
                "clear": 0.4,
                "rain": 0.4,
                "storm": 0.15,
                "fog": 0.05
            },
            Season.SUMMER: {
                "clear": 0.6,
                "rain": 0.2,
                "storm": 0.15,
                "drought": 0.05
            },
            Season.AUTUMN: {
                "clear": 0.3,
                "rain": 0.4,
                "storm": 0.2,
                "fog": 0.1
            },
            Season.WINTER: {
                "clear": 0.3,
                "snow": 0.4,
                "blizzard": 0.2,
                "fog": 0.1
            }
        }
        
        # Weather effects on production and movement
        self.weather_effects = {
            "clear": {
                "production_modifier": 1.0,
                "movement_modifier": 1.0
            },
            "rain": {
                "production_modifier": 0.9,
                "movement_modifier": 1.2,
                ResourceType.FOOD: 1.1  # Rain helps crops
            },
            "storm": {
                "production_modifier": 0.7,
                "movement_modifier": 1.5,
                "naval_movement_modifier": 2.0,
                "battle_modifier": 0.8  # Harder to fight in storms
            },
            "fog": {
                "production_modifier": 0.9,
                "movement_modifier": 1.3,
                "naval_movement_modifier": 1.5,
                "battle_modifier": 0.7  # Harder to coordinate in fog
            },
            "snow": {
                "production_modifier": 0.6,
                "movement_modifier": 1.7,
                "battle_modifier": 0.8
            },
            "blizzard": {
                "production_modifier": 0.3,
                "movement_modifier": 2.5,
                "naval_movement_modifier": 3.0,
                "battle_modifier": 0.5
            },
            "drought": {
                "production_modifier": 0.7,
                ResourceType.FOOD: 0.5,  # Severe impact on food
                "movement_modifier": 0.9,  # Easier to move on dry land
                "fire_risk": 1.5  # Increased risk of fires
            }
        }
        
        # Action points cost by action type
        self.action_point_costs = {
            "recruit_unit": 1,
            "form_army": 1,
            "move_unit": 1,
            "move_army": 2,
            "initiate_battle": 3,
            "initiate_siege": 3,
            "construct_building": 2,
            "upgrade_building": 2,
            "repair_building": 1,
            "develop_territory": 3,
            "establish_trade": 2,
            "cancel_trade": 1,
            "diplomatic_action": 1,
            "create_treaty": 2,
            "break_treaty": 2,
            "declare_war": 4,
            "negotiate_peace": 3
        }
    
    def get_current_season(self, year: int) -> Season:
        """
        Get the current season based on the year.
        
        Args:
            year: Current game year
            
        Returns:
            Current season
        """
        # Simple season calculation based on year
        # Each year has 4 seasons, and we determine the current one
        # based on the year modulo 4
        season_index = year % 4
        if season_index == 0:
            return Season.SPRING
        elif season_index == 1:
            return Season.SUMMER
        elif season_index == 2:
            return Season.AUTUMN
        else:
            return Season.WINTER
    
    def get_weather_for_region(self, region_id: int, season: Season) -> str:
        """
        Get the current weather for a region based on season.
        
        Args:
            region_id: ID of the region
            season: Current season
            
        Returns:
            Weather condition
        """
        # Get weather probabilities for the season
        probabilities = self.weather_probabilities.get(season, {})
        
        # Get region for climate adjustment
        region = self.session.query(Region).get(region_id)
        if not region:
            # Default to random weather based on season probabilities
            weather_types = list(probabilities.keys())
            weights = list(probabilities.values())
            return random.choices(weather_types, weights=weights, k=1)[0]
        
        # Adjust probabilities based on region climate
        adjusted_probabilities = probabilities.copy()
        
        if region.base_climate == "arid":
            # Arid regions have less rain and more clear weather
            if "rain" in adjusted_probabilities:
                adjusted_probabilities["rain"] *= 0.5
            if "clear" in adjusted_probabilities:
                adjusted_probabilities["clear"] *= 1.5
            if "drought" in adjusted_probabilities:
                adjusted_probabilities["drought"] *= 2.0
                
        elif region.base_climate == "tropical":
            # Tropical regions have more rain and storms
            if "rain" in adjusted_probabilities:
                adjusted_probabilities["rain"] *= 1.5
            if "storm" in adjusted_probabilities:
                adjusted_probabilities["storm"] *= 1.3
                
        elif region.base_climate == "cold":
            # Cold regions have more snow and blizzards
            if "snow" in adjusted_probabilities:
                adjusted_probabilities["snow"] *= 1.5
            if "blizzard" in adjusted_probabilities:
                adjusted_probabilities["blizzard"] *= 1.3
        
        # Normalize probabilities
        total = sum(adjusted_probabilities.values())
        normalized_probabilities = {k: v/total for k, v in adjusted_probabilities.items()}
        
        # Select weather based on adjusted probabilities
        weather_types = list(normalized_probabilities.keys())
        weights = list(normalized_probabilities.values())
        return random.choices(weather_types, weights=weights, k=1)[0]
    
    def schedule_event(self, event_type: EventType, year: int, data: Dict[str, Any], 
                      priority: EventPriority = EventPriority.MEDIUM) -> int:
        """
        Schedule an event to occur in a specific year.
        
        Args:
            event_type: Type of event
            year: Year when the event should occur
            data: Event data
            priority: Event priority
            
        Returns:
            Event ID
        """
        event_id = len(self.scheduled_events) + 1
        
        event = {
            "id": event_id,
            "type": event_type,
            "year": year,
            "data": data,
            "priority": priority,
            "processed": False
        }
        
        self.scheduled_events.append(event)
        
        # Sort events by year and priority
        self.scheduled_events.sort(key=lambda e: (e["year"], -e["priority"].value))
        
        return event_id
    
    def cancel_event(self, event_id: int) -> bool:
        """
        Cancel a scheduled event.
        
        Args:
            event_id: ID of the event to cancel
            
        Returns:
            True if event was found and canceled, False otherwise
        """
        for i, event in enumerate(self.scheduled_events):
            if event["id"] == event_id and not event["processed"]:
                self.scheduled_events.pop(i)
                return True
        return False
    
    def get_events_for_year(self, year: int) -> List[Dict[str, Any]]:
        """
        Get all events scheduled for a specific year.
        
        Args:
            year: Year to get events for
            
        Returns:
            List of events
        """
        return [event for event in self.scheduled_events if event["year"] == year and not event["processed"]]
    
    def process_events_for_year(self, year: int) -> List[Dict[str, Any]]:
        """
        Process all events scheduled for a specific year.
        
        Args:
            year: Year to process events for
            
        Returns:
            List of processed events
        """
        events = self.get_events_for_year(year)
        processed_events = []
        
        # Sort events by priority
        events.sort(key=lambda e: -e["priority"].value)
        
        for event in events:
            # Process event based on type
            if event["type"] == EventType.DIPLOMATIC:
                self._process_diplomatic_event(event, year)
            elif event["type"] == EventType.MILITARY:
                self._process_military_event(event, year)
            elif event["type"] == EventType.ECONOMIC:
                self._process_economic_event(event, year)
            elif event["type"] == EventType.CHARACTER:
                self._process_character_event(event, year)
            elif event["type"] == EventType.NATURAL:
                self._process_natural_event(event, year)
            elif event["type"] == EventType.SCHEDULED:
                self._process_scheduled_event(event, year)
            elif event["type"] == EventType.CONDITIONAL:
                self._process_conditional_event(event, year)
            
            # Mark event as processed
            event["processed"] = True
            processed_events.append(event)
        
        return processed_events
    
    def _process_diplomatic_event(self, event: Dict[str, Any], year: int) -> None:
        """
        Process a diplomatic event.
        
        Args:
            event: Event data
            year: Current year
        """
        data = event["data"]
        
        # Check if required data is present
        if "action" not in data or "actor_dynasty_id" not in data:
            return
        
        action = data["action"]
        actor_dynasty_id = data["actor_dynasty_id"]
        
        # Get actor dynasty
        actor_dynasty = self.session.query(DynastyDB).get(actor_dynasty_id)
        if not actor_dynasty:
            return
        
        # Process based on action type
        if action == "treaty_expiration" and "treaty_id" in data:
            treaty_id = data["treaty_id"]
            treaty = self.session.query(Treaty).get(treaty_id)
            
            if treaty and treaty.active:
                # Get diplomatic relation
                relation = self.session.query(DiplomaticRelation).get(treaty.diplomatic_relation_id)
                if not relation:
                    return
                
                # Get dynasties
                dynasty1 = self.session.query(DynastyDB).get(relation.dynasty1_id)
                dynasty2 = self.session.query(DynastyDB).get(relation.dynasty2_id)
                
                if not dynasty1 or not dynasty2:
                    return
                
                # Deactivate treaty
                treaty.active = False
                
                # Create history log entries
                treaty_name = treaty.treaty_type.value.replace('_', ' ').title()
                
                log_entry1 = HistoryLogEntryDB(
                    dynasty_id=dynasty1.id,
                    year=year,
                    event_string=f"Our {treaty_name} with {dynasty2.name} has expired",
                    event_type="treaty_expired",
                    treaty_id=treaty.id
                )
                self.session.add(log_entry1)
                
                log_entry2 = HistoryLogEntryDB(
                    dynasty_id=dynasty2.id,
                    year=year,
                    event_string=f"Our {treaty_name} with {dynasty1.name} has expired",
                    event_type="treaty_expired",
                    treaty_id=treaty.id
                )
                self.session.add(log_entry2)
                
                self.session.commit()
    
    def _process_military_event(self, event: Dict[str, Any], year: int) -> None:
        """
        Process a military event.
        
        Args:
            event: Event data
            year: Current year
        """
        data = event["data"]
        
        # Check if required data is present
        if "action" not in data:
            return
        
        action = data["action"]
        
        # Process based on action type
        if action == "siege_progress" and "siege_id" in data:
            siege_id = data["siege_id"]
            siege = self.session.query(Siege).get(siege_id)
            
            if siege and siege.is_active:
                # Update siege progress
                from models.military_system import MilitarySystem
                military_system = MilitarySystem(self.session)
                military_system.update_siege(siege_id)
    
    def _process_economic_event(self, event: Dict[str, Any], year: int) -> None:
        """
        Process an economic event.
        
        Args:
            event: Event data
            year: Current year
        """
        data = event["data"]
        
        # Check if required data is present
        if "action" not in data:
            return
        
        action = data["action"]
        
        # Process based on action type
        if action == "building_completion" and "building_id" in data:
            building_id = data["building_id"]
            building = self.session.query(Building).get(building_id)
            
            if building and building.under_construction:
                # Complete building construction
                building.under_construction = False
                building.condition = 1.0  # Full condition
                
                # Get territory and dynasty
                territory = self.session.query(Territory).get(building.territory_id)
                if not territory or not territory.controller_dynasty_id:
                    return
                
                dynasty = self.session.query(DynastyDB).get(territory.controller_dynasty_id)
                if not dynasty:
                    return
                
                # Create history log entry
                building_name = building.building_type.value.replace('_', ' ').title()
                
                log_entry = HistoryLogEntryDB(
                    dynasty_id=dynasty.id,
                    year=year,
                    event_string=f"Construction of {building_name} in {territory.name} has been completed",
                    event_type="building_completed",
                    territory_id=territory.id
                )
                self.session.add(log_entry)
                
                self.session.commit()
    
    def _process_character_event(self, event: Dict[str, Any], year: int) -> None:
        """
        Process a character event.
        
        Args:
            event: Event data
            year: Current year
        """
        # Character events are typically handled by the character system
        # This is a placeholder for integration with that system
        pass
    
    def _process_natural_event(self, event: Dict[str, Any], year: int) -> None:
        """
        Process a natural event.
        
        Args:
            event: Event data
            year: Current year
        """
        data = event["data"]
        
        # Check if required data is present
        if "event_name" not in data or "territory_id" not in data:
            return
        
        event_name = data["event_name"]
        territory_id = data["territory_id"]
        
        # Get territory and dynasty
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return
        
        dynasty_id = territory.controller_dynasty_id
        if not dynasty_id:
            return
        
        # Process based on event name
        if event_name == "drought":
            # Reduce food production in territory
            territory_resources = self.session.query(TerritoryResource).filter_by(territory_id=territory_id).all()
            for tr in territory_resources:
                resource = self.session.query(Resource).get(tr.resource_id)
                if resource and resource.resource_type == ResourceType.FOOD:
                    tr.base_production *= 0.7  # 30% reduction
            
            # Create history log entry
            log_entry = HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=year,
                event_string=f"A severe drought has affected {territory.name}, reducing food production",
                event_type="natural_disaster",
                territory_id=territory_id
            )
            self.session.add(log_entry)
            
        elif event_name == "flood":
            # Damage buildings in territory
            buildings = self.session.query(Building).filter_by(territory_id=territory_id).all()
            for building in buildings:
                building.condition = max(0.5, building.condition - 0.2)  # Reduce condition by 20%, minimum 50%
            
            # Create history log entry
            log_entry = HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=year,
                event_string=f"A devastating flood has damaged buildings in {territory.name}",
                event_type="natural_disaster",
                territory_id=territory_id
            )
            self.session.add(log_entry)
            
        elif event_name == "disease":
            # Reduce population in territory
            territory.population = int(territory.population * 0.9)  # 10% reduction
            
            # Create history log entry
            log_entry = HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=year,
                event_string=f"A disease outbreak has reduced the population of {territory.name}",
                event_type="natural_disaster",
                territory_id=territory_id
            )
            self.session.add(log_entry)
        
        self.session.commit()
    
    def _process_scheduled_event(self, event: Dict[str, Any], year: int) -> None:
        """
        Process a scheduled event.
        
        Args:
            event: Event data
            year: Current year
        """
        # This is a generic event type that can be used for custom events
        # The specific processing depends on the event data
        pass
    
    def _process_conditional_event(self, event: Dict[str, Any], year: int) -> None:
        """
        Process a conditional event.
        
        Args:
            event: Event data
            year: Current year
        """
        data = event["data"]
        
        # Check if required data is present
        if "condition" not in data or "action" not in data:
            return
        
        condition = data["condition"]
        action = data["action"]
        
        # Check if condition is met
        condition_met = False
        
        if condition["type"] == "dynasty_wealth" and "dynasty_id" in condition and "threshold" in condition:
            dynasty_id = condition["dynasty_id"]
            threshold = condition["threshold"]
            comparison = condition.get("comparison", ">=")
            
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if dynasty:
                if comparison == ">=" and dynasty.current_wealth >= threshold:
                    condition_met = True
                elif comparison == "<=" and dynasty.current_wealth <= threshold:
                    condition_met = True
                elif comparison == ">" and dynasty.current_wealth > threshold:
                    condition_met = True
                elif comparison == "<" and dynasty.current_wealth < threshold:
                    condition_met = True
        
        # If condition is met, schedule the action as a new event
        if condition_met:
            self.schedule_event(
                event_type=EventType[action["type"]],
                year=year,
                data=action["data"],
                priority=EventPriority[action.get("priority", "MEDIUM")]
            )
    
    def calculate_action_points(self, dynasty_id: int) -> int:
        """
        Calculate the number of action points available to a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Number of action points
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return 0
        
        # Base action points
        base_points = 10
        
        # Adjust based on dynasty size
        territory_count = self.session.query(Territory).filter_by(controller_dynasty_id=dynasty_id).count()
        size_modifier = min(2.0, max(0.5, territory_count / 5))  # 0.5 to 2.0 based on territory count
        
        # Adjust based on current monarch's skills
        monarch = self.session.query(PersonDB).filter_by(
            dynasty_id=dynasty_id,
            is_monarch=True,
            death_year=None
        ).first()
        
        skill_modifier = 1.0
        if monarch:
            # Average of diplomatic, military, and stewardship skills
            avg_skill = (monarch.diplomatic_skill + monarch.military_skill + monarch.stewardship_skill) / 3
            skill_modifier = 1.0 + (avg_skill / 20)  # 1.0 to 2.0 based on skills
        
        # Calculate total action points
        action_points = int(base_points * size_modifier * skill_modifier)
        
        return max(5, action_points)  # Minimum 5 action points
    
    def process_turn(self, dynasty_id: int, phase: GamePhase = None) -> Tuple[bool, str]:
        """
        Process a turn for a dynasty, or a specific phase if provided.
        
        Args:
            dynasty_id: ID of the dynasty
            phase: Specific phase to process (optional)
            
        Returns:
            Tuple of (success, message)
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return False, f"Dynasty with ID {dynasty_id} not found"
        
        current_year = dynasty.current_simulation_year
        
        # If no specific phase is provided, process all phases
        if phase is None:
            # Process planning phase
            success, message = self.process_turn(dynasty_id, GamePhase.PLANNING)
            if not success:
                return False, message
            
            # Process diplomatic phase
            success, message = self.process_turn(dynasty_id, GamePhase.DIPLOMATIC)
            if not success:
                return False, message
            
            # Process military phase
            success, message = self.process_turn(dynasty_id, GamePhase.MILITARY)
            if not success:
                return False, message
            
            # Process economic phase
            success, message = self.process_turn(dynasty_id, GamePhase.ECONOMIC)
            if not success:
                return False, message
            
            # Process character phase
            success, message = self.process_turn(dynasty_id, GamePhase.CHARACTER)
            if not success:
                return False, message
            
            # Process resolution phase
            success, message = self.process_turn(dynasty_id, GamePhase.RESOLUTION)
            if not success:
                return False, message
            
            # Advance year
            dynasty.current_simulation_year += 1
            self.session.commit()
            
            return True, f"Turn processed successfully. Advanced to year {dynasty.current_simulation_year}."
        
        # Process specific phase
        if phase == GamePhase.PLANNING:
            # Planning phase - calculate action points, etc.
            action_points = self.calculate_action_points(dynasty_id)
            
            # Store action points for later use
            dynasty.action_points = action_points
            self.session.commit()
            
            return True, f"Planning phase completed. {action_points} action points available."
            
        elif phase == GamePhase.DIPLOMATIC:
            # Diplomatic phase - process diplomatic events
            diplomatic_events = [e for e in self.get_events_for_year(current_year) 
                               if e["type"] == EventType.DIPLOMATIC]
            
            for event in diplomatic_events:
                self._process_diplomatic_event(event, current_year)
                event["processed"] = True
            
            # Check treaty expirations
            from models.diplomacy_system import DiplomacySystem
            diplomacy_system = DiplomacySystem(self.session)
            
            # Get all active treaties involving this dynasty
            relations = self.session.query(DiplomaticRelation).filter(
                (DiplomaticRelation.dynasty1_id == dynasty_id) | 
                (DiplomaticRelation.dynasty2_id == dynasty_id)
            ).all()
            
            for relation in relations:
                treaties = self.session.query(Treaty).filter_by(
                    diplomatic_relation_id=relation.id,
                    active=True
                ).all()
                
                for treaty in treaties:
                    if treaty.duration and treaty.start_year + treaty.duration <= current_year:
                        # Treaty has expired
                        treaty.active = False
                        
                        # Create history log entries
                        dynasty1 = self.session.query(DynastyDB).get(relation.dynasty1_id)
                        dynasty2 = self.session.query(DynastyDB).get(relation.dynasty2_id)
                        
                        if dynasty1 and dynasty2:
                            treaty_name = treaty.treaty_type.value.replace('_', ' ').title()
                            
                            log_entry1 = HistoryLogEntryDB(
                                dynasty_id=dynasty1.id,
                                year=current_year,
                                event_string=f"Our {treaty_name} with {dynasty2.name} has expired",
                                event_type="treaty_expired",
                                treaty_id=treaty.id
                            )
                            self.session.add(log_entry1)
                            
                            log_entry2 = HistoryLogEntryDB(
                                dynasty_id=dynasty2.id,
                                year=current_year,
                                event_string=f"Our {treaty_name} with {dynasty1.name} has expired",
                                event_type="treaty_expired",
                                treaty_id=treaty.id
                            )
                            self.session.add(log_entry2)
            
            self.session.commit()
            
            return True, "Diplomatic phase completed."
            
        elif phase == GamePhase.MILITARY:
            # Military phase - process military events
            military_events = [e for e in self.get_events_for_year(current_year) 
                             if e["type"] == EventType.MILITARY]
            
            for event in military_events:
                self._process_military_event(event, current_year)
                event["processed"] = True
            
            # Update sieges
            sieges = self.session.query(Siege).filter_by(
                is_active=True
            ).all()
            
            for siege in sieges:
                # Check if siege involves this dynasty
                if siege.attacker_dynasty_id == dynasty_id or siege.defender_dynasty_id == dynasty_id:
                    from models.military_system import MilitarySystem
                    military_system = MilitarySystem(self.session)
                    military_system.update_siege(siege.id)
            
            # Apply military maintenance
            from models.military_system import MilitarySystem
            military_system = MilitarySystem(self.session)
            military_system.apply_maintenance(dynasty_id)
            
            self.session.commit()
            
            return True, "Military phase completed."
            
        elif phase == GamePhase.ECONOMIC:
            # Economic phase - process economic events
            economic_events = [e for e in self.get_events_for_year(current_year) 
                             if e["type"] == EventType.ECONOMIC]
            
            for event in economic_events:
                self._process_economic_event(event, current_year)
                event["processed"] = True
            
            # Update economy
            from models.economy_system import EconomySystem
            economy_system = EconomySystem(self.session)
            economy_system.update_dynasty_economy(dynasty_id)
            
            # Apply seasonal effects
            current_season = self.get_current_season(current_year)
            
            # Get all territories controlled by the dynasty
            territories = self.session.query(Territory).filter_by(controller_dynasty_id=dynasty_id).all()
            
            for territory in territories:
                # Get region for weather
                province = self.session.query(Province).get(territory.province_id)
                if not province:
                    continue
                
                region = self.session.query(Region).get(province.region_id)
                if not region:
                    continue
                
                # Get weather for this region and season
                weather = self.get_weather_for_region(region.id, current_season)
                
                # Apply seasonal and weather effects to territory resources
                territory_resources = self.session.query(TerritoryResource).filter_by(territory_id=territory.id).all()
                
                for tr in territory_resources:
                    resource = self.session.query(Resource).get(tr.resource_id)
                    if not resource:
                        continue
                    
                    # Apply season modifier
                    season_modifier = self.season_production_modifiers.get(current_season, {}).get(resource.resource_type, 1.0)
                    
                    # Apply weather modifier
                    weather_modifier = 1.0
                    weather_effects = self.weather_effects.get(weather, {})
                    
                    if resource.resource_type in weather_effects:
                        weather_modifier = weather_effects[resource.resource_type]
                    else:
                        weather_modifier = weather_effects.get("production_modifier", 1.0)
                    
                    # Apply combined modifier
                    combined_modifier = season_modifier * weather_modifier
                    
                    # Store the modifier for this turn
                    tr.current_modifier = combined_modifier
            
            # Apply population growth based on season
            for territory in territories:
                growth_rate = self.population_growth_rates.get(territory.development_level, 0.01)
                season_growth_modifier = self.season_production_modifiers.get(current_season, {}).get("population_growth", 1.0)
                
                # Apply growth
                territory.population = int(territory.population * (1 + growth_rate * season_growth_modifier))
            
            self.session.commit()
            
            return True, "Economic phase completed."
            
        elif phase == GamePhase.CHARACTER:
            # Character phase - process character events
            character_events = [e for e in self.get_events_for_year(current_year) 
                              if e["type"] == EventType.CHARACTER]
            
            for event in character_events:
                self._process_character_event(event, current_year)
                event["processed"] = True
            
            # Process character aging, deaths, births, etc.
            # This would typically call into the character system
            # For now, we'll just create a placeholder log entry
            
            log_entry = HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=current_year,
                event_string=f"Character events processed for year {current_year}",
                event_type="character_events"
            )
            self.session.add(log_entry)
            self.session.commit()
            
            return True, "Character phase completed."
            
        elif phase == GamePhase.RESOLUTION:
            # Resolution phase - finalize the turn
            
            # Process any remaining events
            remaining_events = self.get_events_for_year(current_year)
            for event in remaining_events:
                if event["type"] == EventType.NATURAL:
                    self._process_natural_event(event, current_year)
                elif event["type"] == EventType.SCHEDULED:
                    self._process_scheduled_event(event, current_year)
                elif event["type"] == EventType.CONDITIONAL:
                    self._process_conditional_event(event, current_year)
                
                event["processed"] = True
            
            # Create turn summary log entry
            log_entry = HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=current_year,
                event_string=f"Year {current_year} has concluded",
                event_type="year_end"
            )
            self.session.add(log_entry)
            self.session.commit()
            
            return True, "Resolution phase completed. Turn is now complete."
        
        return False, f"Unknown game phase: {phase}"
    
    def synchronize_turns(self, dynasty_ids: List[int]) -> Tuple[bool, str]:
        """
        Synchronize turns for multiple dynasties.
        
        Args:
            dynasty_ids: List of dynasty IDs to synchronize
            
        Returns:
            Tuple of (success, message)
        """
        if not dynasty_ids:
            return False, "No dynasties provided for synchronization"
        
        # Get all dynasties
        dynasties = []
        for dynasty_id in dynasty_ids:
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                return False, f"Dynasty with ID {dynasty_id} not found"
            dynasties.append(dynasty)
        
        # Check if all dynasties are at the same year
        current_years = [d.current_simulation_year for d in dynasties]
        if len(set(current_years)) > 1:
            return False, "Dynasties are not at the same year, cannot synchronize"
        
        current_year = current_years[0]
        
        # Process turns for all dynasties
        for dynasty in dynasties:
            success, message = self.process_turn(dynasty.id)
            if not success:
                return False, f"Failed to process turn for dynasty {dynasty.name}: {message}"
        
        return True, f"Successfully synchronized turns for {len(dynasties)} dynasties. Advanced to year {current_year + 1}."
    
    def get_historical_timeline(self, dynasty_id: int, start_year: Optional[int] = None, 
                               end_year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get the historical timeline for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            start_year: Start year for the timeline (optional)
            end_year: End year for the timeline (optional)
            
        Returns:
            List of historical events
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return []
        
        # Set default years if not provided
        if start_year is None:
            start_year = dynasty.start_year
        if end_year is None:
            end_year = dynasty.current_simulation_year
        
        # Query history log entries
        query = self.session.query(HistoryLogEntryDB).filter(
            HistoryLogEntryDB.dynasty_id == dynasty_id,
            HistoryLogEntryDB.year >= start_year,
            HistoryLogEntryDB.year <= end_year
        ).order_by(HistoryLogEntryDB.year, HistoryLogEntryDB.id)
        
        entries = query.all()
        
        # Convert to dictionary format
        timeline = []
        for entry in entries:
            event = {
                "id": entry.id,
                "year": entry.year,
                "event_string": entry.event_string,
                "event_type": entry.event_type,
                "person1_id": entry.person1_sim_id,
                "person2_id": entry.person2_sim_id,
                "territory_id": entry.territory_id,
                "war_id": entry.war_id,
                "battle_id": entry.battle_id,
                "treaty_id": entry.treaty_id
            }
            timeline.append(event)
        
        return timeline
    
    def get_scheduled_timeline(self, dynasty_id: int) -> List[Dict[str, Any]]:
        """
        Get the scheduled timeline for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            List of scheduled events
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return []
        
        # Filter events relevant to this dynasty
        scheduled_events = []
        for event in self.scheduled_events:
            if event["processed"]:
                continue
                
            data = event["data"]
            
            # Check if event is relevant to this dynasty
            is_relevant = False
            
            if "actor_dynasty_id" in data and data["actor_dynasty_id"] == dynasty_id:
                is_relevant = True
            elif "target_dynasty_id" in data and data["target_dynasty_id"] == dynasty_id:
                is_relevant = True
            elif "dynasty_id" in data and data["dynasty_id"] == dynasty_id:
                is_relevant = True
            elif "territory_id" in data:
                territory = self.session.query(Territory).get(data["territory_id"])
                if territory and territory.controller_dynasty_id == dynasty_id:
                    is_relevant = True
            
            if is_relevant:
                scheduled_events.append({
                    "id": event["id"],
                    "type": event["type"].value,
                    "year": event["year"],
                    "priority": event["priority"].value,
                    "data": event["data"]
                })
        
        # Sort by year
        scheduled_events.sort(key=lambda e: e["year"])
        
        return scheduled_events
    
    def get_population_growth_rates(self) -> Dict[int, float]:
        """
        Get the population growth rates by development level.
        
        Returns:
            Dictionary mapping development levels to growth rates
        """
        return self.population_growth_rates
        
        # Check if condition is met
        condition_met = False
        
        if condition["type"] == "dynasty_wealth" and "dynasty_id" in condition and "threshold" in condition:
            dynasty_id = condition["dynasty_id"]
            threshold = condition["threshold"]
            comparison = condition.get("comparison", ">=")
            
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if dynasty:
                if comparison == ">=" and dynasty.current_wealth >= threshold:
                    condition_met = True
                elif comparison == "<=" and dynasty.current_wealth <= threshold:
                    condition_met = True
                elif comparison == ">" and dynasty.current_wealth > threshold:
                    condition_met = True
                elif comparison == "<" and dynasty.current_wealth < threshold:
                    condition_met = True
        
        # If condition is met, schedule the action as a new event
        if condition_met:
            self.schedule_event(
                event_type=EventType[action["type"]],
                year=year,
                data=action["data"],
                priority=EventPriority[action.get("priority", "MEDIUM")]
            )