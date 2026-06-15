# Story L-2: ElevenLabs TTS Narrator (with no-key fallback)

Status: ready-for-dev

## Story
As a **player reading my turn report**,
I want **the turn's chronicle paragraph narrated aloud — in a premium ElevenLabs voice when an API key is configured, and via the browser's built-in speech otherwise**,
so that **the saga comes alive, and the feature works even with no API key.**

## Context & design
The per-turn epic narration is `turn_summary['new_story_paragraph']` (and accumulates in `DynastyDB.epic_story_text`). It is **not currently shown** in `turn_report.html`. This story (a) surfaces the latest chronicle paragraph on the turn report with a **Narrate** control, and (b) adds TTS: ElevenLabs REST (premium voice) when `ELEVENLABS_API_KEY` is set, and the **browser Web Speech API (`window.speechSynthesis`)** as the no-key fallback (free, client-side). `requests` is already a dependency — **no new Python dep**, **no schema change**. (Do NOT use the elevenlabs-tts inference.sh CLI skill — that's for offline CLI use, not a web request path; call the REST API directly.)

## Acceptance Criteria

1. **AC1 — `utils/tts_narrator.py`.**
   - `tts_available() -> bool`: True iff `current_app.config.get('FLASK_APP_ELEVENLABS_API_KEY')` is set.
   - `synthesize(text: str) -> bytes | None`: guard `if not text or not tts_available(): return None`. POST to `https://api.elevenlabs.io/v1/text-to-speech/<voice_id>` (voice id from `current_app.config.get('FLASK_APP_ELEVENLABS_VOICE_ID')` or a sensible default constant) with header `xi-api-key`, JSON body `{text, model_id: 'eleven_multilingual_v2'}`, via `requests.post(..., timeout=...)`. Return `response.content` (MP3 bytes) on HTTP 200, else log a warning and return `None`. Wrap the whole call in try/except → log + `return None` (never raise; a TTS failure must never break the page). Logger `royal_succession.tts`.

2. **AC2 — Config wiring** (`main_flask_app.py`, app-setup region only — mirror the `GOOGLE_API_KEY` block ~:110-131): read `os.environ.get('ELEVENLABS_API_KEY')` → `app.config['FLASK_APP_ELEVENLABS_API_KEY']` and `os.environ.get('ELEVENLABS_VOICE_ID')` → `app.config['FLASK_APP_ELEVENLABS_VOICE_ID']`. Log at startup whether the key is present (like the LLM key log). Keep `main_flask_app.py` ≤ ~300 lines.

3. **AC3 — Narration audio route.** `GET /dynasty/<int:dynasty_id>/turn_narration.mp3` in `blueprints/dynasty.py` (`@login_required`; authz: not owner → redirect dashboard). Derive the text to narrate from the dynasty's **latest chronicle paragraph** (the last paragraph of `dynasty.epic_story_text`, split on the blank-line separator; if empty, a short fallback like "The chronicle of House X has yet to be written."). `audio = synthesize(text)`. If `audio` is None (no key or synth failed) → return **HTTP 204 No Content** (the client then uses the browser fallback). Else `Response(audio, mimetype='audio/mpeg')` with a sensible `Content-Disposition: inline; filename="narration.mp3"`. Stateless — no flask_session dependency.

4. **AC4 — turn_report Narrate control.** In `templates/turn_report.html`, add a "Chronicle of this Turn" section that displays the narratable paragraph (pass it from the `turn_report` route as `narration_text` — the same latest-paragraph derivation; factor a small helper so the route and the audio route agree). Add a **🔊 Narrate** control whose behavior is driven by a `tts_available` flag passed from the route:
   - **Key present (`tts_available` True):** an `<audio controls preload="none">` (or a button that sets the audio `src`) pointing at `url_for('dynasty.turn_narration', dynasty_id=...)`.
   - **No key (`tts_available` False):** a button that runs `window.speechSynthesis.speak(new SpeechSynthesisUtterance(<the text>))` (and a Stop button calling `speechSynthesis.cancel()`). Guard for browsers without `speechSynthesis`. This is the **no-key fallback** and must be the default experience when no key is set.
   - Extend `base.html`, medieval theme, `url_for`, no inline secrets.

5. **AC5 — Route context.** The `turn_report` route passes `tts_available=tts_available()` and `narration_text=<latest paragraph>` to the template. Import the helpers from `utils/tts_narrator`.

6. **AC6 — Tests.** `tests/unit/test_tts_narrator.py` + `tests/integration/test_turn_narration.py`:
   - `synthesize` returns `None` when no key configured (no network call made). With the key set in config and `requests.post` **mocked** to return a 200 with `.content=b'ID3...'` → returns those bytes; mocked non-200 → `None`; mocked exception → `None` (no raise).
   - `tts_available()` reflects the config key.
   - Audio route: no key → **204**; authz (non-owner) → redirect; with `synthesize` mocked to return bytes → 200 + `Content-Type: audio/mpeg`.
   - turn_report renders the Narrate control and, with no key, includes the `speechSynthesis` fallback markup (assert the JS/markup substring is present).
   - Use existing fixtures; mock all network (no real ElevenLabs calls in tests).

7. **AC7 — No regressions + live check.** Full suite green (baseline **627 passed**, 0 failed, 0 skipped) + new tests. `python -c "import main_flask_app"` clean. Boot on 8091 **with no `ELEVENLABS_API_KEY`** (the normal dev state): a turn report page renders the Narrate control with the browser-speech fallback, and `GET /dynasty/<id>/turn_narration.mp3` returns **204** (graceful). (Per Epic 3 retro — real run-the-app check.) The premium path can't be verified without a key — that's expected; the guard + mocked unit tests cover it.

## Tasks
- [ ] Task 1 — `utils/tts_narrator.py` (`tts_available`, `synthesize`) (AC1).
- [ ] Task 2 — config wiring in `main_flask_app.py` (AC2).
- [ ] Task 3 — `turn_narration.mp3` route + latest-paragraph helper (AC3, AC5).
- [ ] Task 4 — turn_report Narrate control + browser-speech fallback (AC4).
- [ ] Task 5 — unit + integration tests, network mocked (AC6).
- [ ] Task 6 — pytest 627+new green; import clean; live no-key check on 8091 (AC7).

## Dev Notes
- **Never raise from `synthesize`** — TTS is best-effort. A failed/absent key → `None` → 204 → browser fallback. The page must work identically whether or not the key exists.
- **No-key is the DEFAULT path in dev** (no key set) — make sure that experience (browser speech) is fully wired and is what the live check exercises.
- Default voice id: pick a known public ElevenLabs voice id as a constant fallback (e.g. "Rachel" `21m00Tcm4TlvDq8ikWAM`); overridable via `ELEVENLABS_VOICE_ID`.
- `requests` is already installed (2.32.x) — use it; **do not** add the `elevenlabs` package or any new dep. Give `requests.post` a timeout.
- Config access via `current_app.config.get(...)` only — never read `os.environ` in the route/util; the key is read once in `main_flask_app.py` and stored in config (mirror the Google key).
- `@login_required` on the audio route; flash categories `success|danger|info|warning` only; `url_for(...)`; serialize before template.
- **Latest paragraph helper:** split `dynasty.epic_story_text` on the same separator `turn_processor` joins with (check `models/turn_processor.py:428` — it uses a blank-line `separator`); take the last non-empty chunk. Factor it so the route + audio route + template text agree.
- **Self-contained → single Sonnet subagent on live `main` (no worktree)** per Epic 11 retro policy.
- Out of scope: caching/storing audio; per-event narration; voice selection UI; streaming. v1 narrates the latest chronicle paragraph on demand.

## References
- `blueprints/dynasty.py`: `turn_report` route (~:475-510), `turn_summary['new_story_paragraph']`, `epic_story_text` usage.
- `models/turn_processor.py:393-453` (epic_story_text accrual + separator + `new_story_paragraph`).
- `main_flask_app.py:110-131` (GOOGLE_API_KEY config pattern to mirror).
- `templates/turn_report.html` (extend; add narration section).
- `utils/llm_prompts.py` LLM-guard idiom (analogous best-effort-with-fallback shape).

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-15 | spec(L-2); ElevenLabs TTS narrator + browser-speech no-key fallback (ready-for-dev) |
