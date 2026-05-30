"""Guarded LLM narration helper (Story 9-2).

A single, self-contained entry point ``narrate_event`` that turns a flavor
prompt into a short narrated string via the Gemini API, falling back to a
deterministic string whenever the LLM is unavailable, unconfigured, errors, or
times out.

Design notes:
- All ``google.generativeai`` / ``flask`` / ``os`` imports are lazy so this
  module is importable in pure unit tests (and so importing it never pulls in
  Flask app context or the genai SDK unless an actual narration is attempted).
- ``narrate_event`` NEVER raises — every failure path returns ``fallback``.
- Mirrors the guarded-genai style in ``models/turn_processor.py`` (~302-326).
"""

import logging

logger = logging.getLogger('royal_succession.llm_narration')


def narrate_event(prompt: str, fallback: str, max_tokens: int = 100, timeout_s: int = 3) -> str:
    """Narrate a single event via the LLM, falling back deterministically.

    Returns the LLM-generated text on success, otherwise ``fallback`` verbatim.
    Never raises.
    """
    try:
        from flask import current_app

        if not current_app.config.get('FLASK_APP_GOOGLE_API_KEY_PRESENT', False):
            return fallback

        import os
        api_key = current_app.config.get("FLASK_APP_GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return fallback

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.85},
            request_options={"timeout": timeout_s},
        )
        text = response.text.strip() if getattr(response, 'text', None) else ""
        return text or fallback
    except Exception:
        logger.debug("narrate_event failed; using deterministic fallback", exc_info=True)
        return fallback
