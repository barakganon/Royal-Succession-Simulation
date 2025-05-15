# test_game_manager.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

# Create a minimal Flask app
app = Flask(__name__)

# Configure the database
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
os.makedirs(instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "dynastysim.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import the database models
from models.db_models import db

# Initialize the database with the Flask app
db.init_app(app)

# Create an application context
with app.app_context():
    # Create the database tables
    db.create_all()
    print("Database tables created successfully")

    # Import the game manager
    from models.game_manager import GameManager

    # Create a game manager instance
    game_manager = GameManager(db.session)
    print("Game manager created successfully")

print("Test completed successfully")