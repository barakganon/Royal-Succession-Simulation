# test_single_import.py
# A simple script to test if the SimulationEngine class can be imported correctly

try:
    from simulation_engine import SimulationEngine
    print("Successfully imported SimulationEngine class")
    
    # Create an instance of SimulationEngine
    engine = SimulationEngine()
    print("Successfully created SimulationEngine instance")
    
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Other error: {e}")