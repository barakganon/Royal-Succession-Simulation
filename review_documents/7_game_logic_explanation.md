# Royal Succession Simulation - Game Logic Explanation

## Overview
This document provides a comprehensive explanation of the game logic behind the Royal Succession Simulation. It details how the core systems work individually and how they interact with each other to create a cohesive simulation of dynasty management, warfare, diplomacy, and economic development across historical periods.

## Core Architecture

### Game Manager
The Game Manager serves as the central coordinator for all game systems. It:
- Initializes and maintains references to all subsystems
- Manages player sessions and authentication
- Coordinates turn processing and game state advancement
- Handles game creation, loading, and saving
- Manages multiplayer synchronization
- Coordinates AI player decisions

The Game Manager follows a modular design pattern, delegating specific functionality to specialized subsystems while maintaining the overall game state and ensuring proper interaction between systems.

### Database Models
The database models define the structure of all game entities and their relationships:
- **User**: Represents player accounts with authentication
- **DynastyDB**: Core entity representing a player's dynasty with attributes like wealth, prestige, etc.
- **PersonDB**: Represents individual characters with attributes, skills, and relationships
- **Territory**: Represents land units with resources, buildings, and population
- **MilitaryUnit/Army**: Represents military forces with attributes and capabilities
- **DiplomaticRelation/Treaty**: Represents relationships and agreements between dynasties
- **HistoryLogEntryDB**: Records historical events for dynasties

The database uses SQLAlchemy ORM with carefully designed relationships to maintain data integrity while allowing efficient queries for game operations.

## Time and Turn System

### Time Progression
Time in the game advances through discrete turns, with each turn representing a period (typically 5 years) of in-game time. The time system:
- Tracks the current year for each dynasty
- Manages seasonal changes and their effects
- Schedules and triggers time-based events
- Coordinates simultaneous turn resolution for multiplayer

### Turn Structure
Each turn follows a structured sequence:
1. **Planning Phase**: Players make decisions and issue orders
   - Diplomatic actions
   - Military movements and recruitment
   - Construction and development projects
   - Character assignments and decisions
   
2. **Execution Phase**: Orders are carried out
   - Military movements are processed
   - Battles and sieges are resolved
   - Construction projects progress
   - Diplomatic actions take effect
   
3. **Resolution Phase**: Automatic events and consequences
   - Character aging and death checks
   - Birth and marriage events
   - Random events based on situation
   - Resource production and consumption
   
4. **Advancement Phase**: Game state updates
   - Year counter advances
   - Seasonal effects apply
   - AI dynasties make decisions
   - History logs are updated

### Event System
The event system generates both scheduled and random events:
- **Scheduled Events**: Predictable occurrences like construction completion
- **Random Events**: Unpredictable occurrences based on probability and conditions
- **Character Events**: Life events for dynasty members (birth, marriage, death)
- **Global Events**: Affect multiple dynasties (plagues, climate events)

Events use a priority system to ensure proper sequencing when multiple events occur in the same turn.

## Character and Dynasty System

### Character Lifecycle
Characters (PersonDB) follow a lifecycle from birth to death:
1. **Birth**: Characters are born to dynasty members with inherited traits
2. **Childhood**: Characters develop basic attributes and traits
3. **Adulthood**: Characters can marry, hold positions, and have children
4. **Death**: Characters die from age, disease, battle, or other causes

Characters have various attributes:
- **Basic Attributes**: Name, gender, birth/death years
- **Skills**: Diplomacy, stewardship, martial, intrigue
- **Relationships**: Parents, spouse, children
- **Positions**: Monarch, commander, governor

### Dynasty Management
Dynasties (DynastyDB) represent the player's royal house:
- **Succession**: When a monarch dies, succession rules determine the next ruler
- **Prestige**: Accumulated from achievements, affects diplomatic weight
- **Wealth**: Currency for construction, recruitment, and maintenance
- **Holdings**: Territories and assets controlled by the dynasty

### Succession Mechanics
Succession follows historical patterns with various possible rules:
- **Primogeniture**: Eldest child inherits (with male or female preference variants)
- **Gavelkind**: Inheritance divided among children
- **Elective**: Successor chosen by vote
- **Tanistry**: Successor chosen from dynasty members
- **Ultimogeniture**: Youngest child inherits

Succession crises can occur when rules are unclear or multiple claimants exist.

## Map and Territory System

### Map Generation
The map system creates the game world through:
- **Procedural Generation**: Algorithmically creates regions, provinces, and territories
- **Template-Based Generation**: Uses predefined templates for historical scenarios
- **Fallback Generation**: Ensures minimum viable map even if other methods fail

Maps are organized hierarchically:
- **Regions**: Large geographical areas with similar climate
- **Provinces**: Administrative divisions within regions
- **Territories**: Individual land units that can be controlled

### Territory Management
Territories are the basic land units with:
- **Resources**: Natural resources based on terrain type
- **Population**: Inhabitants who provide taxes and manpower
- **Buildings**: Constructed improvements for various benefits
- **Development**: Overall advancement level affecting production
- **Controller**: Dynasty currently controlling the territory
- **Governor**: Character assigned to administer the territory

### Movement System
The movement system handles unit and army movement:
- **Pathfinding**: A* algorithm to find optimal paths between territories
- **Movement Costs**: Based on terrain, roads, and unit types
- **Border Control**: Restrictions based on diplomatic status
- **Supply Lines**: Affects maintenance during movement

## Military System

### Unit Management
Military units are the basic components of armies:
- **Unit Types**: Different types with unique stats (infantry, cavalry, siege, etc.)
- **Recruitment**: Creating new units using gold and manpower
- **Maintenance**: Ongoing costs to keep units operational
- **Training**: Improving unit quality and experience
- **Assignment**: Units can be assigned to armies or operate independently

### Army Operations
Armies are collections of units operating together:
- **Formation**: Combining units into a cohesive force
- **Command**: Assigning commanders who provide bonuses
- **Movement**: Coordinated movement across territories
- **Supply**: Resource consumption during operations
- **Morale**: Affects combat effectiveness and desertion risk

### Combat Resolution
Combat occurs when opposing forces meet:
1. **Initialization**: Combat parameters are established
   - Terrain effects
   - Commander bonuses
   - Unit composition
   - Morale and strength calculations
   
2. **Battle Phases**:
   - Initial clash with advantage to certain unit types
   - Main battle with strength-based resolution
   - Pursuit phase with advantage to mobile units
   
3. **Resolution**:
   - Casualties calculated for both sides
   - Winner determined based on remaining strength
   - Retreat or capture of defeated forces
   - Territory control changes if applicable

### Siege Mechanics
Sieges occur when armies attack fortified territories:
1. **Encirclement**: Territory is surrounded
2. **Progression**: Siege progress increases over time
3. **Assault**: Direct attacks can speed resolution but cause casualties
4. **Resolution**: Territory captured or siege broken by relief force

## Economy System

### Resource Management
The economy revolves around resources:
- **Production**: Territories produce resources based on terrain and buildings
- **Consumption**: Population and military consume resources
- **Storage**: Resources can be stored with some decay over time
- **Trade**: Resources can be exchanged between dynasties

### Production Mechanics
Resource production is calculated based on:
- **Base Production**: Determined by territory terrain type
- **Building Bonuses**: Structures that enhance production
- **Population Factor**: More people can work but also consume more
- **Governor Skills**: Administrators can improve efficiency
- **Development Level**: More developed territories produce more
- **Seasonal Effects**: Production varies by season

### Building System
Buildings provide various benefits:
- **Construction**: Requires resources, time, and gold
- **Maintenance**: Ongoing costs to keep buildings operational
- **Upgrades**: Buildings can be improved for greater benefits
- **Damage and Repair**: Buildings can be damaged and require repairs
- **Specialization**: Different building types provide different benefits

### Taxation and Treasury
The financial system manages dynasty wealth:
- **Tax Collection**: Based on territory development and population
- **Expenses**: Military maintenance, building upkeep, diplomatic actions
- **Treasury**: Accumulated wealth available for spending
- **Loans**: Borrowing mechanisms (partially implemented)
- **Interest**: Accumulation on treasury or loans

## Diplomacy System

### Diplomatic Relations
Relations between dynasties are tracked and affect interactions:
- **Relation Score**: Numerical value from -100 (nemesis) to +100 (allied)
- **Relation Status**: Categorized as Allied, Friendly, Neutral, Unfriendly, etc.
- **Historical Actions**: Past interactions affect current relations
- **Cultural Factors**: Cultural similarities or differences affect base relations

### Diplomatic Actions
Dynasties can perform various diplomatic actions:
- **Peaceful Actions**: Sending envoys, arranging marriages, gifts
- **Hostile Actions**: Rivalry declarations, insults, demands
- **Covert Actions**: Spreading rumors, bribing officials, assassination attempts
- **Formal Actions**: Treaty proposals, war declarations, peace offers

### Treaty System
Treaties formalize agreements between dynasties:
- **Treaty Types**: Non-aggression, alliance, vassalage, trade, etc.
- **Duration**: Fixed term or permanent agreements
- **Terms**: Specific conditions and benefits
- **Enforcement**: Consequences for breaking treaties
- **Maintenance**: Some treaties require ongoing payments

### Warfare Diplomacy
War has specific diplomatic mechanics:
- **War Declaration**: Formal start of hostilities with reputation costs
- **War Goals**: Specific objectives determining victory conditions
- **Peace Negotiation**: Terms for ending conflict
- **Reparations**: Post-war payments and concessions
- **Truces**: Forced peace periods after wars

## System Interactions

### Military-Economy Interaction
- Military units require economic resources for recruitment and maintenance
- Warfare can damage economic infrastructure
- Conquered territories provide economic benefits
- Economic strength determines military capacity

### Diplomacy-Military Interaction
- Diplomatic status determines possible military actions
- Military strength affects diplomatic leverage
- Alliances provide military support
- Wars are initiated through diplomacy but resolved through military action

### Character-Military Interaction
- Characters serve as commanders providing bonuses
- Character skills affect military effectiveness
- Military victories increase character prestige
- Character deaths can occur in battle

### Economy-Territory Interaction
- Territories produce economic resources
- Economic investment improves territory development
- Resource distribution affects territory value
- Trade routes connect territories economically

### Character-Diplomacy Interaction
- Character skills affect diplomatic success chances
- Marriages create diplomatic ties
- Character actions can trigger diplomatic incidents
- Ruler personality affects AI diplomatic behavior

### Time-All Systems Interaction
- All systems advance with time progression
- Seasonal effects impact multiple systems
- Long-term trends emerge through time advancement
- Historical events are recorded chronologically

## AI Logic

### AI Decision Making
AI dynasties make decisions based on:
- **Personality Factors**: Aggression, caution, ambition levels
- **Strategic Assessment**: Relative strength, opportunities, threats
- **Resource Evaluation**: Available resources and needs
- **Historical Patterns**: Past interactions and grudges
- **Goal Prioritization**: Balancing multiple objectives

### AI Subsystems
The AI uses specialized subsystems for different aspects:
- **Military AI**: Handles unit recruitment, army formation, and warfare
- **Diplomatic AI**: Manages relations, treaties, and diplomatic actions
- **Economic AI**: Directs construction, development, and resource management
- **Character AI**: Makes decisions for individual AI characters

### AI Difficulty Scaling
AI behavior adjusts based on difficulty settings:
- **Resource Bonuses**: Higher difficulties give AI resource advantages
- **Decision Quality**: Higher difficulties make fewer mistakes
- **Aggressiveness**: Higher difficulties pursue goals more actively
- **Coordination**: Higher difficulties coordinate multiple systems better

## Game Balance Mechanisms

### Resource Equilibrium
The game maintains resource balance through:
- **Production Limits**: Maximum production based on development
- **Consumption Requirements**: Minimum resources needed for stability
- **Diminishing Returns**: Efficiency decreases at higher levels
- **Maintenance Costs**: Higher development requires more upkeep

### Power Balance
Dynasty power is balanced through:
- **Expansion Penalties**: Controlling more territory increases costs
- **Coalition Mechanics**: Strong dynasties face diplomatic opposition
- **Specialization Trade-offs**: Focusing on one area weakens others
- **Catch-up Mechanics**: Smaller dynasties develop faster

### Random Elements
Randomness adds unpredictability through:
- **Event Triggers**: Random events based on probability
- **Character Traits**: Random trait distribution
- **Combat Variance**: Random factors in battle outcomes
- **Resource Variation**: Random fluctuations in production

## Conclusion
The Royal Succession Simulation implements a complex, interconnected set of systems that model the multifaceted nature of historical dynasty management. The game logic balances historical authenticity with engaging gameplay through carefully designed mechanics and system interactions. While some systems are more fully developed than others, the overall architecture provides a solid foundation for an immersive strategy experience that captures the challenges of ruling a dynasty through the ages.