# main_flask_app.py
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json  # For theme handling

# Import database models (adjust path if your structure differs slightly)
from models.db_models import db, User, DynastyDB  # PersonDB and HistoryLogEntryDB will be used later

# Import theme utilities
from utils.theme_manager import load_cultural_themes, get_all_theme_names, generate_theme_from_story_llm
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


# Placeholder for create_dynasty route - will be expanded in next prompt
@app.route('/dynasty/create_placeholder')
@login_required
def create_dynasty_placeholder():
    flash("Dynasty creation page is under construction!", "info")
    return redirect(url_for('dashboard'))


# Placeholder for view_dynasty route - will be expanded
@app.route('/dynasty/<int:dynasty_id>/view_placeholder')
@login_required
def view_dynasty_placeholder(dynasty_id):
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning");
        return redirect(url_for('dashboard'))
    flash(f"Viewing page for dynasty '{dynasty.name}' is under construction!", "info")
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    # Ensure the database tables are created if they don't exist
    # This should be run once, or can be handled by Flask-Migrate for schema changes
    with app.app_context():
        db.create_all()
        print("Database tables checked/created.")

    # Pre-load themes from JSON file into theme_manager when app starts
    load_cultural_themes()  # From utils.theme_manager

    app.run(debug=True,
            use_reloader=False)  # debug=True for development, use_reloader=False often helps with PyCharm debugger