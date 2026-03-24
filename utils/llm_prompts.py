"""Central repository for all LLM prompt templates.

All prompt functions follow the signature:
    def build_<name>_prompt(**kwargs) -> str
"""
from utils.logging_config import setup_logger

logger = setup_logger('royal_succession.llm_prompts')


def build_ai_decision_prompt(phase: str, game_state: dict, personality: str, available_actions: list) -> str:
    """Build a prompt for AI dynasty decision-making.

    max_tokens=100 for all AI decision calls.

    Args:
        phase: Current game phase (diplomacy, military, economy, character)
        game_state: Dictionary summarising the dynasty's current situation
        personality: One-sentence personality string for this AI dynasty
        available_actions: List of action name strings the AI may choose

    Returns:
        Formatted prompt string
    """
    actions_str = '\n'.join(f"- {a}" for a in available_actions)
    return (
        f"You are the ruling dynasty of a medieval kingdom. Your personality: {personality}\n\n"
        f"Current situation ({phase} phase):\n"
        f"Year: {game_state.get('year', 'unknown')}, Season: {game_state.get('season', 'unknown')}\n"
        f"Treasury: {game_state.get('treasury', 0)} gold, "
        f"Army size: {game_state.get('army_size', 0)}, "
        f"Territories: {game_state.get('territory_count', 0)}\n"
        f"Active wars: {game_state.get('active_wars', 0)}\n\n"
        f"Available actions:\n{actions_str}\n\n"
        f"Choose ONE action and briefly explain why (1 sentence). "
        f"Reply format: ACTION: <action name> | REASON: <reason>"
    )


def build_chronicle_prompt(dynasty_name: str, year: int, season: str, events: list) -> str:
    """Build a prompt for generating a chronicle entry after a turn.

    max_tokens=150 for chronicle calls.

    Args:
        dynasty_name: Name of the dynasty being chronicled
        year: Game year of the turn
        season: Current season string
        events: List of event description strings from the turn

    Returns:
        Formatted prompt string
    """
    events_str = '\n'.join(f"- {e}" for e in events) if events else "- No notable events this turn."
    return (
        f"You are a medieval chronicler recording the history of House {dynasty_name}.\n\n"
        f"In the {season} of the year {year}, the following events occurred:\n"
        f"{events_str}\n\n"
        f"Write 2-3 sentences in the style of a medieval chronicler narrating these events. "
        f"Be evocative and avoid anachronisms. Do not merely list the events — interpret them "
        f"into a flowing narrative passage."
    )


def build_advisor_prompt(dynasty_name: str, year: int, season: str, treasury: int,
                         army_size: int, strongest_neighbour: str, active_wars: int,
                         relation_summary: str) -> str:
    """Build a prompt for the in-game AI advisor (Hand of the King).

    max_tokens=200 for advisor calls.

    Args:
        dynasty_name: The player's dynasty name
        year: Current game year
        season: Current season string
        treasury: Current gold in treasury
        army_size: Total number of troops
        strongest_neighbour: Name of the most powerful neighbouring dynasty
        active_wars: Number of ongoing wars
        relation_summary: Brief text describing current diplomatic posture

    Returns:
        Formatted prompt string
    """
    return (
        f"You are the trusted Hand of the King, counsellor to House {dynasty_name}.\n\n"
        f"Current situation — Year {year}, {season}:\n"
        f"  Treasury: {treasury} gold\n"
        f"  Military strength: {army_size} troops\n"
        f"  Most powerful neighbour: {strongest_neighbour}\n"
        f"  Active wars: {active_wars}\n"
        f"  Diplomatic posture: {relation_summary}\n\n"
        f"Provide 2-3 prioritised strategic suggestions written in character as a loyal counsellor. "
        f"Number each suggestion. Be concise and specific. Focus on the most pressing threats and "
        f"opportunities given the current situation."
    )
