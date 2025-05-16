# models/db_initialization.py
"""
Database initialization and integrity checking module.
Handles database setup, table creation, and schema migrations.
"""

import os
import logging
import datetime
import stat
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Import database models
from models.db_models import (
    db, User, DynastyDB, PersonDB, HistoryLogEntryDB, Territory, Region, Province,
    MilitaryUnit, UnitType, Army, Battle, Siege, War, DiplomaticRelation, Treaty, TreatyType,
    Resource, ResourceType, TerritoryResource, Building, BuildingType, Settlement,
    TradeRoute
)

class DatabaseInitializer:
    """
    Handles database initialization, integrity checks, and migrations.
    """
    
    def __init__(self, app=None):
        """
        Initialize the database initializer.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        self.logger = logging.getLogger("royal_succession.db")
        
        # Set up logging if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def init_app(self, app):
        """
        Initialize with Flask application.
        
        Args:
            app: Flask application instance
        """
        self.app = app
    
    def initialize_database(self):
        """
        Initialize the database, create tables if they don't exist,
        and perform integrity checks.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            with self.app.app_context():
                self.logger.info("Starting database initialization")
                
                # Check if database file exists for SQLite
                if self.app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:///'):
                    db_path = self.app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                    
                    # Ensure database directory exists
                    db_dir = os.path.dirname(db_path)
                    if db_dir and not os.path.exists(db_dir):
                        os.makedirs(db_dir, exist_ok=True)
                        self.logger.info(f"Created database directory: {db_dir}")
                    
                    # Check if database file exists
                    if not os.path.exists(db_path):
                        self.logger.info(f"Database file {db_path} does not exist. Creating new database.")
                    else:
                        # Ensure database file has proper permissions
                        try:
                            current_mode = os.stat(db_path).st_mode
                            if not (current_mode & stat.S_IWUSR):
                                os.chmod(db_path, current_mode | stat.S_IRUSR | stat.S_IWUSR)
                                self.logger.info(f"Set read/write permissions on database file: {db_path}")
                        except Exception as perm_error:
                            self.logger.warning(f"Could not set permissions on database file: {str(perm_error)}")
                
                # Create tables if they don't exist
                self._create_tables_if_not_exist()
                
                # Check database integrity
                integrity_ok = self._check_database_integrity()
                if not integrity_ok:
                    self.logger.warning("Database integrity check failed. Attempting to fix issues.")
                    self._fix_database_issues()
                
                # Initialize default resources if needed
                self._initialize_default_resources()
                
                self.logger.info("Database initialization completed successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {str(e)}")
            return False
    
    def _create_tables_if_not_exist(self):
        """
        Create database tables if they don't exist.
        """
        try:
            # Get list of existing tables
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if not existing_tables:
                self.logger.info("No tables found in database. Creating all tables.")
                db.create_all()
                self.logger.info("All tables created successfully")
            else:
                self.logger.info(f"Found {len(existing_tables)} existing tables in database")
                
                # Check for missing tables
                metadata_tables = db.metadata.tables.keys()
                missing_tables = [table for table in metadata_tables if table not in existing_tables]
                
                if missing_tables:
                    self.logger.info(f"Creating {len(missing_tables)} missing tables: {', '.join(missing_tables)}")
                    
                    # Create only the missing tables
                    for table_name in missing_tables:
                        if table_name in db.metadata.tables:
                            db.metadata.tables[table_name].create(db.engine)
                    
                    self.logger.info("Missing tables created successfully")
        
        except Exception as e:
            self.logger.error(f"Error creating tables: {str(e)}")
            raise
    
    def _check_database_integrity(self):
        """
        Check database integrity.
        
        Returns:
            bool: True if integrity check passed, False otherwise
        """
        try:
            self.logger.info("Performing database integrity check")
            
            # Check for required tables
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            required_tables = ['user_account', 'dynasty', 'person_db', 'history_log_entry', 'territory']
            
            for table in required_tables:
                if table not in existing_tables:
                    self.logger.error(f"Required table '{table}' is missing")
                    return False
            
            # Check for foreign key integrity if using SQLite
            if self.app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:///'):
                with db.engine.connect() as conn:
                    result = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
                    if result:
                        self.logger.error(f"Foreign key integrity check failed: {result}")
                        return False
            
            # Check for orphaned records
            orphaned_dynasties = DynastyDB.query.filter(~DynastyDB.user_id.in_(
                db.session.query(User.id)
            )).count()
            
            if orphaned_dynasties > 0:
                self.logger.warning(f"Found {orphaned_dynasties} dynasties with no associated user")
                return False
            
            # Check for orphaned persons
            orphaned_persons = PersonDB.query.filter(~PersonDB.dynasty_id.in_(
                db.session.query(DynastyDB.id)
            )).count()
            
            if orphaned_persons > 0:
                self.logger.warning(f"Found {orphaned_persons} persons with no associated dynasty")
                return False
            
            # Check for territories without provinces
            orphaned_territories = Territory.query.filter(~Territory.province_id.in_(
                db.session.query(Province.id)
            )).count()
            
            if orphaned_territories > 0:
                self.logger.warning(f"Found {orphaned_territories} territories with no associated province")
                return False
            
            self.logger.info("Database integrity check passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking database integrity: {str(e)}")
            return False
    
    def _fix_database_issues(self):
        """
        Attempt to fix database integrity issues.
        """
        try:
            self.logger.info("Attempting to fix database issues")
            
            # Fix orphaned dynasties by creating a system user if needed
            system_user = User.query.filter_by(username="system").first()
            if not system_user:
                system_user = User(
                    username="system",
                    email="system@example.com",
                    password_hash="not_for_login"
                )
                db.session.add(system_user)
                db.session.commit()
                self.logger.info("Created system user for orphaned records")
            
            # Assign orphaned dynasties to system user
            orphaned_dynasties = DynastyDB.query.filter(~DynastyDB.user_id.in_(
                db.session.query(User.id)
            )).all()
            
            for dynasty in orphaned_dynasties:
                dynasty.user_id = system_user.id
            
            if orphaned_dynasties:
                db.session.commit()
                self.logger.info(f"Fixed {len(orphaned_dynasties)} orphaned dynasties")
            
            # Delete orphaned persons
            orphaned_persons = PersonDB.query.filter(~PersonDB.dynasty_id.in_(
                db.session.query(DynastyDB.id)
            )).all()
            
            for person in orphaned_persons:
                db.session.delete(person)
            
            if orphaned_persons:
                db.session.commit()
                self.logger.info(f"Deleted {len(orphaned_persons)} orphaned persons")
            
            # Create default region and province for orphaned territories
            default_region = Region.query.filter_by(name="Default Region").first()
            if not default_region:
                default_region = Region(
                    name="Default Region",
                    description="Default region created during database repair",
                    base_climate="temperate"
                )
                db.session.add(default_region)
                db.session.commit()
            
            default_province = Province.query.filter_by(name="Default Province").first()
            if not default_province:
                default_province = Province(
                    region_id=default_region.id,
                    name="Default Province",
                    description="Default province created during database repair",
                    primary_terrain="plains"
                )
                db.session.add(default_province)
                db.session.commit()
            
            # Fix orphaned territories
            orphaned_territories = Territory.query.filter(~Territory.province_id.in_(
                db.session.query(Province.id)
            )).all()
            
            for territory in orphaned_territories:
                territory.province_id = default_province.id
            
            if orphaned_territories:
                db.session.commit()
                self.logger.info(f"Fixed {len(orphaned_territories)} orphaned territories")
            
            self.logger.info("Database issues fixed")
            
        except Exception as e:
            self.logger.error(f"Error fixing database issues: {str(e)}")
            db.session.rollback()
    
    def _initialize_default_resources(self):
        """
        Initialize default resources if they don't exist.
        """
        try:
            # Check if resources exist
            resources_count = Resource.query.count()
            if resources_count == 0:
                self.logger.info("No resources found. Creating default resources.")
                
                # Create basic resources
                resources = [
                    Resource(
                        name="Food",
                        resource_type=ResourceType.FOOD,
                        base_value=10,
                        volatility=0.2,
                        perishability=0.5,
                        is_luxury=False,
                        scarcity=0.1
                    ),
                    Resource(
                        name="Timber",
                        resource_type=ResourceType.TIMBER,
                        base_value=15,
                        volatility=0.1,
                        perishability=0.0,
                        is_luxury=False,
                        scarcity=0.2
                    ),
                    Resource(
                        name="Stone",
                        resource_type=ResourceType.STONE,
                        base_value=20,
                        volatility=0.05,
                        perishability=0.0,
                        is_luxury=False,
                        scarcity=0.3
                    ),
                    Resource(
                        name="Iron",
                        resource_type=ResourceType.IRON,
                        base_value=25,
                        volatility=0.15,
                        perishability=0.0,
                        is_luxury=False,
                        scarcity=0.4
                    ),
                    Resource(
                        name="Gold",
                        resource_type=ResourceType.GOLD,
                        base_value=50,
                        volatility=0.3,
                        perishability=0.0,
                        is_luxury=True,
                        scarcity=0.7
                    ),
                    Resource(
                        name="Spices",
                        resource_type=ResourceType.SPICES,
                        base_value=40,
                        volatility=0.4,
                        perishability=0.2,
                        is_luxury=True,
                        scarcity=0.6
                    ),
                    Resource(
                        name="Wine",
                        resource_type=ResourceType.WINE,
                        base_value=35,
                        volatility=0.25,
                        perishability=0.3,
                        is_luxury=True,
                        scarcity=0.5
                    ),
                    Resource(
                        name="Silk",
                        resource_type=ResourceType.SILK,
                        base_value=45,
                        volatility=0.2,
                        perishability=0.1,
                        is_luxury=True,
                        scarcity=0.8
                    ),
                    Resource(
                        name="Jewelry",
                        resource_type=ResourceType.JEWELRY,
                        base_value=60,
                        volatility=0.35,
                        perishability=0.0,
                        is_luxury=True,
                        scarcity=0.9
                    )
                ]
                
                for resource in resources:
                    db.session.add(resource)
                
                db.session.commit()
                self.logger.info(f"Created {len(resources)} default resources")
        
        except Exception as e:
            self.logger.error(f"Error initializing default resources: {str(e)}")
            db.session.rollback()
    
    def perform_migrations(self):
        """
        Perform database schema migrations if needed.
        
        Returns:
            bool: True if migrations were successful, False otherwise
        """
        try:
            self.logger.info("Checking for needed database migrations")
            
            # Check database version
            db_version = self._get_db_version()
            current_version = 1  # Current schema version
            
            if db_version < current_version:
                self.logger.info(f"Database needs migration from version {db_version} to {current_version}")
                
                # Perform migrations based on version
                if db_version == 0:
                    self._migrate_from_v0_to_v1()
                
                # Update database version
                self._set_db_version(current_version)
                self.logger.info(f"Database migrated to version {current_version}")
            else:
                self.logger.info(f"Database is at current version {db_version}, no migrations needed")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error performing database migrations: {str(e)}")
            return False
    
    def _get_db_version(self):
        """
        Get the current database schema version.
        
        Returns:
            int: Current database schema version
        """
        try:
            # Check if the person_db table has the required skill columns
            inspector = inspect(db.engine)
            
            # Check person_db table first (most critical for current issue)
            if 'person_db' in inspector.get_table_names():
                person_columns = [col['name'] for col in inspector.get_columns('person_db')]
                required_skill_columns = ['diplomatic_skill', 'military_skill', 'stewardship_skill', 'espionage_skill']
                
                # Force migration if ANY required column is missing
                missing_columns = [col for col in required_skill_columns if col not in person_columns]
                if missing_columns:
                    self.logger.info(f"Columns {missing_columns} missing from person_db table. Forcing migration.")
                    # Reset the version in the db_version table to 0
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text("UPDATE db_version SET version = 0"))
                            conn.commit()
                    except Exception as e:
                        self.logger.error(f"Error resetting db_version: {e}")
                    return 0
            
            # Also check dynasty table
            dynasty_columns = [col['name'] for col in inspector.get_columns('dynasty')]
            
            # If any of the required columns are missing, force a migration by returning 0
            required_columns = ['prestige', 'infamy', 'honor', 'piety', 'capital_territory_id', 'last_updated_at']
            for col in required_columns:
                if col not in dynasty_columns:
                    self.logger.info(f"Column '{col}' missing from dynasty table. Forcing migration.")
                    # Reset the version in the db_version table to 0
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text("UPDATE db_version SET version = 0"))
                            conn.commit()
                    except:
                        pass
                    return 0
            
            # Check history_log_entry table for required columns
            if 'history_log_entry' in inspector.get_table_names():
                history_columns = [col['name'] for col in inspector.get_columns('history_log_entry')]
                required_history_columns = ['territory_id', 'war_id', 'battle_id', 'treaty_id']
                
                for col in required_history_columns:
                    if col not in history_columns:
                        self.logger.info(f"Column '{col}' missing from history_log_entry table. Forcing migration.")
                        # Reset the version in the db_version table to 0
                        try:
                            with db.engine.connect() as conn:
                                conn.execute(text("UPDATE db_version SET version = 0"))
                                conn.commit()
                        except:
                            pass
                        return 0
            
            # Check if the version table exists
            if 'db_version' not in inspector.get_table_names():
                # Create version table
                with db.engine.connect() as conn:
                    conn.execute(text("CREATE TABLE db_version (version INTEGER)"))
                    conn.execute(text("INSERT INTO db_version VALUES (0)"))
                    conn.commit()
                return 0
            
            # Get version from table
            with db.engine.connect() as conn:
                result = conn.execute(text("SELECT version FROM db_version")).fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            self.logger.error(f"Error getting database version: {str(e)}")
            return 0
    
    def _set_db_version(self, version):
        """
        Set the database schema version.
        
        Args:
            version: New schema version
        """
        try:
            with db.engine.connect() as conn:
                conn.execute(text("UPDATE db_version SET version = :version"), {"version": version})
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error setting database version: {str(e)}")
    
    def _migrate_from_v0_to_v1(self):
        """
        Perform migration from version 0 to version 1.
        """
        try:
            self.logger.info("Performing migration from v0 to v1")
            
            # Check which columns already exist in the dynasty table
            inspector = inspect(db.engine)
            dynasty_columns = [col['name'] for col in inspector.get_columns('dynasty')]
            
            # Add missing columns to the dynasty table
            with db.engine.connect() as conn:
                # Add prestige column if it doesn't exist
                if 'prestige' not in dynasty_columns:
                    self.logger.info("Adding 'prestige' column to dynasty table")
                    conn.execute(text("ALTER TABLE dynasty ADD COLUMN prestige INTEGER DEFAULT 0"))
                
                # Add infamy column if it doesn't exist
                if 'infamy' not in dynasty_columns:
                    self.logger.info("Adding 'infamy' column to dynasty table")
                    conn.execute(text("ALTER TABLE dynasty ADD COLUMN infamy INTEGER DEFAULT 0"))
                
                # Add honor column if it doesn't exist
                if 'honor' not in dynasty_columns:
                    self.logger.info("Adding 'honor' column to dynasty table")
                    conn.execute(text("ALTER TABLE dynasty ADD COLUMN honor INTEGER DEFAULT 50"))
                
                # Add piety column if it doesn't exist
                if 'piety' not in dynasty_columns:
                    self.logger.info("Adding 'piety' column to dynasty table")
                    conn.execute(text("ALTER TABLE dynasty ADD COLUMN piety INTEGER DEFAULT 50"))
                
                # Add capital_territory_id column if it doesn't exist
                if 'capital_territory_id' not in dynasty_columns:
                    self.logger.info("Adding 'capital_territory_id' column to dynasty table")
                    conn.execute(text("ALTER TABLE dynasty ADD COLUMN capital_territory_id INTEGER"))
                
                # Add last_updated_at column if it doesn't exist
                if 'last_updated_at' not in dynasty_columns:
                    self.logger.info("Adding 'last_updated_at' column to dynasty table")
                    # Use a constant string value for the default instead of CURRENT_TIMESTAMP
                    current_time = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    conn.execute(text(f"ALTER TABLE dynasty ADD COLUMN last_updated_at TIMESTAMP DEFAULT '{current_time}'"))
                
                # Check which columns already exist in the person_db table
                person_columns = [col['name'] for col in inspector.get_columns('person_db')]
                
                # Define required skill columns
                required_skill_columns = ['diplomatic_skill', 'military_skill', 'stewardship_skill', 'espionage_skill']
                
                # Add missing skill columns to the person_db table
                if 'diplomatic_skill' not in person_columns:
                    self.logger.info("Adding 'diplomatic_skill' column to person_db table")
                    conn.execute(text("ALTER TABLE person_db ADD COLUMN diplomatic_skill INTEGER DEFAULT 0"))
                    conn.commit()
                
                if 'military_skill' not in person_columns:
                    self.logger.info("Adding 'military_skill' column to person_db table")
                    conn.execute(text("ALTER TABLE person_db ADD COLUMN military_skill INTEGER DEFAULT 0"))
                    conn.commit()
                
                if 'stewardship_skill' not in person_columns:
                    self.logger.info("Adding 'stewardship_skill' column to person_db table")
                    conn.execute(text("ALTER TABLE person_db ADD COLUMN stewardship_skill INTEGER DEFAULT 0"))
                    conn.commit()
                
                if 'espionage_skill' not in person_columns:
                    self.logger.info("Adding 'espionage_skill' column to person_db table")
                    conn.execute(text("ALTER TABLE person_db ADD COLUMN espionage_skill INTEGER DEFAULT 0"))
                    conn.commit()
                
                # Verify all columns were added successfully
                person_columns_after = [col['name'] for col in inspector.get_columns('person_db')]
                missing_after = [col for col in required_skill_columns if col not in person_columns_after]
                if missing_after:
                    self.logger.error(f"Failed to add columns {missing_after} to person_db table")
                    raise Exception(f"Migration failed: could not add columns {missing_after}")
                else:
                    self.logger.info("All required skill columns added successfully to person_db table")
                
                # Check which columns already exist in the history_log_entry table
                history_columns = [col['name'] for col in inspector.get_columns('history_log_entry')]
                
                # Add missing columns to the history_log_entry table
                if 'territory_id' not in history_columns:
                    self.logger.info("Adding 'territory_id' column to history_log_entry table")
                    conn.execute(text("ALTER TABLE history_log_entry ADD COLUMN territory_id INTEGER"))
                
                if 'war_id' not in history_columns:
                    self.logger.info("Adding 'war_id' column to history_log_entry table")
                    conn.execute(text("ALTER TABLE history_log_entry ADD COLUMN war_id INTEGER"))
                
                if 'battle_id' not in history_columns:
                    self.logger.info("Adding 'battle_id' column to history_log_entry table")
                    conn.execute(text("ALTER TABLE history_log_entry ADD COLUMN battle_id INTEGER"))
                
                if 'treaty_id' not in history_columns:
                    self.logger.info("Adding 'treaty_id' column to history_log_entry table")
                    conn.execute(text("ALTER TABLE history_log_entry ADD COLUMN treaty_id INTEGER"))
                
                conn.commit()
            
            self.logger.info("Migration from v0 to v1 completed")
            
        except Exception as e:
            self.logger.error(f"Error during migration from v0 to v1: {str(e)}")
            raise