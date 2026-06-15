# tests/integration/test_turn_narration.py
# Integration tests for the ElevenLabs TTS narration feature.
# All network calls are mocked — no real ElevenLabs requests are ever made.

import pytest
from unittest.mock import patch, MagicMock

from models.db_models import User, DynastyDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_login(app, db, client, username='tts_user', password='ttspass123'):
    with app.app_context():
        user = User(username=username, email=f'{username}@example.com')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, dynasty_name='House Narration', start_year='1200'):
    return client.post(
        '/dynasty/create',
        data={
            'dynasty_name': dynasty_name,
            'theme_type': 'predefined',
            'theme_key': VALID_THEME_KEY,
            'start_year': start_year,
            'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
        },
        follow_redirects=True,
    )


def _get_dynasty_id(app, db, username='tts_user'):
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
        return dynasty.id if dynasty else None


def _set_epic_story(app, db, dynasty_id, text):
    with app.app_context():
        dynasty = db.session.get(DynastyDB, dynasty_id)
        dynasty.epic_story_text = text
        db.session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plain_client(app, db, session):
    with app.test_client() as c:
        yield c


@pytest.fixture
def tts_client(app, db, session):
    """Authenticated client with a dynasty that has chronicle text."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username='tts_user')
        _create_dynasty(c)
        yield c


@pytest.fixture
def other_client(app, db, session):
    """Second user — used to test non-owner authorization."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username='tts_other_user')
        yield c


# ---------------------------------------------------------------------------
# Audio route: GET /dynasty/<id>/turn_narration.mp3
# ---------------------------------------------------------------------------

class TestTurnNarrationAudioRoute:
    def test_unauthenticated_redirects(self, plain_client):
        resp = plain_client.get('/dynasty/1/turn_narration.mp3', follow_redirects=False)
        assert resp.status_code == 302

    def test_no_key_returns_204(self, app, db, tts_client):
        """With no ElevenLabs key in config, the route must return 204 — no audio."""
        dynasty_id = _get_dynasty_id(app, db, 'tts_user')
        assert dynasty_id is not None

        # Ensure no key is configured
        with app.app_context():
            app.config['FLASK_APP_ELEVENLABS_API_KEY'] = None

        with patch('utils.tts_narrator.requests.post') as mock_post:
            resp = tts_client.get(f'/dynasty/{dynasty_id}/turn_narration.mp3')
            assert resp.status_code == 204
            mock_post.assert_not_called()

    def test_non_owner_redirected_to_dashboard(self, app, db, session):
        """A logged-in user who does NOT own the dynasty must be redirected."""
        # Create both users and owner's dynasty directly in DB (like test_view_other_user_dynasty_forbidden)
        with app.app_context():
            owner = User(username='narr_owner_user', email='narr_owner@ex.com')
            owner.set_password('pw_owner')
            other = User(username='narr_other_user', email='narr_other@ex.com')
            other.set_password('pw_other')
            db.session.add_all([owner, other])
            db.session.commit()
            dynasty = DynastyDB(
                user_id=owner.id,
                name='House NarrOwner',
                theme_identifier_or_json='MEDIEVAL_EUROPEAN',
                current_wealth=100,
                start_year=1000,
                current_simulation_year=1000,
            )
            db.session.add(dynasty)
            db.session.commit()
            dynasty_id = dynasty.id

        with app.test_client() as other_client:
            other_client.post('/login', data={'username': 'narr_other_user', 'password': 'pw_other'})
            resp = other_client.get(
                f'/dynasty/{dynasty_id}/turn_narration.mp3',
                follow_redirects=False,
            )
            assert resp.status_code == 302
            assert '/dashboard' in resp.headers.get('Location', '')

    def test_with_key_and_audio_returns_200_mpeg(self, app, db, tts_client):
        """When synthesize returns bytes, the route returns 200 audio/mpeg."""
        dynasty_id = _get_dynasty_id(app, db, 'tts_user')
        assert dynasty_id is not None

        _set_epic_story(app, db, dynasty_id, 'The realm prospered.\n\nA golden age dawned.')

        fake_audio = b'ID3\x00\x00\x00fake-mp3'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with app.app_context():
            app.config['FLASK_APP_ELEVENLABS_API_KEY'] = 'sk-test-key'

        try:
            with patch('utils.tts_narrator.requests.post', return_value=mock_response):
                resp = tts_client.get(f'/dynasty/{dynasty_id}/turn_narration.mp3')
                assert resp.status_code == 200
                assert resp.content_type == 'audio/mpeg'
                assert resp.data == fake_audio
        finally:
            with app.app_context():
                app.config['FLASK_APP_ELEVENLABS_API_KEY'] = None


# ---------------------------------------------------------------------------
# turn_report: template rendering
# ---------------------------------------------------------------------------

class TestTurnReportNarrationSection:
    def _get_turn_report(self, app, db, client, username):
        """Helper: advance turn and follow the redirect to turn_report."""
        dynasty_id = _get_dynasty_id(app, db, username)
        if dynasty_id is None:
            return None, None

        # Seed epic_story_text so there is narration text
        _set_epic_story(app, db, dynasty_id, 'Year one passed in splendour.')

        # Inject a pre-built turn summary into the session to bypass actual turn processing
        with client.session_transaction() as sess:
            sess['last_turn_summary'] = {
                'start_year': 1200,
                'end_year': 1205,
                'years_advanced': 5,
                'interrupt_reason': 'quiet_period',
                'stalled_project_ids': [],
                'events': [],
                'living_count': 3,
                'current_wealth': 500,
                'new_story_paragraph': 'Year one passed in splendour.',
            }

        resp = client.get(f'/dynasty/{dynasty_id}/turn_report', follow_redirects=False)
        return dynasty_id, resp

    def test_turn_report_renders_narration_text(self, app, db, tts_client):
        with app.app_context():
            app.config['FLASK_APP_ELEVENLABS_API_KEY'] = None

        dynasty_id, resp = self._get_turn_report(app, db, tts_client, 'tts_user')
        assert resp is not None and resp.status_code == 200
        assert b'Chronicle of this Turn' in resp.data
        assert b'Year one passed in splendour.' in resp.data

    def test_no_key_renders_speech_synthesis_fallback(self, app, db, tts_client):
        """With no API key, the template must include browser speechSynthesis markup."""
        with app.app_context():
            app.config['FLASK_APP_ELEVENLABS_API_KEY'] = None

        dynasty_id, resp = self._get_turn_report(app, db, tts_client, 'tts_user')
        assert resp is not None and resp.status_code == 200
        # The browser-speech fallback JS must be present
        assert b'speechSynthesis' in resp.data
        assert b'SpeechSynthesisUtterance' in resp.data

    def test_with_key_renders_audio_element(self, app, db, tts_client):
        """With API key configured, the template must render an <audio> element."""
        with app.app_context():
            app.config['FLASK_APP_ELEVENLABS_API_KEY'] = 'sk-test-key'

        try:
            dynasty_id, resp = self._get_turn_report(app, db, tts_client, 'tts_user')
            assert resp is not None and resp.status_code == 200
            assert b'<audio' in resp.data
            assert b'turn_narration' in resp.data
        finally:
            with app.app_context():
                app.config['FLASK_APP_ELEVENLABS_API_KEY'] = None
