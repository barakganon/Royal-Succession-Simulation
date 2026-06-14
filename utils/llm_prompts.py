"""
Centralised LLM prompt templates for the Royal Succession Simulation.

All prompt-building functions follow the signature:
    def build_<name>_prompt(**kwargs) -> str

Fallback generators are also co-located here so callers never need to
inline prompt logic or fallback strings elsewhere.
"""

from typing import List, Optional

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


def build_chronicle_prompt(events: List[str], dynasty_name: str, year: int,
                           monarch_traits: Optional[list] = None) -> str:
    """Build a prompt for the living chronicle narrator.

    max_tokens=150. Style: medieval chronicler, 2-3 sentences.
    Fallback: use generate_chronicle_fallback() instead.

    Args:
        monarch_traits: Optional list of trait names for the reigning monarch.
            When truthy, a voice instruction reflecting those traits is appended.
            None/empty leaves the prompt unchanged.
    """
    events_str = '; '.join(events) if events else 'a quiet turn with no notable events'
    voice_instruction = ""
    if monarch_traits:
        traits_str = ', '.join(str(t) for t in monarch_traits)
        voice_instruction = (
            f" The reigning monarch is {traits_str} — let the telling reflect that character."
        )
    return (
        f"You are a medieval chronicler writing the official history of {dynasty_name}. "
        f"In the year {year}, the following events transpired: {events_str}. "
        f"Write 2-3 sentences in the style of a medieval chronicle — formal, dramatic, "
        f"third-person. Do not use modern language.{voice_instruction}"
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
                            years_advanced: int = 5, interrupt_reason: str = 'quiet_period',
                            monarch_traits: Optional[list] = None):
    events_str = '; '.join(events[:8]) if events else 'quiet seasons of governance'
    voice_instruction = ""
    if monarch_traits:
        traits_str = ', '.join(str(t) for t in monarch_traits)
        voice_instruction = (
            f" The reigning monarch is {traits_str} — let the telling reflect that character."
        )
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
        f'{voice_instruction}'
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


# --------------------------------------------------------------------------- #
# Story 7-2: AI marriage decision + wedding chronicle
# --------------------------------------------------------------------------- #

def build_marriage_decision_prompt(personality: str, dynasty_name: str,
                                   relation_score: int, proposer_prestige: float,
                                   own_prestige: float) -> str:
    """Prompt asking the AI dynasty to accept or reject a marriage proposal.

    Story 7-2. max_tokens<=100. The model must answer with a single line:
    ``DECISION: accept`` or ``DECISION: reject``. Fallback (when the LLM is
    unavailable or unparseable): the rule baseline in
    :meth:`AIController.decide_marriage_response`.
    """
    return (
        f"You rule House {dynasty_name}. Personality: {personality} "
        f"A rival house proposes a marriage alliance. "
        f"Your relations with them score {relation_score} "
        f"(below -20 is hostile). Their prestige is {proposer_prestige}; "
        f"yours is {own_prestige}. A wealthier, higher-prestige suitor or a "
        f"friendly neighbour is worth accepting; a hated rival is not. "
        f"Answer with exactly one line: 'DECISION: accept' or 'DECISION: reject'."
    )


def build_wedding_chronicle_prompt(spouse1_name: str, spouse1_traits,
                                   spouse2_name: str, spouse2_traits,
                                   house1: str, house2: str, year: int) -> str:
    """Prompt for a medieval wedding announcement chronicle line.

    Story 7-2. max_tokens<=150. Style: medieval chronicler, third-person,
    2-3 sentences. Names both spouses and both houses, references their traits.
    Fallback: generate_wedding_fallback().
    """
    traits1 = _format_traits(spouse1_traits)
    traits2 = _format_traits(spouse2_traits)
    return (
        f"You are a medieval chronicler recording a royal wedding in the year {year}. "
        f"{spouse1_name} of House {house1} (known for being {traits1}) "
        f"weds {spouse2_name} of House {house2} (known for being {traits2}), "
        f"binding the two houses in alliance. "
        f"Write exactly 2-3 sentences in the style of a medieval chronicle — formal, "
        f"dramatic, third-person. Name both spouses and both houses, and allude to "
        f"their natures. Do not use modern language or lists."
    )


def generate_wedding_fallback(spouse1_name: str, spouse2_name: str,
                              house1: str, house2: str, year: int) -> str:
    """Deterministic, non-empty fallback for the wedding chronicle (Story 7-2).

    Always names both spouses, both houses, and the year.
    """
    return (
        f"In the year {year}, {spouse1_name} of House {house1} was wed to "
        f"{spouse2_name} of House {house2}, and the two houses were joined in "
        f"solemn alliance."
    )


# --------------------------------------------------------------------------- #
# Story 4-2: free-action chronicle flavor
# --------------------------------------------------------------------------- #
# Past-tense deed phrases describing each free action, used both to seed the
# LLM prompt and to build the deterministic fallback line.
_FREE_ACTION_LABELS = {
    'declare_war': 'declared war',
    'propose_treaty': 'proposed a treaty',
    'send_envoy': 'sent an envoy',
    'issue_ultimatum': 'issued an ultimatum',
    'name_heir': 'named an heir',
    'adopt_succession_law': 'reformed the succession law',
    'hold_feast': 'held a grand feast',
    'hold_tournament': 'held a grand tournament',
    'pardon_vassal': 'pardoned a wayward vassal',
}


def _free_action_label(action_type: str) -> str:
    return _FREE_ACTION_LABELS.get(action_type, action_type.replace('_', ' '))


def build_free_action_flavor_prompt(action_type: str, dynasty_name: str,
                                    monarch_name: str, year: int,
                                    target_name: str = None) -> str:
    """Prompt for a one- to two-sentence chronicle line about a free action.

    Story 4-2. max_tokens<=150. Style: medieval chronicler, third-person,
    1-2 sentences. Fallback: generate_free_action_flavor_fallback().
    """
    deed = _free_action_label(action_type)
    target_clause = f" The matter concerned {target_name}." if target_name else ""
    return (
        f"You are a medieval chronicler recording the deeds of House {dynasty_name}. "
        f"In the year {year}, {monarch_name}, ruler of House {dynasty_name}, {deed}."
        f"{target_clause} "
        f"Write exactly 1-2 sentences in the style of a medieval chronicle — formal, "
        f"dramatic, third-person. Name the ruler. Do not use modern language or lists."
    )


def generate_free_action_flavor_fallback(action_type: str, dynasty_name: str,
                                         monarch_name: str, year: int,
                                         target_name: str = None) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 4-2).

    Returns an action-appropriate single-sentence chronicle line that always
    names the dynasty, the ruler, and the year.
    """
    deed = _free_action_label(action_type)
    if target_name:
        return (
            f"In the year {year}, {monarch_name} of House {dynasty_name} "
            f"{deed} against {target_name}."
        )
    return (
        f"In the year {year}, {monarch_name} of House {dynasty_name} {deed}."
    )


# ---------------------------------------------------------------------------
# Story 5-2 — Succession candidate cards + coronation chronicle
# ---------------------------------------------------------------------------

def _format_traits(traits) -> str:
    """Render a traits list/iterable as a human-readable comma string."""
    if not traits:
        return "no notable traits"
    if isinstance(traits, str):
        return traits
    try:
        cleaned = [str(t).replace('_', ' ').strip() for t in traits if str(t).strip()]
    except TypeError:
        return str(traits)
    if not cleaned:
        return "no notable traits"
    return ", ".join(cleaned)


def build_succession_card_prompt(candidate_name: str, candidate_traits,
                                 relation: str, age: int, monarch_name: str,
                                 dynasty_name: str, recent_events) -> str:
    """Prompt for a 3-sentence character sketch of a succession candidate.

    Story 5-2. max_tokens<=120. Style: medieval chronicler, third-person,
    exactly 3 sentences. Fallback: generate_succession_card_fallback().
    """
    traits_str = _format_traits(candidate_traits)
    if not recent_events:
        events_clause = "Recent years have passed without great incident."
    else:
        try:
            events = [str(e).strip() for e in recent_events if str(e).strip()]
        except TypeError:
            events = [str(recent_events)]
        joined = "; ".join(events[:5]) if events else ""
        events_clause = (
            f"Recent events in the realm: {joined}." if joined
            else "Recent years have passed without great incident."
        )
    return (
        f"You are a medieval chronicler of House {dynasty_name}. "
        f"The late {monarch_name} has died, and {candidate_name}, "
        f"the {relation} aged {age}, stands as a candidate for succession. "
        f"This person is known for these traits: {traits_str}. "
        f"{events_clause} "
        f"Write exactly 3 sentences sketching this candidate as a potential ruler — "
        f"formal, dramatic, third-person, in the style of a medieval chronicle. "
        f"Name the candidate. Reflect their traits and relation. "
        f"Do not use modern language or lists."
    )


def generate_succession_card_fallback(candidate_name: str, candidate_traits,
                                      relation: str, age: int) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 5-2).

    Returns a 3-sentence sketch that always names the candidate and references
    their relation, age, and traits.
    """
    traits_str = _format_traits(candidate_traits)
    return (
        f"{candidate_name}, the {relation}, has reached the age of {age}. "
        f"Known for {traits_str}, this candidate is weighed for the succession. "
        f"The realm watches to see whether {candidate_name} shall be crowned."
    )


def build_coronation_prompt(heir_name: str, dynasty_name: str, year: int,
                            heir_traits) -> str:
    """Prompt for a coronation chronicle line (Story 5-2).

    max_tokens<=150. Style: medieval chronicler, third-person, 1-2 sentences.
    Fallback: generate_coronation_fallback().
    """
    traits_str = _format_traits(heir_traits)
    return (
        f"You are a medieval chronicler recording the deeds of House {dynasty_name}. "
        f"In the year {year}, {heir_name} was crowned ruler of House {dynasty_name}, "
        f"a sovereign known for {traits_str}. "
        f"Write exactly 1-2 sentences in the style of a medieval chronicle, marking "
        f"this coronation — formal, dramatic, third-person. Name the new ruler. "
        f"Do not use modern language or lists."
    )


def generate_coronation_fallback(heir_name: str, dynasty_name: str,
                                 year: int) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 5-2)."""
    return (
        f"In the year {year}, {heir_name} was crowned ruler of House "
        f"{dynasty_name}, beginning a new reign."
    )


# ---------------------------------------------------------------------------
# Story 9-1 — Event flavor chronicle lines (births, deaths, battles,
# world news, completed construction)
# ---------------------------------------------------------------------------

def build_birth_flavor_prompt(child_name: str, child_traits, mother_name: str,
                              father_name: str, house: str, year: int) -> str:
    """Prompt for a short medieval chronicle line announcing a birth.

    Story 9-1. max_tokens<=80. Style: medieval chronicler, third-person,
    1 sentence. Fallback: generate_birth_flavor_fallback().
    """
    traits_str = _format_traits(child_traits)
    return (
        f"You are a medieval chronicler recording the deeds of House {house}. "
        f"In the year {year}, {mother_name} and {father_name} of House {house} "
        f"were blessed with a child, {child_name}, said to be {traits_str}. "
        f"Write exactly 1 sentence (about 80 tokens at most) in the style of a "
        f"medieval chronicle — formal, dramatic, third-person. Name the child "
        f"{child_name} and the house. Do not use modern language or lists."
    )


def generate_birth_flavor_fallback(child_name: str, mother_name: str,
                                   father_name: str, house: str,
                                   year: int) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 9-1).

    Always names the child, both parents, the house, and the year.
    """
    return (
        f"In the year {year}, {child_name} was born to {mother_name} and "
        f"{father_name} of House {house}, and the house rejoiced."
    )


def build_death_flavor_prompt(person_name: str, person_traits, house: str,
                              age: int, year: int,
                              was_monarch: bool = False) -> str:
    """Prompt for a short medieval chronicle line marking a death.

    Story 9-1. max_tokens<=90. Style: medieval chronicler, third-person,
    1-2 sentences. When was_monarch is True the prompt references the crown
    and the reign that has ended. Fallback: generate_death_flavor_fallback().
    """
    traits_str = _format_traits(person_traits)
    if was_monarch:
        station_clause = (
            f"{person_name}, the crowned ruler of House {house}, has died at the "
            f"age of {age}, and the reign is ended. Mark the passing of the crown "
            f"and the sorrow of the realm."
        )
    else:
        station_clause = (
            f"{person_name} of House {house} has died at the age of {age}. "
            f"Mark the passing with solemn dignity."
        )
    return (
        f"You are a medieval chronicler recording the deeds of House {house}. "
        f"In the year {year}, {station_clause} "
        f"The departed was known for being {traits_str}. "
        f"Write exactly 1-2 sentences (about 90 tokens at most) in the style of a "
        f"medieval chronicle — formal, dramatic, third-person. Name {person_name}. "
        f"Do not use modern language or lists."
    )


def generate_death_flavor_fallback(person_name: str, house: str, age: int,
                                   year: int, was_monarch: bool = False) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 9-1).

    Always names the person, the house, and the year. When was_monarch is True
    the line references the crown and the ended reign.
    """
    if was_monarch:
        return (
            f"In the year {year}, {person_name}, crowned ruler of House {house}, "
            f"died at the age of {age}, and the reign passed into history."
        )
    return (
        f"In the year {year}, {person_name} of House {house} died at the age "
        f"of {age}, mourned by the house."
    )


def build_battle_flavor_prompt(attacker_name: str, defender_name: str,
                               location: str, victor_name: str,
                               casualties, year: int) -> str:
    """Prompt for a short medieval chronicle line about a battle's outcome.

    Story 9-1. max_tokens<=100. Style: medieval chronicler, third-person,
    1-2 sentences. Fallback: generate_battle_flavor_fallback().
    """
    return (
        f"You are a medieval chronicler recording the wars of the realm. "
        f"In the year {year}, the host of {attacker_name} met the host of "
        f"{defender_name} in battle at {location}. When the dust settled, "
        f"{victor_name} held the field, at a cost of {casualties} fallen. "
        f"Write exactly 1-2 sentences (about 100 tokens at most) in the style of "
        f"a medieval chronicle — formal, dramatic, third-person. Name both "
        f"{attacker_name} and {defender_name}, and the victor. "
        f"Do not use modern language or lists."
    )


def generate_battle_flavor_fallback(attacker_name: str, defender_name: str,
                                    victor_name: str, year: int) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 9-1).

    Always names the attacker, defender, victor, and the year.
    """
    return (
        f"In the year {year}, {attacker_name} and {defender_name} clashed in "
        f"battle, and {victor_name} carried the day."
    )


def build_world_news_prompt(actor_dynasty: str, action_desc: str,
                            player_dynasty: str, year: int) -> str:
    """Prompt for a chronicle line framed as distant news reaching the court.

    Story 9-1. max_tokens<=120. Style: a letter from afar carried to the
    player's court, third-person about the actor. Fallback:
    generate_world_news_fallback().
    """
    return (
        f"You are a medieval chronicler. Word has travelled from afar and reached "
        f"the court of House {player_dynasty} in the year {year}: it is said that "
        f"House {actor_dynasty} {action_desc}. "
        f"Write exactly 1-2 sentences (about 120 tokens at most), framed as tidings "
        f"of distant news carried by letter or messenger to the court of House "
        f"{player_dynasty} — formal, dramatic, third-person. Name House "
        f"{actor_dynasty}. Do not use modern language or lists."
    )


def generate_world_news_fallback(actor_dynasty: str, action_desc: str,
                                 year: int) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 9-1).

    Always names the acting dynasty and the year.
    """
    return (
        f"In the year {year}, word reached the court that House {actor_dynasty} "
        f"{action_desc}."
    )


def build_construction_complete_prompt(building_name: str, territory_name: str,
                                       house: str, year: int) -> str:
    """Prompt for a short chronicle line marking a completed construction.

    Story 9-1. max_tokens<=70. Style: medieval chronicler, third-person,
    1 sentence. Fallback: generate_construction_complete_fallback().
    """
    return (
        f"You are a medieval chronicler recording the works of House {house}. "
        f"In the year {year}, the {building_name} at {territory_name} was at last "
        f"completed. "
        f"Write exactly 1 sentence (about 70 tokens at most) in the style of a "
        f"medieval chronicle — formal, dramatic, third-person. Name the "
        f"{building_name} and {territory_name}. Do not use modern language or lists."
    )


def generate_construction_complete_fallback(building_name: str,
                                            territory_name: str, house: str,
                                            year: int) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 9-1).

    Always names the building, the territory, the house, and the year.
    """
    return (
        f"In the year {year}, the {building_name} at {territory_name} was "
        f"completed for House {house}."
    )


# --------------------------------------------------------------------------- #
# Story 10-2: story-moment interrupt prose
# --------------------------------------------------------------------------- #


def build_story_moment_prompt(title: str, summary: str, monarch_name: str,
                              monarch_traits, recent_events, year: int) -> str:
    """Prompt for the narrated prose of a story-moment interrupt (Story 10-2).

    max_tokens<=200. Style: second-person, medieval, present-tense dilemma.
    Sets up the dilemma described by ``summary`` and references the monarch and
    their traits, but must NOT enumerate the choices — those are shown as cards.
    Handles empty/None ``monarch_traits`` and ``recent_events`` gracefully.
    Fallback: generate_story_moment_fallback().
    """
    traits_str = _format_traits(monarch_traits)
    recent_clause = ""
    if recent_events:
        try:
            recent_list = [str(e).strip() for e in recent_events if str(e).strip()]
        except TypeError:
            recent_list = []
        if recent_list:
            recent_clause = (
                f" Of late the court has spoken of: {recent_list[-1]}. "
            )
    return (
        f"You are a medieval storyteller addressing the ruler directly in the "
        f"year {year}. A moment has come upon the court: \"{title}\". {summary} "
        f"The ruler, {monarch_name}, is known for being {traits_str}.{recent_clause}"
        f"Write 2-3 sentences in the second person ('you'), in a formal, dramatic "
        f"medieval voice, that set the scene and lay the weight of this dilemma "
        f"upon {monarch_name}. Do not propose, list, or describe any choices — "
        f"end on the tension of the decision yet to be made. No modern language, "
        f"no lists."
    )


def generate_story_moment_fallback(title: str, summary: str, year: int) -> str:
    """Deterministic, non-empty fallback when the LLM is unavailable (Story 10-2).

    Always contains the title, the year, and uses the summary.
    """
    return (
        f"In the year {year}, a moment of reckoning came to your court: "
        f"\"{title}\". {summary} The decision now rests with you, and the realm "
        f"awaits your word."
    )


# ---------------------------------------------------------------------------
# Story 12-2 — Chronicle book foreword & epilogue prompts
# ---------------------------------------------------------------------------

def build_foreword_prompt(dynasty_name: str, founding_year: int,
                          first_paragraphs: list,
                          first_monarch_name: str = "") -> str:
    """Prompt for a short framing FOREWORD for the dynasty's Chronicle book.

    Story 12-2. max_tokens<=200. Style: medieval chronicler/archivist voice,
    third-person, 2-4 sentences, sets the stage and introduces the saga,
    does NOT spoil the ending. Fallback: generate_foreword_fallback().

    Args:
        dynasty_name: Name of the dynasty (primitive str, never ORM object).
        founding_year: The year the dynasty was founded.
        first_paragraphs: Opening chronicle paragraphs for context (list of str).
            Only the first 3 are embedded to respect the token budget.
        first_monarch_name: Optional name of the dynasty's first ruler.
    """
    context_paras = first_paragraphs[:3]
    context_str = (
        "\n".join(context_paras)
        if context_paras
        else "(No opening chronicle passages recorded yet.)"
    )
    monarch_hint = (
        f" The dynasty was founded by {first_monarch_name}."
        if first_monarch_name
        else ""
    )
    return (
        f"You are a medieval archivist writing the opening foreword of a great "
        f"dynasty's chronicle book.\n"
        f"Dynasty: {dynasty_name}\n"
        f"Founded: {founding_year}{monarch_hint}\n\n"
        f"Opening passages from the chronicle:\n{context_str}\n\n"
        f"Write exactly 2-4 sentences as a formal medieval foreword — in the "
        f"voice of a humble archivist introducing the saga of {dynasty_name} "
        f"to the reader. Third-person, solemn, sets the stage. "
        f"Do NOT spoil the ending or reveal how the dynasty's story concludes. "
        f"No bullet points, no headings, pure flowing prose only. "
        f"Stay within 200 tokens."
    )


def generate_foreword_fallback(dynasty_name: str, founding_year: int,
                               first_monarch_name: str = "") -> str:
    """Deterministic, non-empty foreword when the LLM is unavailable (Story 12-2).

    Returns 2-3 sentences naming the house and founding year.
    """
    founder_clause = (
        f", founded by {first_monarch_name},"
        if first_monarch_name
        else ""
    )
    return (
        f"Here begins the Chronicle of {dynasty_name}{founder_clause} "
        f"a noble house whose story commenced in the year {founding_year}. "
        f"The deeds herein — of conquest and loss, of love and succession — "
        f"are set down faithfully that they may endure beyond the lives of "
        f"those who lived them. Let the reader turn these pages in the spirit "
        f"of one who seeks to understand the ways of great houses."
    )


def build_epilogue_prompt(dynasty_name: str, current_year: int,
                          last_paragraphs: list,
                          current_state: dict = None) -> str:
    """Prompt for a reflective EPILOGUE closing the dynasty's Chronicle book.

    Story 12-2. max_tokens<=200. Style: medieval chronicler voice, third-person,
    2-4 sentences, reflective, describes where the dynasty stands now (or how it
    ended). Fallback: generate_epilogue_fallback().

    Args:
        dynasty_name: Name of the dynasty (primitive str).
        current_year: The current simulation year.
        last_paragraphs: Most recent chronicle paragraphs (list of str).
            Only the last 5 are embedded to respect the token budget.
        current_state: Optional dict with keys such as 'prestige', 'territories',
            'is_extinct'. Pass None if unavailable.
    """
    context_paras = last_paragraphs[-5:] if last_paragraphs else []
    context_str = (
        "\n".join(context_paras)
        if context_paras
        else "(No closing chronicle passages recorded yet.)"
    )
    state_lines = []
    if current_state:
        if "prestige" in current_state:
            state_lines.append(f"Prestige: {current_state['prestige']}")
        if "territories" in current_state:
            state_lines.append(f"Territories held: {current_state['territories']}")
        if current_state.get("is_extinct"):
            state_lines.append("The dynasty has fallen — its line is extinct.")
    state_str = (
        "Current standing — " + "; ".join(state_lines)
        if state_lines
        else ""
    )
    extinct_hint = (
        " The dynasty has perished — write this epilogue as a closing elegy."
        if (current_state or {}).get("is_extinct")
        else " The dynasty endures — close with a sense of living legacy."
    )
    return (
        f"You are a medieval archivist writing the closing epilogue of a great "
        f"dynasty's chronicle book.\n"
        f"Dynasty: {dynasty_name}\n"
        f"Year: {current_year}\n"
        f"{state_str}\n\n"
        f"Final chronicle passages:\n{context_str}\n\n"
        f"Write exactly 2-4 sentences as a formal medieval epilogue reflecting "
        f"on the saga of {dynasty_name} as it stands in {current_year}. "
        f"Third-person, solemn, reflective.{extinct_hint} "
        f"No bullet points, no headings, pure flowing prose only. "
        f"Stay within 200 tokens."
    )


def generate_epilogue_fallback(dynasty_name: str, current_year: int,
                               current_state: dict = None) -> str:
    """Deterministic, non-empty epilogue when the LLM is unavailable (Story 12-2).

    If current_state indicates extinction, phrases the epilogue as an ending;
    otherwise as an ongoing legacy. Non-empty, LLM-free.
    """
    is_extinct = bool((current_state or {}).get("is_extinct"))
    if is_extinct:
        return (
            f"Thus ends the Chronicle of {dynasty_name}, whose flame was "
            f"extinguished in the year {current_year}. "
            f"The halls that once rang with the laughter of kings fell silent, "
            f"and the name of this house passed into the keeping of memory alone. "
            f"May the scribes who preserved these pages do justice to all that "
            f"{dynasty_name} was, and all it strived to be."
        )
    return (
        f"So the Chronicle of {dynasty_name} stands as of the year {current_year}, "
        f"its story not yet concluded, its banners still raised against the sky. "
        f"The house endures, and future scribes shall yet have deeds to record "
        f"before the final page of this great saga is set down."
    )
