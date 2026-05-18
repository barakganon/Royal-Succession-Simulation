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


def build_turn_story_prompt(dynasty_name, start_year, end_year, events, monarch_name, existing_story,
                            years_advanced: int = 5, interrupt_reason: str = 'quiet_period'):
    events_str = '; '.join(events[:8]) if events else 'quiet seasons of governance'
    continuation_hint = (
        'Continue the saga naturally from where it left off.'
        if existing_story.strip()
        else 'Begin the saga of this dynasty.'
    )
    prev = existing_story[-800:] if existing_story else '(none yet)'
    year_span = f'{years_advanced} year{"s" if years_advanced != 1 else ""}'
    reason_human = interrupt_reason.replace('_', ' ')
    pacing_hint = f'This turn spanned {year_span}. It ended because: {reason_human}. '
    if interrupt_reason == 'monarch_death':
        pacing_hint += "The shadow of the ruler's death defines this passage — write it accordingly. "
    elif interrupt_reason == 'quiet_period':
        pacing_hint += 'These were peaceful, uneventful seasons. '
    return (
        f'You are the immortal chronicler of a great dynasty, writing their epic saga.\n'
        f'Dynasty: {dynasty_name}\n'
        f'Current ruler: {monarch_name}\n'
        f'Years {start_year} to {end_year} the following transpired: {events_str}\n\n'
        f'Previous chronicle:\n{prev}\n\n'
        f'{continuation_hint} {pacing_hint}Write exactly ONE paragraph (4-6 sentences) of vivid, '
        f'high-fantasy prose that weaves these events into the living legend of {dynasty_name}. '
        f'Use dramatic third-person narration. No bullet points, no headings, pure flowing prose only.'
    )


def generate_turn_story_fallback(dynasty_name, start_year, end_year, events, monarch_name,
                                 years_advanced: int = 5, interrupt_reason: str = 'quiet_period'):
    year_word = 'year' if years_advanced == 1 else 'years'
    if interrupt_reason == 'monarch_death':
        key_event = events[0].lower() if events else 'the realm fell into mourning.'
        return (
            f'In the {years_advanced} {year_word} before the passing of {monarch_name}, '
            f'{dynasty_name} was marked by {key_event} '
            f'When the end came, the realm fell silent, and the scribes set down their quills '
            f'to mourn before returning to record what followed.'
        )
    if events:
        key_event = events[0]
        return (
            f'Across the {years_advanced} {year_word} from {start_year} through {end_year}, '
            f'the annals of {dynasty_name} record the reign of {monarch_name}, under whose stewardship '
            f'{key_event.lower()} The scribes of the realm set down these deeds in ink and candlelight, '
            f'that the glory and the grief of this age might endure beyond the lives of those who lived it.'
        )
    return (
        f'The {years_advanced} {year_word} from {start_year} to {end_year} passed like quiet water '
        f'beneath the banner of {dynasty_name}. '
        f'{monarch_name} ruled with measured hand, and the realm held its breath.'
    )


# ---------------------------------------------------------------------------
# Multi-generation project completion (Sprint 2 Story 2-4)
# ---------------------------------------------------------------------------
_PROJECT_LABELS = {
    'build_farm': 'Farm',
    'build_walls': 'Walls',
    'build_cathedral': 'Cathedral',
    'develop_territory': 'territory development',
    'recruit_infantry': 'levy',
    'recruit_cavalry': 'cavalry',
    'envoy_mission': 'envoy mission',
    'march_army_cross_realm': 'cross-realm march',
}


def _project_label(project_type: str) -> str:
    return _PROJECT_LABELS.get(project_type, project_type.replace('_', ' '))


# Sprint 3 Story 3-2: imperative menu labels (Build / Recruit / Develop ...).
# Distinct from _PROJECT_LABELS — the chronicle wants noun phrases ("Farm
# stands"), the right-click menu wants verb phrases ("Build Farm").
_PROJECT_MENU_LABELS = {
    'build_farm': 'Build Farm',
    'build_walls': 'Build Walls',
    'build_cathedral': 'Build Cathedral',
    'develop_territory': 'Develop Territory',
    'recruit_infantry': 'Recruit Infantry',
    'recruit_cavalry': 'Recruit Cavalry',
    'envoy_mission': 'Send Envoy',
    'march_army_cross_realm': 'March Army',
}


def project_menu_label(project_type: str) -> str:
    """Public accessor — imperative label for the right-click menu."""
    return _PROJECT_MENU_LABELS.get(
        project_type, project_type.replace('_', ' ').title()
    )


def build_multigen_project_completion_prompt(project_type: str, initiator_name: str,
                                             completer_name: str, dynasty_name: str,
                                             started_year: int, completion_year: int) -> str:
    """Prompt for the multi-generational project completion chronicle line.

    max_tokens=100. Style: medieval chronicler, 2-3 sentences.
    Fallback: generate_multigen_project_completion_fallback().
    """
    label = _project_label(project_type)
    years = completion_year - started_year
    return (
        f"You are a medieval chronicler of {dynasty_name}. "
        f"The {label} project was begun by {initiator_name} in the year {started_year} "
        f"and finally completed by {completer_name} in the year {completion_year} "
        f"({years} years later, under a different ruler). "
        f"Write exactly 2-3 sentences in the style of a medieval chronicle — formal, "
        f"dramatic, third-person. Mention both rulers by name. Do not use modern language."
    )


def generate_multigen_project_completion_fallback(project_type: str, initiator_name: str,
                                                  completer_name: str, dynasty_name: str,
                                                  started_year: int, completion_year: int) -> str:
    """Rule-based fallback when LLM is unavailable.

    Returns the master-plan template: "What X began, Y finished — the [label] stands."
    """
    label = _project_label(project_type)
    return (
        f"What {initiator_name} began in {started_year}, "
        f"{completer_name} finished in {completion_year} — the {label} stands."
    )
