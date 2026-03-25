# main_flask_app.py
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session as flask_session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json  # For theme handling
import random
import datetime
import signal
import sys
import logging
import atexit
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("flask_app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("royal_succession.flask")

# Import database models (adjust path if your structure differs slightly)
from models.db_models import (
    db, User, DynastyDB, PersonDB, HistoryLogEntryDB, Territory, Region, Province,
    MilitaryUnit, UnitType, Army, Battle, Siege, War, DiplomaticRelation, Treaty, TreatyType, TradeRoute, Resource,
    BuildingType, ResourceType, Building, WarGoal, ChronicleEntryDB
)
from models.map_system import MapGenerator, TerritoryManager, MovementSystem, BorderSystem
from models.military_system import MilitarySystem
from models.diplomacy_system import DiplomacySystem
from models.economy_system import EconomySystem
from models.time_system import TimeSystem, Season, EventType, EventPriority, GamePhase
from models.game_manager import GameManager
from models.db_initialization import DatabaseInitializer
from simulation_engine import SimulationEngine
from models.military_system import MilitarySystem
from visualization.map_renderer import MapRenderer
from visualization.military_renderer import MilitaryRenderer
from visualization.diplomacy_renderer import DiplomacyRenderer
from visualization.economy_renderer import EconomyRenderer
from visualization.time_renderer import TimeRenderer
from visualization.heraldry_renderer import generate_coat_of_arms

# Import theme utilities
from utils.theme_manager import load_cultural_themes, get_all_theme_names, generate_theme_from_story_llm, get_theme
from utils.helpers import set_llm_globals_for_helpers  # To pass LLM model instance

# --- Flask App Configuration ---
app = Flask(__name__)

# Secret Key: Important for session management and security.
# It's best to get this from an environment variable in production.
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_strong_dev_secret_key_!@#$%^&*()')

# Database Configuration: Using SQLite for simplicity.
# The 'instance' folder is a good place for the DB file in Flask projects.
# It's usually created automatically by Flask if it doesn't exist when the DB is first accessed.
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
os.makedirs(instance_path, exist_ok=True)  # Ensure instance folder exists
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL',
                                                       f'sqlite:///{os.path.join(instance_path, "dynastysim.db")}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Recommended to disable

# Initialize SQLAlchemy with the Flask app
db.init_app(app)

# Initialize SocketIO for real-time battle ticker
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database initializer
db_initializer = DatabaseInitializer(app)

# Register Blueprints
from blueprints.auth import auth as auth_bp
app.register_blueprint(auth_bp)
from blueprints.dynasty import dynasty_bp
app.register_blueprint(dynasty_bp)
from blueprints.military import military_bp
app.register_blueprint(military_bp)
from blueprints.economy import economy_bp
app.register_blueprint(economy_bp)
from blueprints.diplomacy import diplomacy_bp
app.register_blueprint(diplomacy_bp)
from blueprints.map import map_bp
app.register_blueprint(map_bp)

# Flask-Login Configuration
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'  # The route Flask-Login redirects to if @login_required fails
login_manager.login_message = "Please log in to access this page."  # Message shown to user
login_manager.login_message_category = "info"  # Bootstrap class for the flash message

# --- LLM Setup for Flask App (if used for theme generation or other web features) ---
FLASK_APP_LLM_MODEL = None
FLASK_APP_GOOGLE_API_KEY_PRESENT = False
try:
    import google.generativeai as genai

    FLASK_APP_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if FLASK_APP_API_KEY:
        genai.configure(api_key=FLASK_APP_API_KEY)
        FLASK_APP_LLM_MODEL = genai.GenerativeModel("gemini-1.5-flash-latest")  # Or your preferred model
        FLASK_APP_GOOGLE_API_KEY_PRESENT = True
        logger.info("LLM Initialized successfully for Flask App.")
    else:
        logger.warning("LLM API Key not found for Flask App. Custom theme generation from story will be disabled.")
except ImportError:
    logger.warning("google-generativeai package not found. LLM features disabled for Flask App.")
except Exception as e_flask_llm:
    logger.error(f"Error initializing LLM for Flask App: {type(e_flask_llm).__name__} - {e_flask_llm}")

# Pass LLM status to helper functions (used by theme_manager.generate_theme_from_story_llm)
set_llm_globals_for_helpers(FLASK_APP_LLM_MODEL, FLASK_APP_GOOGLE_API_KEY_PRESENT)

# Store LLM availability in app config so blueprints can read it via current_app.config
app.config['FLASK_APP_GOOGLE_API_KEY_PRESENT'] = FLASK_APP_GOOGLE_API_KEY_PRESENT
app.config['FLASK_APP_LLM_MODEL'] = FLASK_APP_LLM_MODEL


# --- End LLM Setup ---

# --- Signal Handling ---
def signal_handler(sig, frame):
    """Handle interrupt signals gracefully"""
    logger.info("Received interrupt signal. Shutting down Flask application gracefully...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Cleanup function to run on exit
def cleanup():
    """Perform cleanup operations before exit"""
    logger.info("Performing cleanup before application shutdown")
    # Close database connections
    try:
        with app.app_context():
            db.session.remove()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

# Register cleanup function
atexit.register(cleanup)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Flask-Login user loader callback."""
    return User.query.get(int(user_id))



# --- Routes ---

@app.route('/')
def index():
    """Home page."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    # For unauthenticated users, you might show a landing page
    return render_template('index.html', title="Welcome")  # Create index.html later


# Routes moved to blueprints/map.py (map_bp)




# --- Backfill coat of arms for existing dynasties ---
def backfill_coat_of_arms():
    """Generate coat of arms SVG for any dynasty that does not yet have one.

    Called once at startup; safe to re-run (guarded by None check).
    """
    try:
        dynasties_without_arms = DynastyDB.query.filter(DynastyDB.coat_of_arms_svg == None).all()  # noqa: E711
        if not dynasties_without_arms:
            return
        logger.info(f"Backfilling coat of arms for {len(dynasties_without_arms)} dynasty/dynasties.")
        for dynasty in dynasties_without_arms:
            try:
                dynasty.coat_of_arms_svg = generate_coat_of_arms(dynasty.id, dynasty.name)
            except Exception as e:
                logger.error(f"Failed to backfill coat of arms for dynasty {dynasty.id}: {e}")
        db.session.commit()
        logger.info("Coat of arms backfill complete.")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Coat of arms backfill failed: {e}")


# --- Initialize Test User ---
def initialize_test_user():
    """Initialize a test user in the database if it doesn't exist."""
    with app.app_context():
        # Check if we already have a test user
        test_user = User.query.filter_by(username="test_user").first()
        if not test_user:
            test_user = User(username="test_user", email="test@example.com")
            test_user.set_password("password")
            db.session.add(test_user)
            db.session.commit()
            logger.info("Test user created.")
        else:
            logger.info("Test user already exists.")
        return test_user


def start_flask_app_with_port_fallback(initial_port=8091, max_attempts=10):
    """
    Attempts to start the Flask application, falling back to alternative ports if the initial port is in use.
    
    Args:
        initial_port: The port to try first
        max_attempts: Maximum number of alternative ports to try
    
    Returns:
        True if the app started successfully, False otherwise
    """
    import socket
    from werkzeug.serving import make_server

    # Try the initial port and then alternatives
    for port_offset in range(max_attempts):
        current_port = initial_port + port_offset
        
        try:
            # Check if port is available before trying to start Flask
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', current_port))
                # If we get here, the port is available
                s.close()
                
            logger.info(f"Starting Flask application on port {current_port}...")
            socketio.run(app, host='0.0.0.0', port=current_port, debug=True, allow_unsafe_werkzeug=True, use_reloader=False)
            return True
            
        except socket.error:
            logger.warning(f"Port {current_port} is already in use, trying next port...")
        except Exception as e:
            logger.error(f"Error starting Flask on port {current_port}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    logger.critical(f"Failed to start Flask app after trying {max_attempts} different ports")
    return False

if __name__ == '__main__':
    try:
        # Initialize database with integrity checks and migrations
        with app.app_context():
            # Initialize database
            success = db_initializer.initialize_database()
            if not success:
                logger.error("Database initialization failed. Attempting to continue anyway.")
            
            # Perform migrations if needed
            migration_success = db_initializer.perform_migrations()
            if not migration_success:
                logger.warning("Database migrations failed. Some features may not work correctly.")
            
            # Initialize test user
            initialize_test_user()

            # Backfill coat of arms for existing dynasties that lack one
            backfill_coat_of_arms()

            logger.info("Database initialization completed.")

        # Pre-load themes from JSON file into theme_manager when app starts
        load_cultural_themes()  # From utils.theme_manager
        logger.info("Cultural themes loaded.")

        # Start the Flask application with port fallback
        if not start_flask_app_with_port_fallback(initial_port=8091, max_attempts=10):
            logger.critical("Could not start Flask application on any available port")
            sys.exit(1)
            
    except Exception as e:
        logger.critical(f"Fatal error starting application: {str(e)}")
        import traceback
        logger.critical(traceback.format_exc())
        sys.exit(1)