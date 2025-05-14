# Royal Succession Simulation

A historical dynasty simulation system that models the rise and fall of noble houses through generations, with a focus on succession, marriages, births, deaths, and historical events.

## System Features

### Simulation Engine

The simulation engine models:
- **Births and Deaths**: Characters are born, age, and die based on cultural and environmental factors
- **Marriages**: Strategic alliances through marriage
- **Succession**: Various succession rules (primogeniture, elective, etc.)
- **Events**: Random historical events that affect the dynasty
- **Traits**: Character traits that influence behavior and outcomes
- **Family Trees**: Tracking of complex family relationships

### Web Interface

The Flask web application provides:
- **User Authentication**: Create an account to manage your dynasties
- **Dynasty Creation**: Start a new dynasty with various cultural themes
- **Dynasty Management**: View and manage your dynasty's members, wealth, and history
- **Time Advancement**: Progress the simulation through years and generations
- **Visualization**: Family tree visualizations

## Getting Started

### Prerequisites

- Python 3.8+
- Flask
- SQLAlchemy
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

### Using the House Ganon Saga

1. Log in with username `test_user` and password `password`
2. Navigate to the dashboard to see the House Ganon dynasty
3. Click on "View Dynasty" to explore the family members and history
4. Use the "Advance Turn" button to progress the simulation

### Running Local Simulations

For command-line simulations without the web interface:

```
python run_local_simulation.py
```

This will run a simulation using either a random theme or the one specified in the script.

## Project Structure

- `main_flask_app.py`: Main Flask application with web routes
- `simulation_engine.py`: Core simulation logic
- `run_local_simulation.py`: Command-line simulation runner
- `models/`: Core data models
  - `person.py`: Person class representing individuals
  - `family_tree.py`: Family tree management
  - `history.py`: Historical event tracking
  - `db_models.py`: Database models for Flask app
- `utils/`: Utility functions
  - `theme_manager.py`: Cultural theme management
  - `helpers.py`: Helper functions
- `visualization/`: Visualization tools
  - `plotter.py`: Family tree visualization
- `themes/`: Cultural theme definitions
  - `cultural_themes.json`: Predefined cultural themes
  - `house_ganon_theme.json`: House Ganon specific theme
- `templates/`: HTML templates for the web interface
- `static/`: Static assets for the web interface

## Customizing Dynasties

You can create your own dynasty by:

1. Using the web interface to create a new dynasty with a predefined theme
2. Providing a custom story for LLM-based theme generation (requires API key)
3. Creating a custom theme JSON file in the `themes/` directory
4. Modifying the `run_local_simulation.py` file to use your custom theme or story

## Checking Dynasty Status

To check the status of the House Ganon dynasty:

```
python check_house_ganon.py
```

This will display information about the dynasty, its members, and historical events.

## System Features

### Simulation Engine

The simulation engine models:
- **Births and Deaths**: Characters are born, age, and die based on cultural and environmental factors
- **Marriages**: Strategic alliances through marriage
- **Succession**: Various succession rules (primogeniture, elective, etc.)
- **Events**: Random historical events that affect the dynasty
- **Traits**: Character traits that influence behavior and outcomes
- **Family Trees**: Tracking of complex family relationships

### Web Interface

The Flask web application provides:
- **User Authentication**: Create an account to manage your dynasties
- **Dynasty Creation**: Start a new dynasty with various cultural themes
- **Dynasty Management**: View and manage your dynasty's members, wealth, and history
- **Time Advancement**: Progress the simulation through years and generations
- **Visualization**: Family tree visualizations

## Getting Started

### Prerequisites

- Python 3.8+
- Flask
- SQLAlchemy
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

## Project Structure

- `main_flask_app.py`: Main Flask application with web routes
- `simulation_engine.py`: Core simulation logic
- `run_local_simulation.py`: Command-line simulation runner
- `models/`: Core data models
  - `person.py`: Person class representing individuals
  - `family_tree.py`: Family tree management
  - `history.py`: Historical event tracking
  - `db_models.py`: Database models for Flask app
- `utils/`: Utility functions
  - `theme_manager.py`: Cultural theme management
  - `helpers.py`: Helper functions
- `visualization/`: Visualization tools
  - `plotter.py`: Family tree visualization
- `themes/`: Cultural theme definitions
  - `cultural_themes.json`: Predefined cultural themes
- `templates/`: HTML templates for the web interface
- `static/`: Static assets for the web interface
- `docs/`: Documentation
  - `user_guide.md`: How to use the system
  - `technical_implementation.md`: Developer documentation

## Example Usage

The system comes with predefined cultural themes that can be used to create dynasties. You can:

1. Create a new dynasty through the web interface
2. Choose a cultural theme (Medieval European, Norse, etc.)
3. Set the starting year and succession rules
4. Advance the simulation to see how your dynasty evolves

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.