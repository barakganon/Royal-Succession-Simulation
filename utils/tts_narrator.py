# utils/tts_narrator.py
# ElevenLabs TTS narrator — calls REST API when key is configured, otherwise returns None.
# The caller handles the None case by returning HTTP 204 so the browser can use
# window.speechSynthesis as a fallback.  NEVER raises — TTS is best-effort.

import logging

import requests
from flask import current_app

logger = logging.getLogger('royal_succession.tts')

# Default voice: ElevenLabs "Rachel"
DEFAULT_VOICE_ID = '21m00Tcm4TlvDq8ikWAM'

# How long (seconds) to wait for ElevenLabs before giving up
_REQUEST_TIMEOUT = 15


def tts_available() -> bool:
    """Return True iff an ElevenLabs API key is present in the current app config."""
    return bool(current_app.config.get('FLASK_APP_ELEVENLABS_API_KEY'))


def get_latest_chronicle_paragraph(epic_story_text: str) -> str:
    """Return the last non-empty paragraph from *epic_story_text*.

    Paragraphs are separated by blank lines (``\\n\\n``) — the same separator
    used by ``turn_processor.py`` when it appends each new paragraph.

    If *epic_story_text* is empty or contains no non-empty paragraphs an empty
    string is returned; callers that need a human-readable fallback should
    supply the dynasty name themselves.
    """
    if not epic_story_text:
        return ''
    paragraphs = [p.strip() for p in epic_story_text.split('\n\n')]
    non_empty = [p for p in paragraphs if p]
    return non_empty[-1] if non_empty else ''


def synthesize(text: str):
    """Synthesize *text* to MP3 bytes via ElevenLabs, or return ``None``.

    Returns:
        ``bytes`` — MP3 audio on success.
        ``None``  — when no API key is configured, *text* is empty, or any
                    error occurs (network, API, etc.).  Never raises.
    """
    if not text or not tts_available():
        return None

    try:
        api_key = current_app.config.get('FLASK_APP_ELEVENLABS_API_KEY')
        voice_id = (
            current_app.config.get('FLASK_APP_ELEVENLABS_VOICE_ID')
            or DEFAULT_VOICE_ID
        )
        url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
        headers = {
            'xi-api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'audio/mpeg',
        }
        payload = {
            'text': text,
            'model_id': 'eleven_multilingual_v2',
        }
        response = requests.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT)
        if response.status_code == 200:
            logger.debug('TTS synthesis succeeded (%d bytes)', len(response.content))
            return response.content
        else:
            logger.warning(
                'ElevenLabs TTS returned HTTP %d: %s',
                response.status_code,
                response.text[:200],
            )
            return None
    except Exception as exc:
        logger.error('ElevenLabs TTS error: %s', exc, exc_info=True)
        return None
