"""
Centralised LLM prompt templates for the Royal Succession Simulation.

All prompt-building functions follow the signature:
    def build_<name>_prompt(**kwargs) -> str

Fallback generators are also co-located here so callers never need to
inline prompt logic or fallback strings elsewhere.
"""

from typing import List

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


def build_chronicle_prompt(events: List[str], dynasty_name: str, year: int) -> str:
    """Build a prompt for the living chronicle narrator.

    max_tokens=150. Style: medieval chronicler, 2-3 sentences.
    Fallback: use generate_chronicle_fallback() instead.
    """
    events_str = '; '.join(events) if events else 'a quiet turn with no notable events'
    return (
        f"You are a medieval chronicler writing the official history of {dynasty_name}. "
        f"In the year {year}, the following events transpired: {events_str}. "
        f"Write 2-3 sentences in the style of a medieval chronicle — formal, dramatic, "
        f"third-person. Do not use modern language."
    )


def generate_chronicle_fallback(events: List[str], dynasty_name: str, year: int) -> str:
    """Rule-based fallback when LLM is unavailable."""
    if not events:
        return f"In the year {year}, the annals of {dynasty_name} record a season of quiet governance."
    events_str = ', '.join(events[:3])
    return f"In the year {year}, {dynasty_name} witnessed: {events_str}."


def build_advisor_prompt(dynasty_name: str, year: int, season: str,
                          treasury: float, strongest_neighbour: str,
                          active_wars: int) -> str:
    """Build a prompt for the in-game advisor (Hand of the King).

    max_tokens=200. Returns 2-3 strategic suggestions as a loyal counsellor.
    """
    war_status = f"{active_wars} active war(s)" if active_wars > 0 else "at peace"
    return (
        f"You are the Hand of the King, loyal advisor to {dynasty_name}. "
        f"It is {season} of the year {year}. "
        f"The royal treasury holds {treasury:.0f} gold. "
        f"The strongest neighbouring power is {strongest_neighbour}. "
        f"The kingdom is currently {war_status}.\n\n"
        f"Give exactly 3 strategic suggestions for this turn. "
        f"Format as a numbered list. Be specific, speak as a faithful counsellor would. "
        f"Each suggestion should be one sentence."
    )


def build_battle_commentary_prompt(round_data: dict) -> str:
    """Build a prompt for one-sentence dramatic battle round commentary.

    max_tokens=60. Style: dramatic medieval narrator, one sentence.

    Args:
        round_data: Dict with keys 'round', 'attacker_losses', 'defender_losses'

    Returns:
        Formatted prompt string for LLM
    """
    return (
        f"In one sentence, narrate this medieval battle round dramatically: "
        f"Round {round_data.get('round', '?')}, attacker lost {round_data.get('attacker_losses', 0)} soldiers, "
        f"defender lost {round_data.get('defender_losses', 0)} soldiers. "
        f"Be vivid and concise. Do not start with 'Round'."
    )


def generate_advisor_fallback(treasury: float, active_wars: int, has_allies: bool) -> List[str]:
    """Rule-based fallback suggestions when LLM is unavailable."""
    suggestions = []
    if treasury < 50:
        suggestions.append("Your coffers run dangerously low — levy taxes or sell trade rights before new ventures.")
    if active_wars > 0:
        suggestions.append("Do not open a second front while war already consumes your armies.")
    if not has_allies:
        suggestions.append("Seek allies before your enemies do — even a weak friend is worth having.")
    if treasury >= 200:
        suggestions.append("Your treasury is healthy — consider investing in fortifications or new recruits.")
    if active_wars == 0 and has_allies:
        suggestions.append("Peace reigns — this is the time to build and grow your dynasty's strength.")
    # Ensure we always return at least 2 suggestions
    while len(suggestions) < 2:
        suggestions.append("Govern wisely and your dynasty will endure beyond your years.")
    return suggestions[:3]


def build_turn_story_prompt(dynasty_name, start_year, end_year, events, monarch_name, existing_story):
    events_str = '; '.join(events[:8]) if events else 'quiet seasons of governance'
    continuation_hint = (
        'Continue the saga naturally from where it left off.'
        if existing_story.strip()
        else 'Begin the saga of this dynasty.'
    )
    prev = existing_story[-800:] if existing_story else '(none yet)'
    return (
        f'You are the immortal chronicler of a great dynasty, writing their epic saga.\n'
        f'Dynasty: {dynasty_name}\n'
        f'Current ruler: {monarch_name}\n'
        f'Years {start_year} to {end_year} the following transpired: {events_str}\n\n'
        f'Previous chronicle:\n{prev}\n\n'
        f'{continuation_hint} Write exactly ONE paragraph (4-6 sentences) of vivid, '
        f'high-fantasy prose that weaves these events into the living legend of {dynasty_name}. '
        f'Use dramatic third-person narration. No bullet points, no headings, pure flowing prose only.'
    )


def generate_turn_story_fallback(dynasty_name, start_year, end_year, events, monarch_name):
    if events:
        key_event = events[0]
        return (
            f'In the years {start_year} through {end_year}, the annals of {dynasty_name} record '
            f'the reign of {monarch_name}, under whose stewardship {key_event.lower()} '
            f'The scribes of the realm set down these deeds in ink and candlelight, '
            f'that the glory and the grief of this age might endure beyond the lives of those who lived it.'
        )
    return (
        f'The years {start_year} to {end_year} passed like quiet water beneath the banner of {dynasty_name}. '
        f'{monarch_name} ruled with measured hand, and the realm held its breath.'
    )
