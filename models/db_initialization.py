# models/db_initialization.py
"""
Database initialization and integrity checking module.
Handles database setup, table creation, and schema migrations.
"""

import os
import logging
import datetime
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
                    if not os.path.exists(db_path):
                        self.logger.info(f"Database file {db_path} does not exist. Creating new database.")
                
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
            # Check if the version table exists
            inspector = inspect(db.engine)
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
            
            # Example migration: Add a new column to a table
            # Check if the column already exists
            inspector = inspect(db.engine)
            dynasty_columns = [col['name'] for col in inspector.get_columns('dynasty')]
            
            if 'piety' not in dynasty_columns:
                self.logger.info("Adding 'piety' column to dynasty table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE dynasty ADD COLUMN piety INTEGER DEFAULT 50"))
                    conn.commit()
            
            self.logger.info("Migration from v0 to v1 completed")
            
        except Exception as e:
            self.logger.error(f"Error during migration from v0 to v1: {str(e)}")
            raise