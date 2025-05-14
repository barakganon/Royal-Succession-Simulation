# Check if all necessary imports are available
try:
    from flask import Flask, render_template, redirect, url_for, flash, request
    print("Flask imports OK")
except ImportError as e:
    print(f"Flask import error: {e}")

try:
    from flask_sqlalchemy import SQLAlchemy
    print("Flask-SQLAlchemy imports OK")
except ImportError as e:
    print(f"Flask-SQLAlchemy import error: {e}")

try:
    from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
    print("Flask-Login imports OK")
except ImportError as e:
    print(f"Flask-Login import error: {e}")

try:
    from utils.theme_manager import load_cultural_themes, get_all_theme_names, generate_theme_from_story_llm, get_theme
    print("Theme manager imports OK")
except ImportError as e:
    print(f"Theme manager import error: {e}")

try:
    from utils.helpers import set_llm_globals_for_helpers
    print("Helpers imports OK")
except ImportError as e:
    print(f"Helpers import error: {e}")

try:
    from models.db_models import db, User, DynastyDB, PersonDB, HistoryLogEntryDB
    print("DB models imports OK")
except ImportError as e:
    print(f"DB models import error: {e}")

print("All import checks completed")