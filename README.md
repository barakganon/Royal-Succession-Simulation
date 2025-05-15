# Royal Succession Simulation: Multi-Agent Strategic Game

A historical dynasty simulation system that has evolved into a multi-agent strategic game, where noble houses compete for power, territory, and resources. The game combines dynasty management with strategic gameplay elements including map control, military operations, diplomatic relations, and economic development.

## System Features

### Core Game Systems

The multi-agent strategic game includes several integrated systems:

- **Map System**: Geographic territories with various terrain types, resources, and strategic value
- **Military System**: Unit recruitment, army management, battles, and sieges
- **Diplomacy System**: Relations between dynasties, treaties, alliances, and wars
- **Economy System**: Resource production, trade, building construction, and territory development
- **Time System**: Turn-based progression with seasons, events, and historical tracking
- **Game Manager**: Coordinates all systems and manages game state

### Dynasty Management

The dynasty management features include:

- **Character System**: Leaders and nobles with traits, skills, and relationships
- **Succession**: Various succession rules (primogeniture, elective, etc.)
- **Family Trees**: Tracking of complex family relationships
- **Events**: Random historical events that affect the dynasty

### Web Interface

The Flask web application provides:

- **User Authentication**: Create an account to manage your dynasties
- **Game Creation**: Start new games with customizable settings
- **Dynasty Management**: View and manage your dynasty's members, territories, and armies
- **Strategic Map**: Interactive world map showing territories, resources, and units
- **Turn Management**: Progress through game phases and turns
- **Visualizations**: Maps, family trees, battle reports, and diplomatic networks

## Getting Started

### Prerequisites

- Python 3.8+
- Flask
- SQLAlchemy
- Matplotlib (for visualizations)
- NumPy (for map generation)
- (Optional) Google Generative AI API key for enhanced narrative generation

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/Royal-Succession-Simulation.git
   cd Royal-Succession-Simulation
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the Flask application:
   ```
   python main_flask_app.py
   ```

4. Access the web interface at `http://localhost:5000`

### Creating Your First Game

1. Log in with username `test_user` and password `password` (or create a new account)
2. Click "Create New Game" on the dashboard
3. Choose a map template and number of AI dynasties
4. Name your dynasty and select a cultural theme
5. Start the game and explore your territories

### Game Phases

Each turn in the game consists of several phases:

1. **Planning Phase**: Review your situation and plan your actions
2. **Diplomatic Phase**: Manage relations with other dynasties
3. **Military Phase**: Move armies and conduct battles
4. **Economic Phase**: Manage resources and construction
5. **Character Phase**: Handle dynasty members and events
6. **Resolution Phase**: End of turn processing and event resolution

## Project Structure

- `main_flask_app.py`: Main Flask application with web routes
- `simulation_engine.py`: Core simulation logic
- `run_local_simulation.py`: Command-line simulation runner
- `models/`: Core data models
  - `person.py`: Person class representing individuals
  - `family_tree.py`: Family tree management
  - `history.py`: Historical event tracking
  - `db_models.py`: Database models for Flask app
  - `map_system.py`: Map generation and territory management
  - `military_system.py`: Military units and combat
  - `diplomacy_system.py`: Diplomatic relations and treaties
  - `economy_system.py`: Resources and economic development
  - `time_system.py`: Turn management and events
  - `game_manager.py`: Game state coordination
- `utils/`: Utility functions
  - `theme_manager.py`: Cultural theme management
  - `helpers.py`: Helper functions
  - `logging_config.py`: Logging configuration
- `visualization/`: Visualization tools
  - `plotter.py`: Family tree visualization
  - `map_renderer.py`: Map visualization
  - `military_renderer.py`: Military visualization
  - `diplomacy_renderer.py`: Diplomacy visualization
  - `economy_renderer.py`: Economy visualization
  - `time_renderer.py`: Timeline visualization
- `themes/`: Cultural theme definitions
  - `cultural_themes.json`: Predefined cultural themes
- `templates/`: HTML templates for the web interface
  - `world_map.html`: Map view template
  - `military_view.html`: Military interface
  - `diplomacy_view.html`: Diplomacy interface
  - `economy_view.html`: Economy interface
  - `time_view.html`: Time and events interface
- `static/`: Static assets for the web interface
- `docs/`: Documentation
  - `user_guide.md`: How to play the game
  - `technical_implementation.md`: Developer documentation
  - `development_guide.md`: Guidelines for further development

## Running Local Simulations

For command-line simulations without the web interface:

```
python run_local_simulation.py
```

This will run a simulation using either a random theme or the one specified in the script.

## Customizing Games

You can customize your game experience by:

1. Selecting different map templates (small continent, large continent, archipelago)
2. Adjusting the number of AI dynasties
3. Choosing different cultural themes for your dynasty
4. Providing a custom story for LLM-based theme generation (requires API key)

## Documentation

For more detailed information, please refer to:

- `docs/user_guide.md`: Comprehensive guide on how to play the game
- `docs/technical_implementation.md`: Technical details about the implementation
- `docs/development_guide.md`: Guidelines for extending the game

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.