# Royal Succession Multi-Agent Strategic Game: Development Guide

This document provides comprehensive guidelines and documentation for developers who want to extend or modify the Royal Succession Multi-Agent Strategic Game. It covers the codebase organization, system APIs, extension points, database schema, web interface development, testing strategies, and troubleshooting information.

## Table of Contents

1. [Codebase Organization](#codebase-organization)
2. [System APIs](#system-apis)
3. [Extension Points](#extension-points)
4. [Database Schema](#database-schema)
5. [Web Interface Development](#web-interface-development)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Future Development](#future-development)
9. [API Reference](#api-reference)

## Codebase Organization

### Directory Structure

The project follows a modular structure:

```
Royal-Succession-Simulation/
├── main_flask_app.py         # Main Flask application entry point
├── simulation_engine.py      # Core simulation logic
├── run_local_simulation.py   # Command-line simulation runner
├── run_simple_simulation.py  # Simplified simulation runner
├── check_dynasty.py          # Dynasty status checker utility
├── check_imports.py          # Import validation utility
├── check_syntax.py           # Syntax checking utility
├── restart_app.sh            # Server restart script
├── requirements.txt          # Python dependencies
├── models/                   # Core data models and game systems
│   ├── __init__.py
│   ├── person.py             # Person class for characters
│   ├── family_tree.py        # Family tree management
│   ├── history.py            # Historical event tracking
│   ├── db_models.py          # Database models
│   ├── db_initialization.py  # Database initialization
│   ├── map_system.py         # Map and territory system
│   ├── military_system.py    # Military units and combat
│   ├── diplomacy_system.py   # Diplomatic relations
│   ├── economy_system.py     # Resources and economy
│   ├── economy.py            # Core economy logic
│   ├── politics.py           # Political systems
│   ├── traits.py             # Character traits system
│   ├── time_system.py        # Turn management and events
│   └── game_manager.py       # Central game coordinator
├── utils/                    # Utility functions
│   ├── __init__.py
│   ├── theme_manager.py      # Cultural theme management
│   ├── helpers.py            # Helper functions
│   └── logging_config.py     # Logging configuration
├── visualization/            # Visualization components
│   ├── __init__.py
│   ├── plotter.py            # Family tree visualization
│   ├── map_renderer.py       # Map visualization
│   ├── military_renderer.py  # Military visualization
│   ├── diplomacy_renderer.py # Diplomacy visualization
│   ├── economy_renderer.py   # Economy visualization
│   └── time_renderer.py      # Timeline visualization
├── themes/                   # Cultural theme definitions
│   ├── __init__.py
│   ├── cultural_themes.json  # Predefined cultural themes
│   └── base.html             # Theme base template
├── templates/                # HTML templates
│   ├── __init__.py
│   ├── base.html             # Base template
│   ├── world_map.html        # Map view
│   ├── military_view.html    # Military interface
│   ├── diplomacy_view.html   # Diplomacy interface
│   ├── economy_view.html     # Economy interface
│   ├── time_view.html        # Time management interface
│   └── ...                   # Other interface templates
├── static/                   # Static assets
│   ├── __init__.py
│   ├── css/                  # Stylesheets
│   ├── js/                   # JavaScript files
│   └── images/               # Image assets
├── instance/                 # Instance-specific data
│   ├── __init__.py
│   └── dynastysim.db         # SQLite database
├── tests/                    # Test directory (future)
└── docs/                     # Documentation
    ├── user_guide.md         # User documentation
    ├── technical_implementation.md # Technical documentation
    ├── development_guide.md  # This file
    ├── enhancement_plan.md   # Planned enhancements
    ├── royal_succession_multi_agent_game_design.md # Game design
    └── technical_analysis_for_multi_agent_extension.md # Technical analysis
```

### Module Dependencies

The system follows a layered architecture:

1. **Database Layer**: `db_models.py` defines all database tables
2. **System Layer**: Individual systems (`map_system.py`, `military_system.py`, etc.)
3. **Coordination Layer**: `game_manager.py` coordinates all systems
4. **Interface Layer**: Flask routes and templates

Dependencies flow upward, with higher layers depending on lower layers:

```
Web Interface (Flask routes, templates)
        ↑
    Game Manager
        ↑
Individual Systems (Map, Military, Diplomacy, Economy, Time)
        ↑
    Database Models
```

### Coding Standards

The project follows these coding standards:

1. **PEP 8**: Follow Python style guidelines
2. **Type Hints**: Use type annotations for function parameters and return values
3. **Docstrings**: Document all classes and methods with docstrings
4. **Error Handling**: Use try/except blocks for robust error handling
5. **Logging**: Use the logging module instead of print statements

Example of proper code style:

```python
def calculate_battle_outcome(
    attacker_army: Army,
    defender_army: Army,
    terrain_type: TerrainType
) -> Tuple[int, int, str]:
    """
    Calculate the outcome of a battle between two armies.
    
    Args:
        attacker_army: The attacking army
        defender_army: The defending army
        terrain_type: The terrain where the battle takes place
        
    Returns:
        Tuple containing (attacker_casualties, defender_casualties, winner_side)
    """
    try:
        # Battle calculation logic here
        # ...
        
        return attacker_casualties, defender_casualties, winner_side
    except Exception as e:
        logger.error(f"Error calculating battle outcome: {str(e)}")
        # Return default values in case of error
        return 0, 0, "error"
```

## System APIs

### Game Manager API

The `GameManager` class provides the high-level API for game operations:

#### Game Creation and Management

```python
# Create a new game
success, message, game_id = game_manager.create_new_game(
    user_id=user_id,
    game_name="My Game",
    map_template="small_continent",
    starting_dynasties=1,
    ai_dynasties=3
)

# Load a game
game_state = game_manager.load_game(dynasty_id=dynasty_id)

# Save a game
success, message = game_manager.save_game(dynasty_id=dynasty_id)

# Process a turn
success, message, turn_results = game_manager.process_turn(dynasty_id=dynasty_id)

# Process AI turns
success, message = game_manager.process_ai_turns(user_id=user_id)
```

#### Session Management

```python
# Register a player session
session_token = game_manager.register_player_session(
    user_id=user_id,
    dynasty_id=dynasty_id
)

# Unregister a player session
success = game_manager.unregister_player_session(session_token=session_token)

# Get active players
active_players = game_manager.get_active_players()

# Synchronize multiplayer
sync_data = game_manager.synchronize_multiplayer(session_token=session_token)
```

### Map System API

The map system provides APIs for territory management and movement:

#### Map Generation

```python
# Generate a procedural map
map_data = map_generator.generate_procedural_map(
    regions_count=5,
    provinces_per_region=4,
    territories_per_province=5
)

# Generate a predefined map
map_data = map_generator.generate_predefined_map(template_name="small_continent")
```

#### Territory Management

```python
# Assign territory to a dynasty
territory_manager.assign_territory(
    territory_id=territory_id,
    dynasty_id=dynasty_id,
    is_capital=False
)

# Get territory details
territory_data = territory_manager.get_territory_details(territory_id=territory_id)

# Update territory
territory_manager.update_territory(
    territory_id=territory_id,
    population=new_population,
    development_level=new_development
)
```

#### Movement System

```python
# Calculate path between territories
path, cost = movement_system.calculate_path(
    start_territory_id=start_id,
    end_territory_id=end_id,
    unit_type=UnitType.INFANTRY
)

# Move army
success, arrival_time = movement_system.move_army(
    army_id=army_id,
    destination_territory_id=destination_id
)
```

### Military System API

The military system provides APIs for unit and army management:

#### Unit Management

```python
# Recruit a new unit
unit_id = military_system.recruit_unit(
    dynasty_id=dynasty_id,
    territory_id=territory_id,
    unit_type=UnitType.LEVY_SPEARMEN,
    size=100
)

# Disband a unit
success = military_system.disband_unit(unit_id=unit_id)

# Get unit details
unit_data = military_system.get_unit_details(unit_id=unit_id)
```

#### Army Management

```python
# Create a new army
army_id = military_system.create_army(
    dynasty_id=dynasty_id,
    name="Main Army",
    territory_id=territory_id,
    commander_id=commander_id
)

# Add unit to army
success = military_system.add_unit_to_army(unit_id=unit_id, army_id=army_id)

# Remove unit from army
success = military_system.remove_unit_from_army(unit_id=unit_id)

# Disband army
success = military_system.disband_army(army_id=army_id)
```

#### Combat System

```python
# Initiate battle
battle_id = military_system.initiate_battle(
    attacker_army_id=attacker_id,
    defender_army_id=defender_id,
    territory_id=territory_id
)

# Resolve battle
battle_result = military_system.resolve_battle(battle_id=battle_id)

# Initiate siege
siege_id = military_system.initiate_siege(
    army_id=army_id,
    territory_id=territory_id
)

# Progress siege
siege_progress = military_system.progress_siege(siege_id=siege_id)
```

### Diplomacy System API

The diplomacy system provides APIs for diplomatic relations and actions:

#### Diplomatic Relations

```python
# Get diplomatic relation
relation = diplomacy_system.get_diplomatic_relation(
    dynasty1_id=dynasty1_id,
    dynasty2_id=dynasty2_id
)

# Update relation score
diplomacy_system.update_relation_score(
    dynasty1_id=dynasty1_id,
    dynasty2_id=dynasty2_id,
    change=10
)
```

#### Diplomatic Actions

```python
# Perform diplomatic action
success, message = diplomacy_system.perform_diplomatic_action(
    actor_dynasty_id=actor_id,
    target_dynasty_id=target_id,
    action_type="send_envoy"
)

# Declare war
war_id = diplomacy_system.declare_war(
    attacker_dynasty_id=attacker_id,
    defender_dynasty_id=defender_id,
    war_goal="conquest"
)

# Offer peace
success = diplomacy_system.offer_peace(war_id=war_id, terms=peace_terms)
```

#### Treaty Management

```python
# Create treaty
treaty_id = diplomacy_system.create_treaty(
    dynasty1_id=dynasty1_id,
    dynasty2_id=dynasty2_id,
    treaty_type=TreatyType.NON_AGGRESSION,
    duration_years=10,
    terms=treaty_terms
)

# Cancel treaty
success = diplomacy_system.cancel_treaty(treaty_id=treaty_id)
```

### Economy System API

The economy system provides APIs for resource management and production:

#### Resource Management

```python
# Get territory resources
resources = economy_system.get_territory_resources(territory_id=territory_id)

# Update resource amount
economy_system.update_resource_amount(
    territory_id=territory_id,
    resource_type=ResourceType.FOOD,
    amount_change=100
)
```

#### Production and Consumption

```python
# Calculate territory production
production = economy_system.calculate_territory_production(
    territory_id=territory_id,
    season=Season.SUMMER
)

# Calculate territory consumption
consumption = economy_system.calculate_territory_consumption(territory_id=territory_id)

# Process production cycle
economy_system.process_production_cycle(dynasty_id=dynasty_id)
```

#### Building Management

```python
# Start building construction
building_id = economy_system.start_construction(
    territory_id=territory_id,
    building_type=BuildingType.FARM,
    level=1
)

# Complete building construction
success = economy_system.complete_construction(building_id=building_id)

# Upgrade building
success = economy_system.upgrade_building(
    building_id=building_id,
    new_level=2
)
```

### Time System API

The time system provides APIs for turn management and events:

#### Turn Management

```python
# Advance to next season
new_season, new_year = time_system.advance_season()

# Get current season and year
season, year = time_system.get_current_time()

# Get season modifiers
modifiers = time_system.get_season_modifiers(season=Season.WINTER)
```

#### Event Management

```python
# Schedule event
event_id = time_system.schedule_event(
    event_type=EventType.DIPLOMATIC,
    trigger_year=current_year + 1,
    trigger_season=Season.SPRING,
    data=event_data
)

# Process scheduled events
events = time_system.process_scheduled_events()

# Generate random events
random_events = time_system.generate_random_events(
    dynasty_id=dynasty_id,
    count=3
)
```

## Extension Points

### Adding New Unit Types

To add a new military unit type:

1. Add the new unit type to the `UnitType` enum in `db_models.py`:

```python
class UnitType(enum.Enum):
    # Existing unit types...
    PIKEMEN = "pikemen"  # New unit type
```

2. Add unit costs and stats to the `MilitarySystem` class in `military_system.py`:

```python
self.unit_costs[UnitType.PIKEMEN] = {
    "gold": 15,
    "iron": 10,
    "manpower": 100
}

self.unit_stats[UnitType.PIKEMEN] = {
    "attack": 4,
    "defense": 7,
    "morale": 4,
    "speed": 0.9,
    "maintenance_gold": 1.5,
    "maintenance_food": 1.0
}
```

3. Update the unit recruitment UI in `templates/military_view.html` to include the new unit type.

### Adding New Building Types

To add a new building type:

1. Add the new building type to the `BuildingType` enum in `db_models.py`:

```python
class BuildingType(enum.Enum):
    # Existing building types...
    UNIVERSITY = "university"  # New building type
```

2. Add building effects to the `EconomySystem` class in `economy_system.py`:

```python
self.building_production_bonuses[BuildingType.UNIVERSITY] = {
    "research_points": 5,
    "prestige": 2
}

self.building_requirements[BuildingType.UNIVERSITY] = {
    "gold": 300,
    "stone": 150,
    "timber": 100,
    "development_level": 3
}
```

3. Update the building construction UI in `templates/territory_details.html` to include the new building type.

### Adding New Diplomatic Actions

To add a new diplomatic action:

1. Add the action effect to the `diplomatic_action_effects` dictionary in `diplomacy_system.py`:

```python
self.diplomatic_action_effects["form_confederation"] = 20
```

2. Implement the action logic in the `DiplomacySystem` class:

```python
def form_confederation(self, dynasty1_id: int, dynasty2_id: int) -> Tuple[bool, str]:
    """
    Form a confederation between two dynasties.
    
    Args:
        dynasty1_id: ID of the first dynasty
        dynasty2_id: ID of the second dynasty
        
    Returns:
        Tuple of (success, message)
    """
    # Implementation logic here
    # ...
    
    return True, "Confederation formed successfully"
```

3. Update the diplomatic actions UI in `templates/diplomacy_view.html` to include the new action.

### Adding New Resources

To add a new resource type:

1. Add the new resource type to the `ResourceType` enum in `db_models.py`:

```python
class ResourceType(enum.Enum):
    # Existing resource types...
    HORSES = "horses"  # New resource type
```

2. Update the terrain production rates in `economy_system.py`:

```python
self.terrain_production_rates[TerrainType.PLAINS][ResourceType.HORSES] = 1.2
self.terrain_production_rates[TerrainType.HILLS][ResourceType.HORSES] = 0.8
```

3. Add resource effects to the appropriate systems (e.g., cavalry units might require horses).

### Creating New Map Templates

To add a new map template:

1. Create a new template generation function in `map_system.py`:

```python
def _generate_mountain_valley_template(self) -> Dict[str, Any]:
    """
    Generate a mountain valley map template.
    
    Returns:
        Dictionary with map data
    """
    # Implementation logic here
    # ...
    
    return map_data
```

2. Add the template to the valid templates list in `game_manager.py`:

```python
valid_templates = ["small_continent", "large_continent", "archipelago", "mountain_valley", "default"]
```

3. Update the map template selection UI in `templates/create_game.html`.

## Database Schema

### Core Tables

The database schema is defined in `models/db_models.py`. Key tables include:

- `User`: User accounts
- `DynastyDB`: Dynasty information
- `PersonDB`: Character information
- `Territory`: Map territories
- `MilitaryUnit`: Military units
- `Army`: Groups of military units
- `DiplomaticRelation`: Relations between dynasties
- `Treaty`: Diplomatic treaties
- `War`: Ongoing wars
- `Resource`: Resource types
- `Building`: Territory buildings
- `HistoryLogEntryDB`: Historical events

### Schema Modifications

When modifying the database schema:

1. Add new fields or tables to `models/db_models.py`
2. Create a migration script if needed
3. Update the `db_initialization.py` file to handle initialization of new tables
4. Test the changes with a fresh database

Example of adding a new field to an existing table:

```python
# In models/db_models.py
class Territory(db.Model):
    # Existing fields...
    
    # New field
    pollution_level = db.Column(db.Integer, default=0)
```

## Web Interface Development

### Template Structure

The web interface uses Flask templates with a base template structure:

- `base.html`: Main layout template
- Content templates that extend `base.html`
- Partial templates for reusable components

Example of extending the base template:

```html
{% extends "base.html" %}

{% block title %}My Page Title{% endblock %}

{% block content %}
<div class="container">
    <h1>My Page Content</h1>
    <!-- Page-specific content here -->
</div>
{% endblock %}

{% block scripts %}
<script>
    // Page-specific JavaScript here
</script>
{% endblock %}
```

### Adding New Views

To add a new view to the web interface:

1. Create a new template in the `templates` directory
2. Add a route to `main_flask_app.py`:

```python
@app.route('/my_new_view')
@login_required
def my_new_view():
    # View logic here
    # ...
    
    return render_template('my_new_view.html', data=data)
```

3. Add navigation links to the new view in appropriate templates

### Visualization Components

To add a new visualization component:

1. Create a new renderer class in the `visualization` directory:

```python
# visualization/my_renderer.py
class MyRenderer:
    def __init__(self, session):
        self.session = session
        
    def render_my_visualization(self, param1, param2):
        # Visualization logic here
        # ...
        
        # Return base64-encoded image
        return base64_image
```

2. Import and use the renderer in `main_flask_app.py`:

```python
from visualization.my_renderer import MyRenderer

# Initialize renderer
my_renderer = MyRenderer(db.session)

@app.route('/my_visualization')
@login_required
def my_visualization():
    # Get visualization
    image_data = my_renderer.render_my_visualization(param1, param2)
    
    return render_template('my_visualization.html', image=image_data)
```

## Testing

### Unit Testing

Unit tests are located in the project root and test individual components:

- `test_basic.py`: Basic functionality tests
- `test_flask.py`: Flask route tests
- `test_game_manager.py`: Game manager tests
- `test_imports.py`: Import validation tests

To run tests:

```bash
python -m unittest discover
```

### Writing New Tests

When adding new features, create corresponding tests:

```python
import unittest
from models.my_module import MyClass

class TestMyClass(unittest.TestCase):
    def setUp(self):
        # Setup code
        self.my_instance = MyClass()
        
    def test_my_method(self):
        # Test code
        result = self.my_instance.my_method(param1, param2)
        self.assertEqual(result, expected_result)
        
    def tearDown(self):
        # Cleanup code
        pass
```

## Troubleshooting

### Common Issues

#### Database Connection Issues

If you encounter database connection issues:

1. Check that the database file exists
2. Verify the database URI in `main_flask_app.py`
3. Ensure the database is not locked by another process
4. Try recreating the database with `db.create_all()`

#### Map Rendering Issues

If map visualization fails:

1. Check that matplotlib is properly installed
2. Verify that territory coordinates are valid
3. Check for errors in the map renderer code
4. Try with a smaller map template for debugging

#### Performance Issues

If the game becomes slow:

1. Use the `log_performance` decorator to identify bottlenecks
2. Consider optimizing database queries with indexes
3. Implement caching for frequently accessed data
4. Reduce the complexity of map rendering for large maps

### Debugging Tips

1. **Logging**: Use the logging module to track execution flow:

```python
import logging
logger = logging.getLogger("royal_succession.my_module")
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
```

2. **Flask Debug Mode**: Run Flask in debug mode for detailed error pages:

```python
app.run(debug=True)
```

3. **Database Inspection**: Use SQLite tools to inspect the database directly:

```bash
sqlite3 instance/dynastysim.db
```

4. **Performance Profiling**: Use the `log_performance` decorator to measure function execution time:

```python
from utils.logging_config import log_performance

@log_performance
def my_function(param1, param2):
    # Function code here
    pass
```

## Future Development

This section outlines planned future development work for the Royal Succession Simulation. These enhancements will guide developers working on extending the system.

### System Enhancements

#### Game Manager Enhancements
- Implement comprehensive AI player system with different personality types
- Develop more sophisticated game state caching for performance improvement
- Create robust multiplayer synchronization with conflict resolution
- Implement proper session management for concurrent players

#### Military System Enhancements
- Complete naval combat mechanics with ship types and naval battles
- Enhance siege mechanics with supplies, morale, and assault options
- Implement unit experience and quality effects on combat outcomes
- Add army formations and tactics system
- Implement military traditions that evolve over time

#### Diplomacy System Enhancements
- Implement alliance networks with obligations and calls to arms
- Develop complex diplomatic actions (espionage, sabotage)
- Create diplomatic reputation system with regional and global effects
- Add diplomatic incidents and crisis events
- Implement more sophisticated peace negotiation system

#### Economy System Enhancements
- Implement full resource trading between territories
- Develop economic policies beyond basic tax rates
- Create banking and loans system
- Implement more complex population dynamics (growth, migration)
- Add trade routes with supply and demand affecting prices

#### Map System Enhancements
- Enhance pathfinding algorithm with terrain difficulty and roads
- Implement seasonal effects on territories
- Add natural disasters and events affecting territories
- Develop more sophisticated border system with contested areas
- Implement climate zones with different production patterns

### Technical Improvements

#### Code Structure
- Refactor long methods into smaller, more focused functions
- Standardize error handling patterns across modules
- Eliminate code duplication through shared utilities
- Improve code documentation and add comprehensive comments

#### Performance Optimization
- Implement pagination for large data sets in the UI
- Optimize database queries for large game worlds
- Add caching for frequently accessed data
- Profile and optimize memory usage for long-running games

#### Testing Improvements
- Develop comprehensive unit tests for all core game mechanics
- Create integration tests for system interactions
- Implement performance benchmarks for large game worlds
- Add automated UI testing

## API Reference

This section provides detailed API documentation for each system in the Royal Succession Simulation.

### Game Manager API

#### Class: GameManager

The central coordinator for all game systems.

```python
class GameManager:
    def __init__(self, db_session):
        """
        Initialize the Game Manager.
        
        Args:
            db_session: SQLAlchemy database session
        """
        
    def create_new_game(self, user_id: int, game_name: str, map_template: str,
                        starting_dynasties: int = 1, ai_dynasties: int = 3) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new game instance.
        
        Args:
            user_id: ID of the user creating the game
            game_name: Name of the game
            map_template: Template to use for map generation
            starting_dynasties: Number of player dynasties to create
            ai_dynasties: Number of AI dynasties to create
            
        Returns:
            Tuple of (success, message, game_id)
        """
        
    def load_game(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Load an existing game state.
        
        Args:
            dynasty_id: ID of the dynasty to load
            
        Returns:
            Dictionary containing game state
        """
        
    def save_game(self, dynasty_id: int) -> Tuple[bool, str]:
        """
        Save the current game state.
        
        Args:
            dynasty_id: ID of the dynasty to save
            
        Returns:
            Tuple of (success, message)
        """
        
    def process_turn(self, dynasty_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Process a turn for the specified dynasty.
        
        Args:
            dynasty_id: ID of the dynasty processing the turn
            
        Returns:
            Tuple of (success, message, turn_results)
        """
        
    def process_ai_turns(self, user_id: int) -> Tuple[bool, str]:
        """
        Process turns for all AI dynasties in the user's games.
        
        Args:
            user_id: ID of the user whose games to process
            
        Returns:
            Tuple of (success, message)
        """
        
    def register_player_session(self, user_id: int, dynasty_id: int) -> str:
        """
        Register a player session for multiplayer.
        
        Args:
            user_id: ID of the user
            dynasty_id: ID of the dynasty
            
        Returns:
            Session token
        """
        
    def unregister_player_session(self, session_token: str) -> bool:
        """
        Unregister a player session.
        
        Args:
            session_token: Token to unregister
            
        Returns:
            Success flag
        """
        
    def get_active_players(self) -> List[Dict[str, Any]]:
        """
        Get a list of active players.
        
        Returns:
            List of player information dictionaries
        """
        
    def synchronize_multiplayer(self, session_token: str) -> Dict[str, Any]:
        """
        Synchronize game state for multiplayer.
        
        Args:
            session_token: Session token for the player
            
        Returns:
            Synchronization data
        """
```

### Map System API

#### Class: MapSystem

Manages the game map, territories, and movement.

```python
class MapSystem:
    def __init__(self, db_session):
        """
        Initialize the Map System.
        
        Args:
            db_session: SQLAlchemy database session
        """
        
    def generate_procedural_map(self, regions_count: int, provinces_per_region: int,
                               territories_per_province: int) -> Dict[str, Any]:
        """
        Generate a procedural map.
        
        Args:
            regions_count: Number of regions to generate
            provinces_per_region: Number of provinces per region
            territories_per_province: Number of territories per province
            
        Returns:
            Dictionary with map data
        """
        
    def generate_predefined_map(self, template_name: str) -> Dict[str, Any]:
        """
        Generate a map from a predefined template.
        
        Args:
            template_name: Name of the template to use
            
        Returns:
            Dictionary with map data
        """
        
    def assign_territory(self, territory_id: int, dynasty_id: int, is_capital: bool = False) -> bool:
        """
        Assign a territory to a dynasty.
        
        Args:
            territory_id: ID of the territory
            dynasty_id: ID of the dynasty
            is_capital: Whether this is the dynasty's capital
            
        Returns:
            Success flag
        """
        
    def get_territory_details(self, territory_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a territory.
        
        Args:
            territory_id: ID of the territory
            
        Returns:
            Dictionary with territory data
        """
        
    def update_territory(self, territory_id: int, **kwargs) -> bool:
        """
        Update territory attributes.
        
        Args:
            territory_id: ID of the territory
            **kwargs: Attributes to update
            
        Returns:
            Success flag
        """
        
    def calculate_path(self, start_territory_id: int, end_territory_id: int,
                      unit_type: UnitType) -> Tuple[List[int], float]:
        """
        Calculate the optimal path between territories.
        
        Args:
            start_territory_id: Starting territory ID
            end_territory_id: Destination territory ID
            unit_type: Type of unit for movement costs
            
        Returns:
            Tuple of (path_territory_ids, total_cost)
        """
        
    def move_army(self, army_id: int, destination_territory_id: int) -> Tuple[bool, Optional[int]]:
        """
        Move an army to a destination territory.
        
        Args:
            army_id: ID of the army to move
            destination_territory_id: ID of the destination territory
            
        Returns:
            Tuple of (success, arrival_time)
        """
```

### Military System API

#### Class: MilitarySystem

Manages military units, armies, and combat.

```python
class MilitarySystem:
    def __init__(self, db_session, map_system, time_system):
        """
        Initialize the Military System.
        
        Args:
            db_session: SQLAlchemy database session
            map_system: Reference to the MapSystem
            time_system: Reference to the TimeSystem
        """
        
    def recruit_unit(self, dynasty_id: int, territory_id: int,
                    unit_type: UnitType, size: int) -> Optional[int]:
        """
        Recruit a new military unit.
        
        Args:
            dynasty_id: ID of the recruiting dynasty
            territory_id: ID of the territory for recruitment
            unit_type: Type of unit to recruit
            size: Size of the unit
            
        Returns:
            ID of the new unit or None if recruitment failed
        """
        
    def disband_unit(self, unit_id: int) -> bool:
        """
        Disband a military unit.
        
        Args:
            unit_id: ID of the unit to disband
            
        Returns:
            Success flag
        """
        
    def get_unit_details(self, unit_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a unit.
        
        Args:
            unit_id: ID of the unit
            
        Returns:
            Dictionary with unit data
        """
        
    def create_army(self, dynasty_id: int, name: str, territory_id: int,
                   commander_id: Optional[int] = None) -> Optional[int]:
        """
        Create a new army.
        
        Args:
            dynasty_id: ID of the owning dynasty
            name: Name of the army
            territory_id: ID of the territory where the army is located
            commander_id: ID of the commander (optional)
            
        Returns:
            ID of the new army or None if creation failed
        """
        
    def add_unit_to_army(self, unit_id: int, army_id: int) -> bool:
        """
        Add a unit to an army.
        
        Args:
            unit_id: ID of the unit
            army_id: ID of the army
            
        Returns:
            Success flag
        """
        
    def remove_unit_from_army(self, unit_id: int) -> bool:
        """
        Remove a unit from its army.
        
        Args:
            unit_id: ID of the unit
            
        Returns:
            Success flag
        """
        
    def disband_army(self, army_id: int) -> bool:
        """
        Disband an army.
        
        Args:
            army_id: ID of the army to disband
            
        Returns:
            Success flag
        """
        
    def initiate_battle(self, attacker_army_id: int, defender_army_id: int,
                       territory_id: int) -> Optional[int]:
        """
        Initiate a battle between armies.
        
        Args:
            attacker_army_id: ID of the attacking army
            defender_army_id: ID of the defending army
            territory_id: ID of the territory where the battle takes place
            
        Returns:
            ID of the battle or None if initiation failed
        """
        
    def resolve_battle(self, battle_id: int) -> Dict[str, Any]:
        """
        Resolve a battle.
        
        Args:
            battle_id: ID of the battle to resolve
            
        Returns:
            Dictionary with battle results
        """
        
    def initiate_siege(self, army_id: int, territory_id: int) -> Optional[int]:
        """
        Initiate a siege.
        
        Args:
            army_id: ID of the besieging army
            territory_id: ID of the territory being besieged
            
        Returns:
            ID of the siege or None if initiation failed
        """
        
    def progress_siege(self, siege_id: int) -> Dict[str, Any]:
        """
        Progress a siege by one turn.
        
        Args:
            siege_id: ID of the siege to progress
            
        Returns:
            Dictionary with siege progress information
        """
```

## API Routes and Endpoints

The application provides a comprehensive set of API routes for interacting with the game. These routes are implemented in `main_flask_app.py` and follow RESTful principles where appropriate.

### Authentication Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/register` | GET, POST | User registration | username, email, password, password2 |
| `/login` | GET, POST | User login | username, password, remember_me |
| `/logout` | GET | User logout | None |

### Dashboard and Overview Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/` | GET | Home page, redirects to dashboard if authenticated | None |
| `/dashboard` | GET | User's main dashboard | None |

### Dynasty Management Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/dynasty/create` | GET, POST | Create a new dynasty | dynasty_name, theme_type, theme_key/user_story, start_year, succession_rule |
| `/dynasty/<dynasty_id>/view` | GET | View dynasty details | dynasty_id |
| `/dynasty/<dynasty_id>/advance_turn` | GET | Advance simulation by one turn | dynasty_id |
| `/dynasty/<dynasty_id>/delete` | GET, POST | Delete a dynasty | dynasty_id |

### Economy Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/dynasty/<dynasty_id>/economy` | GET | View dynasty economy | dynasty_id |
| `/world/economy` | GET | View world economy | None |
| `/territory/<territory_id>/economy` | GET | View territory economy | territory_id |
| `/dynasty/<dynasty_id>/construct_building` | POST | Construct a building | dynasty_id, territory_id, building_type |
| `/dynasty/<dynasty_id>/upgrade_building/<building_id>` | POST | Upgrade a building | dynasty_id, building_id |
| `/dynasty/<dynasty_id>/repair_building/<building_id>` | POST | Repair a damaged building | dynasty_id, building_id |
| `/dynasty/<dynasty_id>/develop_territory/<territory_id>` | POST | Develop a territory | dynasty_id, territory_id |
| `/dynasty/<dynasty_id>/establish_trade` | POST | Establish a trade route | dynasty_id, target_dynasty_id, resource_type, amount |
| `/dynasty/<dynasty_id>/cancel_trade/<trade_route_id>` | POST | Cancel a trade route | dynasty_id, trade_route_id |

### Map and Territory Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/world/map` | GET | View world map | None |
| `/territory/<territory_id>` | GET | View territory details | territory_id |
| `/dynasty/<dynasty_id>/territories` | GET | View dynasty territories | dynasty_id |
| `/dynasty/<dynasty_id>/develop_territory` | POST | Develop a territory | dynasty_id, territory_id, development_type |
| `/generate_map` | POST | Generate a new map | map_type, size |
| `/dynasty/<dynasty_id>/add_holding` | POST | Add a new holding | dynasty_id, territory_id, holding_type |
| `/world/seasons/<year>` | GET | View seasonal map | year |

### Military Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/dynasty/<dynasty_id>/military` | GET | View military management | dynasty_id |
| `/dynasty/<dynasty_id>/recruit_unit` | POST | Recruit a military unit | dynasty_id, territory_id, unit_type, size |
| `/dynasty/<dynasty_id>/form_army` | POST | Form a new army | dynasty_id, name, territory_id, unit_ids |
| `/dynasty/<dynasty_id>/assign_commander` | POST | Assign a commander | dynasty_id, army_id, commander_id |
| `/army/<army_id>` | GET | View army details | army_id |
| `/battle/<battle_id>` | GET | View battle details | battle_id |
| `/siege/<siege_id>` | GET | View siege details | siege_id |
| `/dynasty/<dynasty_id>/initiate_battle` | POST | Initiate a battle | dynasty_id, attacker_army_id, defender_army_id, territory_id |
| `/dynasty/<dynasty_id>/initiate_siege` | POST | Initiate a siege | dynasty_id, army_id, territory_id |
| `/dynasty/<dynasty_id>/update_siege/<siege_id>` | GET | Update siege progress | dynasty_id, siege_id |
| `/dynasty/<dynasty_id>/move_unit` | POST | Move a unit | dynasty_id, unit_id, destination_territory_id |
| `/dynasty/<dynasty_id>/move_army` | POST | Move an army | dynasty_id, army_id, destination_territory_id |

### Diplomacy Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/dynasty/<dynasty_id>/diplomacy` | GET | View diplomacy management | dynasty_id |
| `/dynasty/<dynasty_id>/treaties` | GET | View treaties | dynasty_id |
| `/dynasty/<dynasty_id>/diplomatic_action` | POST | Perform diplomatic action | dynasty_id, target_dynasty_id, action_type |
| `/dynasty/<dynasty_id>/create_treaty` | POST | Create a treaty | dynasty_id, target_dynasty_id, treaty_type, duration_years, terms |
| `/dynasty/<dynasty_id>/break_treaty/<treaty_id>` | POST | Break a treaty | dynasty_id, treaty_id |
| `/dynasty/<dynasty_id>/declare_war` | POST | Declare war | dynasty_id, target_dynasty_id, war_goal |
| `/dynasty/<dynasty_id>/negotiate_peace/<war_id>` | POST | Negotiate peace | dynasty_id, war_id, terms |

### Time Management Routes

| Route | Method | Description | Parameters |
|-------|--------|-------------|------------|
| `/dynasty/<dynasty_id>/time` | GET | View time management | dynasty_id |
| `/dynasty/<dynasty_id>/advance_time` | POST | Advance time | dynasty_id, seasons |
| `/dynasty/<dynasty_id>/schedule_event` | POST | Schedule an event | dynasty_id, event_type, trigger_year, trigger_season, data |
| `/dynasty/<dynasty_id>/cancel_event/<event_id>` | POST | Cancel an event | dynasty_id, event_id |
| `/dynasty/<dynasty_id>/timeline` | GET | View timeline | dynasty_id |
| `/world/synchronize_turns` | POST | Synchronize turns | dynasty_ids |

### API Request and Response Format

Most API routes follow these conventions:

1. **GET Requests**: Return HTML templates for browser viewing
2. **POST Requests**: Process form data and return redirects or JSON responses
3. **Authentication**: Most routes require the `@login_required` decorator
4. **Authorization**: Dynasty-specific routes check ownership before processing
5. **Error Handling**: Flash messages for user feedback, HTTP status codes for API responses

### Example API Usage

#### Creating a Dynasty

```python
# Form data for dynasty creation
data = {
    'dynasty_name': 'House Stark',
    'theme_type': 'predefined',
    'theme_key': 'medieval_european',
    'start_year': 1200,
    'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE'
}

# POST request to create dynasty
response = requests.post('http://localhost:5000/dynasty/create', data=data, cookies=session_cookies)

# Check response
if response.status_code == 302:  # Redirect on success
    print("Dynasty created successfully")
else:
    print("Error creating dynasty:", response.text)
```

#### Advancing a Turn

```python
# GET request to advance turn
response = requests.get(f'http://localhost:5000/dynasty/{dynasty_id}/advance_turn', cookies=session_cookies)

# Check response
if response.status_code == 302:  # Redirect on success
    print("Turn advanced successfully")
else:
    print("Error advancing turn:", response.text)
```

## Security Considerations

For detailed security information and best practices, refer to the [Security Considerations](security_considerations.md) document. Key security aspects include:

1. **Authentication**: User registration and login with password hashing
2. **Authorization**: Dynasty ownership checks for protected routes
3. **Input Validation**: Form data validation and sanitization
4. **CSRF Protection**: Cross-Site Request Forgery prevention
5. **Error Handling**: Proper error handling to prevent information leakage
6. **Environment Configuration**: Sensitive configuration via environment variables
## Conclusion

This development guide provides the foundation for extending and modifying the Royal Succession Multi-Agent Strategic Game. By following these guidelines and leveraging the existing architecture, you can add new features, fix issues, and enhance the game experience.

The project is actively evolving, with many planned enhancements and improvements. Developers are encouraged to focus on the areas outlined in the Future Development section while maintaining compatibility with the existing codebase.

For additional assistance or to contribute to the project, please submit issues or pull requests to the project repository.