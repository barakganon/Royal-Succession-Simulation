# tests/unit/test_story_moment_prompt.py
# Story 10-2 (Story-moment interrupt) — CONTRACT-FIRST unit tests written by
# Agent D in an isolated worktree.
#
# These tests pin the contract for the two NEW story-moment text builders that
# live in utils/llm_prompts.py (built by Agent A):
#   - build_story_moment_prompt(title, summary, monarch_name, monarch_traits,
#                               recent_events, year) -> str
#   - generate_story_moment_fallback(title, summary, year) -> str
#
# In this isolated worktree these symbols may not yet exist; the tests WILL
# FAIL until Agent A lands them. That is EXPECTED and correct for a
# contract-first suite. Do NOT weaken, stub, or skip these tests.
#
# Contract (when the LLM is off, the in-game prose IS the fallback string):
#   - build_story_moment_prompt(...) returns a non-empty str that contains the
#     title and the monarch's name, sets up the dilemma from the summary,
#     references the monarch + traits, and does NOT enumerate the choices.
#   - It must handle monarch_traits = None and monarch_traits = [] without error.
#   - generate_story_moment_fallback(...) returns a deterministic non-empty str
#     that contains the title and str(year) and is built from the summary.

import pytest

from utils.llm_prompts import (
    build_story_moment_prompt,
    generate_story_moment_fallback,
)


# ---------------------------------------------------------------------------
# build_story_moment_prompt
# ---------------------------------------------------------------------------

class TestBuildStoryMomentPrompt:
    def test_returns_non_empty_string(self):
        prompt = build_story_moment_prompt(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            'King Aldric',
            ['Brave'],
            ['a feast was held'],
            1300,
        )
        assert isinstance(prompt, str)
        assert prompt.strip() != ''

    def test_contains_title(self):
        prompt = build_story_moment_prompt(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            'King Aldric',
            ['Brave'],
            ['a feast was held'],
            1300,
        )
        assert 'A Forbidden Love' in prompt

    def test_contains_monarch_name(self):
        prompt = build_story_moment_prompt(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            'King Aldric',
            ['Brave'],
            ['a feast was held'],
            1300,
        )
        assert 'King Aldric' in prompt

    def test_handles_none_traits_without_error(self):
        prompt = build_story_moment_prompt(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            'King Aldric',
            None,
            ['a feast was held'],
            1300,
        )
        assert isinstance(prompt, str)
        assert prompt.strip() != ''
        assert 'King Aldric' in prompt

    def test_handles_empty_traits_without_error(self):
        prompt = build_story_moment_prompt(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            'King Aldric',
            [],
            [],
            1300,
        )
        assert isinstance(prompt, str)
        assert prompt.strip() != ''
        assert 'A Forbidden Love' in prompt


# ---------------------------------------------------------------------------
# generate_story_moment_fallback
# ---------------------------------------------------------------------------

class TestGenerateStoryMomentFallback:
    def test_returns_non_empty_string(self):
        fallback = generate_story_moment_fallback(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            1300,
        )
        assert isinstance(fallback, str)
        assert fallback.strip() != ''

    def test_contains_title(self):
        fallback = generate_story_moment_fallback(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            1300,
        )
        assert 'A Forbidden Love' in fallback

    def test_contains_year(self):
        fallback = generate_story_moment_fallback(
            'A Forbidden Love',
            'Two hearts forbidden by station have entwined at court.',
            1300,
        )
        assert '1300' in fallback

    def test_is_deterministic(self):
        a = generate_story_moment_fallback('A Forbidden Love', 'Two hearts.', 1300)
        b = generate_story_moment_fallback('A Forbidden Love', 'Two hearts.', 1300)
        assert a == b
