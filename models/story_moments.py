# models/story_moments.py
"""
Pure story-moments module (Story 10-1).

Generates randomized medieval/dynastic "story moments" — narrative events with
2-3 mechanical choices the player can take. This module is intentionally PURE:
it imports no Flask, no database, no genai, and no project ORM models, so it can
be imported and unit-tested without an application context. It operates on a
plain ``dynasty_state`` dict and returns plain dicts.

dynasty_state shape (extra keys are allowed and ignored)::

    {
        "prestige":        int,            # current dynasty prestige
        "wealth":          int,            # current gold/wealth
        "infamy":          int,            # current infamy
        "at_war":          bool,           # is the dynasty currently at war
        "has_living_heir": bool,           # does a living heir exist
        "heir_age":        int | None,     # age of the heir (or None)
        "monarch_traits":  list[str],      # current monarch's trait names
        "year":            int,            # current simulation year
        "relations":       dict[str, int], # named-target relation scores
    }

Effects vocabulary (declared here, applied elsewhere in Story 10-3). Each
choice's ``effects`` dict may contain any of::

    prestige_delta:        int
    wealth_delta:          int
    infamy_delta:          int
    add_trait_to_monarch:  str
    relation_delta:        {"target": str, "amount": int}
    exile_person:          bool
    chronicle_note:        str

Trait names referenced in templates are real traits from
``models.trait_effects.TRAIT_MODIFIERS`` (Brave, Craven, Cunning, Wroth,
Patient, Pious, Greedy, Sickly).
"""

import logging
import random as _random_module
from typing import List, Optional

logger = logging.getLogger('royal_succession.story_moments')

# Probability that ANY eligible story moment fires on a given roll.
BASE_TRIGGER_CHANCE = 0.05


# ---------------------------------------------------------------------------
# Story moment templates
# ---------------------------------------------------------------------------
# Each template dict has EXACTLY these keys:
#   key, title, summary, preconditions, weight, mechanical_choices
# Each choice dict has EXACTLY: key, label, description, effects
STORY_MOMENT_TEMPLATES: List[dict] = [
    {
        "key": "forbidden_love",
        "title": "A Forbidden Love",
        "summary": "Your monarch is rumored to have taken a lowborn lover.",
        "preconditions": {},
        "weight": 1.0,
        "mechanical_choices": [
            {
                "key": "embrace",
                "label": "Embrace the affair openly",
                "description": "Flaunt the romance and dare the court to object.",
                "effects": {
                    "prestige_delta": -15,
                    "infamy_delta": 5,
                    "chronicle_note": "The crown's heart ruled the crown's head.",
                },
            },
            {
                "key": "deny",
                "label": "Deny the rumors coldly",
                "description": "Crush the whispers with stern royal denial.",
                "effects": {
                    "prestige_delta": 5,
                    "add_trait_to_monarch": "Cunning",
                    "chronicle_note": "The lie was told with a steady, kingly face.",
                },
            },
            {
                "key": "banish",
                "label": "Banish the lover from the realm",
                "description": "End the scandal by exiling the lowborn paramour.",
                "effects": {
                    "prestige_delta": 8,
                    "exile_person": True,
                    "chronicle_note": "Duty was served, though the heart paid the toll.",
                },
            },
        ],
    },
    {
        "key": "council_whispers",
        "title": "Whispers in the Council",
        "summary": "A councilor warns of plots brewing among the lesser lords.",
        "preconditions": {"min_prestige": 20},
        "weight": 1.0,
        "mechanical_choices": [
            {
                "key": "investigate",
                "label": "Quietly investigate the conspirators",
                "description": "Set spies upon the suspected schemers.",
                "effects": {
                    "wealth_delta": -40,
                    "add_trait_to_monarch": "Cunning",
                    "chronicle_note": "Shadows were met with shadows.",
                },
            },
            {
                "key": "purge",
                "label": "Purge the suspected plotters",
                "description": "Strike first and make a bloody example.",
                "effects": {
                    "prestige_delta": -10,
                    "infamy_delta": 10,
                    "chronicle_note": "Heads rolled before the plot could ripen.",
                },
            },
            {
                "key": "ignore",
                "label": "Dismiss the warning",
                "description": "Wave away the councilor's fears as paranoia.",
                "effects": {
                    "prestige_delta": -5,
                    "chronicle_note": "The warning was laughed from the chamber.",
                },
            },
        ],
    },
    {
        "key": "dueling_lords",
        "title": "Two Lords, One Grudge",
        "summary": "Two of your vassals demand the right to settle a feud by the sword.",
        "preconditions": {"max_infamy": 60},
        "weight": 1.0,
        "mechanical_choices": [
            {
                "key": "allow_duel",
                "label": "Permit the trial by combat",
                "description": "Let steel decide and earn the lords' respect.",
                "effects": {
                    "prestige_delta": 10,
                    "add_trait_to_monarch": "Brave",
                    "chronicle_note": "Honor was bought with blood upon the field.",
                },
            },
            {
                "key": "forbid",
                "label": "Forbid the duel and impose peace",
                "description": "Command reconciliation and broker a settlement.",
                "effects": {
                    "prestige_delta": -5,
                    "add_trait_to_monarch": "Patient",
                    "chronicle_note": "The crown stayed two eager blades.",
                },
            },
        ],
    },
    {
        "key": "bonds_of_kin",
        "title": "Bonds of Kin",
        "summary": "A distant cousin arrives at court seeking your favor and a title.",
        "preconditions": {},
        "weight": 1.0,
        "mechanical_choices": [
            {
                "key": "grant_title",
                "label": "Grant the cousin lands and title",
                "description": "Bind kin closer with generosity.",
                "effects": {
                    "wealth_delta": -60,
                    "relation_delta": {"target": "kin", "amount": 20},
                    "chronicle_note": "Blood was rewarded with land and honor.",
                },
            },
            {
                "key": "test_loyalty",
                "label": "Set the cousin a difficult task",
                "description": "Demand proof of worth before any reward.",
                "effects": {
                    "relation_delta": {"target": "kin", "amount": 5},
                    "add_trait_to_monarch": "Patient",
                    "chronicle_note": "Kinship alone bought no easy welcome.",
                },
            },
            {
                "key": "turn_away",
                "label": "Send the cousin away empty-handed",
                "description": "Refuse the petition and guard the treasury.",
                "effects": {
                    "relation_delta": {"target": "kin", "amount": -25},
                    "add_trait_to_monarch": "Greedy",
                    "chronicle_note": "Kin departed with a grudge and an empty purse.",
                },
            },
        ],
    },
    {
        "key": "fading_heir",
        "title": "The Fading Heir",
        "summary": "Your heir has fallen gravely ill, and the physicians despair.",
        "preconditions": {"has_living_heir": True},
        "weight": 1.2,
        "mechanical_choices": [
            {
                "key": "summon_physicians",
                "label": "Summon the realm's finest physicians",
                "description": "Spare no expense to save the heir.",
                "effects": {
                    "wealth_delta": -80,
                    "chronicle_note": "Gold was poured out to buy the heir's breath.",
                },
            },
            {
                "key": "pray",
                "label": "Call for prayer and pilgrimage",
                "description": "Trust the heir's fate to the heavens.",
                "effects": {
                    "add_trait_to_monarch": "Pious",
                    "prestige_delta": 5,
                    "chronicle_note": "The court knelt and begged divine mercy.",
                },
            },
            {
                "key": "accept_fate",
                "label": "Quietly prepare for the worst",
                "description": "Begin arranging the succession in secret.",
                "effects": {
                    "infamy_delta": 5,
                    "add_trait_to_monarch": "Cunning",
                    "chronicle_note": "The crown counted the days with cold eyes.",
                },
            },
        ],
    },
    {
        "key": "letter_from_east",
        "title": "A Letter from the East",
        "summary": "A sealed missive arrives from a distant eastern court with an offer.",
        "preconditions": {"min_year": 1100},
        "weight": 0.8,
        "mechanical_choices": [
            {
                "key": "accept_trade",
                "label": "Accept the trade overture",
                "description": "Open routes to eastern silk and spice.",
                "effects": {
                    "wealth_delta": 120,
                    "relation_delta": {"target": "eastern_court", "amount": 15},
                    "chronicle_note": "Caravans of the East turned toward your gates.",
                },
            },
            {
                "key": "demand_tribute",
                "label": "Demand tribute instead",
                "description": "Answer the offer with a haughty counter-demand.",
                "effects": {
                    "prestige_delta": 10,
                    "relation_delta": {"target": "eastern_court", "amount": -20},
                    "infamy_delta": 5,
                    "chronicle_note": "Pride answered the East with an open hand demanding gold.",
                },
            },
            {
                "key": "burn_letter",
                "label": "Burn the letter unread",
                "description": "Spurn the foreign court entirely.",
                "effects": {
                    "relation_delta": {"target": "eastern_court", "amount": -10},
                    "chronicle_note": "The eastern seal crackled to ash in the hearth.",
                },
            },
        ],
    },
    {
        "key": "peasant_petition",
        "title": "A Peasant's Petition",
        "summary": "Famished commoners gather at the castle gates begging for grain.",
        "preconditions": {},
        "weight": 1.0,
        "mechanical_choices": [
            {
                "key": "open_granary",
                "label": "Open the granaries to the people",
                "description": "Feed the starving and win their love.",
                "effects": {
                    "wealth_delta": -50,
                    "prestige_delta": 12,
                    "chronicle_note": "The smallfolk blessed a king who fed them.",
                },
            },
            {
                "key": "token_alms",
                "label": "Distribute token alms",
                "description": "Give a modest dole to quiet the crowd.",
                "effects": {
                    "wealth_delta": -15,
                    "prestige_delta": 3,
                    "chronicle_note": "A thin charity bought a quieter gate.",
                },
            },
            {
                "key": "disperse",
                "label": "Order the guards to disperse them",
                "description": "Drive the rabble from the gates by force.",
                "effects": {
                    "prestige_delta": -10,
                    "infamy_delta": 8,
                    "add_trait_to_monarch": "Wroth",
                    "chronicle_note": "Spears, not bread, met the hungry at the wall.",
                },
            },
        ],
    },
    {
        "key": "pious_pilgrim",
        "title": "The Wandering Pilgrim",
        "summary": "A revered holy pilgrim seeks an audience and the crown's patronage.",
        "preconditions": {"monarch_lacks_trait": "Pious"},
        "weight": 0.9,
        "mechanical_choices": [
            {
                "key": "fund_shrine",
                "label": "Fund a shrine in the pilgrim's honor",
                "description": "Earn renown for piety across the realm.",
                "effects": {
                    "wealth_delta": -70,
                    "prestige_delta": 15,
                    "add_trait_to_monarch": "Pious",
                    "chronicle_note": "Stone and prayer rose where the pilgrim trod.",
                },
            },
            {
                "key": "host_feast",
                "label": "Host the pilgrim at a modest feast",
                "description": "Offer hospitality without grand expense.",
                "effects": {
                    "wealth_delta": -20,
                    "prestige_delta": 5,
                    "chronicle_note": "Bread was broken and blessings exchanged.",
                },
            },
            {
                "key": "turn_out",
                "label": "Turn the beggar-pilgrim away",
                "description": "Dismiss the holy wanderer at the door.",
                "effects": {
                    "prestige_delta": -8,
                    "infamy_delta": 3,
                    "chronicle_note": "The faithful muttered of a godless gate.",
                },
            },
        ],
    },
    {
        "key": "war_ransom",
        "title": "A Captive of War",
        "summary": "Your soldiers have captured an enemy noble worth a king's ransom.",
        "preconditions": {"at_war": True},
        "weight": 1.0,
        "mechanical_choices": [
            {
                "key": "ransom",
                "label": "Ransom the captive for gold",
                "description": "Trade the prisoner back for a heavy sum.",
                "effects": {
                    "wealth_delta": 150,
                    "relation_delta": {"target": "enemy", "amount": 10},
                    "chronicle_note": "A noble was weighed in gold and sent home.",
                },
            },
            {
                "key": "execute",
                "label": "Execute the captive as a warning",
                "description": "Send a brutal message to the enemy.",
                "effects": {
                    "prestige_delta": 5,
                    "infamy_delta": 15,
                    "add_trait_to_monarch": "Wroth",
                    "relation_delta": {"target": "enemy", "amount": -30},
                    "chronicle_note": "The block ran red, and the foe trembled.",
                },
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Precondition matching
# ---------------------------------------------------------------------------
def _matches(preconditions: dict, dynasty_state: dict) -> bool:
    """Return True iff every known precondition is satisfied by dynasty_state.

    Supported precondition keys:
      - min_prestige / max_prestige  -> dynasty_state['prestige']
      - min_wealth   / max_wealth    -> dynasty_state['wealth']
      - min_infamy   / max_infamy    -> dynasty_state['infamy']
      - at_war (bool)                -> dynasty_state['at_war']
      - has_living_heir (bool)       -> dynasty_state['has_living_heir']
      - monarch_has_trait (str)      -> str in dynasty_state['monarch_traits']
      - monarch_lacks_trait (str)    -> str NOT in dynasty_state['monarch_traits']
      - min_year / max_year          -> dynasty_state['year']

    Behavior:
      - Empty preconditions  -> True.
      - UNKNOWN precondition keys are IGNORED (forward-compatible).
      - A MISSING dynasty_state key needed by a precondition makes that
        precondition FAIL (returns False) WITHOUT raising.
    """
    if not preconditions:
        return True
    if not isinstance(dynasty_state, dict):
        return False

    _SENTINEL = object()

    try:
        for pkey, pval in preconditions.items():
            if pkey == "min_prestige":
                v = dynasty_state.get("prestige", _SENTINEL)
                if v is _SENTINEL or v < pval:
                    return False
            elif pkey == "max_prestige":
                v = dynasty_state.get("prestige", _SENTINEL)
                if v is _SENTINEL or v > pval:
                    return False
            elif pkey == "min_wealth":
                v = dynasty_state.get("wealth", _SENTINEL)
                if v is _SENTINEL or v < pval:
                    return False
            elif pkey == "max_wealth":
                v = dynasty_state.get("wealth", _SENTINEL)
                if v is _SENTINEL or v > pval:
                    return False
            elif pkey == "min_infamy":
                v = dynasty_state.get("infamy", _SENTINEL)
                if v is _SENTINEL or v < pval:
                    return False
            elif pkey == "max_infamy":
                v = dynasty_state.get("infamy", _SENTINEL)
                if v is _SENTINEL or v > pval:
                    return False
            elif pkey == "at_war":
                v = dynasty_state.get("at_war", _SENTINEL)
                if v is _SENTINEL or bool(v) != bool(pval):
                    return False
            elif pkey == "has_living_heir":
                v = dynasty_state.get("has_living_heir", _SENTINEL)
                if v is _SENTINEL or bool(v) != bool(pval):
                    return False
            elif pkey == "monarch_has_trait":
                traits = dynasty_state.get("monarch_traits", _SENTINEL)
                if traits is _SENTINEL or pval not in traits:
                    return False
            elif pkey == "monarch_lacks_trait":
                traits = dynasty_state.get("monarch_traits", _SENTINEL)
                if traits is _SENTINEL or pval in traits:
                    return False
            elif pkey == "min_year":
                v = dynasty_state.get("year", _SENTINEL)
                if v is _SENTINEL or v < pval:
                    return False
            elif pkey == "max_year":
                v = dynasty_state.get("year", _SENTINEL)
                if v is _SENTINEL or v > pval:
                    return False
            else:
                # Unknown precondition key: ignore (forward-compatible).
                continue
    except Exception:
        # Never raise from precondition checking; treat odd states as no-match.
        logger.debug("Precondition check failed safe for %r", preconditions, exc_info=True)
        return False

    return True


def eligible_templates(dynasty_state: dict) -> List[dict]:
    """Return all templates whose preconditions match (no probability roll)."""
    result: List[dict] = []
    try:
        for template in STORY_MOMENT_TEMPLATES:
            if _matches(template.get("preconditions", {}), dynasty_state):
                result.append(template)
    except Exception:
        logger.debug("eligible_templates failed safe", exc_info=True)
        return []
    return result


def maybe_trigger_story_moment(dynasty_state: dict, rng=None) -> Optional[dict]:
    """Possibly return one eligible story-moment template, else None.

    - ``rng`` may be an injected ``random.Random`` instance; defaults to the
      module-level random.
    - Computes the eligible templates; if none, returns None.
    - Rolls BASE_TRIGGER_CHANCE (``rng.random() < BASE_TRIGGER_CHANCE``) to
      decide whether ANY moment fires.
    - If it fires, picks one eligible template weighted by ``template['weight']``.
    - NEVER raises: a bad/empty/missing-key state yields None.
    """
    if rng is None:
        rng = _random_module

    try:
        eligible = eligible_templates(dynasty_state)
        if not eligible:
            return None

        if rng.random() >= BASE_TRIGGER_CHANCE:
            return None

        weights = []
        for t in eligible:
            w = t.get("weight", 1.0)
            try:
                w = float(w)
            except (TypeError, ValueError):
                w = 1.0
            if w < 0:
                w = 0.0
            weights.append(w)

        total = sum(weights)
        if total <= 0:
            # All weights zero/invalid: fall back to a uniform pick.
            return rng.choice(eligible)

        # Weighted pick using a single uniform draw (rng.choices may be absent
        # on injected objects, so do it manually for robustness).
        roll = rng.random() * total
        upto = 0.0
        for template, w in zip(eligible, weights):
            upto += w
            if roll < upto:
                return template
        return eligible[-1]
    except Exception:
        logger.debug("maybe_trigger_story_moment failed safe", exc_info=True)
        return None
