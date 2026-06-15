# tests/unit/test_tts_narrator.py
# Unit tests for utils/tts_narrator.py
# All network calls are mocked — no real ElevenLabs requests are made.

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(api_key=None, voice_id=None):
    """Return a minimal Flask app configured for TTS tests."""
    from flask import Flask
    app = Flask(__name__)
    app.config['FLASK_APP_ELEVENLABS_API_KEY'] = api_key
    app.config['FLASK_APP_ELEVENLABS_VOICE_ID'] = voice_id
    return app


# ---------------------------------------------------------------------------
# tts_available()
# ---------------------------------------------------------------------------

class TestTtsAvailable:
    def test_returns_false_when_no_key(self):
        app = _make_app(api_key=None)
        with app.app_context():
            from utils.tts_narrator import tts_available
            assert tts_available() is False

    def test_returns_false_when_empty_string(self):
        app = _make_app(api_key='')
        with app.app_context():
            from utils.tts_narrator import tts_available
            assert tts_available() is False

    def test_returns_true_when_key_set(self):
        app = _make_app(api_key='sk-test-key')
        with app.app_context():
            from utils.tts_narrator import tts_available
            assert tts_available() is True


# ---------------------------------------------------------------------------
# get_latest_chronicle_paragraph()
# ---------------------------------------------------------------------------

class TestGetLatestChronicle:
    def test_empty_string(self):
        from utils.tts_narrator import get_latest_chronicle_paragraph
        assert get_latest_chronicle_paragraph('') == ''

    def test_none_like_empty(self):
        from utils.tts_narrator import get_latest_chronicle_paragraph
        assert get_latest_chronicle_paragraph('') == ''

    def test_single_paragraph(self):
        from utils.tts_narrator import get_latest_chronicle_paragraph
        assert get_latest_chronicle_paragraph('Only paragraph.') == 'Only paragraph.'

    def test_multiple_paragraphs_returns_last(self):
        from utils.tts_narrator import get_latest_chronicle_paragraph
        text = 'First paragraph.\n\nSecond paragraph.\n\nThird paragraph.'
        assert get_latest_chronicle_paragraph(text) == 'Third paragraph.'

    def test_trailing_blank_lines_ignored(self):
        from utils.tts_narrator import get_latest_chronicle_paragraph
        text = 'First.\n\nSecond.\n\n\n\n'
        assert get_latest_chronicle_paragraph(text) == 'Second.'

    def test_only_whitespace_returns_empty(self):
        from utils.tts_narrator import get_latest_chronicle_paragraph
        assert get_latest_chronicle_paragraph('   \n\n   \n\n') == ''


# ---------------------------------------------------------------------------
# synthesize()
# ---------------------------------------------------------------------------

class TestSynthesize:
    def test_no_key_returns_none_no_network(self):
        """When no API key is configured, synthesize must return None and NOT call requests.post."""
        app = _make_app(api_key=None)
        with app.app_context():
            with patch('utils.tts_narrator.requests.post') as mock_post:
                from utils.tts_narrator import synthesize
                result = synthesize('Hello world')
                assert result is None
                mock_post.assert_not_called()

    def test_empty_text_returns_none_no_network(self):
        app = _make_app(api_key='sk-test-key')
        with app.app_context():
            with patch('utils.tts_narrator.requests.post') as mock_post:
                from utils.tts_narrator import synthesize
                result = synthesize('')
                assert result is None
                mock_post.assert_not_called()

    def test_success_200_returns_bytes(self):
        app = _make_app(api_key='sk-test-key')
        fake_audio = b'ID3\x00\x00\x00fake-mp3-bytes'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with app.app_context():
            with patch('utils.tts_narrator.requests.post', return_value=mock_response) as mock_post:
                from utils.tts_narrator import synthesize
                result = synthesize('Once upon a time in the realm...')
                assert result == fake_audio
                mock_post.assert_called_once()

    def test_non_200_returns_none(self):
        app = _make_app(api_key='sk-test-key')
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'

        with app.app_context():
            with patch('utils.tts_narrator.requests.post', return_value=mock_response):
                from utils.tts_narrator import synthesize
                result = synthesize('Some text')
                assert result is None

    def test_exception_returns_none_does_not_raise(self):
        app = _make_app(api_key='sk-test-key')

        with app.app_context():
            with patch('utils.tts_narrator.requests.post', side_effect=ConnectionError('network down')):
                from utils.tts_narrator import synthesize
                # Must not raise — returns None gracefully
                result = synthesize('Some text')
                assert result is None

    def test_uses_default_voice_id_when_none_configured(self):
        """When no ELEVENLABS_VOICE_ID is configured, DEFAULT_VOICE_ID is used in URL."""
        app = _make_app(api_key='sk-test-key', voice_id=None)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'mp3bytes'

        with app.app_context():
            with patch('utils.tts_narrator.requests.post', return_value=mock_response) as mock_post:
                from utils.tts_narrator import synthesize, DEFAULT_VOICE_ID
                synthesize('Text')
                call_url = mock_post.call_args[0][0]
                assert DEFAULT_VOICE_ID in call_url

    def test_uses_configured_voice_id(self):
        custom_voice = 'custom-voice-xyz'
        app = _make_app(api_key='sk-test-key', voice_id=custom_voice)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'mp3bytes'

        with app.app_context():
            with patch('utils.tts_narrator.requests.post', return_value=mock_response) as mock_post:
                from utils.tts_narrator import synthesize
                synthesize('Text')
                call_url = mock_post.call_args[0][0]
                assert custom_voice in call_url
