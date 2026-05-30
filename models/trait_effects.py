# models/trait_effects.py
"""
Pure trait-effects module (Story 6-1).

Maps personality traits to domain modifiers (combat, tax, diplomacy).
This module is intentionally PURE: it imports no Flask, no database, and no
project ORM models, so it can be imported and unit-tested without an
application context.

Domain deltas per trait:
  - combat:    additive delta applied as a multiplier (1.0 + sum_of_deltas)
  - tax:       additive delta applied as a multiplier (1.0 + sum_of_deltas)
  - diplomacy: additive integer delta (sum_of_deltas)

Unknown traits are ignored. An empty or None trait list yields the identity
modifier for every domain (combat 1.0, tax 1.0, diplomacy 0).
"""

import logging
from typing import Iterable, Optional

logger = logging.getLogger('royal_succession.trait_effects')

# Per-trait domain deltas. Missing domains default to 0.
TRAIT_MODIFIERS = {
    "Brave":   {"combat": 0.15},
    "Craven":  {"combat": -0.15},
    "Wroth":   {"combat": 0.10, "diplomacy": -10},
    "Patient": {"combat": 0.05, "diplomacy": 10},
    "Cunning": {"diplomacy": 15},
    "Pious":   {"diplomacy": 10},
    "Greedy":  {"tax": 0.20, "diplomacy": -5},
    "Sickly":  {"combat": -0.05},
}


def _sum_delta(traits: Optional[Iterable[str]], domain: str) -> float:
    """Sum the deltas for the given domain over all known traits."""
    if not traits:
        return 0.0
    total = 0.0
    for trait in traits:
        deltas = TRAIT_MODIFIERS.get(trait)
        if deltas:
            total += deltas.get(domain, 0)
    return total


def combat_modifier(traits: Optional[Iterable[str]]) -> float:
    """Multiplicative combat modifier: 1.0 + sum of combat deltas."""
    return 1.0 + _sum_delta(traits, "combat")


def tax_modifier(traits: Optional[Iterable[str]]) -> float:
    """Multiplicative tax modifier: 1.0 + sum of tax deltas."""
    return 1.0 + _sum_delta(traits, "tax")


def diplomacy_modifier(traits: Optional[Iterable[str]]) -> int:
    """Additive diplomacy modifier: sum of diplomacy deltas (integer)."""
    return int(_sum_delta(traits, "diplomacy"))
