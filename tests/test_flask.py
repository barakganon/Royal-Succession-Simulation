# test_flask.py
# A script to specifically test the import that was causing the error in main_flask_app.py

print("Testing import of SimulationEngine from simulation_engine...")
try:
    from simulation_engine import SimulationEngine
    print("✅ SUCCESS: SimulationEngine class imported successfully")
    
    # Create an instance to verify it works
    engine = SimulationEngine()
    print("✅ SUCCESS: SimulationEngine instance created successfully")
    
    # Test some methods to ensure functionality
    engine.configure(verbose_log=True, viz_interval=25)
    print("✅ SUCCESS: SimulationEngine.configure() method works")
    
    print("\nThe import error has been resolved. The SimulationEngine class is now properly defined in simulation_engine.py")
    
except ImportError as e:
    print(f"❌ IMPORT ERROR: {e}")
except Exception as e:
    print(f"❌ OTHER ERROR: {e}")