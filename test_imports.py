# test_imports.py
print("Starting import test...")

print("Importing Flask...")
from flask import Flask
print("Flask imported successfully")

print("Importing SQLAlchemy...")
from flask_sqlalchemy import SQLAlchemy
print("SQLAlchemy imported successfully")

print("Importing db_models...")
from models.db_models import db
print("db_models imported successfully")

print("Importing map_system...")
from models.map_system import MapGenerator, TerritoryManager, MovementSystem, BorderSystem
print("map_system imported successfully")

print("Importing military_system...")
from models.military_system import MilitarySystem
print("military_system imported successfully")

print("Importing diplomacy_system...")
from models.diplomacy_system import DiplomacySystem
print("diplomacy_system imported successfully")

print("Importing economy_system...")
from models.economy_system import EconomySystem
print("economy_system imported successfully")

print("Importing time_system...")
from models.time_system import TimeSystem
print("time_system imported successfully")

print("Importing game_manager...")
from models.game_manager import GameManager
print("game_manager imported successfully")

print("All imports successful!")