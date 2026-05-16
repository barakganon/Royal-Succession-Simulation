from utils.llm_prompts import build_turn_story_prompt, generate_turn_story_fallback


class TestBuildTurnStoryPrompt:
    def _call(self, **overrides):
        kwargs = dict(
            dynasty_name='Anjou',
            start_year=1300,
            end_year=1304,
            events=['A harvest festival was held'],
            monarch_name='Aldric I',
            existing_story='',
            years_advanced=5,
            interrupt_reason='quiet_period',
        )
        kwargs.update(overrides)
        return build_turn_story_prompt(**kwargs)

    def test_years_advanced_appears_in_prompt(self):
        result = self._call(years_advanced=3)
        assert 'This turn spanned 3 years.' in result

    def test_interrupt_reason_appears_in_prompt(self):
        result = self._call(interrupt_reason='monarch_death')
        assert 'monarch' in result.lower() or 'death' in result.lower()

    def test_quiet_period_pacing_hint(self):
        result = self._call(interrupt_reason='quiet_period')
        assert (
            'peaceful' in result.lower()
            or 'uneventful' in result.lower()
            or 'quiet' in result.lower()
        )

    def test_singular_year_grammar_in_prompt(self):
        result = self._call(years_advanced=1)
        assert 'This turn spanned 1 year.' in result
        assert 'This turn spanned 1 years.' not in result

    def test_returns_non_empty_for_no_events(self):
        result = self._call(events=[])
        assert len(result) > 100


class TestGenerateTurnStoryFallback:
    def _call(self, **overrides):
        kwargs = dict(
            dynasty_name='Anjou',
            start_year=1300,
            end_year=1304,
            events=['Walls were completed at Riverlands'],
            monarch_name='Aldric I',
            years_advanced=5,
            interrupt_reason='quiet_period',
        )
        kwargs.update(overrides)
        return generate_turn_story_fallback(**kwargs)

    def test_monarch_death_differs_from_quiet_period(self):
        quiet = self._call(interrupt_reason='quiet_period')
        death = self._call(interrupt_reason='monarch_death')
        assert quiet != death

    def test_singular_year_grammar(self):
        # events-branch (default _call has non-empty events) renders "Across the N year(s) from ..."
        result_events = self._call(years_advanced=1, interrupt_reason='quiet_period')
        assert 'Across the 1 year from' in result_events
        assert 'Across the 1 years from' not in result_events
        # no-events branch renders "The N year(s) from ..."
        result_empty = self._call(years_advanced=1, interrupt_reason='quiet_period', events=[])
        assert 'The 1 year from' in result_empty
        assert 'The 1 years from' not in result_empty

    def test_monarch_death_mentions_passing(self):
        result = self._call(interrupt_reason='monarch_death')
        lower = result.lower()
        assert 'passing' in lower or 'mourning' in lower or 'death' in lower

    def test_returns_non_empty_for_no_events_quiet(self):
        result = self._call(events=[], interrupt_reason='quiet_period')
        assert len(result) > 20

    def test_returns_non_empty_for_no_events_death(self):
        result = self._call(events=[], interrupt_reason='monarch_death')
        assert len(result) > 20
