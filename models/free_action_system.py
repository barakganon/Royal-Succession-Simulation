# models/free_action_system.py
"""
Free Action system (Story 4-1).

Provides a single dispatcher, :class:`FreeActionSystem`, that performs an
out-of-turn ("free") action for a dynasty. Free actions do NOT tick the turn:
they never modify ``current_simulation_year``. Diplomatic actions delegate to
the existing :class:`DiplomacySystem` (we do not reimplement diplomacy here).

Every successful action appends a deterministic ``HistoryLogEntryDB`` with
``event_type='free_action'`` to the session (the route is responsible for
committing — this module never commits).

Frozen contract (route + tests depend on these exact names):
    from models.free_action_system import FreeActionSystem, VALID_FREE_ACTIONS
    FreeActionSystem(session)
    perform_free_action(dynasty_id, action_type, params) -> (ok, message)
"""

import logging
from typing import Tuple

from sqlalchemy.orm import Session

from models.db_models import (
    DynastyDB, PersonDB, HistoryLogEntryDB, TreatyType, WarGoal,
)
from models.diplomacy_system import DiplomacySystem

logger = logging.getLogger('royal_succession.free_action_system')

# Frozen list of accepted free-action types.
VALID_FREE_ACTIONS = [
    'declare_war',
    'propose_treaty',
    'send_envoy',
    'issue_ultimatum',
    'name_heir',
    'adopt_succession_law',
    'hold_feast',
    'hold_tournament',
    'pardon_vassal',
]

# Accepted succession laws for the `adopt_succession_law` action.
VALID_SUCCESSION_LAWS = [
    'PRIMOGENITURE_MALE_PREFERENCE',
    'PRIMOGENITURE_ABSOLUTE',
    'ELECTIVE',
    'SENIORITY',
]


class FreeActionSystem:
    """Dispatches out-of-turn free actions for a dynasty."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------ #
    # Public dispatcher
    # ------------------------------------------------------------------ #
    def perform_free_action(
        self, dynasty_id: int, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        """
        Perform a free action.

        Args:
            dynasty_id: ID of the acting dynasty.
            action_type: One of ``VALID_FREE_ACTIONS``.
            params: Action-specific parameters.

        Returns:
            ``(ok, message)``.
        """
        params = params or {}

        if action_type not in VALID_FREE_ACTIONS:
            return False, f"Unknown free action: {action_type}"

        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if dynasty is None:
            return False, f"Dynasty {dynasty_id} not found"

        handler = {
            'declare_war': self._declare_war,
            'propose_treaty': self._propose_treaty,
            'send_envoy': self._diplomatic_action,
            'issue_ultimatum': self._diplomatic_action,
            'name_heir': self._name_heir,
            'adopt_succession_law': self._adopt_succession_law,
            'hold_feast': self._hold_feast,
            'hold_tournament': self._hold_tournament,
            'pardon_vassal': self._pardon_vassal,
        }[action_type]

        return handler(dynasty, action_type, params)

    # ------------------------------------------------------------------ #
    # Chronicle helper (AC4)
    # ------------------------------------------------------------------ #
    def _append_chronicle(self, dynasty: DynastyDB, event_string: str) -> None:
        """Queue a deterministic free-action history entry. Does NOT commit."""
        entry = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=dynasty.current_simulation_year,
            event_string=event_string,
            event_type='free_action',
        )
        self.session.add(entry)
        logger.info(
            "Free-action chronicle queued for dynasty %s (year %s): %s",
            dynasty.id, dynasty.current_simulation_year, event_string,
        )

    # ------------------------------------------------------------------ #
    # Diplomatic actions — delegate to DiplomacySystem
    # ------------------------------------------------------------------ #
    def _declare_war(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        target_id = params.get('target_dynasty_id')
        if target_id is None:
            return False, "declare_war requires 'target_dynasty_id'"

        diplomacy = DiplomacySystem(self.session)
        result = diplomacy.declare_war(
            attacker_dynasty_id=dynasty.id,
            defender_dynasty_id=target_id,
            war_goal=WarGoal.HUMILIATE,
        )
        ok, message = self._normalize(result)
        if ok:
            self._append_chronicle(
                dynasty,
                f"{dynasty.name} declared war upon dynasty {target_id}.",
            )
        return ok, message

    def _propose_treaty(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        target_id = params.get('target_dynasty_id')
        if target_id is None:
            return False, "propose_treaty requires 'target_dynasty_id'"

        treaty_type = self._resolve_treaty_type(params.get('treaty_type'))

        diplomacy = DiplomacySystem(self.session)
        result = diplomacy.create_treaty(
            dynasty1_id=dynasty.id,
            dynasty2_id=target_id,
            treaty_type=treaty_type,
        )
        ok, message = self._normalize(result)
        if ok:
            self._append_chronicle(
                dynasty,
                f"{dynasty.name} proposed a {treaty_type.value} treaty "
                f"to dynasty {target_id}.",
            )
        return ok, message

    def _diplomatic_action(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        """Handles send_envoy and issue_ultimatum."""
        target_id = params.get('target_dynasty_id')
        if target_id is None:
            return False, f"{action_type} requires 'target_dynasty_id'"

        diplomacy = DiplomacySystem(self.session)
        result = diplomacy.perform_diplomatic_action(
            actor_dynasty_id=dynasty.id,
            target_dynasty_id=target_id,
            action_type=action_type,
        )
        ok, message = self._normalize(result)
        if ok:
            verb = "sent an envoy to" if action_type == 'send_envoy' \
                else "issued an ultimatum to"
            self._append_chronicle(
                dynasty,
                f"{dynasty.name} {verb} dynasty {target_id}.",
            )
        return ok, message

    # ------------------------------------------------------------------ #
    # Succession actions
    # ------------------------------------------------------------------ #
    def _name_heir(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        heir_id = params.get('heir_person_id')
        if heir_id is None:
            return False, "name_heir requires 'heir_person_id'"

        heir = self.session.query(PersonDB).get(heir_id)
        if heir is None:
            return False, f"Person {heir_id} not found"
        if heir.dynasty_id != dynasty.id:
            return False, f"Person {heir_id} does not belong to dynasty {dynasty.id}"
        if heir.death_year is not None:
            return False, f"Person {heir_id} is deceased and cannot be named heir"

        dynasty.designated_heir_id = heir.id
        self._append_chronicle(
            dynasty,
            f"{dynasty.name} named {heir.name} as designated heir.",
        )
        return True, f"{heir.name} has been named heir."

    def _adopt_succession_law(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        law = params.get('law')
        if law is None:
            return False, "adopt_succession_law requires 'law'"
        if law not in VALID_SUCCESSION_LAWS:
            return False, f"Invalid succession law: {law}"

        dynasty.succession_law = law
        self._append_chronicle(
            dynasty,
            f"{dynasty.name} adopted the {law} succession law.",
        )
        return True, f"Succession law set to {law}."

    # ------------------------------------------------------------------ #
    # Court / prestige actions
    # ------------------------------------------------------------------ #
    def _hold_feast(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        cost = 30
        if dynasty.current_wealth < cost:
            return False, f"Cannot afford feast (need {cost} gold)"

        dynasty.current_wealth -= cost
        dynasty.prestige = (dynasty.prestige or 0) + 5
        self._append_chronicle(
            dynasty,
            f"{dynasty.name} held a grand feast, gaining prestige.",
        )
        return True, "A grand feast was held (+5 prestige)."

    def _hold_tournament(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        cost = 50
        if dynasty.current_wealth < cost:
            return False, f"Cannot afford tournament (need {cost} gold)"

        dynasty.current_wealth -= cost
        dynasty.prestige = (dynasty.prestige or 0) + 10
        self._append_chronicle(
            dynasty,
            f"{dynasty.name} held a grand tournament, gaining prestige.",
        )
        return True, "A grand tournament was held (+10 prestige)."

    def _pardon_vassal(
        self, dynasty: DynastyDB, action_type: str, params: dict
    ) -> Tuple[bool, str]:
        dynasty.honor = min(100, (dynasty.honor or 0) + 5)
        self._append_chronicle(
            dynasty,
            f"{dynasty.name} pardoned a vassal, gaining honor.",
        )
        return True, "A vassal was pardoned (+5 honor)."

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(result) -> Tuple[bool, str]:
        """Normalize ``(ok, msg)`` or ``(ok, msg, obj)`` to ``(ok, msg)``."""
        ok = bool(result[0])
        message = result[1] if len(result) > 1 else ""
        return ok, message

    @staticmethod
    def _resolve_treaty_type(raw) -> TreatyType:
        """Resolve a treaty type from params, defaulting to NON_AGGRESSION."""
        if isinstance(raw, TreatyType):
            return raw
        if isinstance(raw, str):
            # Accept either the enum name or the enum value.
            by_name = getattr(TreatyType, raw.upper(), None)
            if isinstance(by_name, TreatyType):
                return by_name
            for member in TreatyType:
                if member.value == raw:
                    return member
        return TreatyType.NON_AGGRESSION
