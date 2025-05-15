# models/game_manager.py
"""
Game manager for the multi-agent strategic game.
Provides a high-level API for game operations, manages player sessions and authentication,
handles multiplayer synchronization, coordinates AI players, and manages game creation,
loading, and saving.
"""

import random
import json
import datetime
from typing import List, Dict, Tuple, Optional, Union, Any, Set
from sqlalchemy.orm import Session

from models.db_models import (
    db, User, DynastyDB, PersonDB, Territory, TerrainType, Settlement,
    MilitaryUnit, UnitType, Army, Battle, Siege, War, DiplomaticRelation, Treaty, TreatyType,
    HistoryLogEntryDB, Region, Province
)
from models.map_system import MapGenerator, TerritoryManager, MovementSystem, BorderSystem
from models.military_system import MilitarySystem
from models.diplomacy_system import DiplomacySystem
from models.economy_system import EconomySystem
from models.time_system import TimeSystem, Season, EventType, EventPriority, GamePhase

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
        
        # AI player controllers
        self.ai_controllers = {}
        
        # Game state cache
        self.game_state_cache = {}
        
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
                logging.warning(f"Invalid map template '{map_template}'. Falling back to 'small_continent'.")
                map_template = "small_continent"
            
            # Generate map with error handling
            try:
                map_data = self.map_system['generator'].generate_predefined_map(map_template)
                if not map_data or not map_data.get('territories'):
                    logging.error(f"Map generation failed for template '{map_template}'. Trying fallback template.")
                    map_data = self.map_system['generator'].generate_predefined_map("default")
            except Exception as map_error:
                logging.error(f"Error generating map with template '{map_template}': {str(map_error)}")
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
                logging.error(f"Not enough territories ({len(territories)}) for all dynasties ({len(all_dynasties)}). Generating additional territories.")
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
                    logging.error(f"Error creating additional territories: {str(territory_error)}")
                    return False, f"Failed to create game: Territory generation error: {str(territory_error)}", None
            
            # Distribute territories evenly among dynasties with minimum guarantee
            min_territories_per_dynasty = 1  # Minimum guarantee
            remaining_territories = len(territories) - (min_territories_per_dynasty * len(all_dynasties))
            
            if remaining_territories < 0:
                logging.error("Critical error: Not enough territories even after generation attempt")
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
                        logging.error(f"Error assigning territory {territory.id} to dynasty {dynasty.id}: {str(assign_error)}")
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
                logging.error(f"Dynasty with ID {dynasty_id} not found during founder initialization")
                return
            
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
            except Exception as founder_error:
                logging.error(f"Error creating dynasty founder: {str(founder_error)}")
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
                except Exception as spouse_error:
                    logging.error(f"Error creating spouse for dynasty founder: {str(spouse_error)}")
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
            except Exception as log_error:
                logging.error(f"Error creating dynasty founding log entry: {str(log_error)}")
                # Continue without log entry if there's an error
                
        except Exception as e:
            logging.error(f"Unhandled error in _initialize_dynasty_founder: {str(e)}")
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
            logging.error(f"Error in name generation: {str(e)}")
            return f"{role.capitalize()} of {dynasty_name}"  # Fallback name
    
    def load_game(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Load a game state for a specific dynasty.
        
        Args:
            dynasty_id: ID of the dynasty to load
            
        Returns:
            Dictionary with game state information
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return {'error': f"Dynasty with ID {dynasty_id} not found"}
        
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
        
        # Update cache
        self.game_state_cache[dynasty_id] = {
            'last_updated': datetime.datetime.now(),
            'current_year': dynasty.current_simulation_year,
            'current_phase': GamePhase.PLANNING
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
        try:
            # Get dynasty
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if not dynasty:
                return False, f"Dynasty with ID {dynasty_id} not found", {}
            
            # Process turn using time system
            success, message = self.time_system.process_turn(dynasty_id)
            
            if not success:
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
            
            turn_results['events'] = [{
                'year': event.year,
                'description': event.event_string,
                'type': event.event_type
            } for event in recent_events]
            
            # Update game state cache
            self.game_state_cache[dynasty_id] = {
                'last_updated': datetime.datetime.now(),
                'current_year': dynasty.current_simulation_year,
                'current_phase': GamePhase.PLANNING
            }
            
            return True, "Turn processed successfully", turn_results
        except Exception as e:
            self.session.rollback()
            return False, f"Error processing turn: {str(e)}", {}
    
    def process_ai_turns(self, user_id: int) -> Tuple[bool, str]:
        """
        Process turns for all AI dynasties belonging to a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get all AI dynasties for this user
            ai_dynasties = self.session.query(DynastyDB).filter_by(
                user_id=user_id, is_ai_controlled=True
            ).all()
            
            for dynasty in ai_dynasties:
                # Generate AI decisions
                self._generate_ai_decisions(dynasty.id)
                
                # Process turn
                self.time_system.process_turn(dynasty.id)
            
            return True, f"Processed turns for {len(ai_dynasties)} AI dynasties"
        except Exception as e:
            self.session.rollback()
            return False, f"Error processing AI turns: {str(e)}"
    
    def _generate_ai_decisions(self, dynasty_id: int) -> None:
        """
        Generate decisions for an AI-controlled dynasty.
        
        Args:
            dynasty_id: ID of the AI dynasty
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty or not dynasty.is_ai_controlled:
            return
        
        # Simple AI decision making
        # 1. Military: Recruit units if wealth allows
        if dynasty.current_wealth > 100:
            # Find a territory to recruit in
            territory = self.session.query(Territory).filter_by(
                controller_dynasty_id=dynasty_id
            ).first()
            
            if territory:
                # Recruit a random unit type
                unit_type = random.choice([
                    UnitType.LEVY_SPEARMEN,
                    UnitType.ARCHERS,
                    UnitType.LIGHT_CAVALRY
                ])
                
                # Random size between 100-500
                size = random.randint(100, 500)
                
                self.military_system.recruit_unit(
                    dynasty_id=dynasty_id,
                    unit_type=unit_type,
                    size=size,
                    territory_id=territory.id
                )
        
        # 2. Diplomacy: Improve relations with random dynasty
        other_dynasties = self.session.query(DynastyDB).filter(
            DynastyDB.id != dynasty_id
        ).all()
        
        if other_dynasties:
            target_dynasty = random.choice(other_dynasties)
            
            # Perform a random diplomatic action
            action_type = random.choice([
                "send_envoy",
                "gift",
                "cultural_exchange"
            ])
            
            self.diplomacy_system.perform_diplomatic_action(
                actor_dynasty_id=dynasty_id,
                target_dynasty_id=target_dynasty.id,
                action_type=action_type
            )
        
        # 3. Economy: Develop a random territory
        territory = self.session.query(Territory).filter_by(
            controller_dynasty_id=dynasty_id
        ).order_by(Territory.development_level).first()
        
        if territory and territory.development_level < 10 and dynasty.current_wealth > 50:
            self.economy_system.develop_territory(territory.id)
    
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
        if session_token not in self.active_sessions:
            return {'error': 'Invalid session token'}
        
        # Update last activity
        self.active_sessions[session_token]['last_activity'] = datetime.datetime.now()
        
        # Get session info
        session = self.active_sessions[session_token]
        dynasty_id = session['dynasty_id']
        
        # Get basic synchronization data
        sync_data = {
            'active_players': self.get_active_players(),
            'current_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Check if game state needs to be refreshed
        if dynasty_id in self.game_state_cache:
            cache_entry = self.game_state_cache[dynasty_id]
            if (datetime.datetime.now() - cache_entry['last_updated']).total_seconds() < 60:
                # Use cached data if less than 60 seconds old
                sync_data['game_state_fresh'] = False
                return sync_data
        
        # Load fresh game state
        game_state = self.load_game(dynasty_id)
        sync_data['game_state'] = game_state
        sync_data['game_state_fresh'] = True
        
        return sync_data