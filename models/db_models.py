# models/db_models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin  # For Flask-Login integration
import datetime
import json  # For storing list/dict data like titles, traits
import enum  # For enumeration types

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
    founder = db.relationship('PersonDB', foreign_keys=[founder_person_db_id], backref=db.backref('founded_this_dynasty', uselist=False))

    # New fields for multi-agent game
    prestige = db.Column(db.Integer, default=0)  # Dynasty's prestige score
    infamy = db.Column(db.Integer, default=0)  # Negative reputation from aggressive actions
    honor = db.Column(db.Integer, default=50)  # Trustworthiness in keeping agreements (0-100)
    piety = db.Column(db.Integer, default=50)  # Religious standing (0-100)
    
    # Capital territory - main seat of power
    capital_territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=True)
    capital = db.relationship('Territory', foreign_keys=[capital_territory_id])

    # Relationships to related simulation data for this dynasty
    # 'dynamic' allows for querying, e.g., dynasty.persons.filter_by(...).all()
    # 'cascade="all, delete-orphan"' means if a DynastyDB is deleted, its associated persons and history logs are also deleted.
    persons = db.relationship('PersonDB',
                             primaryjoin="DynastyDB.id == PersonDB.dynasty_id",
                             backref='dynasty_owner',
                             lazy='dynamic',
                             cascade="all, delete-orphan")
    history_logs = db.relationship('HistoryLogEntryDB', backref='dynasty_context', lazy='dynamic',
                                   cascade="all, delete-orphan")
    
    # New relationships for multi-agent game
    controlled_territories = db.relationship('Territory',
                                           foreign_keys='Territory.controller_dynasty_id',
                                           backref='controller_dynasty',
                                           lazy='dynamic')
    military_units = db.relationship('MilitaryUnit', backref='owner_dynasty', lazy='dynamic',
                                    cascade="all, delete-orphan")
    armies = db.relationship('Army', backref='owner_dynasty', lazy='dynamic',
                            cascade="all, delete-orphan")
    wars_initiated = db.relationship('War',
                                    foreign_keys='War.attacker_dynasty_id',
                                    backref='attacker_dynasty',
                                    lazy='dynamic')
    wars_defending = db.relationship('War',
                                    foreign_keys='War.defender_dynasty_id',
                                    backref='defender_dynasty',
                                    lazy='dynamic')
    outgoing_relations = db.relationship('DiplomaticRelation',
                                        foreign_keys='DiplomaticRelation.dynasty1_id',
                                        backref='source_dynasty',
                                        lazy='dynamic',
                                        cascade="all, delete-orphan")
    incoming_relations = db.relationship('DiplomaticRelation',
                                        foreign_keys='DiplomaticRelation.dynasty2_id',
                                        backref='target_dynasty',
                                        lazy='dynamic')
    battles_won = db.relationship('Battle',
                                 foreign_keys='Battle.winner_dynasty_id',
                                 backref='winner_dynasty',
                                 lazy='dynamic')

    # For storing serialized complex data like alliances or active global event effects for this dynasty
    # serialized_alliances_json = db.Column(db.Text, nullable=True) # e.g., JSON string of the alliances dict
    # serialized_active_events_json = db.Column(db.Text, nullable=True) # e.g., JSON string of active_event_effects dict

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_played_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

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
    
    # New fields for multi-agent game
    diplomatic_skill = db.Column(db.Integer, default=0)  # Skill for diplomacy (0-20)
    military_skill = db.Column(db.Integer, default=0)    # Skill for military leadership (0-20)
    stewardship_skill = db.Column(db.Integer, default=0) # Skill for economic management (0-20)
    espionage_skill = db.Column(db.Integer, default=0)   # Skill for covert operations (0-20)

    # New relationships for multi-agent game
    commanded_units = db.relationship('MilitaryUnit',
                                      foreign_keys='MilitaryUnit.commander_id',
                                      lazy='dynamic')
    commanded_armies = db.relationship('Army',
                                       foreign_keys='Army.commander_id',
                                       lazy='dynamic')
    # Fix backref conflict by using a different name
    governed_territories = db.relationship('Territory',
                                           foreign_keys='Territory.governor_id',
                                           backref=db.backref('governor_person', uselist=False),
                                           lazy='dynamic',
                                           overlaps="governor")

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
        
    def can_lead_army(self) -> bool:
        """Determines if person can lead an army based on traits and skills."""
        traits = self.get_traits()
        return self.military_skill > 3 and not any(trait in ["Craven", "Infirm"] for trait in traits)
    
    def calculate_command_bonus(self) -> float:
        """Calculate military command bonus based on traits and skills."""
        bonus = self.military_skill * 0.1
        traits = self.get_traits()
        if "Brave" in traits: bonus += 0.05
        if "Strategist" in traits: bonus += 0.1
        return bonus

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
    
    # New fields for multi-agent game
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=True)
    war_id = db.Column(db.Integer, db.ForeignKey('war.id'), nullable=True)
    battle_id = db.Column(db.Integer, db.ForeignKey('battle.id'), nullable=True)
    treaty_id = db.Column(db.Integer, db.ForeignKey('treaty.id'), nullable=True)
    
    # Relationships for multi-agent game
    # Use different relationship names to avoid conflicts with backrefs
    territory_rel = db.relationship('Territory', foreign_keys=[territory_id], backref=db.backref('history_entries_rel', lazy='dynamic'))
    war_rel = db.relationship('War', foreign_keys=[war_id], backref=db.backref('history_entries_rel', lazy='dynamic'))
    battle_rel = db.relationship('Battle', foreign_keys=[battle_id], backref=db.backref('history_entries_rel', lazy='dynamic'))
    treaty_rel = db.relationship('Treaty', foreign_keys=[treaty_id], backref=db.backref('history_entries_rel', lazy='dynamic'))

    # Timestamp for when the log entry was created in the database
    recorded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<HistoryLogEntryDB ID:{self.id} (Dynasty:{self.dynasty_id}, Year:{self.year}, Type:{self.event_type})>"


# New models for multi-agent game

class TerrainType(enum.Enum):
    """Enumeration of terrain types for territories."""
    PLAINS = "plains"
    HILLS = "hills"
    MOUNTAINS = "mountains"
    FOREST = "forest"
    DESERT = "desert"
    TUNDRA = "tundra"
    COASTAL = "coastal"
    RIVER = "river"
    LAKE = "lake"
    SWAMP = "swamp"


class Region(db.Model):
    """Model for large geographical regions containing multiple provinces."""
    __tablename__ = 'region'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    
    # Geographical data
    base_climate = db.Column(db.String(50), nullable=False, default="temperate")
    
    # Relationships
    provinces = db.relationship('Province', backref='region', lazy='dynamic',
                               cascade="all, delete-orphan")
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Region '{self.name}' (ID: {self.id})>"


class Province(db.Model):
    """Model for provinces within regions, containing multiple territories."""
    __tablename__ = 'province'
    
    id = db.Column(db.Integer, primary_key=True)
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    
    # Geographical data
    primary_terrain = db.Column(db.Enum(TerrainType), nullable=False)
    
    # Relationships
    territories = db.relationship('Territory', backref='province', lazy='dynamic',
                                 cascade="all, delete-orphan")
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Province '{self.name}' (ID: {self.id}, Region: {self.region_id})>"


class Territory(db.Model):
    """Model for territories (smallest land unit) that can be controlled by dynasties."""
    __tablename__ = 'territory'
    
    id = db.Column(db.Integer, primary_key=True)
    province_id = db.Column(db.Integer, db.ForeignKey('province.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    
    # Control information
    controller_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=True, index=True)
    governor_id = db.Column(db.Integer, db.ForeignKey('person_db.id'), nullable=True)
    is_capital = db.Column(db.Boolean, default=False)
    
    # Geographical data
    terrain_type = db.Column(db.Enum(TerrainType), nullable=False)
    x_coordinate = db.Column(db.Float, nullable=False)  # For map positioning
    y_coordinate = db.Column(db.Float, nullable=False)  # For map positioning
    
    # Economic data
    base_tax = db.Column(db.Integer, default=1)  # Base tax income
    base_manpower = db.Column(db.Integer, default=100)  # Base recruitable population
    development_level = db.Column(db.Integer, default=1)  # Overall development (1-10)
    population = db.Column(db.Integer, default=1000)  # Population count
    
    # Fortification
    fortification_level = db.Column(db.Integer, default=0)  # 0-5, affects siege difficulty
    
    # Relationships
    # Modified to avoid conflict with HistoryLogEntryDB.territory_rel
    history_entries = db.relationship('HistoryLogEntryDB',
                                     foreign_keys='HistoryLogEntryDB.territory_id',
                                     overlaps="territory_rel,history_entries_rel")
    governor = db.relationship('PersonDB', foreign_keys=[governor_id], overlaps="governor_person,governed_territories")
    buildings = db.relationship('Building', backref='territory', lazy='dynamic',
                               cascade="all, delete-orphan")
    resources = db.relationship('TerritoryResource', backref='territory', lazy='dynamic',
                               cascade="all, delete-orphan")
    settlements = db.relationship('Settlement', backref='territory', lazy='dynamic',
                                 cascade="all, delete-orphan")
    units_present = db.relationship('MilitaryUnit',
                                    foreign_keys='MilitaryUnit.territory_id',
                                    lazy='dynamic')
    armies_present = db.relationship('Army',
                                     foreign_keys='Army.territory_id',
                                     lazy='dynamic')
    battles = db.relationship('Battle',
                             backref=db.backref('battle_territory', uselist=False),
                             lazy='dynamic',
                             foreign_keys='Battle.territory_id',
                             overlaps="battle_rel,history_entries_rel")
    
    sieges = db.relationship('Siege',
                            backref=db.backref('siege_territory', uselist=False),
                            lazy='dynamic',
                            foreign_keys='Siege.territory_id')
    
    wars_over_territory = db.relationship('War',
                                         foreign_keys='War.target_territory_id',
                                         backref=db.backref('target_territory_ref', uselist=False),
                                         lazy='dynamic',
                                         overlaps="war_rel,history_entries_rel")
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        controller = f", Controller: Dynasty {self.controller_dynasty_id}" if self.controller_dynasty_id else ""
        return f"<Territory '{self.name}' (ID: {self.id}, Province: {self.province_id}{controller})>"


class Settlement(db.Model):
    """Model for settlements within territories (cities, towns, villages)."""
    __tablename__ = 'settlement'
    
    id = db.Column(db.Integer, primary_key=True)
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Settlement properties
    settlement_type = db.Column(db.String(50), nullable=False)  # city, town, village, castle, etc.
    population = db.Column(db.Integer, default=500)
    importance = db.Column(db.Integer, default=1)  # 1-10 scale of strategic importance
    
    # Economic data
    trade_value = db.Column(db.Integer, default=0)  # Trade value generated
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Settlement '{self.name}' ({self.settlement_type}, ID: {self.id}, Territory: {self.territory_id})>"


class ResourceType(enum.Enum):
    """Enumeration of resource types."""
    # Basic resources
    FOOD = "food"
    TIMBER = "timber"
    STONE = "stone"
    IRON = "iron"
    GOLD = "gold"
    
    # Luxury resources
    SPICES = "spices"
    WINE = "wine"
    SILK = "silk"
    JEWELRY = "jewelry"


class Resource(db.Model):
    """Model for resources that can be produced, traded, and consumed."""
    __tablename__ = 'resource'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    resource_type = db.Column(db.Enum(ResourceType), nullable=False)
    
    # Economic properties
    base_value = db.Column(db.Integer, nullable=False)  # Base value in gold
    volatility = db.Column(db.Float, default=0.1)  # Price volatility (0.0-1.0)
    perishability = db.Column(db.Float, default=0.0)  # Rate of decay if stored (0.0-1.0)
    
    # Game balance
    is_luxury = db.Column(db.Boolean, default=False)  # If it's a luxury resource
    scarcity = db.Column(db.Float, default=0.5)  # Rarity in the game world (0.0-1.0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Resource '{self.name}' (ID: {self.id}, Type: {self.resource_type.value})>"


class TerritoryResource(db.Model):
    """Model for resources available in a specific territory."""
    __tablename__ = 'territory_resource'
    
    id = db.Column(db.Integer, primary_key=True)
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=False, index=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)
    
    # Resource properties in this territory
    base_production = db.Column(db.Float, nullable=False)  # Base units produced per year
    quality = db.Column(db.Float, default=1.0)  # Quality multiplier (0.5-1.5)
    depletion_rate = db.Column(db.Float, default=0.0)  # Rate of depletion with extraction (0.0-1.0)
    current_depletion = db.Column(db.Float, default=0.0)  # Current depletion level (0.0-1.0)
    
    # Relationships
    resource = db.relationship('Resource', backref='territory_resources')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('territory_id', 'resource_id', name='uix_territory_resource'),
    )
    
    def __repr__(self):
        return f"<TerritoryResource (Territory: {self.territory_id}, Resource: {self.resource_id})>"


class BuildingType(enum.Enum):
    """Enumeration of building types."""
    # Production buildings
    FARM = "farm"
    MINE = "mine"
    LUMBER_CAMP = "lumber_camp"
    WORKSHOP = "workshop"
    
    # Trade buildings
    MARKET = "market"
    PORT = "port"
    WAREHOUSE = "warehouse"
    TRADE_POST = "trade_post"
    
    # Military buildings
    BARRACKS = "barracks"
    STABLE = "stable"
    TRAINING_GROUND = "training_ground"
    FORTRESS = "fortress"
    
    # Infrastructure
    ROADS = "roads"
    IRRIGATION = "irrigation"
    GUILD_HALL = "guild_hall"
    BANK = "bank"


class Building(db.Model):
    """Model for buildings that can be constructed in territories."""
    __tablename__ = 'building'
    
    id = db.Column(db.Integer, primary_key=True)
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=False, index=True)
    building_type = db.Column(db.Enum(BuildingType), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    # Building properties
    level = db.Column(db.Integer, default=1)  # Building level (1-5)
    condition = db.Column(db.Float, default=1.0)  # Condition (0.0-1.0)
    
    # Effects (stored as JSON)
    effects_json = db.Column(db.Text, default='{}')  # JSON string of effects
    
    # Construction and maintenance
    construction_year = db.Column(db.Integer, nullable=False)
    last_upgraded_year = db.Column(db.Integer, nullable=True)
    maintenance_cost = db.Column(db.Integer, default=1)  # Annual maintenance cost
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def get_effects(self) -> dict:
        """Deserializes effects from JSON string."""
        return json.loads(self.effects_json or '{}')
    
    def set_effects(self, effects_dict: dict):
        """Serializes effects dict to JSON string."""
        self.effects_json = json.dumps(effects_dict or {})
    
    def __repr__(self):
        return f"<Building '{self.name}' (Type: {self.building_type.value}, Level: {self.level}, Territory: {self.territory_id})>"


class TradeRoute(db.Model):
    """Model for trade routes between territories."""
    __tablename__ = 'trade_route'
    
    id = db.Column(db.Integer, primary_key=True)
    source_territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=False, index=True)
    destination_territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=False, index=True)
    
    # Trade route properties
    trade_volume = db.Column(db.Integer, default=10)  # Base trade volume
    efficiency = db.Column(db.Float, default=1.0)  # Efficiency multiplier (0.5-1.5)
    risk = db.Column(db.Float, default=0.1)  # Risk of disruption (0.0-1.0)
    
    # Relationships
    source_territory = db.relationship('Territory', foreign_keys=[source_territory_id],
                                      backref='outgoing_trade_routes')
    destination_territory = db.relationship('Territory', foreign_keys=[destination_territory_id],
                                           backref='incoming_trade_routes')
    
    # Metadata
    established_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<TradeRoute (Source: {self.source_territory_id}, Destination: {self.destination_territory_id})>"


class UnitType(enum.Enum):
    """Enumeration of military unit types."""
    # Infantry
    LEVY_SPEARMEN = "levy_spearmen"
    PROFESSIONAL_SWORDSMEN = "professional_swordsmen"
    ELITE_GUARDS = "elite_guards"
    ARCHERS = "archers"
    
    # Cavalry
    LIGHT_CAVALRY = "light_cavalry"
    HEAVY_CAVALRY = "heavy_cavalry"
    HORSE_ARCHERS = "horse_archers"
    KNIGHTS = "knights"
    
    # Siege
    BATTERING_RAM = "battering_ram"
    SIEGE_TOWER = "siege_tower"
    CATAPULT = "catapult"
    TREBUCHET = "trebuchet"
    
    # Naval
    TRANSPORT_SHIP = "transport_ship"
    WAR_GALLEY = "war_galley"
    HEAVY_WARSHIP = "heavy_warship"
    FIRE_SHIP = "fire_ship"


class MilitaryUnit(db.Model):
    """Model for military units that can engage in battles."""
    __tablename__ = 'military_unit'
    
    id = db.Column(db.Integer, primary_key=True)
    dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)
    unit_type = db.Column(db.Enum(UnitType), nullable=False)
    name = db.Column(db.String(100), nullable=True)  # Optional custom name
    
    # Unit properties
    size = db.Column(db.Integer, nullable=False)  # Number of troops
    quality = db.Column(db.Float, nullable=False, default=1.0)  # Equipment/training level (0.5-2.0)
    experience = db.Column(db.Float, default=0.0)  # Combat experience (0.0-1.0)
    morale = db.Column(db.Float, default=1.0)  # Current morale (0.0-1.0)
    
    # Location and command
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=True, index=True)
    commander_id = db.Column(db.Integer, db.ForeignKey('person_db.id'), nullable=True)
    
    # Army grouping
    army_id = db.Column(db.Integer, db.ForeignKey('army.id'), nullable=True, index=True)
    
    # Maintenance
    maintenance_cost = db.Column(db.Integer, nullable=False)  # Annual cost in gold
    food_consumption = db.Column(db.Float, nullable=False)  # Annual food consumption
    
    # Metadata
    created_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def calculate_strength(self, terrain_type=None) -> float:
        """Calculate combat strength considering all factors."""
        base_strength = self.size * self.quality * (1.0 + self.experience)
        
        # Apply morale modifier
        strength = base_strength * self.morale
        
        # Apply terrain modifier if provided
        if terrain_type and isinstance(terrain_type, TerrainType):
            # Different unit types have different terrain advantages
            terrain_modifiers = {
                UnitType.LEVY_SPEARMEN: {'HILLS': 1.1, 'MOUNTAINS': 0.8},
                UnitType.ARCHERS: {'FOREST': 1.2, 'PLAINS': 1.1},
                UnitType.LIGHT_CAVALRY: {'PLAINS': 1.3, 'FOREST': 0.7},
                UnitType.HEAVY_CAVALRY: {'PLAINS': 1.4, 'HILLS': 0.8, 'MOUNTAINS': 0.6},
                # Add more as needed
            }
            
            if self.unit_type in terrain_modifiers and terrain_type.name in terrain_modifiers[self.unit_type]:
                strength *= terrain_modifiers[self.unit_type][terrain_type.name]
        
        # Apply commander bonus if available
        if self.commander_id:
            from sqlalchemy.orm import object_session
            session = object_session(self)
            if session:
                commander = session.query(PersonDB).get(self.commander_id)
                if commander:
                    strength *= (1.0 + commander.calculate_command_bonus())
        
        return strength
    
    def __repr__(self):
        return f"<MilitaryUnit {self.name or self.unit_type.value} (Size: {self.size}, Dynasty: {self.dynasty_id})>"


class Army(db.Model):
    """Model for grouping military units into armies."""
    __tablename__ = 'army'
    
    id = db.Column(db.Integer, primary_key=True)
    dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Army properties
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=True, index=True)
    commander_id = db.Column(db.Integer, db.ForeignKey('person_db.id'), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_sieging = db.Column(db.Boolean, default=False)
    
    # Relationships
    units = db.relationship('MilitaryUnit', lazy='dynamic')
    
    # Metadata
    created_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def calculate_total_strength(self, terrain=None) -> float:
        """Calculate the total combat strength of all units in the army."""
        return sum(unit.calculate_strength(terrain) for unit in self.units)
    
    def __repr__(self):
        return f"<Army '{self.name}' (Dynasty: {self.dynasty_id}, Units: {self.units.count()})>"


class DiplomaticRelation(db.Model):
    """Model for diplomatic relations between two dynasties."""
    __tablename__ = 'diplomatic_relation'
    
    id = db.Column(db.Integer, primary_key=True)
    dynasty1_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)
    dynasty2_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)
    
    # Relation properties
    relation_score = db.Column(db.Integer, default=0)  # -100 to 100
    
    # Relationships
    treaties = db.relationship('Treaty', lazy='dynamic',
                              cascade="all, delete-orphan")
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('dynasty1_id', 'dynasty2_id', name='uix_diplomatic_relation'),
    )
    
    def update_relation(self, action_type, magnitude):
        """Update relation score based on diplomatic action."""
        self.relation_score += magnitude
        # Ensure score stays within bounds
        self.relation_score = max(-100, min(100, self.relation_score))
        
        # Add to recent actions log if needed
        # self.recent_actions.append((action_type, magnitude, datetime.datetime.utcnow()))
    
    def __repr__(self):
        return f"<DiplomaticRelation (Dynasty1: {self.dynasty1_id}, Dynasty2: {self.dynasty2_id}, Score: {self.relation_score})>"


class TreatyType(enum.Enum):
    """Enumeration of treaty types."""
    NON_AGGRESSION = "non_aggression"
    DEFENSIVE_ALLIANCE = "defensive_alliance"
    MILITARY_ALLIANCE = "military_alliance"
    VASSALAGE = "vassalage"
    TRADE_AGREEMENT = "trade_agreement"
    MARKET_ACCESS = "market_access"
    RESOURCE_EXCHANGE = "resource_exchange"
    ECONOMIC_UNION = "economic_union"
    CULTURAL_EXCHANGE = "cultural_exchange"
    ROYAL_MARRIAGE = "royal_marriage"


class Treaty(db.Model):
    """Model for formal agreements between dynasties."""
    __tablename__ = 'treaty'
    
    id = db.Column(db.Integer, primary_key=True)
    diplomatic_relation_id = db.Column(db.Integer, db.ForeignKey('diplomatic_relation.id'), nullable=False, index=True)
    treaty_type = db.Column(db.Enum(TreatyType), nullable=False)
    
    # Treaty properties
    start_year = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Integer, nullable=True)  # None = permanent until broken
    active = db.Column(db.Boolean, default=True)
    
    # Terms (stored as JSON)
    terms_json = db.Column(db.Text, default='{}')  # JSON string of terms
    
    # Relationships
    history_entries = db.relationship('HistoryLogEntryDB')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def get_terms(self) -> dict:
        """Deserializes terms from JSON string."""
        return json.loads(self.terms_json or '{}')
    
    def set_terms(self, terms_dict: dict):
        """Serializes terms dict to JSON string."""
        self.terms_json = json.dumps(terms_dict or {})
    
    def check_validity(self, current_year):
        """Check if treaty is still valid based on duration and terms."""
        if not self.active:
            return False
        
        if self.duration is not None:
            if current_year >= self.start_year + self.duration:
                self.active = False
                return False
        
        return True
    
    def __repr__(self):
        status = "Active" if self.active else "Inactive"
        return f"<Treaty {self.treaty_type.value} (ID: {self.id}, {status})>"


class WarGoal(enum.Enum):
    """Enumeration of war goals."""
    CONQUEST = "conquest"  # Take territory
    VASSALIZE = "vassalize"  # Make target a vassal
    INDEPENDENCE = "independence"  # Break vassalage
    TRIBUTE = "tribute"  # Force target to pay tribute
    HUMILIATE = "humiliate"  # Reduce target's prestige
    RELIGIOUS = "religious"  # Religious conversion


class War(db.Model):
    """Model for wars between dynasties."""
    __tablename__ = 'war'
    
    id = db.Column(db.Integer, primary_key=True)
    attacker_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)
    defender_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False, index=True)
    
    # War properties
    war_goal = db.Column(db.Enum(WarGoal), nullable=False)
    target_territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=True)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=True)
    
    # War status
    attacker_war_score = db.Column(db.Integer, default=0)  # -100 to 100
    defender_war_score = db.Column(db.Integer, default=0)  # -100 to 100
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    battles = db.relationship('Battle', lazy='dynamic',
                             cascade="all, delete-orphan")
    history_entries = db.relationship('HistoryLogEntryDB')
    target_territory = db.relationship('Territory')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def calculate_war_score(self):
        """Calculate current war score based on battles and objectives."""
        # Base score from battles
        battle_score = sum(1 if b.winner_dynasty_id == self.attacker_dynasty_id else -1
                          for b in self.battles if b.winner_dynasty_id is not None)
        
        # Adjust for war goal progress
        # Example: If conquest and attacker controls target territory
        if self.war_goal == WarGoal.CONQUEST and self.target_territory_id:
            from sqlalchemy.orm import object_session
            session = object_session(self)
            if session:
                territory = session.query(Territory).get(self.target_territory_id)
                if territory and territory.controller_dynasty_id == self.attacker_dynasty_id:
                    battle_score += 50  # Big bonus for achieving the war goal
        
        # Normalize to -100 to 100 range
        normalized_score = max(-100, min(100, battle_score))
        
        self.attacker_war_score = normalized_score if normalized_score > 0 else 0
        self.defender_war_score = abs(normalized_score) if normalized_score < 0 else 0
        
        return self.attacker_war_score, self.defender_war_score
    
    def __repr__(self):
        status = "Active" if self.is_active else "Ended"
        return f"<War (ID: {self.id}, Attacker: {self.attacker_dynasty_id}, Defender: {self.defender_dynasty_id}, {status})>"


class Battle(db.Model):
    """Model for battles between military forces."""
    __tablename__ = 'battle'
    
    id = db.Column(db.Integer, primary_key=True)
    war_id = db.Column(db.Integer, db.ForeignKey('war.id'), nullable=False, index=True)
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=False)
    
    # Battle properties
    year = db.Column(db.Integer, nullable=False)
    attacker_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False)
    defender_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False)
    attacker_army_id = db.Column(db.Integer, db.ForeignKey('army.id'), nullable=True)
    defender_army_id = db.Column(db.Integer, db.ForeignKey('army.id'), nullable=True)
    
    # Battle outcome
    winner_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=True)
    attacker_casualties = db.Column(db.Integer, default=0)
    defender_casualties = db.Column(db.Integer, default=0)
    
    # Battle details (stored as JSON)
    details_json = db.Column(db.Text, default='{}')  # JSON string of battle details
    
    # Relationships
    territory = db.relationship('Territory')
    attacker = db.relationship('DynastyDB', foreign_keys=[attacker_dynasty_id])
    defender = db.relationship('DynastyDB', foreign_keys=[defender_dynasty_id])
    winner = db.relationship('DynastyDB', foreign_keys=[winner_dynasty_id])
    attacker_army = db.relationship('Army', foreign_keys=[attacker_army_id])
    defender_army = db.relationship('Army', foreign_keys=[defender_army_id])
    history_entries = db.relationship('HistoryLogEntryDB')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def get_details(self) -> dict:
        """Deserializes battle details from JSON string."""
        return json.loads(self.details_json or '{}')
    
    def set_details(self, details_dict: dict):
        """Serializes battle details dict to JSON string."""
        self.details_json = json.dumps(details_dict or {})
    
    def __repr__(self):
        winner = f", Winner: {self.winner_dynasty_id}" if self.winner_dynasty_id else ""
        return f"<Battle (ID: {self.id}, War: {self.war_id}, Territory: {self.territory_id}{winner})>"


class Siege(db.Model):
    """Model for sieges of territories."""
    __tablename__ = 'siege'
    
    id = db.Column(db.Integer, primary_key=True)
    war_id = db.Column(db.Integer, db.ForeignKey('war.id'), nullable=False, index=True)
    territory_id = db.Column(db.Integer, db.ForeignKey('territory.id'), nullable=False)
    
    # Siege properties
    attacker_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False)
    defender_dynasty_id = db.Column(db.Integer, db.ForeignKey('dynasty.id'), nullable=False)
    attacker_army_id = db.Column(db.Integer, db.ForeignKey('army.id'), nullable=True)
    
    # Siege status
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=True)
    progress = db.Column(db.Float, default=0.0)  # 0.0-1.0, 1.0 means successful
    is_active = db.Column(db.Boolean, default=True)
    successful = db.Column(db.Boolean, default=False)
    
    # Relationships
    war = db.relationship('War')
    territory = db.relationship('Territory')
    attacker = db.relationship('DynastyDB', foreign_keys=[attacker_dynasty_id])
    defender = db.relationship('DynastyDB', foreign_keys=[defender_dynasty_id])
    attacker_army = db.relationship('Army', foreign_keys=[attacker_army_id])
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        status = "Active" if self.is_active else ("Successful" if self.successful else "Failed")
        return f"<Siege (ID: {self.id}, Territory: {self.territory_id}, Progress: {self.progress:.1f}, {status})>"

print("models.db_models defined (User, DynastyDB, PersonDB, HistoryLogEntryDB, Region, Province, Territory, Settlement, Resource, TerritoryResource, Building, TradeRoute, MilitaryUnit, Army, DiplomaticRelation, Treaty, War, Battle, Siege).")