# Technical Implementation of Royal Succession Multi-Agent Strategic Game

This document provides technical details about how the Royal Succession Multi-Agent Strategic Game is implemented. It's intended for developers who want to understand the code structure, database schema, and game systems.

## Implementation Overview

The game system is implemented through several integrated components:

1. **Theme Configuration**: JSON definitions of cultural elements
2. **Database Schema**: Comprehensive data model for game entities
3. **Game Systems**: Specialized systems for different aspects of gameplay
4. **Game Manager**: Central coordinator for all game systems
5. **Web Interface**: Flask routes for viewing and interacting with the game

## System Architecture

The multi-agent strategic game is built on a modular architecture with several specialized systems:

```
                    ┌─────────────────┐
                    │  Game Manager   │
                    └────────┬────────┘
                             │
         ┌──────────┬────────┼────────┬──────────┐
         │          │        │        │          │
┌────────▼───┐ ┌────▼─────┐ ┌▼─────┐ ┌▼────────┐ ┌▼────────────┐
│ Map System │ │ Military │ │ Time │ │ Economy │ │ Diplomacy   │
│            │ │ System   │ │System│ │ System  │ │ System      │
└────────────┘ └──────────┘ └──────┘ └─────────┘ └─────────────┘
```

### System Interactions

- **Game Manager**: Coordinates all systems, manages player sessions, and handles game state
- **Map System**: Provides territory information to all other systems
- **Military System**: Uses map data for movement, interacts with diplomacy for wars
- **Diplomacy System**: Affects military and economic interactions between dynasties
- **Economy System**: Uses map data for resource production, affected by military and diplomacy
- **Time System**: Synchronizes all systems through turn-based progression

## Game Systems

### Map System

The map system (`models/map_system.py`) handles:

1. **Map Generation**: Creates procedural or template-based maps
2. **Territory Management**: Handles territory ownership and attributes
3. **Movement Mechanics**: Calculates movement costs and paths
4. **Border Management**: Determines adjacency and border effects

Key classes:
- `MapGenerator`: Creates new game maps
- `TerritoryManager`: Handles territory ownership and attributes
- `MovementSystem`: Calculates movement costs and paths
- `BorderSystem`: Manages territory borders and adjacency

### Military System

The military system (`models/military_system.py`) handles:

1. **Unit Management**: Creation and maintenance of military units
2. **Army Organization**: Grouping units into armies
3. **Combat Resolution**: Battle and siege mechanics
4. **Military Movement**: Coordinating with the map system for unit movement

Key classes:
- `MilitarySystem`: Core class that manages all military aspects
- `UnitType` (enum): Defines different types of military units
- `CombatResolver`: Handles battle calculations and outcomes

### Diplomacy System

The diplomacy system (`models/diplomacy_system.py`) handles:

1. **Diplomatic Relations**: Tracks relationships between dynasties
2. **Treaty Management**: Creation and enforcement of treaties
3. **War Declaration**: Formal war mechanics and war goals
4. **Reputation Mechanics**: Honor, prestige, and infamy tracking

Key classes:
- `DiplomacySystem`: Core class that manages all diplomatic aspects
- `TreatyType` (enum): Defines different types of treaties
- `DiplomaticAction`: Represents actions dynasties can take toward each other

### Economy System

The economy system (`models/economy_system.py`) handles:

1. **Resource Production**: Generation of resources based on territory
2. **Trade Mechanics**: Exchange of resources between territories
3. **Building Management**: Construction and effects of buildings
4. **Territory Development**: Improvement of territories over time

Key classes:
- `EconomySystem`: Core class that manages all economic aspects
- `ResourceType` (enum): Defines different types of resources
- `BuildingType` (enum): Defines different types of buildings
- `TradeManager`: Handles trade routes and resource exchange

### Time System

The time system (`models/time_system.py`) handles:

1. **Turn Management**: Progression through game turns
2. **Season Effects**: Seasonal modifiers to production and movement
3. **Event Scheduling**: Timing and triggering of game events
4. **Historical Recording**: Logging of significant game events

Key classes:
- `TimeSystem`: Core class that manages time progression
- `Season` (enum): Defines seasons with different effects
- `GamePhase` (enum): Defines phases within a game turn
- `EventType` (enum): Categorizes different types of events

### Game Manager

The game manager (`models/game_manager.py`) serves as the central coordinator:

1. **Game Creation**: Sets up new game instances
2. **Player Session Management**: Handles player authentication and sessions
3. **AI Coordination**: Manages AI player decisions
4. **Game State Management**: Maintains and updates the game state
5. **System Coordination**: Ensures proper interaction between systems

Key methods:
- `create_new_game()`: Sets up a new game instance
- `load_game()`: Loads an existing game state
- `process_turn()`: Advances the game by one turn
- `process_ai_turns()`: Handles AI player decisions

## Database Schema

The game uses an expanded database schema defined in `models/db_models.py`:

### Core Tables

#### DynastyDB Table

The main dynasty record now includes:

```python
dynasty = DynastyDB(
    user_id=user.id,
    name="Dynasty Name",
    theme_identifier_or_json=theme_key_or_json_string,
    current_wealth=initial_wealth,
    start_year=start_year,
    current_simulation_year=start_year,
    prestige=50,           # New field for dynasty prestige
    honor=50,              # New field for dynasty honor
    infamy=0,              # New field for negative reputation
    is_ai_controlled=False # Whether this dynasty is AI-controlled
)
```

#### PersonDB Table

Character records now include additional attributes:

```python
person = PersonDB(
    dynasty_id=dynasty.id,
    name="Character Name",
    surname="Surname",
    gender="MALE",  # or "FEMALE"
    birth_year=birth_year,
    is_noble=True,
    is_monarch=is_founder,
    diplomacy_skill=5,    # New skill for diplomatic actions
    stewardship_skill=5,  # New skill for economic management
    martial_skill=5,      # New skill for military leadership
    intrigue_skill=5      # New skill for covert actions
)
```

### Map-Related Tables

#### Region Table

Defines large geographic regions:

```python
region = Region(
    name="Region Name",
    description="Region description",
    base_climate="temperate"  # Base climate affecting production
)
```

#### Province Table

Defines provinces within regions:

```python
province = Province(
    region_id=region.id,
    name="Province Name",
    description="Province description",
    primary_terrain=TerrainType.PLAINS
)
```

#### Territory Table

Defines individual territories:

```python
territory = Territory(
    province_id=province.id,
    name="Territory Name",
    description="Territory description",
    terrain_type=TerrainType.PLAINS,
    x_coordinate=100.0,
    y_coordinate=100.0,
    base_tax=2,
    base_manpower=100,
    development_level=1,
    population=1000,
    controller_dynasty_id=dynasty.id,
    is_capital=False
)
```

### Military Tables

#### MilitaryUnit Table

Defines individual military units:

```python
unit = MilitaryUnit(
    dynasty_id=dynasty.id,
    name="Unit Name",
    unit_type=UnitType.LEVY_SPEARMEN,
    size=100,
    morale=100,
    experience=0,
    territory_id=territory.id,
    army_id=army.id if army else None
)
```

#### Army Table

Groups units into armies:

```python
army = Army(
    dynasty_id=dynasty.id,
    name="Army Name",
    territory_id=territory.id,
    commander_id=commander.id if commander else None,
    is_moving=False,
    destination_territory_id=None,
    arrival_time=None
)
```

#### Battle and Siege Tables

Track military engagements:

```python
battle = Battle(
    attacker_army_id=attacker_army.id,
    defender_army_id=defender_army.id,
    territory_id=territory.id,
    start_year=year,
    start_season=Season.SUMMER.value,
    end_year=None,
    end_season=None,
    attacker_casualties=0,
    defender_casualties=0,
    winner_side=None
)

siege = Siege(
    attacker_army_id=attacker_army.id,
    territory_id=territory.id,
    start_year=year,
    start_season=Season.SUMMER.value,
    end_year=None,
    end_season=None,
    progress=0,
    is_completed=False
)
```

### Diplomacy Tables

#### DiplomaticRelation Table

Tracks relations between dynasties:

```python
relation = DiplomaticRelation(
    dynasty1_id=dynasty1.id,
    dynasty2_id=dynasty2.id,
    relation_score=0,  # -100 to 100
    last_action_year=None
)
```

#### Treaty Table

Defines treaties between dynasties:

```python
treaty = Treaty(
    dynasty1_id=dynasty1.id,
    dynasty2_id=dynasty2.id,
    treaty_type=TreatyType.NON_AGGRESSION,
    start_year=year,
    end_year=year + 10,  # 10-year treaty
    terms_json=json.dumps({"tribute": 5})
)
```

#### War Table

Tracks ongoing wars:

```python
war = War(
    attacker_dynasty_id=attacker.id,
    defender_dynasty_id=defender.id,
    start_year=year,
    end_year=None,
    attacker_war_score=0,
    defender_war_score=0,
    status="ongoing"
)
```

### Economy Tables

#### Resource Table

Defines resource types:

```python
resource = Resource(
    name="Resource Name",
    resource_type=ResourceType.FOOD,
    base_value=10,
    is_luxury=False
)
```

#### TerritoryResource Table

Links territories to resources:

```python
territory_resource = TerritoryResource(
    territory_id=territory.id,
    resource_id=resource.id,
    amount=100,
    production_rate=10
)
```

#### Building Table

Defines buildings in territories:

```python
building = Building(
    territory_id=territory.id,
    building_type=BuildingType.FARM,
    level=1,
    construction_year=year,
    completion_year=year + 1
)
```

## Web Interface Integration

The game is accessible through an enhanced Flask web interface:

### Key Routes

New routes in `main_flask_app.py`:

- **`/games`**: Lists all games for the current user
- **`/games/new`**: Creates a new game
- **`/games/<id>/view`**: Main game view
- **`/world_map`**: Displays the world map
- **`/territory/<id>`**: Shows territory details
- **`/military/view`**: Military management interface
- **`/diplomacy/view`**: Diplomacy management interface
- **`/economy/view`**: Economy management interface
- **`/process_turn`**: Advances the game by one turn

### Templates

The interface uses these new templates:

- **`templates/world_map.html`**: Interactive map view
- **`templates/territory_details.html`**: Territory management
- **`templates/military_view.html`**: Military management
- **`templates/diplomacy_view.html`**: Diplomacy management
- **`templates/economy_view.html`**: Economy management
- **`templates/time_view.html`**: Turn and event management

### Visualization Components

Enhanced visualization is handled by:

- **`visualization/map_renderer.py`**: Renders the world map
- **`visualization/military_renderer.py`**: Visualizes military units and battles
- **`visualization/diplomacy_renderer.py`**: Visualizes diplomatic relations
- **`visualization/economy_renderer.py`**: Visualizes economic data
- **`visualization/time_renderer.py`**: Visualizes timeline and events

## Game Progression

When a user clicks "Process Turn", the following happens:

1. `process_turn()` route is called with the dynasty ID
2. `game_manager.process_turn()` is called to advance the game
3. For each phase:
   - Planning Phase: Review game state
   - Diplomatic Phase: Process diplomatic actions
   - Military Phase: Move armies and resolve combat
   - Economic Phase: Calculate production and consumption
   - Character Phase: Process character events
   - Resolution Phase: Finalize the turn and trigger events
4. Update the game state and advance to the next turn
5. Redirect back to the game view

## AI Player Logic

AI dynasties are controlled by the game manager:

1. `process_ai_turns()` is called after the human player's turn
2. For each AI dynasty:
   - Analyze the current situation
   - Determine diplomatic strategy
   - Plan military movements
   - Manage economic development
   - Execute actions through the same systems as human players
3. Update the game state to reflect AI actions

## Performance Considerations

The enhanced game system has these performance characteristics:

- **Database Growth**: Each turn generates many new records across multiple tables
- **Visualization Cost**: Map rendering is the most resource-intensive operation
- **Memory Usage**: Moderate, with caching of frequently accessed data
- **Scaling**: Can support multiple games in parallel with reasonable performance

## Known Limitations

Current implementation limitations:

1. **AI Sophistication**: AI players have limited strategic depth
2. **Combat Complexity**: Battle resolution is somewhat simplified
3. **Economic Balance**: Resource production and consumption may need tuning
4. **UI Responsiveness**: Map rendering can be slow with many territories

## Conclusion

The Royal Succession Multi-Agent Strategic Game provides a comprehensive framework for historically-inspired strategy gameplay. The implementation balances historical authenticity with engaging gameplay mechanics to create a rich, dynamic world where dynasties compete for power and legacy across generations.