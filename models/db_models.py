# models/db_models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin  # For Flask-Login integration
import datetime
import json  # For storing list/dict data like titles, traits

# Create the SQLAlchemy database instance.
# This will be initialized with the Flask app in main_flask_app.py
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Model for user accounts."""
    __tablename__ = 'user_account'  # Explicit table name is good practice

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # Optional, but good for recovery/notifications
    password_hash = db.Column(db.String(200), nullable=False)  # Increased length for stronger hashes

    # Relationship to dynasties owned by the user
    # 'dynamic' allows further querying on the relationship before fetching data
    dynasties = db.relationship('DynastyDB', backref='owner_user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password: str):
        """Hashes and sets the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Checks if the provided password matches the hashed password."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} (ID: {self.id})>"


class DynastyDB(db.Model):
    """Model for storing core information about a player's dynasty."""
    __tablename__ = 'dynasty'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False, index=True)  # Indexed for faster lookups by name

    # Stores either the key of a predefined theme from cultural_themes.json
    # OR the full JSON string of an LLM-generated custom theme.
    theme_identifier_or_json = db.Column(db.Text, nullable=False)

    current_wealth = db.Column(db.Integer, default=100)
    start_year = db.Column(db.Integer, nullable=False)
    current_simulation_year = db.Column(db.Integer, nullable=False)

    # This will link to the PersonDB record of the founder
    founder_person_db_id = db.Column(db.Integer, db.ForeignKey('person_db.id'), nullable=True)
    # founder = db.relationship('PersonDB', foreign_keys=[founder_person_db_id], backref=db.backref('founded_this_dynasty', uselist=False))

    # Relationships to related simulation data for this dynasty
    # 'dynamic' allows for querying, e.g., dynasty.persons.filter_by(...).all()
    # 'cascade="all, delete-orphan"' means if a DynastyDB is deleted, its associated persons and history logs are also deleted.
    persons = db.relationship('PersonDB', backref='dynasty_owner', lazy='dynamic', cascade="all, delete-orphan")
    history_logs = db.relationship('HistoryLogEntryDB', backref='dynasty_context', lazy='dynamic',
                                   cascade="all, delete-orphan")

    # For storing serialized complex data like alliances or active global event effects for this dynasty
    # serialized_alliances_json = db.Column(db.Text, nullable=True) # e.g., JSON string of the alliances dict
    # serialized_active_events_json = db.Column(db.Text, nullable=True) # e.g., JSON string of active_event_effects dict

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_played_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<DynastyDB '{self.name}' (ID: {self.id}, User: {self.user_id})>"


class PersonDB(db.Model):
    """Model for storing individual persons belonging to a dynasty."""
    __tablename__ = 'person_db'

    id = db.Column(db.Integer, primary_key=True)  # This ID MUST match the simulation's Person.id for consistency
    dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)

    # Core attributes from simulation Person class
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)  # Store the calculated surname
    gender = db.Column(db.String(10), nullable=False)
    birth_year = db.Column(db.Integer, nullable=False)
    death_year = db.Column(db.Integer, nullable=True)

    # Relationships by ID - these are sim IDs, not direct FKs if sim IDs can reset
    # For simplicity now, these are just numbers. When loading, we'd use these IDs to find the corresponding PersonDB objects.
    mother_sim_id = db.Column(db.Integer, nullable=True)
    father_sim_id = db.Column(db.Integer, nullable=True)
    spouse_sim_id = db.Column(db.Integer, nullable=True)

    # Store lists as JSON strings. Ensure proper default values.
    titles_json = db.Column(db.Text, default='[]')  # Default to empty JSON list string
    traits_json = db.Column(db.Text, default='[]')

    is_noble = db.Column(db.Boolean, default=True)
    is_monarch = db.Column(db.Boolean, default=False)  # If they are CURRENTLY the monarch of their dynasty
    reign_start_year = db.Column(db.Integer, nullable=True)
    reign_end_year = db.Column(db.Integer, nullable=True)

    # If you want a direct relationship for founder on DynastyDB
    # founded_dynasty_rel = db.relationship('DynastyDB', foreign_keys=[DynastyDB.founder_person_db_id], backref='founder_character', uselist=False)

    def get_titles(self) -> list:
        """Deserializes titles from JSON string."""
        return json.loads(self.titles_json or '[]')

    def set_titles(self, titles_list: list):
        """Serializes titles list to JSON string."""
        self.titles_json = json.dumps(titles_list or [])

    def get_traits(self) -> list:
        """Deserializes traits from JSON string."""
        return json.loads(self.traits_json or '[]')

    def set_traits(self, traits_list: list):
        """Serializes traits list to JSON string."""
        self.traits_json = json.dumps(traits_list or [])

    def __repr__(self):
        return f"<PersonDB ID:{self.id} - {self.name} {self.surname} (DynastyID:{self.dynasty_id})>"


class HistoryLogEntryDB(db.Model):
    """Model for storing historical log entries for each dynasty."""
    __tablename__ = 'history_log_entry'

    id = db.Column(db.Integer, primary_key=True)
    dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)

    year = db.Column(db.Integer, nullable=True, index=True)  # Nullable for system messages, indexed for sorting
    event_string = db.Column(db.Text, nullable=False)

    # These are simulation Person IDs (Person._next_id values), not foreign keys to PersonDB.id directly
    # This is because PersonDB.id might be an auto-incrementing PK, while sim IDs are specific.
    # This could be changed if PersonDB.id is forced to be the simulation Person.id.
    person1_sim_id = db.Column(db.Integer, nullable=True)
    person2_sim_id = db.Column(db.Integer, nullable=True)
    event_type = db.Column(db.String(50), nullable=True)

    # Timestamp for when the log entry was created in the database
    recorded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<HistoryLogEntryDB ID:{self.id} (Dynasty:{self.dynasty_id}, Year:{self.year}, Type:{self.event_type})>"


print("models.db_models defined (User, DynastyDB, PersonDB, HistoryLogEntryDB).")