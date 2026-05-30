# tests/unit/test_chronicle_trait_voice.py
# Story 6-3 (Agent C / contract-first): the chronicle/turn-story prompt
# builders must accept an optional `monarch_traits` list and weave the trait
# names into the prompt so the narrator adopts the monarch's "voice".
#
# Contract:
#   - build_chronicle_prompt(..., monarch_traits=['Brave','Pious'])  -> string
#     CONTAINS 'Brave' AND 'Pious'.
#   - build_chronicle_prompt(..., monarch_traits=None) / [] -> no error and the
#     string matches the no-traits baseline shape (no trait-voice line / names).
#   - Same contract for build_turn_story_prompt(..., monarch_traits=[...]).
#
# These tests are EXPECTED TO FAIL until the prompt builders gain the param.

from utils.llm_prompts import build_chronicle_prompt, build_turn_story_prompt


class TestBuildChronicleTraitVoice:
    def _baseline_kwargs(self, **overrides):
        kwargs = dict(
            events=['A harvest festival was held', 'A bridge was raised'],
            dynasty_name='Anjou',
            year=1305,
        )
        kwargs.update(overrides)
        return kwargs

    def test_chronicle_prompt_includes_both_trait_names(self):
        """build_chronicle_prompt with monarch_traits=['Brave','Pious'] contains both names."""
        result = build_chronicle_prompt(
            **self._baseline_kwargs(), monarch_traits=['Brave', 'Pious']
        )
        assert 'Brave' in result
        assert 'Pious' in result

    def test_chronicle_prompt_none_traits_matches_baseline_and_omits_names(self):
        """monarch_traits=None does not raise, names absent, equals the no-traits baseline shape."""
        with_none = build_chronicle_prompt(**self._baseline_kwargs(), monarch_traits=None)
        baseline = build_chronicle_prompt(**self._baseline_kwargs())
        # No trait names leak into the prompt when there are no traits.
        assert 'Brave' not in with_none
        assert 'Pious' not in with_none
        # Passing None must be equivalent to omitting the param entirely.
        assert with_none == baseline

    def test_chronicle_prompt_empty_traits_omits_trait_voice_line(self):
        """monarch_traits=[] behaves like the no-traits baseline (no trait-voice line)."""
        with_empty = build_chronicle_prompt(**self._baseline_kwargs(), monarch_traits=[])
        baseline = build_chronicle_prompt(**self._baseline_kwargs())
        assert with_empty == baseline


class TestBuildTurnStoryTraitVoice:
    def _baseline_kwargs(self, **overrides):
        kwargs = dict(
            dynasty_name='Anjou',
            start_year=1300,
            end_year=1304,
            events=['Walls were completed at Riverlands'],
            monarch_name='Aldric I',
            existing_story='',
            years_advanced=5,
            interrupt_reason='quiet_period',
        )
        kwargs.update(overrides)
        return kwargs

    def test_turn_story_prompt_includes_trait_name(self):
        """build_turn_story_prompt with monarch_traits=['Cunning'] contains 'Cunning'."""
        result = build_turn_story_prompt(
            **self._baseline_kwargs(), monarch_traits=['Cunning']
        )
        assert 'Cunning' in result

    def test_turn_story_prompt_empty_traits_unaffected(self):
        """monarch_traits=[] leaves the prompt equal to the no-traits baseline shape."""
        with_empty = build_turn_story_prompt(**self._baseline_kwargs(), monarch_traits=[])
        baseline = build_turn_story_prompt(**self._baseline_kwargs())
        assert with_empty == baseline
        assert 'Cunning' not in with_empty
