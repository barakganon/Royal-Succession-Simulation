# test_single_import.py
import sys
import os

def test_import(module_name):
    try:
        print(f"Attempting to import {module_name}...")
        __import__(module_name)
        print(f"{module_name} imported successfully")
        return True
    except Exception as e:
        print(f"Error importing {module_name}: {e}")
        return False

# Test basic imports first
test_import('flask')
test_import('flask_sqlalchemy')

# Test project modules one by one
test_import('models')
test_import('models.db_models')
test_import('models.map_system')
test_import('models.military_system')
test_import('models.diplomacy_system')
test_import('models.economy_system')
test_import('models.time_system')
test_import('models.game_manager')

print("Import test completed")