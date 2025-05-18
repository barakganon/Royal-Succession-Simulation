# models/game_manager.py
"""
Game manager for the multi-agent strategic game.
Provides a high-level API for game operations, manages player sessions and authentication,
handles multiplayer synchronization, coordinates AI players, and manages game creation,
loading, and saving.
"""

import datetime
import random
from typing import List, Dict, Tuple, Optional, Any
import logging

# Import custom logging configuration
from utils.logging_config import setup_logger

from sqlalchemy.orm import Session

from models.db_models import (
    User, DynastyDB, PersonDB, Territory, MilitaryUnit, UnitType, Army, War, DiplomaticRelation, HistoryLogEntryDB,
    Province
)
from models.diplomacy_system import DiplomacySystem
from models.economy_system import EconomySystem
from models.map_system import MapGenerator, TerritoryManager, MovementSystem, BorderSystem
from models.military_system import MilitarySystem
from models.time_system import TimeSystem, GamePhase


class GameManager:
    """
    Core game manager that provides a high-level API for game operations,
    manages player sessions and authentication, handles multiplayer synchronization,
    coordinates AI players, and manages game creation, loading, and saving.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the game manager.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        
        # Initialize logger
        self.logger = setup_logger('royal_succession.game_manager', level='info')
        self.logger.info("Initializing Game Manager")
        
        # Initialize all subsystems
        self.map_system = {
            'generator': MapGenerator(session),
            'territory_manager': TerritoryManager(session),
            'movement_system': MovementSystem(session),
            'border_system': BorderSystem(session)
        }
        
        self.military_system = MilitarySystem(session)
        self.diplomacy_system = DiplomacySystem(session)
        self.economy_system = EconomySystem(session)
        self.time_system = TimeSystem(session)
        
        # Active player sessions
        self.active_sessions = {}
        
        # AI player controllers - initialize with different personality types
        self.ai_controllers = {
            'aggressive': {
                'military_focus': 0.7,
                'diplomacy_focus': 0.2,
                'economy_focus': 0.1,
                'risk_tolerance': 0.8
            },
            'diplomatic': {
                'military_focus': 0.3,
                'diplomacy_focus': 0.6,
                'economy_focus': 0.1,
                'risk_tolerance': 0.3
            },
            'economic': {
                'military_focus': 0.2,
                'diplomacy_focus': 0.3,
                'economy_focus': 0.5,
                'risk_tolerance': 0.4
            },
            'balanced': {
                'military_focus': 0.33,
                'diplomacy_focus': 0.33,
                'economy_focus': 0.34,
                'risk_tolerance': 0.5
            }
        }
        
        # Dynasty to AI controller mapping
        self.dynasty_ai_mapping = {}
        
        # Game state cache with TTL and invalidation tracking
        self.game_state_cache = {
            'data': {},
            'ttl': 60,  # Cache time-to-live in seconds
            'invalidation_keys': {}  # Track keys that should invalidate cache
        }
        
        self.logger.info("Game Manager initialized successfully")
        
    def create_new_game(self, user_id: int, game_name: str, map_template: str = "small_continent",
                        starting_dynasties: int = 4, ai_dynasties: int = 3) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new game with the specified parameters.
        
        Args:
            user_id: ID of the user creating the game
            game_name: Name of the game
            map_template: Map template to use
            starting_dynasties: Number of starting dynasties
            ai_dynasties: Number of AI-controlled dynasties
            
        Returns:
            Tuple of (success, message, game_id)
        """
        try:
            # Check if user exists
            user = self.session.query(User).get(user_id)
            if not user:
                return False, f"User with ID {user_id} not found", None
            
            # Validate map template
            valid_templates = ["small_continent", "large_continent", "archipelago", "default"]
            if map_template not in valid_templates:
                self.logger.warning(f"Invalid map template '{map_template}'. Falling back to 'small_continent'.")
                map_template = "small_continent"
            
            # Generate map with error handling
            try:
                map_data = self.map_system['generator'].generate_predefined_map(map_template)
                if not map_data or not map_data.get('territories'):
                    self.logger.error(f"Map generation failed for template '{map_template}'. Trying fallback template.")
                    map_data = self.map_system['generator'].generate_predefined_map("default")
            except Exception as map_error:
                self.logger.error(f"Error generating map with template '{map_template}': {str(map_error)}")
                # Fallback to default map generation
                map_data = self.map_system['generator'].generate_procedural_map()
            
            # Create game record (using the first dynasty as the game record for now)
            start_year = 1000
            
            # Create player dynasty
            player_dynasty = DynastyDB(
                user_id=user_id,
                name=f"{game_name} Dynasty",
                theme_identifier_or_json="medieval_europe",  # Default theme
                current_wealth=100,
                start_year=start_year,
                current_simulation_year=start_year,
                prestige=50,
                honor=50,
                infamy=0,
                is_ai_controlled=False
            )
            self.session.add(player_dynasty)
            self.session.flush()  # Get ID without committing
            
            # Create AI dynasties
            for i in range(ai_dynasties):
                ai_dynasty = DynastyDB(
                    user_id=user_id,  # Same user owns the AI dynasties for now
                    name=f"AI Dynasty {i+1}",
                    theme_identifier_or_json="medieval_europe",  # Default theme
                    current_wealth=100,
                    start_year=start_year,
                    current_simulation_year=start_year,
                    prestige=50,
                    honor=50,
                    infamy=0,
                    is_ai_controlled=True
                )
                self.session.add(ai_dynasty)
            
            # Distribute territories among dynasties
            all_dynasties = [player_dynasty]
            self.session.flush()  # Get IDs for all dynasties
            
            ai_dynasties_list = self.session.query(DynastyDB).filter_by(
                user_id=user_id, is_ai_controlled=True
            ).all()
            all_dynasties.extend(ai_dynasties_list)
            
            # Get all territories
            territories = map_data.get('territories', [])
            
            # Ensure there are enough territories for all dynasties
            if len(territories) < len(all_dynasties):
                self.logger.error(f"Not enough territories ({len(territories)}) for all dynasties ({len(all_dynasties)}). Generating additional territories.")
                # Generate additional territories if needed
                additional_territories_needed = len(all_dynasties) - len(territories)
                try:
                    # Create additional territories in existing provinces
                    provinces = self.session.query(Province).all()
                    if provinces:
                        for i in range(additional_territories_needed):
                            province = random.choice(provinces)
                            new_territory = Territory(
                                province_id=province.id,
                                name=f"Emergency Territory {i+1}",
                                description="An emergency territory created due to shortage",
                                terrain_type=province.primary_terrain,
                                x_coordinate=random.uniform(0, 1000),
                                y_coordinate=random.uniform(0, 1000),
                                base_tax=random.randint(1, 3),
                                base_manpower=random.randint(50, 100) * 10,
                                development_level=1,
                                population=random.randint(500, 1000)
                            )
                            self.session.add(new_territory)
                            self.session.flush()
                            territories.append(new_territory)
                    else:
                        return False, "Failed to create game: Not enough territories and no provinces available", None
                except Exception as territory_error:
                    self.logger.error(f"Error creating additional territories: {str(territory_error)}")
                    return False, f"Failed to create game: Territory generation error: {str(territory_error)}", None
            
            # Distribute territories evenly among dynasties with minimum guarantee
            min_territories_per_dynasty = 1  # Minimum guarantee
            remaining_territories = len(territories) - (min_territories_per_dynasty * len(all_dynasties))
            
            if remaining_territories < 0:
                self.logger.error("Critical error: Not enough territories even after generation attempt")
                return False, "Failed to create game: Critical territory shortage", None
                
            # First pass: assign minimum territories
            territory_assignments = {dynasty.id: [] for dynasty in all_dynasties}
            territory_index = 0
            
            # Assign minimum guaranteed territories
            for dynasty in all_dynasties:
                for i in range(min_territories_per_dynasty):
                    if territory_index < len(territories):
                        territory_assignments[dynasty.id].append((territories[territory_index], i == 0))
                        territory_index += 1
            
            # Second pass: distribute remaining territories
            if remaining_territories > 0:
                territories_per_dynasty_extra = remaining_territories // len(all_dynasties)
                extra_remaining = remaining_territories % len(all_dynasties)
                
                for dynasty in all_dynasties:
                    # Calculate extra territories this dynasty gets
                    extra_count = territories_per_dynasty_extra
                    if extra_remaining > 0:
                        extra_count += 1
                        extra_remaining -= 1
                    
                    # Assign extra territories
                    for i in range(extra_count):
                        if territory_index < len(territories):
                            territory_assignments[dynasty.id].append((territories[territory_index], False))
                            territory_index += 1
            
            # Now perform the actual territory assignments
            for dynasty in all_dynasties:
                for territory, is_capital in territory_assignments[dynasty.id]:
                    try:
                        self.map_system['territory_manager'].assign_territory(
                            territory.id, dynasty.id, is_capital
                        )
                    except Exception as assign_error:
                        self.logger.error(f"Error assigning territory {territory.id} to dynasty {dynasty.id}: {str(assign_error)}")
                        # Continue with other assignments even if one fails
            
            # Initialize founder and spouse for each dynasty
            for dynasty in all_dynasties:
                self._initialize_dynasty_founder(dynasty.id, start_year)
            
            # Commit all changes
            self.session.commit()
            
            # Initialize game state cache
            self.game_state_cache[player_dynasty.id] = {
                'last_updated': datetime.datetime.now(),
                'current_year': start_year,
                'current_phase': GamePhase.PLANNING
            }
            
            return True, f"Game '{game_name}' created successfully", player_dynasty.id
            
        except Exception as e:
            self.session.rollback()
            return False, f"Error creating game: {str(e)}", None
    
    def _initialize_dynasty_founder(self, dynasty_id: int, start_year: int) -> None:
        """
        Initialize the founder and spouse for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            start_year: Starting year
        """
        try:
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                self.logger.error(f"Dynasty with ID {dynasty_id} not found during founder initialization")
                return
            
            self.logger.info(f"Initializing founder for dynasty {dynasty.name} (ID: {dynasty_id})")
            
            # Create founder with error handling
            try:
                founder_gender = random.choice(["MALE", "FEMALE"])
                
                # Generate founder name with fallback
                founder_name = self._generate_character_name(dynasty.name, "founder")
                if not founder_name or len(founder_name) < 2:
                    founder_name = f"Founder {dynasty.name}"
                
                founder_age = random.randint(25, 40)
                founder_birth_year = start_year - founder_age
                
                founder = PersonDB(
                    dynasty_id=dynasty_id,
                    name=founder_name,
                    surname=dynasty.name,
                    gender=founder_gender,
                    birth_year=founder_birth_year,
                    is_noble=True,
                    is_monarch=True,
                    diplomacy_skill=random.randint(3, 8),
                    stewardship_skill=random.randint(3, 8),
                    martial_skill=random.randint(3, 8),
                    intrigue_skill=random.randint(3, 8)
                )
                self.session.add(founder)
                self.session.flush()  # Get ID
                self.logger.info(f"Created founder {founder_name} for dynasty {dynasty.name}")
            except Exception as founder_error:
                self.logger.error(f"Error creating dynasty founder: {str(founder_error)}")
                # Create a basic founder as fallback
                founder = PersonDB(
                    dynasty_id=dynasty_id,
                    name="Emergency Founder",
                    surname=dynasty.name,
                    gender="MALE",
                    birth_year=start_year - 30,
                    is_noble=True,
                    is_monarch=True,
                    diplomacy_skill=5,
                    stewardship_skill=5,
                    martial_skill=5,
                    intrigue_skill=5
                )
                self.session.add(founder)
                self.session.flush()  # Get ID
                self.logger.warning(f"Created emergency founder for dynasty {dynasty.name}")
            
            # Create spouse with error handling
            spouse = None
            if random.random() < 0.9:  # 90% chance of having a spouse
                try:
                    spouse_gender = "FEMALE" if founder_gender == "MALE" else "MALE"
                    
                    # Generate spouse name with fallback
                    spouse_name = self._generate_character_name(dynasty.name, "spouse")
                    if not spouse_name or len(spouse_name) < 2:
                        spouse_name = f"Spouse of {founder.name}"
                    
                    spouse_age = random.randint(max(16, founder_age - 10), founder_age + 5)
                    spouse_birth_year = start_year - spouse_age
                    
                    # Generate a random house name for the spouse
                    house_names = ['Alba', 'Blackwood', 'Highgarden', 'Winterfell', 'Casterly', 'Riverrun', 'Sunspear']
                    spouse_house = random.choice(house_names)
                    
                    spouse = PersonDB(
                        dynasty_id=dynasty_id,
                        name=spouse_name,
                        surname=f"of House {spouse_house}",
                        gender=spouse_gender,
                        birth_year=spouse_birth_year,
                        is_noble=True,
                        is_monarch=False,
                        diplomacy_skill=random.randint(2, 7),
                        stewardship_skill=random.randint(2, 7),
                        martial_skill=random.randint(2, 7),
                        intrigue_skill=random.randint(2, 7)
                    )
                    self.session.add(spouse)
                    self.session.flush()  # Get ID
                    
                    # Link as spouses
                    founder.spouse_sim_id = spouse.id
                    spouse.spouse_sim_id = founder.id
                    self.logger.info(f"Created spouse {spouse_name} for founder {founder.name}")
                except Exception as spouse_error:
                    self.logger.error(f"Error creating spouse for dynasty founder: {str(spouse_error)}")
                    # Continue without spouse if there's an error
            
            # Create history log entry
            try:
                log_entry = HistoryLogEntryDB(
                    dynasty_id=dynasty_id,
                    year=start_year,
                    event_string=f"{founder.name} founded the dynasty and became its first ruler.",
                    event_type="dynasty_founding",
                    person1_sim_id=founder.id
                )
                self.session.add(log_entry)
                self.logger.info(f"Created founding history entry for dynasty {dynasty.name}")
            except Exception as log_error:
                self.logger.error(f"Error creating dynasty founding log entry: {str(log_error)}")
                # Continue without log entry if there's an error
                
            # Assign an AI personality if this is an AI dynasty
            if dynasty.is_ai_controlled:
                self._assign_ai_personality(dynasty_id)
                
        except Exception as e:
            self.logger.error(f"Unhandled error in _initialize_dynasty_founder: {str(e)}")
            # We don't re-raise the exception to allow the game creation to continue
    
    def _generate_character_name(self, dynasty_name: str, role: str) -> str:
        """
        Generate a character name based on dynasty and role.
        Includes fallback mechanisms for name generation.
        
        Args:
            dynasty_name: Name of the dynasty
            role: Role of the character (founder, spouse, etc.)
            
        Returns:
            Generated name
        """
        try:
            # Simple name generation based on dynasty name and role
            prefixes = {
                "founder": ["Lord", "Lady", "Duke", "Duchess", "Count", "Countess", "Baron", "Baroness"],
                "spouse": ["Consort", "Partner", "Companion"],
                "heir": ["Young", "Heir", "Successor"],
                "general": ["Commander", "General", "Captain"]
            }
            
            suffixes = ["the Bold", "the Wise", "the Just", "the Cruel", "the Fair", "the Strong"]
            
            # Get appropriate prefix based on role
            role_prefixes = prefixes.get(role, ["Noble"])
            prefix = random.choice(role_prefixes)
            
            # Generate a name based on dynasty name
            first_letter = dynasty_name[0] if dynasty_name else "A"
            consonants = "bcdfghjklmnpqrstvwxyz"
            vowels = "aeiou"
            
            # Generate a name with alternating consonants and vowels
            name_length = random.randint(3, 7)
            name_parts = []
            
            for i in range(name_length):
                if i % 2 == 0:
                    name_parts.append(random.choice(consonants))
                else:
                    name_parts.append(random.choice(vowels))
            
            # Capitalize first letter and add first letter of dynasty
            base_name = ''.join(name_parts).capitalize()
            if random.random() < 0.3:  # 30% chance to add a suffix
                return f"{prefix} {base_name} {random.choice(suffixes)}"
            else:
                return f"{prefix} {base_name}"
                
        except Exception as e:
            self.logger.error(f"Error in name generation: {str(e)}")
            return f"{role.capitalize()} of {dynasty_name}"  # Fallback name
    
    def _assign_ai_personality(self, dynasty_id: int) -> None:
        """
        Assign an AI personality to a dynasty.
        
        Args:
            dynasty_id: ID of the AI dynasty
        """
        try:
            # Get available personality types
            personality_types = list(self.ai_controllers.keys())
            
            # Assign a random personality
            personality = random.choice(personality_types)
            
            # Store the mapping
            self.dynasty_ai_mapping[dynasty_id] = personality
            
            self.logger.info(f"Assigned {personality} AI personality to dynasty {dynasty_id}")
        except Exception as e:
            self.logger.error(f"Error assigning AI personality: {str(e)}")
            # Fallback to balanced personality
            self.dynasty_ai_mapping[dynasty_id] = 'balanced'
    
    def load_game(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Load a game state for a specific dynasty.
        
        Args:
            dynasty_id: ID of the dynasty to load
            
        Returns:
            Dictionary with game state information
        """
        self.logger.info(f"Loading game state for dynasty ID {dynasty_id}")
        
        # Check if we have a valid cached state
        if dynasty_id in self.game_state_cache['data']:
            cache_entry = self.game_state_cache['data'][dynasty_id]
            cache_age = (datetime.datetime.now() - cache_entry['last_updated']).total_seconds()
            
            # If cache is still valid, return it
            if cache_age < self.game_state_cache['ttl']:
                self.logger.info(f"Using cached game state for dynasty {dynasty_id} (age: {cache_age:.1f}s)")
                return cache_entry['state']
            else:
                self.logger.debug(f"Cache expired for dynasty {dynasty_id} (age: {cache_age:.1f}s)")
        
        # Cache miss or expired, load from database
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            error_msg = f"Dynasty with ID {dynasty_id} not found"
            self.logger.error(error_msg)
            return {'error': error_msg}
        
        self.logger.debug(f"Building game state for dynasty {dynasty.name}")
        
        # Get basic dynasty information
        game_state = {
            'dynasty': {
                'id': dynasty.id,
                'name': dynasty.name,
                'current_year': dynasty.current_simulation_year,
                'wealth': dynasty.current_wealth,
                'prestige': dynasty.prestige,
                'honor': dynasty.honor,
                'infamy': dynasty.infamy
            },
            'current_phase': GamePhase.PLANNING.value
        }
        
        # Get current monarch
        monarch = self.session.query(PersonDB).filter_by(
            dynasty_id=dynasty_id, is_monarch=True, death_year=None
        ).first()
        
        if monarch:
            game_state['monarch'] = {
                'id': monarch.id,
                'name': f"{monarch.name} {monarch.surname}",
                'age': dynasty.current_simulation_year - monarch.birth_year,
                'gender': monarch.gender,
                'diplomacy': monarch.diplomacy_skill,
                'stewardship': monarch.stewardship_skill,
                'martial': monarch.martial_skill,
                'intrigue': monarch.intrigue_skill
            }
        
        # Get territories
        territories = self.session.query(Territory).filter_by(
            controller_dynasty_id=dynasty_id
        ).all()
        
        game_state['territories'] = {
            'count': len(territories),
            'list': [{
                'id': t.id,
                'name': t.name,
                'terrain': t.terrain_type.value,
                'population': t.population,
                'development': t.development_level,
                'is_capital': t.is_capital
            } for t in territories]
        }
        
        # Get military units
        units = self.session.query(MilitaryUnit).filter_by(
            dynasty_id=dynasty_id
        ).all()
        
        game_state['military'] = {
            'units_count': len(units),
            'units': [{
                'id': u.id,
                'name': u.name,
                'type': u.unit_type.value,
                'size': u.size,
                'territory_id': u.territory_id,
                'army_id': u.army_id
            } for u in units]
        }
        
        # Get armies
        armies = self.session.query(Army).filter_by(
            dynasty_id=dynasty_id, is_active=True
        ).all()
        
        game_state['armies'] = {
            'count': len(armies),
            'list': [{
                'id': a.id,
                'name': a.name,
                'territory_id': a.territory_id,
                'commander_id': a.commander_id,
                'is_sieging': a.is_sieging
            } for a in armies]
        }
        
        # Get diplomatic relations
        relations = []
        for relation in self.session.query(DiplomaticRelation).all():
            other_dynasty_id = None
            if relation.dynasty1_id == dynasty_id:
                other_dynasty_id = relation.dynasty2_id
            elif relation.dynasty2_id == dynasty_id:
                other_dynasty_id = relation.dynasty1_id
            
            if other_dynasty_id:
                other_dynasty = self.session.query(DynastyDB).get(other_dynasty_id)
                if other_dynasty:
                    status, score = self.diplomacy_system.get_relation_status(
                        dynasty_id, other_dynasty_id
                    )
                    relations.append({
                        'dynasty_id': other_dynasty_id,
                        'dynasty_name': other_dynasty.name,
                        'status': status,
                        'score': score
                    })
        
        game_state['diplomacy'] = {
            'relations': relations
        }
        
        # Get active wars
        wars = []
        for war in self.session.query(War).filter(
            ((War.attacker_dynasty_id == dynasty_id) | (War.defender_dynasty_id == dynasty_id)) &
            (War.end_year == None)
        ).all():
            other_dynasty_id = war.defender_dynasty_id if war.attacker_dynasty_id == dynasty_id else war.attacker_dynasty_id
            other_dynasty = self.session.query(DynastyDB).get(other_dynasty_id)
            
            wars.append({
                'id': war.id,
                'against': other_dynasty.name if other_dynasty else "Unknown",
                'started': war.start_year,
                'is_attacker': war.attacker_dynasty_id == dynasty_id
            })
        
        game_state['wars'] = wars
        
        # Get economy data
        try:
            economy_data = self.economy_system.calculate_dynasty_economy(dynasty_id)
            game_state['economy'] = economy_data
        except Exception as e:
            game_state['economy'] = {'error': str(e)}
        
        # Get current season and weather
        current_season = self.time_system.get_current_season(dynasty.current_simulation_year)
        game_state['time'] = {
            'current_year': dynasty.current_simulation_year,
            'season': current_season.value,
            'action_points': self.time_system.calculate_action_points(dynasty_id)
        }
        
        # Store in cache
        self.logger.debug(f"Caching game state for dynasty {dynasty_id}")
        self.game_state_cache['data'][dynasty_id] = {
            'last_updated': datetime.datetime.now(),
            'state': game_state,
            'current_year': dynasty.current_simulation_year,
            'current_phase': GamePhase.PLANNING
        }
        
        # Set invalidation keys
        self.game_state_cache['invalidation_keys'][dynasty_id] = {
            'territories': [t.id for t in territories],
            'units': [u.id for u in units],
            'armies': [a.id for a in armies],
            'wars': [w['id'] for w in wars]
        }
        
        return game_state
    
    def save_game(self, dynasty_id: int) -> Tuple[bool, str]:
        """
        Save the current game state for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # For now, the game state is automatically saved to the database
            # This method could be expanded to create save files or snapshots
            
            # Update last played timestamp
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                return False, f"Dynasty with ID {dynasty_id} not found"
            
            dynasty.last_played_at = datetime.datetime.now()
            self.session.commit()
            
            return True, "Game saved successfully"
        except Exception as e:
            self.session.rollback()
            return False, f"Error saving game: {str(e)}"
    
    def process_turn(self, dynasty_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Process a turn for a dynasty, advancing the simulation by one year.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Tuple of (success, message, turn_results)
        """
        self.logger.info(f"Processing turn for dynasty ID {dynasty_id}")
        
        try:
            # Get dynasty
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                error_msg = f"Dynasty with ID {dynasty_id} not found"
                self.logger.error(error_msg)
                return False, error_msg, {}
            
            self.logger.info(f"Processing turn for dynasty {dynasty.name}, year {dynasty.current_simulation_year}")
            
            # Process turn using time system
            success, message = self.time_system.process_turn(dynasty_id)
            
            if not success:
                self.logger.error(f"Time system failed to process turn: {message}")
                return False, message, {}
            
            # Get turn results
            turn_results = {
                'year': dynasty.current_simulation_year,
                'events': []
            }
            
            # Get recent events
            recent_events = self.session.query(HistoryLogEntryDB).filter_by(
                dynasty_id=dynasty_id,
                year=dynasty.current_simulation_year
            ).order_by(HistoryLogEntryDB.id.desc()).limit(10).all()
            
            self.logger.debug(f"Found {len(recent_events)} events for dynasty {dynasty.name} in year {dynasty.current_simulation_year}")
            
            turn_results['events'] = [{
                'year': event.year,
                'description': event.event_string,
                'type': event.event_type
            } for event in recent_events]
            
            # Invalidate cache for this dynasty
            if dynasty_id in self.game_state_cache['data']:
                self.logger.debug(f"Invalidating cache for dynasty {dynasty_id}")
                del self.game_state_cache['data'][dynasty_id]
                
                # Also invalidate any related dynasties (those with diplomatic relations, wars, etc.)
                if dynasty_id in self.game_state_cache['invalidation_keys']:
                    related_dynasties = self._get_related_dynasties(dynasty_id)
                    for related_id in related_dynasties:
                        if related_id in self.game_state_cache['data']:
                            self.logger.debug(f"Invalidating cache for related dynasty {related_id}")
                            del self.game_state_cache['data'][related_id]
            
            self.logger.info(f"Turn processed successfully for dynasty {dynasty.name}, new year: {dynasty.current_simulation_year}")
            return True, "Turn processed successfully", turn_results
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error processing turn: {str(e)}", exc_info=True)
            return False, f"Error processing turn: {str(e)}", {}
    
    def process_ai_turns(self, user_id: int) -> Tuple[bool, str]:
        """
        Process turns for all AI dynasties belonging to a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Tuple of (success, message)
        """
        self.logger.info(f"Processing AI turns for user ID {user_id}")
        
        try:
            # Get all AI dynasties for this user
            ai_dynasties = self.session.query(DynastyDB).filter_by(
                user_id=user_id, is_ai_controlled=True
            ).all()
            
            self.logger.info(f"Found {len(ai_dynasties)} AI dynasties for user {user_id}")
            
            success_count = 0
            error_count = 0
            
            for dynasty in ai_dynasties:
                try:
                    self.logger.info(f"Processing AI turn for dynasty {dynasty.name} (ID: {dynasty.id})")
                    
                    # Ensure dynasty has an AI personality assigned
                    if dynasty.id not in self.dynasty_ai_mapping:
                        self._assign_ai_personality(dynasty.id)
                    
                    # Generate AI decisions
                    self._generate_ai_decisions(dynasty.id)
                    
                    # Process turn
                    turn_success, turn_message = self.time_system.process_turn(dynasty.id)
                    
                    if turn_success:
                        success_count += 1
                        self.logger.info(f"Successfully processed turn for AI dynasty {dynasty.name}")
                        
                        # Invalidate cache for this dynasty
                        if dynasty.id in self.game_state_cache['data']:
                            del self.game_state_cache['data'][dynasty.id]
                    else:
                        error_count += 1
                        self.logger.error(f"Failed to process turn for AI dynasty {dynasty.name}: {turn_message}")
                        
                except Exception as dynasty_error:
                    error_count += 1
                    self.logger.error(f"Error processing AI turn for dynasty {dynasty.name}: {str(dynasty_error)}")
                    # Continue with other dynasties even if one fails
            
            if error_count == 0:
                return True, f"Successfully processed turns for {success_count} AI dynasties"
            else:
                return True, f"Processed turns for {success_count} AI dynasties with {error_count} errors"
                
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error processing AI turns: {str(e)}", exc_info=True)
            return False, f"Error processing AI turns: {str(e)}"
    
    def _get_related_dynasties(self, dynasty_id: int) -> List[int]:
        """
        Get a list of dynasty IDs that are related to the given dynasty.
        Related dynasties include those with diplomatic relations, wars, etc.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            List of related dynasty IDs
        """
        related_ids = set()
        
        try:
            # Get dynasties with diplomatic relations
            relations = self.session.query(DiplomaticRelation).filter(
                (DiplomaticRelation.dynasty1_id == dynasty_id) |
                (DiplomaticRelation.dynasty2_id == dynasty_id)
            ).all()
            
            for relation in relations:
                if relation.dynasty1_id == dynasty_id:
                    related_ids.add(relation.dynasty2_id)
                else:
                    related_ids.add(relation.dynasty1_id)
            
            # Get dynasties involved in wars
            wars = self.session.query(War).filter(
                (War.attacker_dynasty_id == dynasty_id) |
                (War.defender_dynasty_id == dynasty_id)
            ).all()
            
            for war in wars:
                if war.attacker_dynasty_id == dynasty_id:
                    related_ids.add(war.defender_dynasty_id)
                else:
                    related_ids.add(war.attacker_dynasty_id)
            
            # Get dynasties with trade routes (if applicable)
            try:
                trade_routes = self.session.query(TradeRoute).filter(
                    (TradeRoute.exporter_dynasty_id == dynasty_id) |
                    (TradeRoute.importer_dynasty_id == dynasty_id)
                ).all()
                
                for route in trade_routes:
                    if route.exporter_dynasty_id == dynasty_id:
                        related_ids.add(route.importer_dynasty_id)
                    else:
                        related_ids.add(route.exporter_dynasty_id)
            except Exception as e:
                self.logger.warning(f"Error getting trade routes: {str(e)}")
            
            self.logger.debug(f"Found {len(related_ids)} related dynasties for dynasty {dynasty_id}")
            
        except Exception as e:
            self.logger.error(f"Error finding related dynasties: {str(e)}")
        
        # Remove the original dynasty ID if it somehow got included
        if dynasty_id in related_ids:
            related_ids.remove(dynasty_id)
            
        return list(related_ids)
    
    def _generate_ai_decisions(self, dynasty_id: int) -> None:
        """
        Generate decisions for an AI-controlled dynasty based on its personality.
        
        Args:
            dynasty_id: ID of the AI dynasty
        """
        try:
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty or not dynasty.is_ai_controlled:
                return
            
            self.logger.info(f"Generating AI decisions for dynasty {dynasty.name} (ID: {dynasty_id})")
            
            # Get AI personality
            personality = self.dynasty_ai_mapping.get(dynasty_id, 'balanced')
            if not personality:
                # If no personality assigned yet, assign one
                self._assign_ai_personality(dynasty_id)
                personality = self.dynasty_ai_mapping.get(dynasty_id, 'balanced')
                
            personality_traits = self.ai_controllers.get(personality, self.ai_controllers['balanced'])
            
            # Extract focus values
            military_focus = personality_traits['military_focus']
            diplomacy_focus = personality_traits['diplomacy_focus']
            economy_focus = personality_traits['economy_focus']
            risk_tolerance = personality_traits['risk_tolerance']
            
            self.logger.debug(f"AI personality: {personality}, Military: {military_focus}, Diplomacy: {diplomacy_focus}, Economy: {economy_focus}, Risk: {risk_tolerance}")
            
            # Calculate action probabilities based on focus values
            military_prob = military_focus * 1.5  # Scale to make it more likely to take action
            diplomacy_prob = diplomacy_focus * 1.5
            economy_prob = economy_focus * 1.5
            
            # 1. Military decisions
            if random.random() < military_prob:
                self._make_military_decision(dynasty_id, risk_tolerance)
            
            # 2. Diplomacy decisions
            if random.random() < diplomacy_prob:
                self._make_diplomacy_decision(dynasty_id, risk_tolerance)
            
            # 3. Economy decisions
            if random.random() < economy_prob:
                self._make_economy_decision(dynasty_id, risk_tolerance)
                
        except Exception as e:
            self.logger.error(f"Error generating AI decisions: {str(e)}")
    
    def _make_military_decision(self, dynasty_id: int, risk_tolerance: float) -> None:
        """
        Make a military decision for an AI dynasty based on risk tolerance.
        
        Args:
            dynasty_id: ID of the AI dynasty
            risk_tolerance: Risk tolerance factor (0-1)
        """
        try:
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                return
                
            self.logger.debug(f"Making military decision for dynasty {dynasty.name}")
            
            # Get controlled territories
            territories = self.session.query(Territory).filter_by(
                controller_dynasty_id=dynasty_id
            ).all()
            
            if not territories:
                return
                
            # Determine wealth threshold based on risk tolerance
            # Higher risk tolerance = willing to spend more of their wealth
            wealth_threshold = max(50, 100 * (1 - risk_tolerance))
            
            if dynasty.current_wealth > wealth_threshold:
                # Choose a territory - prefer capital or high development
                if random.random() < 0.7:  # 70% chance to choose strategically
                    # Try to find capital first
                    capital = next((t for t in territories if t.is_capital), None)
                    if capital:
                        territory = capital
                    else:
                        # Sort by development level and pick one of the top territories
                        sorted_territories = sorted(territories, key=lambda t: t.development_level, reverse=True)
                        territory = sorted_territories[0] if sorted_territories else random.choice(territories)
                else:
                    territory = random.choice(territories)
                
                # Determine unit type based on risk tolerance
                if risk_tolerance > 0.7:
                    # High risk: prefer offensive units
                    unit_types = [UnitType.LIGHT_CAVALRY, UnitType.HEAVY_CAVALRY, UnitType.KNIGHTS]
                    weights = [0.4, 0.4, 0.2]  # Weighted choice
                elif risk_tolerance > 0.4:
                    # Medium risk: balanced units
                    unit_types = [UnitType.LEVY_SPEARMEN, UnitType.ARCHERS, UnitType.LIGHT_CAVALRY]
                    weights = [0.3, 0.4, 0.3]
                else:
                    # Low risk: prefer defensive units
                    unit_types = [UnitType.LEVY_SPEARMEN, UnitType.ARCHERS]
                    weights = [0.6, 0.4]
                
                unit_type = random.choices(unit_types, weights=weights, k=1)[0]
                
                # Size based on wealth and risk tolerance
                base_size = 100
                wealth_factor = min(5, dynasty.current_wealth / 100)
                size = int(base_size * wealth_factor * (0.5 + risk_tolerance))
                
                # Cap size based on wealth
                max_size = dynasty.current_wealth // 2
                size = min(size, max_size, 1000)
                
                # Recruit unit
                unit_id = self.military_system.recruit_unit(
                    dynasty_id=dynasty_id,
                    unit_type=unit_type,
                    size=size,
                    territory_id=territory.id
                )
                
                if unit_id:
                    self.logger.info(f"AI dynasty {dynasty.name} recruited {size} {unit_type.value} in {territory.name}")
        except Exception as e:
            self.logger.error(f"Error making military decision: {str(e)}")
    
    def _make_diplomacy_decision(self, dynasty_id: int, risk_tolerance: float) -> None:
        """
        Make a diplomacy decision for an AI dynasty based on risk tolerance.
        
        Args:
            dynasty_id: ID of the AI dynasty
            risk_tolerance: Risk tolerance factor (0-1)
        """
        try:
            # Get other dynasties
            other_dynasties = self.session.query(DynastyDB).filter(
                DynastyDB.id != dynasty_id
            ).all()
            
            if not other_dynasties:
                return
                
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                return
                
            self.logger.debug(f"Making diplomacy decision for dynasty {dynasty.name}")
            
            # Choose target dynasty - not completely random
            # Higher chance to target dynasties with existing relations
            related_ids = self._get_related_dynasties(dynasty_id)
            
            if related_ids and random.random() < 0.7:  # 70% chance to focus on existing relations
                target_dynasty_id = random.choice(related_ids)
                target_dynasty = self.session.query(DynastyDB).get(target_dynasty_id)
            else:
                target_dynasty = random.choice(other_dynasties)
            
            # Get current relation
            relation_status, relation_score = self.diplomacy_system.get_relation_status(
                dynasty_id, target_dynasty.id
            )
            
            # Determine action based on relation and risk tolerance
            if relation_score < -50:
                # Very negative relations
                if risk_tolerance > 0.7 and random.random() < 0.3:
                    # High risk: consider war
                    action_type = "declare_war"
                else:
                    # Try to improve slightly
                    action_type = "send_envoy"
            elif relation_score < 0:
                # Negative relations
                action_type = random.choice(["send_envoy", "gift"])
            elif relation_score < 50:
                # Neutral relations
                action_type = random.choice(["send_envoy", "gift", "cultural_exchange"])
            else:
                # Positive relations
                if risk_tolerance < 0.3:
                    # Low risk: consolidate friendship
                    action_type = random.choice(["gift", "cultural_exchange", "propose_alliance"])
                else:
                    # Higher risk: more varied actions
                    action_type = random.choice(["send_envoy", "gift", "cultural_exchange", "propose_alliance", "request_military_access"])
            
            # Execute action
            success, message = self.diplomacy_system.perform_diplomatic_action(
                actor_dynasty_id=dynasty_id,
                target_dynasty_id=target_dynasty.id,
                action_type=action_type
            )
            
            if success:
                self.logger.info(f"AI dynasty {dynasty.name} performed {action_type} towards dynasty {target_dynasty.name}")
            else:
                self.logger.warning(f"AI dynasty {dynasty.name} failed to perform {action_type}: {message}")
        except Exception as e:
            self.logger.error(f"Error making diplomacy decision: {str(e)}")
    
    def _make_economy_decision(self, dynasty_id: int, risk_tolerance: float) -> None:
        """
        Make an economy decision for an AI dynasty based on risk tolerance.
        
        Args:
            dynasty_id: ID of the AI dynasty
            risk_tolerance: Risk tolerance factor (0-1)
        """
        try:
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                return
                
            self.logger.debug(f"Making economy decision for dynasty {dynasty.name}")
            
            # Get territories
            territories = self.session.query(Territory).filter_by(
                controller_dynasty_id=dynasty_id
            ).all()
            
            if not territories:
                return
            
            # Determine wealth threshold based on risk tolerance
            # Lower risk tolerance = save more money
            wealth_threshold = 50 * (1 + (1 - risk_tolerance))
            
            if dynasty.current_wealth > wealth_threshold:
                # Decide between developing territory or constructing building
                if random.random() < 0.6:  # 60% chance to develop territory
                    # Choose territory to develop - prefer least developed
                    sorted_territories = sorted(territories, key=lambda t: t.development_level)
                    territory = sorted_territories[0] if sorted_territories else random.choice(territories)
                    
                    if territory.development_level < 10:  # Max development level
                        success, message = self.economy_system.develop_territory(territory.id)
                        if success:
                            self.logger.info(f"AI dynasty {dynasty.name} developed territory {territory.name}")
                        else:
                            self.logger.warning(f"AI dynasty {dynasty.name} failed to develop territory: {message}")
                else:
                    # Construct building
                    # Choose territory - prefer capital or high development
                    capital = next((t for t in territories if t.is_capital), None)
                    if capital:
                        territory = capital
                    else:
                        # Sort by development level and pick one of the top territories
                        sorted_territories = sorted(territories, key=lambda t: t.development_level, reverse=True)
                        territory = sorted_territories[0] if sorted_territories else random.choice(territories)
                    
                    # Choose building type based on risk tolerance
                    if risk_tolerance > 0.7:
                        # High risk: military buildings
                        building_types = [BuildingType.BARRACKS, BuildingType.WALLS, BuildingType.WATCHTOWER]
                    elif risk_tolerance > 0.4:
                        # Medium risk: balanced buildings
                        building_types = [BuildingType.MARKET, BuildingType.FARM, BuildingType.MINE, BuildingType.BARRACKS]
                    else:
                        # Low risk: economic buildings
                        building_types = [BuildingType.MARKET, BuildingType.FARM, BuildingType.MINE, BuildingType.WORKSHOP]
                    
                    building_type = random.choice(building_types)
                    
                    try:
                        success, message = self.economy_system.construct_building(territory.id, building_type)
                        if success:
                            self.logger.info(f"AI dynasty {dynasty.name} constructed {building_type.value} in {territory.name}")
                        else:
                            self.logger.warning(f"AI dynasty {dynasty.name} failed to construct building: {message}")
                    except Exception as building_error:
                        self.logger.error(f"Error constructing building: {str(building_error)}")
        except Exception as e:
            self.logger.error(f"Error making economy decision: {str(e)}")
    
    def register_player_session(self, user_id: int, dynasty_id: int) -> str:
        """
        Register a player session for multiplayer synchronization.
        
        Args:
            user_id: ID of the user
            dynasty_id: ID of the dynasty
            
        Returns:
            Session token
        """
        # Generate a session token
        session_token = f"session_{user_id}_{dynasty_id}_{random.randint(1000, 9999)}"
        
        # Register session
        self.active_sessions[session_token] = {
            'user_id': user_id,
            'dynasty_id': dynasty_id,
            'last_activity': datetime.datetime.now()
        }
        
        return session_token
    
    def unregister_player_session(self, session_token: str) -> bool:
        """
        Unregister a player session.
        
        Args:
            session_token: Session token
            
        Returns:
            True if session was found and removed, False otherwise
        """
        if session_token in self.active_sessions:
            del self.active_sessions[session_token]
            return True
        return False
    
    def get_active_players(self) -> List[Dict[str, Any]]:
        """
        Get a list of active players.
        
        Returns:
            List of active player information
        """
        active_players = []
        current_time = datetime.datetime.now()
        
        # Clean up old sessions (inactive for more than 30 minutes)
        tokens_to_remove = []
        for token, session in self.active_sessions.items():
            if (current_time - session['last_activity']).total_seconds() > 1800:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self.active_sessions[token]
        
        # Get active players
        for token, session in self.active_sessions.items():
            dynasty = self.session.query(DynastyDB).get(session['dynasty_id'])
            user = self.session.query(User).get(session['user_id'])
            
            if dynasty and user:
                active_players.append({
                    'user_id': user.id,
                    'username': user.username,
                    'dynasty_id': dynasty.id,
                    'dynasty_name': dynasty.name,
                    'last_activity': session['last_activity'].strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return active_players
    
    def synchronize_multiplayer(self, session_token: str) -> Dict[str, Any]:
        """
        Synchronize multiplayer game state.
        
        Args:
            session_token: Session token
            
        Returns:
            Dictionary with synchronized game state
        """
        try:
            if session_token not in self.active_sessions:
                self.logger.warning(f"Invalid session token: {session_token}")
                return {'error': 'Invalid session token'}
            
            # Update last activity
            self.active_sessions[session_token]['last_activity'] = datetime.datetime.now()
            
            # Get session info
            session = self.active_sessions[session_token]
            dynasty_id = session['dynasty_id']
            user_id = session['user_id']
            
            self.logger.info(f"Synchronizing multiplayer state for user {user_id}, dynasty {dynasty_id}")
            
            # Get basic synchronization data
            sync_data = {
                'active_players': self.get_active_players(),
                'current_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Check if game state needs to be refreshed
            cache_valid = False
            if 'data' in self.game_state_cache and dynasty_id in self.game_state_cache['data']:
                cache_entry = self.game_state_cache['data'][dynasty_id]
                cache_age = (datetime.datetime.now() - cache_entry['last_updated']).total_seconds()
                
                # Check if cache is still valid
                if cache_age < self.game_state_cache['ttl']:
                    self.logger.debug(f"Using cached game state for dynasty {dynasty_id} (age: {cache_age:.1f}s)")
                    sync_data['game_state'] = cache_entry['state']
                    sync_data['game_state_fresh'] = False
                    cache_valid = True
                else:
                    self.logger.debug(f"Cache expired for dynasty {dynasty_id} (age: {cache_age:.1f}s)")
            
            # Load fresh game state if cache is invalid
            if not cache_valid:
                self.logger.debug(f"Loading fresh game state for dynasty {dynasty_id}")
                game_state = self.load_game(dynasty_id)
                sync_data['game_state'] = game_state
                sync_data['game_state_fresh'] = True
            
            # Add additional synchronization data
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if dynasty:
                sync_data['dynasty_year'] = dynasty.current_simulation_year
                
                # Get notifications
                recent_events = self.session.query(HistoryLogEntryDB).filter_by(
                    dynasty_id=dynasty_id
                ).order_by(HistoryLogEntryDB.id.desc()).limit(5).all()
                
                sync_data['notifications'] = [{
                    'id': event.id,
                    'year': event.year,
                    'message': event.event_string,
                    'type': event.event_type,
                    'is_read': event.is_read
                } for event in recent_events]
            
            return sync_data
            
        except Exception as e:
            self.logger.error(f"Error synchronizing multiplayer: {str(e)}", exc_info=True)
            return {
                'error': f"Error synchronizing: {str(e)}",
                'current_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }