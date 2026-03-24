# models/__init__.py

# This file makes the 'models' directory a Python package.
# It also provides a convenient way to import all core model classes.

from .person import Person
from .history import History
from .family_tree import FamilyTree
from utils.logging_config import setup_logger

# You can define a list of all public objects of this module if desired:
# __all__ = ['Person', 'History', 'FamilyTree']

_logger = setup_logger('royal_succession.models')
_logger.debug("Core simulation models (Person, History, FamilyTree) initialized for import.")