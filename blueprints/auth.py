"""Auth Blueprint — handles /login, /logout, /register, and /dashboard routes."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from models.db_models import db, User, DynastyDB, HistoryLogEntryDB, Territory, Battle, Treaty
from models.game_manager import GameManager
from utils.logging_config import setup_logger

logger = setup_logger('royal_succession.auth')

auth = Blueprint('auth', __name__)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))  # Already logged in

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')  # Optional: add email validation
        password = request.form.get('password')
        password2 = request.form.get('password2')

        if not username or not password or not password2:
            flash('All fields are required!', 'danger')
            return redirect(url_for('auth.register'))
        if password != password2:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('auth.register'))

        existing_user_username = User.query.filter_by(username=username).first()
        if existing_user_username:
            flash('Username already exists. Please choose a different one.', 'warning')
            return redirect(url_for('auth.register'))

        # Optional: Check for existing email if you add an email field and want it unique
        # existing_user_email = User.query.filter_by(email=email).first()
        # if existing_user_email:
        #     flash('Email address already registered.', 'warning')
        #     return redirect(url_for('auth.register'))

        new_user = User(username=username,
                        email=email if email else f"{username}@example.com")  # Use a placeholder email if not provided
        new_user.set_password(password)
        db.session.add(new_user)
        try:
            db.session.commit()
            flash('Congratulations, your account has been created! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e_register:
            db.session.rollback()
            flash(f'Error creating account: {e_register}. Please try again.', 'danger')
            logger.error(f"ERROR during registration commit: {e_register}")

    return render_template('register.html', title='Register')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = True if request.form.get('remember_me') else False

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember_me)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')  # For redirecting after login if user tried to access a protected page
            return redirect(next_page) if next_page else redirect(url_for('auth.dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html', title='Login')


@auth.route('/logout')
@login_required  # Ensures only logged-in users can access this
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@auth.route('/dashboard')
@login_required
def dashboard():
    """User's main dashboard after login."""
    # Query DynastyDB for the user's dynasties (paginated)
    page = request.args.get('page', 1, type=int)
    user_dynasties = DynastyDB.query.filter_by(user_id=current_user.id).order_by(DynastyDB.name).paginate(page=page, per_page=20, error_out=False)

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
