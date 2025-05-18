# main_flask_app.py
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json  # For theme handling
import random
import datetime
import signal
import sys
import logging
import atexit

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
    BuildingType, ResourceType, Building, WarGoal
)
from models.map_system import MapGenerator, TerritoryManager, MovementSystem, BorderSystem
from models.military_system import MilitarySystem
from models.diplomacy_system import DiplomacySystem
from models.economy_system import EconomySystem
from models.time_system import TimeSystem, Season, EventType, EventPriority, GamePhase
from models.game_manager import GameManager
from models.db_initialization import DatabaseInitializer
from simulation_engine import SimulationEngine

from visualization.map_renderer import MapRenderer
from visualization.military_renderer import MilitaryRenderer
from visualization.diplomacy_renderer import DiplomacyRenderer
from visualization.economy_renderer import EconomyRenderer
from visualization.time_renderer import TimeRenderer

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

# Initialize database initializer
db_initializer = DatabaseInitializer(app)

# Flask-Login Configuration
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # The route Flask-Login redirects to if @login_required fails
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
        return redirect(url_for('dashboard'))
    # For unauthenticated users, you might show a landing page
    return render_template('index.html', title="Welcome")  # Create index.html later


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))  # Already logged in

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')  # Optional: add email validation
        password = request.form.get('password')
        password2 = request.form.get('password2')

        if not username or not password or not password2:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))
        if password != password2:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        existing_user_username = User.query.filter_by(username=username).first()
        if existing_user_username:
            flash('Username already exists. Please choose a different one.', 'warning')
            return redirect(url_for('register'))

        # Optional: Check for existing email if you add an email field and want it unique
        # existing_user_email = User.query.filter_by(email=email).first()
        # if existing_user_email:
        #     flash('Email address already registered.', 'warning')
        #     return redirect(url_for('register'))

        new_user = User(username=username,
                        email=email if email else f"{username}@example.com")  # Use a placeholder email if not provided
        new_user.set_password(password)
        db.session.add(new_user)
        try:
            db.session.commit()
            flash('Congratulations, your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e_register:
            db.session.rollback()
            flash(f'Error creating account: {e_register}. Please try again.', 'danger')
            print(f"ERROR during registration commit: {e_register}")

    return render_template('register.html', title='Register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = True if request.form.get('remember_me') else False

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember_me)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')  # For redirecting after login if user tried to access a protected page
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html', title='Login')


@app.route('/logout')
@login_required  # Ensures only logged-in users can access this
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    """User's main dashboard after login."""
    # Query DynastyDB for the user's dynasties
    user_dynasties = DynastyDB.query.filter_by(user_id=current_user.id).order_by(DynastyDB.name).all()
    
    # Initialize game systems
    game_manager = GameManager(db.session)
    
    # Get active players
    active_players = game_manager.get_active_players()
    
    # Get game statistics
    game_stats = {
        'total_dynasties': DynastyDB.query.count(),
        'total_territories': Territory.query.count(),
        'total_battles': Battle.query.count(),
        'total_treaties': Treaty.query.count()
    }
    
    # Get recent global events
    recent_global_events = HistoryLogEntryDB.query.order_by(
        HistoryLogEntryDB.year.desc(), HistoryLogEntryDB.id.desc()
    ).limit(10).all()
    
    return render_template('dashboard.html',
                          title='Dashboard',
                          dynasties=user_dynasties,
                          active_players=active_players,
                          game_stats=game_stats,
                          recent_global_events=recent_global_events)


# Dynasty creation route
@app.route('/dynasty/create', methods=['GET', 'POST'])
@login_required
def create_dynasty():
    """Handles dynasty creation with theme selection or custom story."""
    if request.method == 'POST':
        # Process form data
        dynasty_name = request.form.get('dynasty_name')
        theme_type = request.form.get('theme_type')  # 'predefined' or 'custom'
        
        # Validate dynasty name
        if not dynasty_name or len(dynasty_name) < 2:
            flash('Please provide a valid dynasty name (at least 2 characters).', 'danger')
            return redirect(url_for('create_dynasty'))
        
        # Get theme configuration
        theme_config = None
        theme_key = None
        
        if theme_type == 'predefined':
            theme_key = request.form.get('theme_key')
            theme_config = get_theme(theme_key)
            if not theme_config:
                flash('Selected theme not found. Please try again.', 'danger')
                return redirect(url_for('create_dynasty'))
        else:  # custom
            user_story = request.form.get('user_story')
            if not user_story or len(user_story) < 50:
                flash('Please provide a more detailed story for custom theme generation (at least 50 characters).', 'danger')
                return redirect(url_for('create_dynasty'))
                
            theme_config = generate_theme_from_story_llm(user_story)
            if not theme_config:
                flash('Failed to generate theme from story. Please try again or select a predefined theme.', 'danger')
                return redirect(url_for('create_dynasty'))
        
        # Get simulation settings
        start_year = request.form.get('start_year')
        if start_year and start_year.isdigit():
            start_year = int(start_year)
        else:
            start_year = theme_config.get('start_year_suggestion', 1000)
            
        succession_rule = request.form.get('succession_rule')
        if not succession_rule:
            succession_rule = theme_config.get('succession_rule_default', 'PRIMOGENITURE_MALE_PREFERENCE')
        
        # Create dynasty in database
        new_dynasty = DynastyDB(
            user_id=current_user.id,
            name=dynasty_name,
            theme_identifier_or_json=theme_key if theme_type == 'predefined' else json.dumps(theme_config),
            current_wealth=int(theme_config.get('starting_wealth_modifier', 1.0) * 100),
            start_year=start_year,
            current_simulation_year=start_year
        )
        db.session.add(new_dynasty)
        db.session.commit()
        
        # Initialize founder and spouse
        initialize_dynasty_founder(new_dynasty.id, theme_config, start_year, succession_rule)
        
        flash(f'Dynasty "{dynasty_name}" created successfully!', 'success')
        return redirect(url_for('view_dynasty', dynasty_id=new_dynasty.id))
    
    # GET request - show form
    all_themes = get_all_theme_names()
    return render_template('create_dynasty.html',
                          themes=all_themes,
                          llm_available=FLASK_APP_GOOGLE_API_KEY_PRESENT)


# Dynasty view route
@app.route('/dynasty/<int:dynasty_id>/view')
@login_required
def view_dynasty(dynasty_id):
    """View a dynasty's details and family tree."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Load theme configuration
    theme_config = {}
    theme_description = "Custom Theme"
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            # Predefined theme
            theme_config = get_theme(dynasty.theme_identifier_or_json)
            theme_description = theme_config.get('description', dynasty.theme_identifier_or_json)
        else:
            # Custom theme stored as JSON
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
                theme_description = theme_config.get('description', "Custom Theme")
            except json.JSONDecodeError:
                theme_description = "Invalid Theme Configuration"
    
    # Get current monarch
    current_monarch = None
    current_monarch_age = 0
    monarch_query = PersonDB.query.filter_by(
        dynasty_id=dynasty.id,
        is_monarch=True,
        death_year=None
    ).first()
    
    if monarch_query:
        current_monarch = monarch_query
        current_monarch_age = dynasty.current_simulation_year - current_monarch.birth_year
    
    # Get living nobles
    living_nobles = PersonDB.query.filter_by(
        dynasty_id=dynasty.id,
        is_noble=True,
        death_year=None
    ).order_by(PersonDB.birth_year).all()
    
    # Calculate ages for all living nobles
    person_ages = {}
    for person in living_nobles:
        person_ages[person.id] = dynasty.current_simulation_year - person.birth_year
    
    # Get recent events
    recent_events = HistoryLogEntryDB.query.filter_by(
        dynasty_id=dynasty.id
    ).order_by(HistoryLogEntryDB.year.desc()).limit(10).all()
    
    # Check if family tree visualization exists
    family_tree_image = None
    tree_filename = f"family_tree_{dynasty.name.replace(' ', '_')}_year_{dynasty.current_simulation_year}_living_nobles.png"
    tree_path = os.path.join('static', 'visualizations', tree_filename)
    if os.path.exists(tree_path):
        family_tree_image = url_for('static', filename=f'visualizations/{tree_filename}')
    
    return render_template('view_dynasty.html',
                          dynasty=dynasty,
                          theme_config=theme_config,
                          theme_description=theme_description,
                          current_monarch=current_monarch,
                          current_monarch_age=current_monarch_age,
                          living_nobles=living_nobles,
                          person_ages=person_ages,
                          recent_events=recent_events,
                          family_tree_image=family_tree_image,
                          current_year=dynasty.current_simulation_year)


# Advance turn route
@app.route('/dynasty/<int:dynasty_id>/advance_turn')
@login_required
def advance_turn(dynasty_id):
    """Advance the simulation by one turn (5 years by default)."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Number of years to advance per turn
    years_per_turn = 5
    
    # Process the turn advancement
    success, message = process_dynasty_turn(dynasty.id, years_per_turn)
    
    if success:
        flash(message, 'success')
    else:
        flash(f"Error advancing turn: {message}", 'danger')
    
    # Update last played timestamp
    dynasty.last_played_at = datetime.datetime.utcnow()
    db.session.commit()
    
    return redirect(url_for('view_dynasty', dynasty_id=dynasty.id))


# Dynasty deletion route
@app.route('/dynasty/<int:dynasty_id>/delete', methods=['GET', 'POST'])
@login_required
def delete_dynasty(dynasty_id):
    """Delete a dynasty and all associated data."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    
    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        dynasty_name = dynasty.name  # Store for flash message
        
        try:
            # Fix for circular dependency: manually break relationships before deletion
            # 1. Get all persons in this dynasty
            persons = PersonDB.query.filter_by(dynasty_id=dynasty.id).all()
            
            # 2. Break circular references between persons
            for person in persons:
                # Clear relationship references
                person.spouse_sim_id = None
                person.mother_sim_id = None
                person.father_sim_id = None
            
            # 3. Commit these changes first
            db.session.commit()
            
            # 4. Delete history logs
            HistoryLogEntryDB.query.filter_by(dynasty_id=dynasty.id).delete()
            
            # 5. Delete persons
            PersonDB.query.filter_by(dynasty_id=dynasty.id).delete()
            
            # 6. Finally delete the dynasty
            db.session.delete(dynasty)
            db.session.commit()
            
            flash(f'Dynasty "{dynasty_name}" has been permanently deleted.', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting dynasty: {str(e)}', 'danger')
            return redirect(url_for('view_dynasty', dynasty_id=dynasty_id))
    
    # GET request - show confirmation page
    return render_template('delete_dynasty.html', dynasty=dynasty)


# Dynasty economy view route
@app.route('/dynasty/<int:dynasty_id>/economy')
@login_required
def dynasty_economy(dynasty_id):
    """View a dynasty's economic details."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Load theme configuration
    theme_config = {}
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            # Predefined theme
            theme_config = get_theme(dynasty.theme_identifier_or_json)
        else:
            # Custom theme stored as JSON
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
            except json.JSONDecodeError:
                pass
    
    # Get economy data for this dynasty
    economy_data = None
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        
        # Create economy system
        economy_system = EconomySystem(db.session)
        
        # Get economy data
        economy_data = economy_system.calculate_dynasty_economy(dynasty.id)
        
        # Generate visualizations
        from visualization.economy_renderer import EconomyRenderer
        economy_renderer = EconomyRenderer(db.session)
        
        # Generate resource production visualization
        production_chart = economy_renderer.render_resource_production(dynasty.id)
        production_chart_url = production_chart.replace('static/', '/static/')
        
        # Generate trade network visualization
        trade_chart = economy_renderer.render_trade_network(dynasty.id)
        trade_chart_url = trade_chart.replace('static/', '/static/')
        
        # Generate economic trends visualization
        trends_chart = economy_renderer.render_economic_trends(dynasty.id)
        trends_chart_url = trends_chart.replace('static/', '/static/')
        
    except (ImportError, Exception) as e:
        # Economy system not available or error
        flash(f"Error loading economy system: {str(e)}", "warning")
        economy_data = None
        production_chart_url = None
        trade_chart_url = None
        trends_chart_url = None
    
    return render_template('economy_view.html',
                          dynasty=dynasty,
                          theme_config=theme_config,
                          economy_data=economy_data,
                          production_chart_url=production_chart_url,
                          trade_chart_url=trade_chart_url,
                          trends_chart_url=trends_chart_url)


# World economy view route
@app.route('/world/economy')
@login_required
def world_economy_view():
    """View the world economy and interactions between dynasties."""
    # Get all dynasties
    dynasties = DynastyDB.query.all()
    
    # Get global economy data
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        from visualization.economy_renderer import EconomyRenderer
        
        # Create economy system and renderer
        economy_system = EconomySystem(db.session)
        economy_renderer = EconomyRenderer(db.session)
        
        # Get all trade routes
        trade_routes = db.session.query(TradeRoute).filter_by(is_active=True).all()
        
        # Generate market prices visualization
        market_chart = economy_renderer.render_market_prices()
        market_chart_url = market_chart.replace('static/', '/static/')
        
        # Generate global trade network visualization
        trade_network_chart = economy_renderer.render_trade_network()
        trade_network_url = trade_network_chart.replace('static/', '/static/')
        
        # Get resources
        resources = db.session.query(Resource).all()
        
    except (ImportError, Exception) as e:
        # Economy system not available or error
        flash(f"Error loading economy system: {str(e)}", "warning")
        trade_routes = []
        market_chart_url = None
        trade_network_url = None
        resources = []
    
    # Get recent economic events
    economic_events = db.session.query(HistoryLogEntryDB).filter(
        HistoryLogEntryDB.event_type.like('economic_%')
    ).order_by(HistoryLogEntryDB.year.desc()).limit(10).all()
    
    return render_template('world_economy.html',
                          dynasties=dynasties,
                          trade_routes=trade_routes,
                          market_chart_url=market_chart_url,
                          trade_network_url=trade_network_url,
                          resources=resources,
                          economic_events=economic_events)
# --- Map System Routes ---

# --- Economy System Routes ---

@app.route('/dynasty/<int:dynasty_id>/construct_building', methods=['POST'])
@login_required
def construct_building(dynasty_id):
    """Construct a new building in a territory."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    territory_id = request.form.get('territory_id', type=int)
    building_type_str = request.form.get('building_type')
    
    if not territory_id or not building_type_str:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))
    
    try:
        # Convert string to BuildingType enum
        building_type = BuildingType[building_type_str.upper()]
        
        # Import the economy system
        from models.economy_system import EconomySystem
        
        # Create economy system
        economy_system = EconomySystem(db.session)
        
        # Construct building
        success, message = economy_system.construct_building(territory_id, building_type)
        
        if success:
            flash(message, "success")
        else:
            flash(message, "warning")
            
    except (ValueError, KeyError, ImportError, Exception) as e:
        flash(f"Error constructing building: {str(e)}", "danger")
    
    return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/upgrade_building/<int:building_id>', methods=['POST'])
@login_required
def upgrade_building(dynasty_id, building_id):
    """Upgrade an existing building."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        
        # Create economy system
        economy_system = EconomySystem(db.session)
        
        # Upgrade building
        success, message = economy_system.upgrade_building(building_id)
        
        if success:
            flash(message, "success")
        else:
            flash(message, "warning")
            
    except Exception as e:
        flash(f"Error upgrading building: {str(e)}", "danger")
    
    return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/repair_building/<int:building_id>', methods=['POST'])
@login_required
def repair_building(dynasty_id, building_id):
    """Repair a damaged building."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        
        # Create economy system
        economy_system = EconomySystem(db.session)
        
        # Repair building
        success, message = economy_system.repair_building(building_id)
        
        if success:
            flash(message, "success")
        else:
            flash(message, "warning")
            
    except Exception as e:
        flash(f"Error repairing building: {str(e)}", "danger")
    
    return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/develop_territory/<int:territory_id>', methods=['POST'])
@login_required
def develop_territory_economy(dynasty_id, territory_id):
    """Develop a territory to increase its development level."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        
        # Create economy system
        economy_system = EconomySystem(db.session)
        
        # Develop territory
        success, message = economy_system.develop_territory(territory_id)
        
        if success:
            flash(message, "success")
        else:
            flash(message, "warning")
            
    except Exception as e:
        flash(f"Error developing territory: {str(e)}", "danger")
    
    return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/establish_trade', methods=['POST'])
@login_required
def establish_trade(dynasty_id):
    """Establish a trade route with another dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    resource_type_str = request.form.get('resource_type')
    amount = request.form.get('amount', type=float)
    
    if not target_dynasty_id or not resource_type_str or not amount:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))
    
    try:
        # Convert string to ResourceType enum
        resource_type = ResourceType[resource_type_str.upper()]
        
        # Import the economy system
        from models.economy_system import EconomySystem
        
        # Create economy system
        economy_system = EconomySystem(db.session)
        
        # Establish trade route
        success, message, _ = economy_system.establish_trade_route(
            dynasty_id, target_dynasty_id, resource_type, amount
        )
        
        if success:
            flash(message, "success")
        else:
            flash(message, "warning")
            
    except (ValueError, KeyError, ImportError, Exception) as e:
        flash(f"Error establishing trade route: {str(e)}", "danger")
    
    return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/cancel_trade/<int:trade_route_id>', methods=['POST'])
@login_required
def cancel_trade(dynasty_id, trade_route_id):
    """Cancel an existing trade route."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        
        # Create economy system
        economy_system = EconomySystem(db.session)
        
        # Cancel trade route
        success, message = economy_system.cancel_trade_route(trade_route_id, dynasty_id)
        
        if success:
            flash(message, "success")
        else:
            flash(message, "warning")
            
    except Exception as e:
        flash(f"Error canceling trade route: {str(e)}", "danger")
    
    return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))

@app.route('/territory/<int:territory_id>/economy')
@login_required
def territory_economy(territory_id):
    """View economic details for a specific territory."""
    territory = Territory.query.get_or_404(territory_id)
    
    # Check if user has access to this territory
    if territory.controller_dynasty_id:
        dynasty = DynastyDB.query.get(territory.controller_dynasty_id)
        if dynasty and dynasty.owner_user != current_user:
            flash("Not authorized.", "warning")
            return redirect(url_for('dashboard'))
    
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        from visualization.economy_renderer import EconomyRenderer
        
        # Create economy system and renderer
        economy_system = EconomySystem(db.session)
        economy_renderer = EconomyRenderer(db.session)
        
        # Get production and consumption data
        production = economy_system.calculate_territory_production(territory_id)
        consumption = economy_system.calculate_territory_consumption(territory_id)
        tax_income = economy_system.calculate_territory_tax_income(territory_id)
        
        # Get buildings
        buildings = Building.query.filter_by(territory_id=territory_id).all()
        
        # Generate territory economy visualization
        economy_chart = economy_renderer.render_territory_economy(territory_id)
        economy_chart_url = economy_chart.replace('static/', '/static/')
        
    except (ImportError, Exception) as e:
        # Economy system not available or error
        flash(f"Error loading economy data: {str(e)}", "warning")
        production = {}
        consumption = {}
        tax_income = 0
        buildings = []
        economy_chart_url = None
    
    return render_template('territory_economy.html',
                          territory=territory,
                          production=production,
                          consumption=consumption,
                          tax_income=tax_income,
                          buildings=buildings,
                          economy_chart_url=economy_chart_url)

@app.route('/world/map')
@login_required
def world_map():
    """Display the world map with territories and units."""
    # Get user dynasties
    user_dynasties = DynastyDB.query.filter_by(user_id=current_user.id).all()
    
    # Get all territories
    territories = Territory.query.all()
    
    # Check if we have territories, if not, we need to generate a map
    if not territories:
        # Create a map generator
        map_generator = MapGenerator(db.session)
        
        # Generate a procedural map
        map_data = map_generator.generate_procedural_map()
        
        # Assign some territories to user dynasties
        territory_manager = TerritoryManager(db.session)
        
        # For each user dynasty, assign a random territory as capital
        for dynasty in user_dynasties:
            # Get a random territory
            territory = Territory.query.order_by(db.func.random()).first()
            if territory:
                territory_manager.assign_territory(territory.id, dynasty.id, is_capital=True)
    
    # Create map renderer
    map_renderer = MapRenderer(db.session)
    
    # Render map
    map_image = None
    try:
        # Check if there are territories to render
        if territories:
            # Determine if we should highlight a specific dynasty
            highlight_dynasty = None
            if len(user_dynasties) == 1:
                highlight_dynasty = user_dynasties[0].id
            
            # Render the map
            map_image = map_renderer.render_world_map(
                show_terrain=True,
                show_territories=True,
                show_settlements=True,
                show_units=True,
                highlight_dynasty_id=highlight_dynasty
            )
        else:
            print("No territories found in the database. Map cannot be rendered.")
    except Exception as e:
        print(f"Error rendering map: {e}")
        import traceback
        traceback.print_exc()
    
    # Get regions and provinces for filtering
    regions = Region.query.all()
    provinces = Province.query.all()
    
    return render_template('world_map.html',
                          user_dynasties=user_dynasties,
                          territories=territories,
                          regions=regions,
                          provinces=provinces,
                          map_image=map_image)

@app.route('/territory/<int:territory_id>')
@login_required
def territory_details(territory_id):
    """View details of a specific territory."""
    # Get territory
    territory = Territory.query.get_or_404(territory_id)
    
    # Check if territory is controlled by user's dynasty
    user_dynasties = DynastyDB.query.filter_by(user_id=current_user.id).all()
    user_dynasty_ids = [d.id for d in user_dynasties]
    
    is_owned = territory.controller_dynasty_id in user_dynasty_ids
    
    # Get settlements in this territory
    settlements = territory.settlements
    
    # Get resources in this territory
    resources = territory.resources
    
    # Get buildings in this territory
    buildings = territory.buildings
    
    # Get units in this territory
    units = territory.units_present
    
    # Get armies in this territory
    armies = territory.armies_present
    
    # Create map renderer
    map_renderer = MapRenderer(db.session)
    
    # Render territory map
    territory_image = None
    try:
        territory_image = map_renderer.render_territory_map(territory_id)
    except Exception as e:
        print(f"Error rendering territory map: {e}")
    
    return render_template('territory_details.html',
                          territory=territory,
                          is_owned=is_owned,
                          settlements=settlements,
                          resources=resources,
                          buildings=buildings,
                          units=units,
                          armies=armies,
                          territory_image=territory_image)

@app.route('/dynasty/<int:dynasty_id>/territories')
@login_required
def dynasty_territories(dynasty_id):
    """View and manage territories controlled by a dynasty."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    
    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get territories controlled by this dynasty
    territories = Territory.query.filter_by(controller_dynasty_id=dynasty_id).all()
    
    # Get border territories
    border_system = BorderSystem(db.session)
    border_territories = border_system.get_border_territories(dynasty_id)
    
    # Get contested territories (territories at borders with potential conflicts)
    contested_territories = []
    try:
        # Get territories that are at the border and have neighboring territories controlled by other dynasties
        for territory in border_territories:
            neighbors = border_system.get_neighboring_territories(territory.id)
            for neighbor in neighbors:
                if neighbor.controller_dynasty_id and neighbor.controller_dynasty_id != dynasty_id:
                    contested_territories.append(territory)
                    break
    except Exception as e:
        print(f"Error determining contested territories: {e}")
    
    # Create map renderer
    map_renderer = MapRenderer(db.session)
    
    # Render map highlighting dynasty territories
    dynasty_map = None
    try:
        dynasty_map = map_renderer.render_world_map(
            show_terrain=False,  # Show dynasty colors instead
            show_territories=True,
            show_settlements=True,
            show_units=True,
            highlight_dynasty_id=dynasty_id
        )
    except Exception as e:
        print(f"Error rendering dynasty map: {e}")
    
    return render_template('dynasty_territories.html',
                          dynasty=dynasty,
                          territories=territories,
                          border_territories=border_territories,
                          contested_territories=contested_territories,
                          dynasty_map=dynasty_map)

# Military routes
@app.route('/dynasty/<int:dynasty_id>/military')
@login_required
def military_view(dynasty_id):
    """View and manage military units and armies for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get military units and armies
    units = MilitaryUnit.query.filter_by(dynasty_id=dynasty_id, army_id=None).all()
    armies = Army.query.filter_by(dynasty_id=dynasty_id).all()
    
    # Get potential commanders
    commanders = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        death_year=None
    ).all()
    
    # Filter to those who can lead armies
    potential_commanders = [p for p in commanders if p.can_lead_army()]
    
    # Get controlled territories for recruitment
    territories = Territory.query.filter_by(controller_dynasty_id=dynasty_id).all()
    
    # Get military overview visualization
    from visualization.military_renderer import MilitaryRenderer
    military_renderer = MilitaryRenderer(db.session)
    military_overview = military_renderer.render_military_overview(dynasty_id)
    
    return render_template('military_view.html',
                          dynasty=dynasty,
                          units=units,
                          armies=armies,
                          potential_commanders=potential_commanders,
                          territories=territories,
                          military_overview=military_overview)

@app.route('/dynasty/<int:dynasty_id>/recruit_unit', methods=['POST'])
@login_required
def recruit_unit(dynasty_id):
    """Recruit a new military unit."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    unit_type_str = request.form.get('unit_type')
    size = request.form.get('size', type=int)
    territory_id = request.form.get('territory_id', type=int)
    name = request.form.get('name')
    
    # Validate data
    if not unit_type_str or not size or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military_view', dynasty_id=dynasty_id))
    
    try:
        unit_type = UnitType(unit_type_str)
    except ValueError:
        flash("Invalid unit type.", "danger")
        return redirect(url_for('military_view', dynasty_id=dynasty_id))
    
    # Recruit unit
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, unit = military_system.recruit_unit(
        dynasty_id=dynasty_id,
        unit_type=unit_type,
        size=size,
        territory_id=territory_id,
        name=name
    )
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('military_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/form_army', methods=['POST'])
@login_required
def form_army(dynasty_id):
    """Form a new army from individual units."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    unit_ids = request.form.getlist('unit_ids', type=int)
    name = request.form.get('name')
    commander_id = request.form.get('commander_id', type=int)
    
    # Validate data
    if not unit_ids or not name:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military_view', dynasty_id=dynasty_id))
    
    # Form army
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, army = military_system.form_army(
        dynasty_id=dynasty_id,
        unit_ids=unit_ids,
        name=name,
        commander_id=commander_id
    )
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('military_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/assign_commander', methods=['POST'])
@login_required
def assign_commander(dynasty_id):
    """Assign a commander to an army."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    army_id = request.form.get('army_id', type=int)
    commander_id = request.form.get('commander_id', type=int)
    
    # Validate data
    if not army_id or not commander_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military_view', dynasty_id=dynasty_id))
    
    # Assign commander
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message = military_system.assign_commander(
        army_id=army_id,
        commander_id=commander_id
    )
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('military_view', dynasty_id=dynasty_id))

@app.route('/army/<int:army_id>')
@login_required
def army_details(army_id):
    """View details of an army."""
    army = Army.query.get_or_404(army_id)
    dynasty = DynastyDB.query.get_or_404(army.dynasty_id)
    
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get army composition visualization
    from visualization.military_renderer import MilitaryRenderer
    military_renderer = MilitaryRenderer(db.session)
    army_composition = military_renderer.render_army_composition(army_id)
    
    # Get potential commanders
    commanders = PersonDB.query.filter_by(
        dynasty_id=dynasty.id,
        death_year=None
    ).all()
    
    # Filter to those who can lead armies
    potential_commanders = [p for p in commanders if p.can_lead_army()]
    
    return render_template('army_details.html',
                          army=army,
                          dynasty=dynasty,
                          army_composition=army_composition,
                          potential_commanders=potential_commanders)

@app.route('/battle/<int:battle_id>')
@login_required
def battle_details(battle_id):
    """View details of a battle."""
    battle = Battle.query.get_or_404(battle_id)
    
    # Check if user has access to this battle
    attacker_dynasty = DynastyDB.query.get(battle.attacker_dynasty_id)
    defender_dynasty = DynastyDB.query.get(battle.defender_dynasty_id)
    
    if (attacker_dynasty and attacker_dynasty.owner_user == current_user) or \
       (defender_dynasty and defender_dynasty.owner_user == current_user):
        # Get battle visualization
        from visualization.military_renderer import MilitaryRenderer
        military_renderer = MilitaryRenderer(db.session)
        battle_result = military_renderer.render_battle_result(battle_id)
        
        return render_template('battle_details.html',
                              battle=battle,
                              attacker_dynasty=attacker_dynasty,
                              defender_dynasty=defender_dynasty,
                              battle_result=battle_result)
    else:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))

@app.route('/siege/<int:siege_id>')
@login_required
def siege_details(siege_id):
    """View details of a siege."""
    siege = Siege.query.get_or_404(siege_id)
    
    # Check if user has access to this siege
    attacker_dynasty = DynastyDB.query.get(siege.attacker_dynasty_id)
    defender_dynasty = DynastyDB.query.get(siege.defender_dynasty_id)
    
    if (attacker_dynasty and attacker_dynasty.owner_user == current_user) or \
       (defender_dynasty and defender_dynasty.owner_user == current_user):
        # Get siege visualization
        from visualization.military_renderer import MilitaryRenderer
        military_renderer = MilitaryRenderer(db.session)
        siege_progress = military_renderer.render_siege_progress(siege_id)
        
        return render_template('siege_details.html',
                              siege=siege,
                              attacker_dynasty=attacker_dynasty,
                              defender_dynasty=defender_dynasty,
                              siege_progress=siege_progress)
    else:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))

@app.route('/dynasty/<int:dynasty_id>/initiate_battle', methods=['POST'])
@login_required
def initiate_battle(dynasty_id):
    """Initiate a battle between two armies."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    attacker_army_id = request.form.get('attacker_army_id', type=int)
    defender_army_id = request.form.get('defender_army_id', type=int)
    territory_id = request.form.get('territory_id', type=int)
    war_id = request.form.get('war_id', type=int)
    
    # Validate data
    if not attacker_army_id or not defender_army_id or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military_view', dynasty_id=dynasty_id))
    
    # Initiate battle
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, battle = military_system.initiate_battle(
        attacker_army_id=attacker_army_id,
        defender_army_id=defender_army_id,
        territory_id=territory_id,
        war_id=war_id
    )
    
    if success:
        flash(message, "success")
        if battle:
            return redirect(url_for('battle_details', battle_id=battle.id))
    else:
        flash(message, "danger")
    
    return redirect(url_for('military_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/initiate_siege', methods=['POST'])
@login_required
def initiate_siege(dynasty_id):
    """Initiate a siege of a territory."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    army_id = request.form.get('army_id', type=int)
    territory_id = request.form.get('territory_id', type=int)
    war_id = request.form.get('war_id', type=int)
    
    # Validate data
    if not army_id or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military_view', dynasty_id=dynasty_id))
    
    # Initiate siege
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, siege = military_system.initiate_siege(
        army_id=army_id,
        territory_id=territory_id,
        war_id=war_id
    )
    
    if success:
        flash(message, "success")
        if siege:
            return redirect(url_for('siege_details', siege_id=siege.id))
    else:
        flash(message, "danger")
    
    return redirect(url_for('military_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/update_siege/<int:siege_id>')
@login_required
def update_siege(dynasty_id, siege_id):
    """Update the progress of a siege."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Update siege
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, siege = military_system.update_siege(siege_id=siege_id)
    
    if success:
        flash(message, "success")
        if siege:
            return redirect(url_for('siege_details', siege_id=siege.id))
    else:
        flash("Siege update failed: " + message, "danger")
        return redirect(url_for('military_view', dynasty_id=dynasty_id))

# Diplomacy routes
@app.route('/dynasty/<int:dynasty_id>/diplomacy')
@login_required
def diplomacy_view(dynasty_id):
    """View and manage diplomatic relations for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get all other dynasties
    other_dynasties = DynastyDB.query.filter(DynastyDB.id != dynasty_id).all()
    
    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)
    
    # Get diplomatic relations
    relations = []
    for other_dynasty in other_dynasties:
        status, score = diplomacy_system.get_relation_status(dynasty_id, other_dynasty.id)
        relations.append({
            'dynasty': other_dynasty,
            'status': status,
            'score': score
        })
    
    # Get active treaties
    active_treaties = []
    for other_dynasty in other_dynasties:
        relation = diplomacy_system.get_diplomatic_relation(dynasty_id, other_dynasty.id, create_if_not_exists=False)
        if relation:
            treaties = Treaty.query.filter_by(diplomatic_relation_id=relation.id, active=True).all()
            for treaty in treaties:
                active_treaties.append({
                    'treaty': treaty,
                    'other_dynasty': other_dynasty,
                    'treaty_type': treaty.treaty_type.value.replace('_', ' ').title(),
                    'start_year': treaty.start_year,
                    'duration': treaty.duration
                })
    
    # Get active wars
    active_wars = []
    wars_as_attacker = War.query.filter_by(attacker_dynasty_id=dynasty_id, is_active=True).all()
    wars_as_defender = War.query.filter_by(defender_dynasty_id=dynasty_id, is_active=True).all()
    
    for war in wars_as_attacker:
        defender = DynastyDB.query.get(war.defender_dynasty_id)
        if defender:
            active_wars.append({
                'war': war,
                'other_dynasty': defender,
                'is_attacker': True,
                'war_goal': war.war_goal.value.replace('_', ' ').title(),
                'start_year': war.start_year,
                'war_score': war.attacker_war_score
            })
    
    for war in wars_as_defender:
        attacker = DynastyDB.query.get(war.attacker_dynasty_id)
        if attacker:
            active_wars.append({
                'war': war,
                'other_dynasty': attacker,
                'is_attacker': False,
                'war_goal': war.war_goal.value.replace('_', ' ').title(),
                'start_year': war.start_year,
                'war_score': war.defender_war_score
            })
    
    # Generate diplomatic relations visualization
    diplomacy_renderer = DiplomacyRenderer(db.session)
    relations_image = diplomacy_renderer.render_diplomatic_relations(dynasty_id=dynasty_id)
    treaty_image = diplomacy_renderer.render_treaty_network()
    history_image = diplomacy_renderer.render_diplomatic_history(dynasty_id=dynasty_id)
    
    # Get reputation metrics
    reputation = {
        'prestige': dynasty.prestige,
        'honor': dynasty.honor,
        'infamy': dynasty.infamy
    }
    
    return render_template('diplomacy_view.html',
                          dynasty=dynasty,
                          relations=relations,
                          active_treaties=active_treaties,
                          active_wars=active_wars,
                          reputation=reputation,
                          relations_image=relations_image,
                          treaty_image=treaty_image,
                          history_image=history_image)

@app.route('/dynasty/<int:dynasty_id>/treaties')
@login_required
def treaty_view(dynasty_id):
    """View and manage treaties for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get all treaties
    treaties = []
    relations = DiplomaticRelation.query.filter((DiplomaticRelation.dynasty1_id == dynasty_id) | 
                                              (DiplomaticRelation.dynasty2_id == dynasty_id)).all()
    
    for relation in relations:
        other_dynasty_id = relation.dynasty2_id if relation.dynasty1_id == dynasty_id else relation.dynasty1_id
        other_dynasty = DynastyDB.query.get(other_dynasty_id)
        
        if other_dynasty:
            relation_treaties = Treaty.query.filter_by(diplomatic_relation_id=relation.id).all()
            
            for treaty in relation_treaties:
                treaties.append({
                    'treaty': treaty,
                    'other_dynasty': other_dynasty,
                    'treaty_type': treaty.treaty_type.value.replace('_', ' ').title(),
                    'start_year': treaty.start_year,
                    'duration': treaty.duration,
                    'active': treaty.active,
                    'terms': treaty.get_terms() if hasattr(treaty, 'get_terms') else {}
                })
    
    # Generate treaty network visualization
    diplomacy_renderer = DiplomacyRenderer(db.session)
    treaty_image = diplomacy_renderer.render_treaty_network()
    
    return render_template('treaty_view.html',
                          dynasty=dynasty,
                          treaties=treaties,
                          treaty_image=treaty_image)

@app.route('/dynasty/<int:dynasty_id>/diplomatic_action', methods=['POST'])
@login_required
def perform_diplomatic_action(dynasty_id):
    """Perform a diplomatic action."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    action_type = request.form.get('action_type')
    
    if not target_dynasty_id or not action_type:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))
    
    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)
    
    # Perform action
    success, message = diplomacy_system.perform_diplomatic_action(
        dynasty_id, target_dynasty_id, action_type
    )
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/create_treaty', methods=['POST'])
@login_required
def create_treaty(dynasty_id):
    """Create a treaty between dynasties."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    treaty_type = request.form.get('treaty_type')
    duration = request.form.get('duration', type=int)
    
    if not target_dynasty_id or not treaty_type:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))
    
    # Convert treaty_type string to enum
    try:
        treaty_type_enum = TreatyType[treaty_type]
    except (KeyError, ValueError):
        flash("Invalid treaty type.", "danger")
        return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))
    
    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)
    
    # Create treaty
    success, message, _ = diplomacy_system.create_treaty(
        dynasty_id, target_dynasty_id, treaty_type_enum, duration
    )
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/break_treaty/<int:treaty_id>', methods=['POST'])
@login_required
def break_treaty(dynasty_id, treaty_id):
    """Break a treaty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)
    
    # Break treaty
    success, message = diplomacy_system.break_treaty(treaty_id, dynasty_id)
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/declare_war', methods=['POST'])
@login_required
def declare_war(dynasty_id):
    """Declare war on another dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    war_goal = request.form.get('war_goal')
    target_territory_id = request.form.get('target_territory_id', type=int)
    
    if not target_dynasty_id or not war_goal:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))
    
    # Convert war_goal string to enum
    try:
        war_goal_enum = WarGoal[war_goal]
    except (KeyError, ValueError):
        flash("Invalid war goal.", "danger")
        return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))
    
    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)
    
    # Declare war
    success, message, _ = diplomacy_system.declare_war(
        dynasty_id, target_dynasty_id, war_goal_enum, target_territory_id
    )
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/negotiate_peace/<int:war_id>', methods=['POST'])
@login_required
def negotiate_peace(dynasty_id, war_id):
    """Negotiate peace to end a war."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get war
    war = War.query.get_or_404(war_id)
    
    # Check if dynasty is involved in the war
    if war.attacker_dynasty_id != dynasty_id and war.defender_dynasty_id != dynasty_id:
        flash("Not authorized.", "warning")
        return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))
    
    # Determine if dynasty is attacker or defender
    is_attacker = (war.attacker_dynasty_id == dynasty_id)
    
    # Get form data
    terms = {}
    
    # Territory transfer
    territory_id = request.form.get('territory_id', type=int)
    if territory_id:
        terms['territory_transfer'] = territory_id
    
    # Gold payment
    gold_payment = request.form.get('gold_payment', type=int)
    if gold_payment:
        terms['gold_payment'] = gold_payment
    
    # Vassalization
    vassalize = request.form.get('vassalize') == 'on'
    if vassalize:
        terms['vassalize'] = True
    
    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)
    
    # Negotiate peace
    success, message = diplomacy_system.negotiate_peace(
        war_id, is_attacker, terms
    )
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('diplomacy_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/move_unit', methods=['POST'])
@login_required
def move_unit(dynasty_id):
    """Move a military unit to a target territory."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    
    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    unit_id = request.form.get('unit_id', type=int)
    target_territory_id = request.form.get('target_territory_id', type=int)
    
    if not unit_id or not target_territory_id:
        flash("Missing unit ID or target territory ID.", "danger")
        return redirect(url_for('dynasty_territories', dynasty_id=dynasty_id))
    
    # Create movement system
    movement_system = MovementSystem(db.session)
    
    # Move unit
    success, message = movement_system.move_unit(unit_id, target_territory_id)
    
    if success:
        flash(message, "success")
    else:
        flash(f"Failed to move unit: {message}", "danger")
    
    # Redirect back to territories page
    return redirect(url_for('dynasty_territories', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/move_army', methods=['POST'])
@login_required
def move_army(dynasty_id):
    """Move an army to a target territory."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    
    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    army_id = request.form.get('army_id', type=int)
    target_territory_id = request.form.get('target_territory_id', type=int)
    
    if not army_id or not target_territory_id:
        flash("Missing army ID or target territory ID.", "danger")
        return redirect(url_for('dynasty_territories', dynasty_id=dynasty_id))
    
    # Create movement system
    movement_system = MovementSystem(db.session)
    
    # Move army
    success, message = movement_system.move_army(army_id, target_territory_id)
    
    if success:
        flash(message, "success")
    else:
        flash(f"Failed to move army: {message}", "danger")
    
    # Redirect back to territories page
# Time system routes
@app.route('/dynasty/<int:dynasty_id>/time')
@login_required
def time_view(dynasty_id):
    """View time management interface for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get current year and season
    current_year = dynasty.current_simulation_year
    
    try:
        # Import the time system
        from models.time_system import TimeSystem, Season
        from visualization.time_renderer import TimeRenderer
        
        # Create time system and renderer
        time_system = TimeSystem(db.session)
        time_renderer = TimeRenderer(db.session)
        
        # Get current season
        current_season = time_system.get_current_season(current_year)
        
        # Get historical timeline
        timeline_events = time_system.get_historical_timeline(dynasty_id, 
                                                            start_year=current_year-10 if current_year > dynasty.start_year+10 else dynasty.start_year,
                                                            end_year=current_year)
        
        # Get scheduled events
        scheduled_events = time_system.get_scheduled_timeline(dynasty_id)
        
        # Generate timeline visualization
        timeline_image = time_renderer.render_timeline(dynasty_id, 
                                                     start_year=current_year-10 if current_year > dynasty.start_year+10 else dynasty.start_year,
                                                     end_year=current_year)
        if timeline_image:
            timeline_image_url = timeline_image.replace('static/', '/static/')
        else:
            timeline_image_url = None
        
        # Generate scheduled events visualization if there are any
        if scheduled_events:
            scheduled_events_image = time_renderer.render_scheduled_events(dynasty_id)
            if scheduled_events_image:
                scheduled_events_image_url = scheduled_events_image.replace('static/', '/static/')
            else:
                scheduled_events_image_url = None
        else:
            scheduled_events_image_url = None
        
        # Generate seasonal map
        seasonal_map_image = time_renderer.render_seasonal_map(current_year)
        if seasonal_map_image:
            seasonal_map_image_url = seasonal_map_image.replace('static/', '/static/')
        else:
            seasonal_map_image_url = None
        
        # Calculate action points
        action_points = time_system.calculate_action_points(dynasty_id)
        
        # Get population growth rates
        population_growth_rates = time_system.get_population_growth_rates()
        
    except Exception as e:
        flash(f"Error loading time system: {str(e)}", "danger")
        return render_template('time_view.html', 
                              dynasty=dynasty,
                              current_year=current_year,
                              current_season=None,
                              timeline_events=[],
                              scheduled_events=[],
                              timeline_image_url=None,
                              scheduled_events_image_url=None,
                              seasonal_map_image_url=None,
                              action_points=0,
                              population_growth_rates={})
    
    return render_template('time_view.html', 
                          dynasty=dynasty,
                          current_year=current_year,
                          current_season=current_season,
                          timeline_events=timeline_events,
                          scheduled_events=scheduled_events,
                          timeline_image_url=timeline_image_url,
                          scheduled_events_image_url=scheduled_events_image_url,
                          seasonal_map_image_url=seasonal_map_image_url,
                          action_points=action_points,
                          population_growth_rates=population_growth_rates)

@app.route('/dynasty/<int:dynasty_id>/advance_time', methods=['POST'])
@login_required
def advance_time(dynasty_id):
    """Advance time for a dynasty by processing a turn."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        # Import the time system
        from models.time_system import TimeSystem
        
        # Create time system
        time_system = TimeSystem(db.session)
        
        # Process turn
        success, message = time_system.process_turn(dynasty_id)
        
        if success:
            flash(message, "success")
        else:
            flash(f"Error advancing time: {message}", "danger")
        
    except Exception as e:
        flash(f"Error advancing time: {str(e)}", "danger")
    
    return redirect(url_for('time_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/schedule_event', methods=['POST'])
@login_required
def schedule_event(dynasty_id):
    """Schedule a new event for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        # Import the time system
        from models.time_system import TimeSystem, EventType, EventPriority
        
        # Get form data
        event_type_str = request.form.get('event_type')
        year = request.form.get('year')
        priority_str = request.form.get('priority', 'MEDIUM')
        action = request.form.get('action')
        target_dynasty_id = request.form.get('target_dynasty_id')
        territory_id = request.form.get('territory_id')
        
        # Validate data
        if not event_type_str or not year or not action:
            flash("Missing required fields for scheduling an event.", "danger")
            return redirect(url_for('time_view', dynasty_id=dynasty_id))
        
        # Convert year to int
        try:
            year = int(year)
        except ValueError:
            flash("Year must be a number.", "danger")
            return redirect(url_for('time_view', dynasty_id=dynasty_id))
        
        # Check if year is in the future
        if year <= dynasty.current_simulation_year:
            flash("Events can only be scheduled for future years.", "danger")
            return redirect(url_for('time_view', dynasty_id=dynasty_id))
        
        # Create event data
        event_data = {
            "action": action,
            "actor_dynasty_id": dynasty_id
        }
        
        if target_dynasty_id:
            event_data["target_dynasty_id"] = int(target_dynasty_id)
        
        if territory_id:
            event_data["territory_id"] = int(territory_id)
        
        # Create time system
        time_system = TimeSystem(db.session)
        
        # Schedule event
        event_id = time_system.schedule_event(
            event_type=EventType[event_type_str],
            year=year,
            data=event_data,
            priority=EventPriority[priority_str]
        )
        
        flash(f"Event scheduled successfully for year {year}.", "success")
        
    except Exception as e:
        flash(f"Error scheduling event: {str(e)}", "danger")
    
    return redirect(url_for('time_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/cancel_event/<int:event_id>', methods=['POST'])
@login_required
def cancel_event(dynasty_id, event_id):
    """Cancel a scheduled event."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    try:
        # Import the time system
        from models.time_system import TimeSystem
        
        # Create time system
        time_system = TimeSystem(db.session)
        
        # Cancel event
        success = time_system.cancel_event(event_id)
        
        if success:
            flash("Event cancelled successfully.", "success")
        else:
            flash("Event not found or already processed.", "warning")
        
    except Exception as e:
        flash(f"Error cancelling event: {str(e)}", "danger")
    
    return redirect(url_for('time_view', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/timeline')
@login_required
def timeline_view(dynasty_id):
    """View the historical timeline for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get start and end years from query parameters
    start_year = request.args.get('start_year')
    end_year = request.args.get('end_year')
    
    if start_year:
        try:
            start_year = int(start_year)
        except ValueError:
            start_year = dynasty.start_year
    else:
        start_year = dynasty.start_year
    
    if end_year:
        try:
            end_year = int(end_year)
        except ValueError:
            end_year = dynasty.current_simulation_year
    else:
        end_year = dynasty.current_simulation_year
    
    try:
        # Import the time system
        from models.time_system import TimeSystem
        from visualization.time_renderer import TimeRenderer
        
        # Create time system and renderer
        time_system = TimeSystem(db.session)
        time_renderer = TimeRenderer(db.session)
        
        # Get historical timeline
        timeline_events = time_system.get_historical_timeline(dynasty_id, start_year, end_year)
        
        # Generate timeline visualization
        timeline_image = time_renderer.render_timeline(dynasty_id, start_year, end_year)
        if timeline_image:
            timeline_image_url = timeline_image.replace('static/', '/static/')
        else:
            timeline_image_url = None
        
    except Exception as e:
        flash(f"Error loading timeline: {str(e)}", "danger")
        return render_template('timeline_view.html', 
                              dynasty=dynasty,
                              start_year=start_year,
                              end_year=end_year,
                              timeline_events=[],
                              timeline_image_url=None)
    
    return render_template('timeline_view.html', 
                          dynasty=dynasty,
                          start_year=start_year,
                          end_year=end_year,
                          timeline_events=timeline_events,
                          timeline_image_url=timeline_image_url)

@app.route('/world/seasons/<int:year>')
@login_required
def seasonal_map(year):
    """View the seasonal map for a specific year."""
    try:
        # Import the time system
        from models.time_system import TimeSystem
        from visualization.time_renderer import TimeRenderer
        
        # Create time system and renderer
        time_system = TimeSystem(db.session)
        time_renderer = TimeRenderer(db.session)
        
        # Get current season
        current_season = time_system.get_current_season(year)
        
        # Generate seasonal map
        seasonal_map_image = time_renderer.render_seasonal_map(year)
        if seasonal_map_image:
            seasonal_map_image_url = seasonal_map_image.replace('static/', '/static/')
        else:
            seasonal_map_image_url = None
        
    except Exception as e:
        flash(f"Error generating seasonal map: {str(e)}", "danger")
        return render_template('seasonal_map.html', 
                              year=year,
                              current_season=None,
                              seasonal_map_image_url=None)
    
    return render_template('seasonal_map.html', 
                          year=year,
                          current_season=current_season,
                          seasonal_map_image_url=seasonal_map_image_url)

@app.route('/world/synchronize_turns', methods=['POST'])
@login_required
def synchronize_turns():
    """Synchronize turns for multiple dynasties."""
    # Get dynasty IDs from form
    dynasty_ids = request.form.getlist('dynasty_ids')
    
    if not dynasty_ids:
        flash("No dynasties selected for synchronization.", "warning")
        return redirect(url_for('dashboard'))
    
    # Convert to integers
    try:
        dynasty_ids = [int(did) for did in dynasty_ids]
    except ValueError:
        flash("Invalid dynasty IDs.", "danger")
        return redirect(url_for('dashboard'))
    
    # Check if user owns all dynasties
    for dynasty_id in dynasty_ids:
        dynasty = DynastyDB.query.get(dynasty_id)
        if not dynasty or dynasty.owner_user != current_user:
            flash("You can only synchronize dynasties that you own.", "warning")
            return redirect(url_for('dashboard'))
    
    try:
        # Import the time system
        from models.time_system import TimeSystem
        
        # Create time system
        time_system = TimeSystem(db.session)
        
        # Synchronize turns
        success, message = time_system.synchronize_turns(dynasty_ids)
        
        if success:
            flash(message, "success")
        else:
            flash(f"Error synchronizing turns: {message}", "danger")
        
    except Exception as e:
        flash(f"Error synchronizing turns: {str(e)}", "danger")
    
    return redirect(url_for('dashboard'))
    return redirect(url_for('dynasty_territories', dynasty_id=dynasty_id))

@app.route('/dynasty/<int:dynasty_id>/develop_territory', methods=['POST'])
@login_required
def develop_territory(dynasty_id):
    """Develop a territory by increasing its development level or adding buildings."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    
    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    territory_id = request.form.get('territory_id', type=int)
    development_type = request.form.get('development_type')
    
    if not territory_id or not development_type:
        flash("Missing territory ID or development type.", "danger")
        return redirect(url_for('dynasty_territories', dynasty_id=dynasty_id))
    
    # Check if territory is controlled by this dynasty
    territory = Territory.query.get_or_404(territory_id)
    if territory.controller_dynasty_id != dynasty_id:
        flash("You don't control this territory.", "danger")
        return redirect(url_for('dynasty_territories', dynasty_id=dynasty_id))
    
    # Create territory manager
    territory_manager = TerritoryManager(db.session)
    
    try:
        # Develop territory
        territory_manager.develop_territory(territory_id, development_type)
        flash(f"Territory {territory.name} developed successfully.", "success")
    except Exception as e:
        flash(f"Failed to develop territory: {e}", "danger")
    
    # Redirect back to territory details page
    return redirect(url_for('territory_details', territory_id=territory_id))

@app.route('/generate_map', methods=['POST'])
@login_required
def generate_map():
    """Generate a new map."""
    # Only allow admins to generate maps
    if current_user.username != 'admin':
        flash("Only administrators can generate maps.", "danger")
        return redirect(url_for('dashboard'))
    
    # Get form data
    template_name = request.form.get('template_name', 'default')
    
    # Create map generator
    map_generator = MapGenerator(db.session)
    
    try:
        # Generate map
        if template_name != 'default':
            map_data = map_generator.generate_predefined_map(template_name)
        else:
            map_data = map_generator.generate_procedural_map()
        
        flash(f"Map generated successfully with {len(map_data['territories'])} territories.", "success")
    except Exception as e:
        flash(f"Failed to generate map: {e}", "danger")
    
    # Redirect to world map
    return redirect(url_for('world_map'))


# Add holding route
@app.route('/dynasty/<int:dynasty_id>/add_holding', methods=['POST'])
@login_required
def add_holding(dynasty_id):
    """Add a new holding to a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('dashboard'))
    
    # Get form data
    name = request.form.get('name')
    holding_type = request.form.get('holding_type')
    size = float(request.form.get('size', 1.0))
    
    # Validate
    if not name or not holding_type:
        flash("Name and holding type are required.", "danger")
        return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))
    
    # Cost based on size and type
    base_costs = {
        "farm": 50,
        "mine": 100,
        "forest": 40,
        "coastal": 80,
        "urban": 150
    }
    
    cost = base_costs.get(holding_type, 50) * size
    
    # Check if dynasty can afford it
    if dynasty.current_wealth < cost:
        flash(f"Not enough wealth to purchase this holding. Cost: {cost}, Available: {dynasty.current_wealth}", "danger")
        return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))
    
    try:
        # Import the economy module
        from models.economy import EconomyManager
        
        # Load theme configuration
        theme_config = {}
        if dynasty.theme_identifier_or_json:
            if dynasty.theme_identifier_or_json in get_all_theme_names():
                theme_config = get_theme(dynasty.theme_identifier_or_json)
            else:
                try:
                    theme_config = json.loads(dynasty.theme_identifier_or_json)
                except json.JSONDecodeError:
                    pass
        
        # Create or get economy manager
        economy = EconomyManager(dynasty_id=dynasty.id, theme_config=theme_config)
        
        # Add the holding
        economy.add_holding(name, holding_type, size)
        
        # Deduct cost
        dynasty.current_wealth -= cost
        db.session.commit()
        
        flash(f"Added new {holding_type} holding: {name}", "success")
    except ImportError:
        flash("Economy system not available.", "danger")
    except Exception as e:
        flash(f"Error adding holding: {str(e)}", "danger")
    
    return redirect(url_for('dynasty_economy', dynasty_id=dynasty_id))


# Placeholder routes for multi-agent game functionality
@app.route('/propose_trade', methods=['POST'])
@login_required
def propose_trade():
    """Propose a trade agreement with another dynasty."""
    flash("Trade proposal functionality will be implemented in a future update.", "info")
    return redirect(url_for('world_economy_view'))


@app.route('/form_alliance', methods=['POST'])
@login_required
def form_alliance():
    """Form an alliance with another dynasty."""
    flash("Alliance formation functionality will be implemented in a future update.", "info")
    return redirect(url_for('world_economy_view'))


# Placeholder routes for backward compatibility
@app.route('/dynasty/create_placeholder')
@login_required
def create_dynasty_placeholder():
    return redirect(url_for('create_dynasty'))


@app.route('/dynasty/<int:dynasty_id>/view_placeholder')
@login_required
def view_dynasty_placeholder(dynasty_id):
    return redirect(url_for('view_dynasty', dynasty_id=dynasty_id))


# --- Helper Functions for Dynasty Management ---

def initialize_dynasty_founder(dynasty_id: int, theme_config: dict, start_year: int, succession_rule: str):
    """Initialize the founder and spouse for a newly created dynasty."""
    dynasty = DynastyDB.query.get(dynasty_id)
    if not dynasty:
        return False, "Dynasty not found"
    
    # Create a history log for the dynasty
    history_log = HistoryLogEntryDB(
        dynasty_id=dynasty_id,
        year=None,
        event_string=f"The saga of House {dynasty.name} begins in the year {start_year}.",
        event_type="foundation"
    )
    db.session.add(history_log)
    
    # Determine founder gender randomly
    founder_gender = random.choice(["MALE", "FEMALE"])
    
    # Generate founder name
    name_key = "names_male" if founder_gender == "MALE" else "names_female"
    founder_name = random.choice(theme_config.get(name_key, ["Founder"]))
    
    # Create founder
    founder = PersonDB(
        dynasty_id=dynasty_id,
        name=founder_name,
        surname=dynasty.name,
        gender=founder_gender,
        birth_year=start_year - random.randint(25, 40),  # Founder is an adult
        is_noble=True,
        is_monarch=True,
        reign_start_year=start_year
    )
    
    # Set founder traits
    founder_traits = []
    available_traits = theme_config.get("common_traits", ["Noble"])
    if available_traits:
        num_traits = min(2, len(available_traits))
        founder_traits = random.sample(available_traits, num_traits)
    founder.set_traits(founder_traits)
    
    # Set founder titles
    founder_title_key = "founder_title_male" if founder_gender == "MALE" else "founder_title_female"
    founder_title = theme_config.get(founder_title_key, "Leader")
    founder.set_titles([founder_title])
    
    db.session.add(founder)
    db.session.flush()  # Get ID without committing
    
    # Set founder as the dynasty founder
    dynasty.founder_person_db_id = founder.id
    
    # Create spouse (80% chance)
    if random.random() < 0.8:
        spouse_gender = "FEMALE" if founder_gender == "MALE" else "MALE"
        name_key = "names_male" if spouse_gender == "MALE" else "names_female"
        spouse_name = random.choice(theme_config.get(name_key, ["Spouse"]))
        
        # Choose a different surname for spouse
        available_surnames = theme_config.get("surnames_dynastic", ["OtherHouse"])
        spouse_surname = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "OtherHouse"
        
        spouse = PersonDB(
            dynasty_id=dynasty_id,
            name=spouse_name,
            surname=spouse_surname,
            gender=spouse_gender,
            birth_year=start_year - random.randint(18, 35),  # Spouse is an adult
            is_noble=True
        )
        
        # Set spouse traits
        spouse_traits = []
        if available_traits:
            num_traits = min(2, len(available_traits))
            spouse_traits = random.sample(available_traits, num_traits)
        spouse.set_traits(spouse_traits)
        
        # Set spouse titles
        default_title_key = "default_noble_male" if spouse_gender == "MALE" else "default_noble_female"
        spouse_title = theme_config.get(default_title_key, "Noble")
        spouse.set_titles([spouse_title])
        
        db.session.add(spouse)
        db.session.flush()  # Get ID without committing
        
        # Link spouse and founder
        founder.spouse_sim_id = spouse.id
        spouse.spouse_sim_id = founder.id
        
        # Log marriage
        marriage_log = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=start_year,
            event_string=f"{founder.name} {founder.surname} and {spouse.name} {spouse.surname} were united in marriage.",
            person1_sim_id=founder.id,
            person2_sim_id=spouse.id,
            event_type="marriage"
        )
        db.session.add(marriage_log)
    
    # Log founder's rise to power
    founder_log = HistoryLogEntryDB(
        dynasty_id=dynasty_id,
        year=start_year,
        event_string=f"{founder.name} {founder.surname} became the first {founder_title} of House {dynasty.name}.",
        person1_sim_id=founder.id,
        event_type="succession_end"
    )
    db.session.add(founder_log)
    
    db.session.commit()
    return True


def process_dynasty_turn(dynasty_id: int, years_to_advance: int = 5):
    """Process a turn for the dynasty, advancing the simulation by the specified number of years."""
    dynasty = DynastyDB.query.get(dynasty_id)
    if not dynasty:
        return False, "Dynasty not found"
    
    # Load theme configuration
    theme_config = {}
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            # Predefined theme
            theme_config = get_theme(dynasty.theme_identifier_or_json)
        else:
            # Custom theme stored as JSON
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
            except json.JSONDecodeError:
                return False, "Invalid theme configuration"
    
    # Get all living persons in the dynasty
    living_persons = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        death_year=None
    ).all()
    
    # Get current monarch
    current_monarch = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        is_monarch=True,
        death_year=None
    ).first()
    
    # Process each year
    start_year = dynasty.current_simulation_year
    end_year = start_year + years_to_advance
    
    for current_year in range(start_year, end_year):
        # Process world events
        process_world_events(dynasty, current_year, theme_config)
        
        # Process each person's yearly events
        for person in living_persons:
            # Skip if person died in a previous year of this turn
            if person.death_year is not None:
                continue
                
            # Process death check
            if process_death_check(person, current_year, theme_config):
                # Person died, check if they were the monarch
                if person.is_monarch:
                    process_succession(dynasty, person, current_year, theme_config)
                continue
            
            # Process marriage for unmarried nobles
            if person.is_noble and person.spouse_sim_id is None:
                process_marriage_check(dynasty, person, current_year, theme_config)
            
            # Process childbirth for married women
            if person.gender == "FEMALE" and person.spouse_sim_id is not None:
                process_childbirth_check(dynasty, person, current_year, theme_config)
        
        # Update living persons list (remove those who died)
        living_persons = [p for p in living_persons if p.death_year is None]
        
        # Update dynasty's current year
        dynasty.current_simulation_year = current_year + 1
    
    # Generate family tree visualization
    try:
        generate_family_tree_visualization(dynasty, theme_config)
    except Exception as e:
        print(f"Error generating family tree: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        db.session.commit()
        return True, f"Advanced {years_to_advance} years from {start_year} to {end_year}."
    except Exception as commit_error:
        db.session.rollback()
        print(f"Error committing changes: {commit_error}")
        import traceback
        traceback.print_exc()
        return False, f"Error advancing turn: {commit_error}"


def process_death_check(person: PersonDB, current_year: int, theme_config: dict):
    """Check if a person dies this year."""
    age = current_year - person.birth_year
    
    # Base mortality chance increases with age
    base_mortality = 0.01  # 1% base chance
    
    # Age modifiers
    if age < 5:
        # Child mortality
        base_mortality = 0.15 * theme_config.get("mortality_factor", 1.0)
    elif age > 60:
        # Elderly mortality increases
        base_mortality = 0.05 * theme_config.get("mortality_factor", 1.0)
        if age > 75:
            base_mortality += 0.15 * theme_config.get("mortality_factor", 1.0)
    
    # Check against themed max age
    max_age = 85 * theme_config.get("max_age_factor", 1.0)
    if age > max_age:
        base_mortality = 1.0  # Guaranteed death if past max age
    
    # Roll for death
    if random.random() < base_mortality:
        person.death_year = current_year
        
        # Log death
        death_log = HistoryLogEntryDB(
            dynasty_id=person.dynasty_id,
            year=current_year,
            event_string=f"{person.name} {person.surname} passed away at the age of {age}.",
            person1_sim_id=person.id,
            event_type="death"
        )
        db.session.add(death_log)
        return True
    
    return False


def process_marriage_check(dynasty: DynastyDB, person: PersonDB, current_year: int, theme_config: dict):
    """Check if an unmarried noble gets married this year."""
    age = current_year - person.birth_year
    
    # Check if person is of marriageable age
    min_marriage_age = 16
    max_marriage_age = 45 if person.gender == "FEMALE" else 55
    
    if age < min_marriage_age or age > max_marriage_age:
        return False
    
    # Base chance to seek marriage
    marriage_chance = 0.35
    
    # Roll for marriage
    if random.random() < marriage_chance:
        # Create a spouse
        spouse_gender = "FEMALE" if person.gender == "MALE" else "MALE"
        name_key = "names_male" if spouse_gender == "MALE" else "names_female"
        spouse_name = random.choice(theme_config.get(name_key, ["Spouse"]))
        
        # Choose a different surname for spouse
        available_surnames = theme_config.get("surnames_dynastic", ["OtherHouse"])
        spouse_surname = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "OtherHouse"
        
        # Determine spouse age
        spouse_age = random.randint(min_marriage_age, max_marriage_age)
        if person.gender == "MALE":
            # Males often marry younger females
            spouse_age = min(age - random.randint(0, 7), max_marriage_age)
        else:
            # Females often marry older males
            spouse_age = max(age + random.randint(0, 7), min_marriage_age)
        
        spouse_birth_year = current_year - spouse_age
        
        spouse = PersonDB(
            dynasty_id=dynasty.id,
            name=spouse_name,
            surname=spouse_surname,
            gender=spouse_gender,
            birth_year=spouse_birth_year,
            is_noble=person.is_noble
        )
        
        # Set spouse traits
        spouse_traits = []
        available_traits = theme_config.get("common_traits", ["Noble"])
        if available_traits:
            num_traits = min(2, len(available_traits))
            spouse_traits = random.sample(available_traits, num_traits)
        spouse.set_traits(spouse_traits)
        
        # Set spouse titles
        default_title_key = "default_noble_male" if spouse_gender == "MALE" else "default_noble_female"
        spouse_title = theme_config.get(default_title_key, "Noble")
        spouse.set_titles([spouse_title])
        
        db.session.add(spouse)
        db.session.flush()  # Get ID without committing
        
        # Link spouse and person
        person.spouse_sim_id = spouse.id
        spouse.spouse_sim_id = person.id
        
        # Log marriage
        marriage_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{person.name} {person.surname} and {spouse.name} {spouse.surname} were united in marriage.",
            person1_sim_id=person.id,
            person2_sim_id=spouse.id,
            event_type="marriage"
        )
        db.session.add(marriage_log)
        return True
    
    return False


def process_childbirth_check(dynasty: DynastyDB, woman: PersonDB, current_year: int, theme_config: dict):
    """Check if a married woman has a child this year."""
    age = current_year - woman.birth_year
    
    # Check if woman is of childbearing age
    min_fertility_age = 18
    max_fertility_age = 45
    
    if age < min_fertility_age or age > max_fertility_age:
        return False
    
    # Check if spouse exists
    if woman.spouse_sim_id is None:
        return False
    
    spouse = PersonDB.query.get(woman.spouse_sim_id)
    if not spouse or spouse.death_year is not None:
        return False
    
    # Check max children
    existing_children = PersonDB.query.filter(
        (PersonDB.mother_sim_id == woman.id) |
        (PersonDB.father_sim_id == woman.id)
    ).count()
    
    max_children = 8 * theme_config.get("max_children_factor", 1.0)
    if existing_children >= max_children:
        return False
    
    # Base chance for pregnancy
    pregnancy_chance = 0.4 * theme_config.get("pregnancy_chance_factor", 1.0)
    
    # Roll for pregnancy
    if random.random() < pregnancy_chance:
        # Determine child's gender
        child_gender = random.choice(["MALE", "FEMALE"])
        
        # Generate child's name
        name_key = "names_male" if child_gender == "MALE" else "names_female"
        child_name = random.choice(theme_config.get(name_key, ["Child"]))
        
        # Determine surname based on convention
        surname_convention = theme_config.get("surname_convention", "INHERITED_PATRILINEAL")
        
        if surname_convention == "PATRONYMIC":
            suffix_key = "patronymic_suffix_male" if child_gender == "MALE" else "patronymic_suffix_female"
            suffix = theme_config.get(suffix_key, "son" if child_gender == "MALE" else "dottir")
            child_surname = f"{spouse.name}{suffix}"
        elif surname_convention == "MATRONYMIC":
            suffix_key = "matronymic_suffix_male" if child_gender == "MALE" else "matronymic_suffix_female"
            suffix = theme_config.get(suffix_key, "son" if child_gender == "MALE" else "dottir")
            child_surname = f"{woman.name}{suffix}"
        else:  # Default to patrilineal
            child_surname = spouse.surname if spouse.gender == "MALE" else woman.surname
        
        # Create child
        child = PersonDB(
            dynasty_id=dynasty.id,
            name=child_name,
            surname=child_surname,
            gender=child_gender,
            birth_year=current_year,
            mother_sim_id=woman.id,
            father_sim_id=spouse.id,
            is_noble=woman.is_noble or spouse.is_noble
        )
        
        # Set child traits
        child_traits = []
        available_traits = theme_config.get("common_traits", ["Noble"])
        if available_traits:
            num_traits = min(1, len(available_traits))
            child_traits = random.sample(available_traits, num_traits)
        child.set_traits(child_traits)
        
        db.session.add(child)
        
        # Log birth
        birth_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{child_name} {child_surname} was born to {woman.name} {woman.surname} and {spouse.name} {spouse.surname}.",
            person1_sim_id=child.id,
            event_type="birth"
        )
        db.session.add(birth_log)
        
        # Child mortality check (15% chance)
        if random.random() < 0.15 * theme_config.get("mortality_factor", 1.0):
            child.death_year = current_year
            
            # Log infant death
            death_log = HistoryLogEntryDB(
                dynasty_id=dynasty.id,
                year=current_year,
                event_string=f"{child_name} {child_surname}, infant child of {woman.name} {woman.surname}, did not survive birth.",
                person1_sim_id=child.id,
                event_type="death"
            )
            db.session.add(death_log)
        
        return True
    
    return False


def process_succession(dynasty: DynastyDB, deceased_monarch: PersonDB, current_year: int, theme_config: dict):
    """Process succession after a monarch's death."""
    # Log the succession crisis
    succession_log = HistoryLogEntryDB(
        dynasty_id=dynasty.id,
        year=current_year,
        event_string=f"With the death of {deceased_monarch.name} {deceased_monarch.surname}, the matter of succession weighs heavily on House {dynasty.name}.",
        person1_sim_id=deceased_monarch.id,
        event_type="succession_start"
    )
    db.session.add(succession_log)
    
    # Get succession rule
    succession_rule = theme_config.get("succession_rule_default", "PRIMOGENITURE_MALE_PREFERENCE")
    
    # Find eligible heirs
    eligible_heirs = []
    
    # First, check for children of the deceased
    children = PersonDB.query.filter(
        (PersonDB.father_sim_id == deceased_monarch.id) |
        (PersonDB.mother_sim_id == deceased_monarch.id),
        PersonDB.death_year.is_(None),
        PersonDB.is_noble == True
    ).all()
    
    if children:
        if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
            # Sort by gender (males first) then by birth year (oldest first)
            children.sort(key=lambda c: (c.gender != "MALE", c.birth_year))
        elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
            # Sort by birth year only (oldest first)
            children.sort(key=lambda c: c.birth_year)
        elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
            # For simplicity, just sort by traits count and age
            children.sort(key=lambda c: (-len(c.get_traits()), c.birth_year))
        
        eligible_heirs = children
    
    # If no children, look for siblings
    if not eligible_heirs:
        siblings = PersonDB.query.filter(
            ((PersonDB.father_sim_id == deceased_monarch.father_sim_id) |
             (PersonDB.mother_sim_id == deceased_monarch.mother_sim_id)),
            PersonDB.id != deceased_monarch.id,
            PersonDB.death_year.is_(None),
            PersonDB.is_noble == True
        ).all()
        
        if siblings:
            if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                siblings.sort(key=lambda s: (s.gender != "MALE", s.birth_year))
            elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
                siblings.sort(key=lambda s: s.birth_year)
            elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
                siblings.sort(key=lambda s: (-len(s.get_traits()), s.birth_year))
            
            eligible_heirs = siblings
    
    # If still no heirs, look for any living noble in the dynasty
    if not eligible_heirs:
        nobles = PersonDB.query.filter_by(
            dynasty_id=dynasty.id,
            death_year=None,
            is_noble=True
        ).all()
        
        if nobles:
            if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                nobles.sort(key=lambda n: (n.gender != "MALE", n.birth_year))
            elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
                nobles.sort(key=lambda n: n.birth_year)
            elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
                nobles.sort(key=lambda n: (-len(n.get_traits()), n.birth_year))
            
            eligible_heirs = nobles
    
    # If we have an heir, make them the new monarch
    if eligible_heirs:
        new_monarch = eligible_heirs[0]
        new_monarch.is_monarch = True
        new_monarch.reign_start_year = current_year
        
        # Set monarch title
        title_key = "titles_male" if new_monarch.gender == "MALE" else "titles_female"
        titles = theme_config.get(title_key, ["Leader"])
        if titles:
            monarch_title = titles[0]
            current_titles = new_monarch.get_titles()
            if monarch_title not in current_titles:
                current_titles.insert(0, monarch_title)
                new_monarch.set_titles(current_titles)
        
        # Log succession
        succession_end_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{new_monarch.name} {new_monarch.surname} has become the new {monarch_title} of House {dynasty.name}.",
            person1_sim_id=new_monarch.id,
            event_type="succession_end"
        )
        db.session.add(succession_end_log)
    else:
        # No heir found - dynasty in crisis
        crisis_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"House {dynasty.name} faces a succession crisis as no clear heir can be found.",
            event_type="succession_crisis"
        )
        db.session.add(crisis_log)


def process_world_events(dynasty: DynastyDB, current_year: int, theme_config: dict):
    """Process random world events for the year."""
    events = theme_config.get("events", [])
    if not events:
        return
    
    # Shuffle events for randomness
    random.shuffle(events)
    
    for event in events:
        # Check if event should trigger
        min_year = event.get("min_year", 0)
        max_year = event.get("max_year", 99999)
        chance = event.get("chance_per_year", 0.0)
        
        if min_year <= current_year <= max_year and random.random() < chance:
            # Event triggered
            event_name = event.get("name", "A Mysterious Happening")
            
            # Format narrative
            narrative = event.get("narrative", "Its consequences were felt.")
            narrative = narrative.replace("{dynasty_name}", dynasty.name)
            narrative = narrative.replace("{location_flavor}", theme_config.get("location_flavor", "these lands"))
            
            if "{rival_clan_name}" in narrative:
                available_surnames = theme_config.get("surnames_dynastic", ["Rivals"])
                rival_name = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "Rivals"
                narrative = narrative.replace("{rival_clan_name}", rival_name)
            
            # Apply wealth change if specified
            wealth_change = event.get("wealth_change", 0)
            if wealth_change != 0:
                dynasty.current_wealth = max(0, dynasty.current_wealth + wealth_change)
            
            # Log event
            event_log = HistoryLogEntryDB(
                dynasty_id=dynasty.id,
                year=current_year,
                event_string=f"{event_name}: {narrative}",
                event_type="generic_event"
            )
            db.session.add(event_log)
            
            # Only one world event per year
            break


def generate_family_tree_visualization(dynasty: DynastyDB, theme_config: dict):
    """Generate a family tree visualization for the dynasty."""
    try:
        from visualization.plotter import visualize_family_tree_snapshot
        from models.family_tree import FamilyTree
        from models.person import Person
        
        # Create a directory for visualizations
        visualizations_dir = os.path.join('static', 'visualizations')
        os.makedirs(visualizations_dir, exist_ok=True)
        
        # Create a FamilyTree object from the database
        family_tree = FamilyTree(dynasty.name, theme_config)
        family_tree.current_year = dynasty.current_simulation_year
        
        # Load all persons from the database into the family tree
        persons = PersonDB.query.filter_by(dynasty_id=dynasty.id).all()
        
        # First pass: Create Person objects
        person_objects = {}
        for db_person in persons:
            # Create Person object with required parameters
            person = Person(
                name=db_person.name,
                gender=db_person.gender,
                birth_year=db_person.birth_year,
                theme_config=theme_config,
                is_noble=db_person.is_noble
            )
            
            # Set additional attributes
            person.surname = db_person.surname
            person.death_year = db_person.death_year
            person.is_monarch = db_person.is_monarch
            person.reign_start_year = db_person.reign_start_year
            person.reign_end_year = db_person.reign_end_year
            person.titles = db_person.get_titles()
            person.traits = db_person.get_traits()
            
            # Store the Person object with the database ID as the key
            person_objects[db_person.id] = person
            # Use the database ID as the key in the family tree members dictionary
            family_tree.members[db_person.id] = person
            
            if db_person.is_monarch and db_person.death_year is None:
                family_tree.current_monarch = person
        
        # Second pass: Set relationships
        for db_person in persons:
            person = person_objects.get(db_person.id)
            if not person:
                continue
                
            # Set parents
            if db_person.father_sim_id and db_person.father_sim_id in person_objects:
                person.father = person_objects[db_person.father_sim_id]
                if person not in person.father.children:
                    person.father.children.append(person)
                    
            if db_person.mother_sim_id and db_person.mother_sim_id in person_objects:
                person.mother = person_objects[db_person.mother_sim_id]
                if person not in person.mother.children:
                    person.mother.children.append(person)
            
            # Set spouse
            if db_person.spouse_sim_id and db_person.spouse_sim_id in person_objects:
                person.spouse = person_objects[db_person.spouse_sim_id]
        
        # Generate the visualization
        visualize_family_tree_snapshot(
            family_tree_obj=family_tree,
            year=dynasty.current_simulation_year,
            display_mode="living_nobles"
        )
        
        print(f"Family tree visualization generated for {dynasty.name} in year {dynasty.current_simulation_year}")
        return True
    except Exception as e:
        print(f"Error generating family tree visualization: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


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
            app.run(debug=True, use_reloader=False, host='0.0.0.0', port=current_port)
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