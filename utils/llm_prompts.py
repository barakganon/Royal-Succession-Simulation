"""
utils/llm_prompts.py — Centralised LLM prompt templates for the Royal Succession Simulation.

All prompt-building functions follow the signature:
    def build_<name>_prompt(**kwargs) -> str

Fallback generators return plain Python values (str or list) when LLM is unavailable.
"""

from typing import List


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
