"""Personality-driven AI dynasty controller.

Each non-human dynasty gets one AIController. The controller makes
decisions for all 4 game phases each turn, either via LLM or rule-based
fallback when the LLM is unavailable.

Usage::

    controller = AIController(session, dynasty_id=3,
                              personality="House Vane is paranoid and expansionist.")
    game_state = controller._build_game_state()
    controller.decide_diplomacy(game_state)
    controller.decide_military(game_state)
    controller.decide_economy(game_state)
    controller.decide_character(game_state)
"""

import re
from typing import Dict, Optional, Any

from sqlalchemy.orm import Session

from models.db_models import (
    DynastyDB, PersonDB, Territory, MilitaryUnit, Army,
    DiplomaticRelation, War, BuildingType,
)
from utils.logging_config import setup_logger
from utils.llm_prompts import build_ai_decision_prompt

logger = setup_logger('royal_succession.ai_controller')

# ---------------------------------------------------------------------------
# Available action lists per phase
# ---------------------------------------------------------------------------
_DIPLOMACY_ACTIONS = [
    "propose_nap",
    "propose_alliance",
    "send_envoy",
    "gift",
    "issue_ultimatum",
    "none",
]

_MILITARY_ACTIONS = [
    "recruit_troops",
    "attack",
    "retreat",
    "siege",
    "none",
]

_ECONOMY_ACTIONS = [
    "build_farm",
    "build_market",
    "build_barracks",
    "develop_territory",
    "none",
]

_CHARACTER_ACTIONS = [
    "arrange_marriage",
    "appoint_heir",
    "none",
]


class AIController:
    """Personality-driven decision-maker for a single AI-controlled dynasty.

    Makes decisions for diplomacy, military, economy, and character phases
    each turn. When an LLM model is available the controller calls it with the
    dynasty's personality string and current game state; otherwise it falls
    back to deterministic rule-based logic so the game remains fully playable
    without an API key.
    """

    def __init__(self, session: Session, dynasty_id: int, personality: str) -> None:
        """Initialise the controller.

        Args:
            session: SQLAlchemy database session (no Flask context needed).
            dynasty_id: Primary key of the dynasty this controller governs.
            personality: One-sentence personality description used in LLM prompts.
        """
        self.session = session
        self.dynasty_id = dynasty_id
        self.personality = personality
        self._dynasty_name: Optional[str] = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Public phase methods
    # ------------------------------------------------------------------

    def decide_diplomacy(self, game_state: dict) -> Dict[str, Any]:
        """Choose a diplomatic action for this turn.

        Rule-based fallback logic:
        - relations < -50 AND own army weaker → propose_nap with weakest enemy
        - relations > 60 AND no existing alliance → propose_alliance with friendliest
        - otherwise → none

        Args:
            game_state: State dict from :meth:`_build_game_state`.

        Returns:
            ``{'action': str, 'target_id': int | None}``
        """
        dynasty_name = self._get_dynasty_name()

        # Try LLM path first
        llm_action = self._llm_decide('diplomacy', game_state, _DIPLOMACY_ACTIONS)
        if llm_action:
            action = llm_action.get('action', 'none')
            target_id = llm_action.get('target_id')
            logger.info(
                f"{dynasty_name} [diplomacy]: {action} (target={target_id}) — LLM decision"
            )
            return {'action': action, 'target_id': target_id}

        # Rule-based fallback
        result = self._fallback_diplomacy()
        logger.info(
            f"{dynasty_name} [diplomacy]: {result['action']} "
            f"(target={result['target_id']}) — rule-based fallback"
        )
        return result

    def decide_military(self, game_state: dict) -> Dict[str, Any]:
        """Choose a military action for this turn.

        Rule-based fallback logic:
        - own army > 1.5× nearest enemy AND active war → attack enemy capital
        - under attack AND own army < enemy army → retreat
        - otherwise → none

        Args:
            game_state: State dict from :meth:`_build_game_state`.

        Returns:
            ``{'action': str, 'target_id': int | None}``
        """
        dynasty_name = self._get_dynasty_name()

        llm_action = self._llm_decide('military', game_state, _MILITARY_ACTIONS)
        if llm_action:
            action = llm_action.get('action', 'none')
            target_id = llm_action.get('target_id')
            logger.info(
                f"{dynasty_name} [military]: {action} (target={target_id}) — LLM decision"
            )
            return {'action': action, 'target_id': target_id}

        result = self._fallback_military()
        logger.info(
            f"{dynasty_name} [military]: {result['action']} "
            f"(target={result['target_id']}) — rule-based fallback"
        )
        return result

    def decide_economy(self, game_state: dict) -> Dict[str, Any]:
        """Choose an economic action for this turn.

        Rule-based fallback logic:
        - food resources < 20 % of food capacity → build_farm
        - treasury < 50 → build_market
        - otherwise → build_barracks

        Args:
            game_state: State dict from :meth:`_build_game_state`.

        Returns:
            ``{'action': str, 'building_type': str | None}``
        """
        dynasty_name = self._get_dynasty_name()

        llm_action = self._llm_decide('economy', game_state, _ECONOMY_ACTIONS)
        if llm_action:
            action = llm_action.get('action', 'none')
            building_type = llm_action.get('building_type')
            logger.info(
                f"{dynasty_name} [economy]: {action} "
                f"(building={building_type}) — LLM decision"
            )
            return {'action': action, 'building_type': building_type}

        result = self._fallback_economy(game_state)
        logger.info(
            f"{dynasty_name} [economy]: {result['action']} "
            f"(building={result['building_type']}) — rule-based fallback"
        )
        return result

    def decide_character(self, game_state: dict) -> Dict[str, Any]:
        """Choose a character / succession action for this turn.

        Rule-based fallback logic:
        - leader age > 55 AND no heir → arrange_marriage for eldest child
        - otherwise → none

        Args:
            game_state: State dict from :meth:`_build_game_state`.

        Returns:
            ``{'action': str, 'person_id': int | None}``
        """
        dynasty_name = self._get_dynasty_name()

        llm_action = self._llm_decide('character', game_state, _CHARACTER_ACTIONS)
        if llm_action:
            action = llm_action.get('action', 'none')
            person_id = llm_action.get('person_id')
            logger.info(
                f"{dynasty_name} [character]: {action} "
                f"(person={person_id}) — LLM decision"
            )
            return {'action': action, 'person_id': person_id}

        result = self._fallback_character(game_state)
        logger.info(
            f"{dynasty_name} [character]: {result['action']} "
            f"(person={result['person_id']}) — rule-based fallback"
        )
        return result

    # ------------------------------------------------------------------
    # State builder
    # ------------------------------------------------------------------

    def _build_game_state(self) -> dict:
        """Query the DB and return a summary dict suitable for LLM prompts.

        Returns:
            Dictionary with keys: dynasty_id, dynasty_name, year, season,
            treasury, army_size, territory_count, active_wars, monarch_age,
            monarch_id, has_heir, relations.
        """
        state: Dict[str, Any] = {
            'dynasty_id': self.dynasty_id,
            'dynasty_name': self._get_dynasty_name(),
            'year': 1000,
            'season': 'Spring',
            'treasury': 0,
            'army_size': 0,
            'territory_count': 0,
            'active_wars': 0,
            'monarch_age': 0,
            'monarch_id': None,
            'has_heir': False,
            'relations': {},
        }

        try:
            dynasty = self.session.query(DynastyDB).get(self.dynasty_id)
            if dynasty is None:
                logger.warning(f"AIController._build_game_state: dynasty {self.dynasty_id} not found")
                return state

            state['dynasty_name'] = dynasty.name
            state['year'] = dynasty.current_simulation_year
            state['treasury'] = dynasty.current_wealth

            # Territory count
            territory_count = self.session.query(Territory).filter_by(
                controller_dynasty_id=self.dynasty_id
            ).count()
            state['territory_count'] = territory_count

            # Army size (total troops across all units)
            units = self.session.query(MilitaryUnit).filter_by(
                dynasty_id=self.dynasty_id
            ).all()
            state['army_size'] = sum(u.size for u in units)

            # Active wars
            active_wars = self.session.query(War).filter(
                ((War.attacker_dynasty_id == self.dynasty_id) |
                 (War.defender_dynasty_id == self.dynasty_id)),
                War.is_active == True  # noqa: E712
            ).count()
            state['active_wars'] = active_wars

            # Monarch info
            monarch = self.session.query(PersonDB).filter_by(
                dynasty_id=self.dynasty_id, is_monarch=True, death_year=None
            ).first()
            if monarch:
                state['monarch_id'] = monarch.id
                state['monarch_age'] = state['year'] - monarch.birth_year
                # Check for heir: any living non-monarch member
                heir = self.session.query(PersonDB).filter(
                    PersonDB.dynasty_id == self.dynasty_id,
                    PersonDB.is_monarch == False,  # noqa: E712
                    PersonDB.death_year == None,  # noqa: E711
                    PersonDB.id != monarch.id,
                ).first()
                state['has_heir'] = heir is not None

            # Relations summary (other dynasty id → score)
            outgoing = self.session.query(DiplomaticRelation).filter_by(
                dynasty1_id=self.dynasty_id
            ).all()
            incoming = self.session.query(DiplomaticRelation).filter_by(
                dynasty2_id=self.dynasty_id
            ).all()
            relations: Dict[int, int] = {}
            for rel in outgoing:
                relations[rel.dynasty2_id] = rel.relation_score
            for rel in incoming:
                if rel.dynasty1_id not in relations:
                    relations[rel.dynasty1_id] = rel.relation_score
            state['relations'] = relations

        except Exception as exc:
            logger.error(f"AIController._build_game_state error for dynasty {self.dynasty_id}: {exc}")

        return state

    # ------------------------------------------------------------------
    # LLM helper
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the LLM and return the raw response text, or None if unavailable.

        Args:
            prompt: The full prompt string to send.

        Returns:
            Response text stripped of leading/trailing whitespace, or None.
        """
        # Import lazily to avoid circular import issues at module load time
        try:
            from utils.helpers import LLM_MODEL_GLOBAL as llm_model  # type: ignore
        except ImportError:
            llm_model = None

        if llm_model is None:
            return None

        try:
            response = llm_model.generate_content(
                prompt,
                generation_config={'max_output_tokens': 100},
            )
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
        except Exception as exc:
            logger.warning(f"AIController LLM call failed: {exc}")

        return None

    def _llm_decide(self, phase: str, game_state: dict, actions: list) -> Optional[Dict[str, Any]]:
        """Build a prompt, call the LLM, and parse the result.

        Returns a dict with at least ``'action'`` key, or None if LLM
        is unavailable or parsing fails.
        """
        prompt = build_ai_decision_prompt(
            phase=phase,
            game_state=game_state,
            personality=self.personality,
            available_actions=actions,
        )
        raw = self._call_llm(prompt)
        if raw is None:
            return None

        # Parse "ACTION: <x> | REASON: <reason>"
        action_match = re.search(r'ACTION\s*:\s*([^|]+)', raw, re.IGNORECASE)
        reason_match = re.search(r'REASON\s*:\s*(.+)', raw, re.IGNORECASE)

        action_text = action_match.group(1).strip().lower() if action_match else 'none'
        reason_text = reason_match.group(1).strip() if reason_match else raw[:120]

        # Normalise action to snake_case and validate against known actions
        action_normalised = action_text.replace(' ', '_').replace('-', '_')
        valid_action = action_normalised if action_normalised in [a.lower() for a in actions] else 'none'

        dynasty_name = self._get_dynasty_name()
        logger.info(f"{dynasty_name} [{phase}]: {valid_action} — {reason_text}")

        return {'action': valid_action, 'target_id': None, 'building_type': None, 'person_id': None}

    # ------------------------------------------------------------------
    # Rule-based fallback implementations
    # ------------------------------------------------------------------

    def _fallback_diplomacy(self) -> Dict[str, Any]:
        """Deterministic diplomacy decision when LLM is unavailable."""
        try:
            own_units = self.session.query(MilitaryUnit).filter_by(
                dynasty_id=self.dynasty_id
            ).all()
            own_strength = sum(u.size for u in own_units)

            # Gather all relations
            outgoing = self.session.query(DiplomaticRelation).filter_by(
                dynasty1_id=self.dynasty_id
            ).all()
            incoming = self.session.query(DiplomaticRelation).filter_by(
                dynasty2_id=self.dynasty_id
            ).all()

            relations: Dict[int, int] = {}
            for rel in outgoing:
                relations[rel.dynasty2_id] = rel.relation_score
            for rel in incoming:
                if rel.dynasty1_id not in relations:
                    relations[rel.dynasty1_id] = rel.relation_score

            # Check for very hostile relations where we are weaker
            for other_id, score in relations.items():
                if score < -50:
                    other_units = self.session.query(MilitaryUnit).filter_by(
                        dynasty_id=other_id
                    ).all()
                    other_strength = sum(u.size for u in other_units)
                    if own_strength < other_strength:
                        return {'action': 'propose_nap', 'target_id': other_id}

            # Check for potential alliance
            best_friend_id: Optional[int] = None
            best_score = 60  # threshold
            for other_id, score in relations.items():
                if score > best_score:
                    best_score = score
                    best_friend_id = other_id

            if best_friend_id is not None:
                return {'action': 'propose_alliance', 'target_id': best_friend_id}

        except Exception as exc:
            logger.error(f"_fallback_diplomacy error for dynasty {self.dynasty_id}: {exc}")

        return {'action': 'none', 'target_id': None}

    def _fallback_military(self) -> Dict[str, Any]:
        """Deterministic military decision when LLM is unavailable."""
        try:
            own_units = self.session.query(MilitaryUnit).filter_by(
                dynasty_id=self.dynasty_id
            ).all()
            own_strength = sum(u.size for u in own_units)

            # Check for active wars
            active_war = self.session.query(War).filter(
                ((War.attacker_dynasty_id == self.dynasty_id) |
                 (War.defender_dynasty_id == self.dynasty_id)),
                War.is_active == True  # noqa: E712
            ).first()

            if active_war:
                # Determine the enemy dynasty
                if active_war.attacker_dynasty_id == self.dynasty_id:
                    enemy_id = active_war.defender_dynasty_id
                else:
                    enemy_id = active_war.attacker_dynasty_id

                enemy_units = self.session.query(MilitaryUnit).filter_by(
                    dynasty_id=enemy_id
                ).all()
                enemy_strength = sum(u.size for u in enemy_units)

                if own_strength > enemy_strength * 1.5:
                    # Find enemy capital
                    capital = self.session.query(Territory).filter_by(
                        controller_dynasty_id=enemy_id, is_capital=True
                    ).first()
                    if capital is None:
                        capital = self.session.query(Territory).filter_by(
                            controller_dynasty_id=enemy_id
                        ).first()
                    target_id = capital.id if capital else None
                    return {'action': 'attack', 'target_id': target_id}

                if own_strength < enemy_strength:
                    return {'action': 'retreat', 'target_id': None}

        except Exception as exc:
            logger.error(f"_fallback_military error for dynasty {self.dynasty_id}: {exc}")

        return {'action': 'none', 'target_id': None}

    def _fallback_economy(self, game_state: dict) -> Dict[str, Any]:
        """Deterministic economy decision when LLM is unavailable."""
        try:
            treasury = game_state.get('treasury', 0)

            # Rough heuristic: check food resources vs territory count as capacity proxy
            territory_count = game_state.get('territory_count', 1) or 1
            # We don't have a direct food stockpile counter easily; use a simple
            # treasury/capacity proxy based on territories
            food_capacity_proxy = territory_count * 100
            # Query TerritoryResource for food would require more joins; use simplified check
            if treasury < food_capacity_proxy * 0.2:
                return {'action': 'build', 'building_type': BuildingType.FARM.value}
            if treasury < 50:
                return {'action': 'build', 'building_type': BuildingType.MARKET.value}
            return {'action': 'build', 'building_type': BuildingType.BARRACKS.value}

        except Exception as exc:
            logger.error(f"_fallback_economy error for dynasty {self.dynasty_id}: {exc}")

        return {'action': 'build', 'building_type': BuildingType.BARRACKS.value}

    def _fallback_character(self, game_state: dict) -> Dict[str, Any]:
        """Deterministic character decision when LLM is unavailable."""
        try:
            monarch_age = game_state.get('monarch_age', 0)
            has_heir = game_state.get('has_heir', True)

            if monarch_age > 55 and not has_heir:
                # Find eldest child to arrange a marriage for
                monarch_id = game_state.get('monarch_id')
                if monarch_id:
                    child = self.session.query(PersonDB).filter(
                        (PersonDB.father_sim_id == monarch_id) |
                        (PersonDB.mother_sim_id == monarch_id),
                        PersonDB.death_year == None,  # noqa: E711
                    ).order_by(PersonDB.birth_year).first()
                    if child:
                        return {'action': 'arrange_marriage', 'person_id': child.id}

        except Exception as exc:
            logger.error(f"_fallback_character error for dynasty {self.dynasty_id}: {exc}")

        return {'action': 'none', 'person_id': None}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_dynasty_name(self) -> str:
        """Return the dynasty name, caching after the first DB hit."""
        if self._dynasty_name is None:
            try:
                dynasty = self.session.query(DynastyDB).get(self.dynasty_id)
                self._dynasty_name = dynasty.name if dynasty else f"Dynasty#{self.dynasty_id}"
            except Exception:
                self._dynasty_name = f"Dynasty#{self.dynasty_id}"
        return self._dynasty_name
