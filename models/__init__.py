# models/__init__.py

# This file makes the 'models' directory a Python package.
# It also provides a convenient way to import all core model classes.

from .person import Person
from .history import History
from .family_tree import FamilyTree

# You can define a list of all public objects of this module if desired:
# __all__ = ['Person', 'History', 'FamilyTree']

print("Core simulation models (Person, History, FamilyTree) initialized for import.")