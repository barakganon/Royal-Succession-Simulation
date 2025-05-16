# test_imports.py
# A script to test if the imports in main_flask_app.py work correctly

try:
    # Import the specific line that was causing the error
    from simulation_engine import SimulationEngine
    print("Successfully imported SimulationEngine class")
    
    # Try to import other modules used in main_flask_app.py
    from models.db_models import db, User
    print("Successfully imported db models")
    
    from models.game_manager import GameManager
    print("Successfully imported GameManager")
    
    # Create an instance of SimulationEngine to verify it works
    engine = SimulationEngine()
    print("Successfully created SimulationEngine instance")
    
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Other error: {e}")