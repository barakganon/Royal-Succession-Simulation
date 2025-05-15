# Royal Succession Multi-Agent Strategic Game: User Guide

This guide will help you navigate the Royal Succession Multi-Agent Strategic Game and master its various systems.

## Getting Started

### Accessing the Web Interface

1. Start the Flask application:
   ```
   python main_flask_app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

3. You will be directed to the home page of the Royal Succession game.

### Logging In

1. Click on the "Login" button in the navigation bar.
2. Use the following credentials:
   - Username: `test_user`
   - Password: `password`
3. Click "Login" to access your dashboard.

## Game Dashboard

The dashboard displays all games and dynasties associated with your account:

1. You'll see a list of your games with basic information including:
   - Game name
   - Map type
   - Number of dynasties
   - Current year
   - Last played date

2. Click on "Create New Game" to start a new game, or "Load Game" to continue an existing one.

## Creating a New Game

To create a new game:

1. Click "Create New Game" on the dashboard.
2. Enter a name for your game.
3. Select a map template:
   - Small Continent: Compact map with fewer territories
   - Large Continent: Expansive map with many territories
   - Archipelago: Island-based map with naval focus
4. Choose the number of AI dynasties (1-10).
5. Click "Create Game" to generate the world and begin.

## Game Interface

The game interface consists of several key views:

### Main Game View

The central hub for your game with:
- Current year and season
- Dynasty overview (wealth, prestige, etc.)
- Current monarch information
- Quick access to all game systems
- Turn management controls

### World Map

The strategic map shows:
- Territories and their controllers (color-coded)
- Terrain types (plains, mountains, forests, etc.)
- Settlements and resources
- Military units and armies
- Current borders and contested areas

Map controls allow you to:
- Filter territories by region, province, or terrain
- Highlight your dynasty's territories
- Show/hide different map elements (units, resources, etc.)
- Zoom in/out for detailed or strategic views

### Dynasty Management

The dynasty view provides:
- Dynasty name and description
- Current wealth, prestige, honor, and infamy
- Current monarch details and skills
- Living nobles and their attributes
- Family tree visualization
- Recent dynasty events

## Game Systems

### Map and Territory System

Territories are the foundation of your power:

1. **Territory Types**:
   - Each territory has a terrain type (plains, hills, mountains, etc.)
   - Terrain affects resource production, movement costs, and combat

2. **Territory Management**:
   - View territory details by clicking on the map
   - See population, development level, and resources
   - Build improvements to increase production
   - Construct defenses to protect against invasion

3. **Settlements**:
   - Territories may contain settlements (villages, towns, cities, castles)
   - Settlements provide additional tax income and manpower
   - Upgrade settlements to increase their benefits

### Military System

Build and command armies to protect your lands and conquer new territories:

1. **Unit Recruitment**:
   - Recruit military units from your territories
   - Unit types include:
     - Infantry: Levy Spearmen, Professional Swordsmen, Elite Guards
     - Ranged: Archers, Crossbowmen
     - Cavalry: Light Cavalry, Heavy Cavalry, Knights
     - Siege: Battering Rams, Siege Towers, Catapults, Trebuchets
     - Naval: Transport Ships, War Galleys, Heavy Warships

2. **Army Management**:
   - Create armies by combining units
   - Assign commanders from your dynasty members
   - Commander skills affect army performance
   - Maintain armies with gold and food

3. **Military Movement**:
   - Move armies between territories
   - Movement speed depends on terrain and season
   - Units require supply lines to maintain effectiveness

4. **Combat System**:
   - **Battles**: When armies meet in the field
     - Combat factors include unit types, numbers, terrain, commander skills
     - Battle phases: skirmish, main engagement, pursuit
     - Casualties reduce unit strength
   
   - **Sieges**: When attacking settlements or fortifications
     - Siege progress depends on attacker strength and defender fortifications
     - Sieges take time to complete
     - Defenders can attempt to break sieges with relief forces

### Diplomacy System

Manage relations with other dynasties:

1. **Diplomatic Relations**:
   - Each dynasty has a relation score with every other dynasty
   - Scores range from -100 (hostile) to +100 (allied)
   - View relations in the diplomacy screen

2. **Diplomatic Actions**:
   - Send Envoy: Improve relations
   - Arrange Marriage: Create dynastic ties
   - Form Alliance: Military or defensive pact
   - Declare Rivalry: Formalize hostility
   - Declare War: Begin military conflict
   - Negotiate Peace: End ongoing wars

3. **Treaties**:
   - Non-Aggression Pact: Agree not to attack each other
   - Defensive Alliance: Come to each other's aid if attacked
   - Military Alliance: Join each other's offensive wars
   - Trade Agreement: Increase economic benefits
   - Vassalage: Establish overlord/subject relationship

4. **Reputation Mechanics**:
   - Prestige: Increases with victories and achievements
   - Honor: Affected by keeping or breaking agreements
   - Infamy: Increases with aggressive actions

### Economy System

Develop your economy to fund your ambitions:

1. **Resources**:
   - **Basic Resources**:
     - Food: Required for population and armies
     - Timber: Used for buildings and ships
     - Stone: Used for fortifications
     - Iron: Required for military equipment
     - Gold: Universal currency
   
   - **Luxury Resources**:
     - Spices: Increase happiness and trade value
     - Wine: Improve court prestige
     - Silk: Enhance diplomatic relations
     - Jewelry: Significant wealth store

2. **Production and Consumption**:
   - Territories produce resources based on terrain
   - Population consumes food
   - Military units require maintenance
   - Buildings require resources to construct

3. **Trade System**:
   - Establish trade routes between territories
   - Trade agreements with other dynasties
   - Market prices fluctuate based on supply and demand

4. **Building Construction**:
   - Economic buildings (farms, mines, markets)
   - Military buildings (barracks, walls, towers)
   - Administrative buildings (town halls, courts)
   - Cultural buildings (temples, universities)

### Time System

The game progresses through turns with seasonal changes:

1. **Turn Structure**:
   - Each turn represents one season
   - Four seasons per year (Spring, Summer, Autumn, Winter)
   - Each season has different effects on production and movement

2. **Game Phases**:
   - Planning Phase: Review your situation
   - Diplomatic Phase: Conduct diplomatic actions
   - Military Phase: Move armies and conduct battles
   - Economic Phase: Manage resources and construction
   - Character Phase: Handle dynasty members
   - Resolution Phase: Process events and end turn

3. **Events**:
   - Random events based on season, location, and dynasty
   - Character events (births, deaths, marriages)
   - Natural events (harvests, storms, plagues)
   - Political events (rebellions, coups, festivals)

## Playing the Game

### Turn-by-Turn Gameplay

1. **Start of Turn**:
   - Review your current situation
   - Check notifications for important events
   - Plan your strategy for the turn

2. **Diplomatic Actions**:
   - Review your relations with other dynasties
   - Send envoys or arrange marriages to improve relations
   - Form alliances with potential friends
   - Declare wars if necessary

3. **Military Operations**:
   - Recruit new units if needed
   - Organize your armies
   - Move armies to strategic positions
   - Conduct battles or sieges

4. **Economic Management**:
   - Collect taxes and resources
   - Build improvements in your territories
   - Establish or modify trade routes
   - Manage your treasury

5. **Dynasty Management**:
   - Arrange marriages for dynasty members
   - Assign roles to characters based on skills
   - Handle succession planning

6. **End Turn**:
   - Click "Process Turn" to advance to the next season
   - Review the results of your actions
   - Respond to any events that occurred

### Victory Conditions

The game can be won through various paths:

1. **Conquest Victory**: Control a majority of the world's territories
2. **Diplomatic Victory**: Form alliances with a majority of dynasties
3. **Economic Victory**: Accumulate vast wealth and develop your territories
4. **Legacy Victory**: Maintain your dynasty for a set number of generations

## Advanced Strategies

### Military Strategies

1. **Defensive Posture**:
   - Focus on fortifying your borders
   - Maintain defensive alliances
   - Build walls and castles in border territories

2. **Expansionist Approach**:
   - Build large armies quickly
   - Target weaker neighbors first
   - Use diplomatic isolation before attacking

3. **Naval Dominance**:
   - Focus on coastal territories
   - Build a strong fleet
   - Control key trade routes

### Diplomatic Strategies

1. **Alliance Network**:
   - Form a web of alliances for protection
   - Maintain high honor to be a reliable ally
   - Mediate conflicts between allies

2. **Divide and Conquer**:
   - Foster rivalries between potential threats
   - Support weaker dynasties against stronger ones
   - Break enemy alliances through diplomatic actions

3. **Marriage Politics**:
   - Arrange strategic marriages with powerful dynasties
   - Use family ties to improve relations
   - Claim territories through inheritance

### Economic Strategies

1. **Trade Empire**:
   - Focus on controlling resource-rich territories
   - Establish extensive trade networks
   - Build markets and ports

2. **Development Focus**:
   - Invest heavily in territory improvements
   - Increase population and production
   - Build specialized economic buildings

3. **Resource Monopoly**:
   - Control territories with rare resources
   - Create scarcity to drive up prices
   - Use economic leverage for diplomatic advantage

## Troubleshooting

### Login Issues

If you cannot log in with the test user:
1. Ensure the Flask application is running.
2. Check that the database has been properly initialized.
3. Try restarting the application with `python main_flask_app.py`.

### Game Not Loading

If a game fails to load:
1. Check for error messages in the Flask console.
2. Ensure the database is not corrupted.
3. Try creating a new game if the issue persists.

### Map Visualization Issues

If the map doesn't display correctly:
1. Check your browser's JavaScript console for errors.
2. Try a different browser if issues persist.
3. Ensure all static files are properly loaded.

## Command Line Tools

For advanced users, several command-line tools are available:

### Run Local Simulation

To run a standalone simulation without the web interface:
```
python run_local_simulation.py
```

### Check Dynasty Status

To check the status of a specific dynasty:
```
python check_dynasty.py --dynasty_id=1
```

## Next Steps

After mastering the basics, consider:

1. Creating games with different map templates and settings.
2. Trying different victory strategies.
3. Contributing to the project by adding new features or cultural themes.
4. Creating custom scenarios or historical settings.

Enjoy your conquest of the world with the Royal Succession Multi-Agent Strategic Game!