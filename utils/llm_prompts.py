"""
Centralised LLM prompt templates for the Royal Succession Simulation.

All prompt-building functions follow the signature:
    def build_<name>_prompt(**kwargs) -> str

Fallback generators are also co-located here so callers never need to
inline prompt logic or fallback strings elsewhere.
"""

from typing import List


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
