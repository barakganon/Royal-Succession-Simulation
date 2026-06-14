"""Unit tests for Story 12-2 foreword/epilogue prompt builders and fallbacks.

Pure unit tests — no Flask app context, no network, no genai. They exercise:
    build_foreword_prompt(dynasty_name, founding_year, first_paragraphs, first_monarch_name="") -> str
    generate_foreword_fallback(dynasty_name, founding_year, first_monarch_name="") -> str
    build_epilogue_prompt(dynasty_name, current_year, last_paragraphs, current_state=None) -> str
    generate_epilogue_fallback(dynasty_name, current_year, current_state=None) -> str
"""

import pytest

from utils.llm_prompts import (
    build_foreword_prompt,
    generate_foreword_fallback,
    build_epilogue_prompt,
    generate_epilogue_fallback,
)

DYNASTY = "House Vexley"
FOUNDING_YEAR = 1100
CURRENT_YEAR = 1340
SAMPLE_PARAS = [
    "The banners of Vexley first rose above the eastern marches in a cold spring.",
    "Lord Aldric led his knights across the frozen river at great cost.",
    "A peace was struck and the realm breathed easy for a generation.",
    "Then came the plague years, dark and merciless.",
    "Still the house endured, its walls unbroken.",
]


# ---------------------------------------------------------------------------
# build_foreword_prompt
# ---------------------------------------------------------------------------

class TestBuildForewordPrompt:
    def test_returns_nonempty_str(self):
        result = build_foreword_prompt(DYNASTY, FOUNDING_YEAR, SAMPLE_PARAS[:3])
        assert isinstance(result, str) and result

    def test_contains_dynasty_name(self):
        result = build_foreword_prompt(DYNASTY, FOUNDING_YEAR, SAMPLE_PARAS[:3])
        assert DYNASTY in result

    def test_contains_founding_year(self):
        result = build_foreword_prompt(DYNASTY, FOUNDING_YEAR, SAMPLE_PARAS[:3])
        assert str(FOUNDING_YEAR) in result

    def test_contains_first_monarch_name_when_provided(self):
        result = build_foreword_prompt(DYNASTY, FOUNDING_YEAR, SAMPLE_PARAS, "Aldric the Elder")
        assert "Aldric the Elder" in result

    def test_empty_paragraphs_does_not_raise(self):
        result = build_foreword_prompt(DYNASTY, FOUNDING_YEAR, [])
        assert isinstance(result, str) and result
        assert DYNASTY in result

    def test_caps_paragraphs_at_three(self):
        # Supply 5 paragraphs; only the first 3 should appear in the prompt.
        result = build_foreword_prompt(DYNASTY, FOUNDING_YEAR, SAMPLE_PARAS)
        # The 4th paragraph should not be embedded.
        assert SAMPLE_PARAS[3] not in result

    def test_no_first_monarch_name_no_error(self):
        result = build_foreword_prompt(DYNASTY, FOUNDING_YEAR, SAMPLE_PARAS[:2])
        assert isinstance(result, str) and result


# ---------------------------------------------------------------------------
# generate_foreword_fallback
# ---------------------------------------------------------------------------

class TestGenerateForewordFallback:
    def test_returns_nonempty_str(self):
        result = generate_foreword_fallback(DYNASTY, FOUNDING_YEAR)
        assert isinstance(result, str) and result

    def test_contains_dynasty_name(self):
        result = generate_foreword_fallback(DYNASTY, FOUNDING_YEAR)
        assert DYNASTY in result

    def test_contains_founding_year(self):
        result = generate_foreword_fallback(DYNASTY, FOUNDING_YEAR)
        assert str(FOUNDING_YEAR) in result

    def test_with_first_monarch_name(self):
        result = generate_foreword_fallback(DYNASTY, FOUNDING_YEAR, "Aldric the Elder")
        assert "Aldric the Elder" in result
        assert DYNASTY in result

    def test_without_first_monarch_name(self):
        result = generate_foreword_fallback(DYNASTY, FOUNDING_YEAR)
        assert isinstance(result, str) and result

    def test_no_llm_call(self):
        # Should complete synchronously with no HTTP or model dependency.
        result = generate_foreword_fallback("House Empty", 900)
        assert result


# ---------------------------------------------------------------------------
# build_epilogue_prompt
# ---------------------------------------------------------------------------

class TestBuildEpiloguePrompt:
    def test_returns_nonempty_str(self):
        result = build_epilogue_prompt(DYNASTY, CURRENT_YEAR, SAMPLE_PARAS)
        assert isinstance(result, str) and result

    def test_contains_dynasty_name(self):
        result = build_epilogue_prompt(DYNASTY, CURRENT_YEAR, SAMPLE_PARAS)
        assert DYNASTY in result

    def test_contains_current_year(self):
        result = build_epilogue_prompt(DYNASTY, CURRENT_YEAR, SAMPLE_PARAS)
        assert str(CURRENT_YEAR) in result

    def test_empty_paragraphs_does_not_raise(self):
        result = build_epilogue_prompt(DYNASTY, CURRENT_YEAR, [])
        assert isinstance(result, str) and result
        assert DYNASTY in result

    def test_current_state_none_does_not_raise(self):
        result = build_epilogue_prompt(DYNASTY, CURRENT_YEAR, SAMPLE_PARAS, None)
        assert isinstance(result, str) and result

    def test_caps_paragraphs_at_five(self):
        long_paras = [f"Para {i}" for i in range(10)]
        result = build_epilogue_prompt(DYNASTY, CURRENT_YEAR, long_paras)
        # Paragraphs 0-4 should NOT be present; only the last 5 (5-9).
        assert "Para 0" not in result
        assert "Para 9" in result

    def test_extinct_hint_present_when_is_extinct_true(self):
        result = build_epilogue_prompt(
            DYNASTY, CURRENT_YEAR, SAMPLE_PARAS,
            {"is_extinct": True, "prestige": 50, "territories": 0}
        )
        assert "extinct" in result.lower() or "perish" in result.lower() or "elegy" in result.lower()

    def test_current_state_with_prestige_and_territories(self):
        result = build_epilogue_prompt(
            DYNASTY, CURRENT_YEAR, SAMPLE_PARAS,
            {"prestige": 420, "territories": 7, "is_extinct": False}
        )
        assert isinstance(result, str) and result
        assert DYNASTY in result


# ---------------------------------------------------------------------------
# generate_epilogue_fallback
# ---------------------------------------------------------------------------

class TestGenerateEpilogueFallback:
    def test_returns_nonempty_str(self):
        result = generate_epilogue_fallback(DYNASTY, CURRENT_YEAR)
        assert isinstance(result, str) and result

    def test_contains_dynasty_name(self):
        result = generate_epilogue_fallback(DYNASTY, CURRENT_YEAR)
        assert DYNASTY in result

    def test_contains_current_year(self):
        result = generate_epilogue_fallback(DYNASTY, CURRENT_YEAR)
        assert str(CURRENT_YEAR) in result

    def test_current_state_none_does_not_raise(self):
        result = generate_epilogue_fallback(DYNASTY, CURRENT_YEAR, None)
        assert isinstance(result, str) and result

    def test_ongoing_legacy_phrasing(self):
        result = generate_epilogue_fallback(DYNASTY, CURRENT_YEAR, {"is_extinct": False})
        # Should suggest the house still stands
        assert "endures" in result or "still" in result or "future" in result

    def test_extinct_phrasing(self):
        result = generate_epilogue_fallback(
            DYNASTY, CURRENT_YEAR, {"is_extinct": True}
        )
        # Should read as an ending
        assert "ends" in result or "silent" in result or "extinct" in result or "memory" in result

    def test_empty_current_state_dict_does_not_raise(self):
        result = generate_epilogue_fallback(DYNASTY, CURRENT_YEAR, {})
        assert isinstance(result, str) and result

    def test_no_llm_call(self):
        result = generate_epilogue_fallback("House Empty", 999)
        assert result
