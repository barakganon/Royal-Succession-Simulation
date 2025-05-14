# main_flask_app.py
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json  # For theme handling
import random
import datetime

# Import database models (adjust path if your structure differs slightly)
from models.db_models import db, User, DynastyDB, PersonDB, HistoryLogEntryDB

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
        print("LLM Initialized successfully for Flask App.")
    else:
        print("LLM API Key not found for Flask App. Custom theme generation from story will be disabled.")
except ImportError:
    print("google-generativeai package not found. LLM features disabled for Flask App.")
except Exception as e_flask_llm:
    print(f"Error initializing LLM for Flask App: {type(e_flask_llm).__name__} - {e_flask_llm}")

# Pass LLM status to helper functions (used by theme_manager.generate_theme_from_story_llm)
set_llm_globals_for_helpers(FLASK_APP_LLM_MODEL, FLASK_APP_GOOGLE_API_KEY_PRESENT)


# --- End LLM Setup ---


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
    # In later phases, this will query DynastyDB for the user's dynasties
    user_dynasties = DynastyDB.query.filter_by(user_id=current_user.id).order_by(DynastyDB.name).all()
    return render_template('dashboard.html', title='Dashboard', dynasties=user_dynasties)


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
    
    db.session.commit()
    return True, f"Advanced {years_to_advance} years from {start_year} to {end_year}."


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
    # This is a placeholder for actual visualization logic
    # In a real implementation, this would use NetworkX and matplotlib
    # to generate a family tree image similar to visualization/plotter.py
    
    # For now, we'll just create a directory for visualizations
    visualizations_dir = os.path.join('static', 'visualizations')
    os.makedirs(visualizations_dir, exist_ok=True)
    
    # In a full implementation, this would save the image to:
    # f"{visualizations_dir}/family_tree_{dynasty.name.replace(' ', '_')}_year_{dynasty.current_simulation_year}_living_nobles.png"
    
    # For now, we'll just log that visualization would be generated
    print(f"Family tree visualization would be generated for {dynasty.name} in year {dynasty.current_simulation_year}")


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
            print("Test user created.")
        else:
            print("Test user already exists.")
        return test_user


if __name__ == '__main__':
    # Ensure the database tables are created if they don't exist
    # This should be run once, or can be handled by Flask-Migrate for schema changes
    with app.app_context():
        db.create_all()
        print("Database tables checked/created.")
        
        # Initialize test user
        initialize_test_user()

    # Pre-load themes from JSON file into theme_manager when app starts
    load_cultural_themes()  # From utils.theme_manager

    app.run(debug=True,
            use_reloader=False)  # debug=True for development, use_reloader=False often helps with PyCharm debugger