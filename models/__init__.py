# models/__init__.py

# This file makes the 'models' directory a Python package.
# The live application uses the SQLAlchemy ORM models in db_models.py
# (PersonDB, DynastyDB, ...) and the modern subsystem classes
# (EconomySystem, MilitarySystem, ...). The legacy in-memory simulation
# classes (Person, FamilyTree) were retired in Story 11-1.

from .history import History
from utils.logging_config import setup_logger

_logger = setup_logger('royal_succession.models')
_logger.debug("models package initialized for import.")
