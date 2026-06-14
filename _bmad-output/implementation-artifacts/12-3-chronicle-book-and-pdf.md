# Story 12-3: Chronicle Book + PDF Export

Status: ready-for-dev

## Story
As a **player who has built a dynasty**,
I want **to compile and read my Chronicle as a formatted book on screen and download it as a PDF**,
so that **I have a keepable artifact of my dynasty's saga.**

## Context
12-1 built `compile_chronicle(dynasty_id) -> ChronicleBook` (reign chapters + weighted highlights). 12-2 added `build_foreword_prompt`/`generate_foreword_fallback` + `build_epilogue_prompt`/`generate_epilogue_fallback`. This story is the **UI + export**: an on-screen book reader, a PDF download, and a left-rail "Compile Chronicle" button. The route wires the foreword/epilogue into the book via the standard LLM guard (LLM if present, deterministic fallback otherwise). PDF uses **reportlab** (pip-only, no system libs — the `pdf` skill's recommended tool).

## Acceptance Criteria

1. **AC1 — Dependency.** Add `reportlab` to `requirements.txt` and install into `.venv`. No other new deps (do NOT add weasyprint/xhtml2pdf — they need system libs).

2. **AC2 — Book reader route.** Add `GET /dynasty/<int:dynasty_id>/chronicle_book` to `blueprints/dynasty.py` (`@login_required`, authz: redirect to dashboard with a `"warning"` flash if `dynasty.user_id != current_user.id`). Logic:
   - `book = compile_chronicle(dynasty_id)`; if `None` → flash `"danger"` + redirect to dashboard.
   - Wire foreword/epilogue with the LLM guard (mirror `blueprints/map.py:923-929`): `llm_model = current_app.config.get('FLASK_APP_LLM_MODEL')`. Build `first_paragraphs` = first up-to-3 paragraphs across chapters, `last_paragraphs` = last up-to-5, `current_state` = `{'prestige': dynasty.prestige, 'territories': <count via Territory.query.filter_by(controller_dynasty_id=...).count()>, 'is_extinct': <no living monarch>}`. If `llm_model` is not None: `book.foreword = llm_model.generate_content(build_foreword_prompt(...)).text` (wrap in try/except → fallback on error); else `book.foreword = generate_foreword_fallback(...)`. Same for epilogue. Keep within the 200-token budget (pass `generation_config` max_output_tokens like the map.py advisor call if it does).
   - `render_template('chronicle_book.html', dynasty=dynasty, book=book)`.

3. **AC3 — Book template.** `templates/chronicle_book.html` extends `base.html`. Sections in order: (a) **cover** — `dynasty.coat_of_arms_svg | safe` + book title ("The Chronicle of {{ dynasty.name }}"); (b) **foreword** (`book.foreword`); (c) one block **per chapter**: monarch heading (`chapter.monarch_name` or "The Founding" when empty) with reign years, `chapter.portrait_svg | safe` if present, the prose `chapter.paragraphs`, and a **"Key Events of the Reign" callout box** listing `chapter.highlights` (year — text); (d) embedded `dynasty.family_tree_svg | safe` if present; (e) **epilogue** (`book.epilogue`); (f) a "Download PDF" link → the PDF route, and a back-to-map link. Include a print-friendly `@media print` block. The `ChronicleBook`/`ChronicleChapter`/`ChronicleHighlight` are plain dataclasses (not ORM) — safe to pass to the template.

4. **AC4 — PDF export route.** Add `GET /dynasty/<int:dynasty_id>/chronicle_book.pdf` to `blueprints/dynasty.py` (`@login_required` + same authz). Compile the book the same way (incl. foreword/epilogue wiring — factor the shared build into a helper to avoid duplication). Build a PDF with **reportlab Platypus** (`SimpleDocTemplate`, `Paragraph`, `Spacer`, `PageBreak`, `getSampleStyleSheet`) into an `io.BytesIO`: title page (dynasty name + founding/current year), foreword, then per chapter a heading + reign years + prose paragraphs + a "Key Events" list, then epilogue. Return `Response(buffer.getvalue(), mimetype='application/pdf')` with `Content-Disposition: attachment; filename="chronicle_<dynasty_id>.pdf"`. **SVG heraldry is NOT embedded in the PDF** (reportlab can't render inline SVG without extra deps) — the PDF is text-focused; note this in a code comment. Do NOT use Unicode sub/superscript glyphs (reportlab renders them as black boxes — per the pdf skill).

5. **AC5 — Left-rail button.** Add a "Compile Chronicle" button to the left rail in `templates/world_map.html` (`#game-left-rail`, near the other rail buttons), linking via `url_for('dynasty.chronicle_book', dynasty_id=dynasty.id)`. Always available (not end-game gated). Use a 📜/book glyph consistent with the rail's style.

6. **AC6 — Tests.** Add `tests/integration/test_chronicle_book.py`:
   - Book route returns 200 for the owner and the HTML contains the dynasty name and at least one chapter/monarch element.
   - PDF route returns 200, `Content-Type: application/pdf`, body is non-empty and starts with `b'%PDF'`.
   - Authz: a different (non-owner) logged-in user gets a redirect (302) or access-denied, not the book.
   - Works with the LLM off (no `FLASK_APP_LLM_MODEL`) → fallback foreword/epilogue present (page still 200, PDF still valid).
   Use the existing integration fixtures (`tests/integration/conftest.py`, `dynasty_client`/`plain_client` patterns as in `test_dynasty_routes.py`).

7. **AC7 — No regressions + live check.** Full suite green (baseline **576 passed**, 0 failed, 0 skipped) + new tests. `python -c "import main_flask_app"` clean. Boot the app on 8091 and confirm (urllib, no curl in shell): `/dynasty/<id>/chronicle_book` returns 200 and renders, and `/dynasty/<id>/chronicle_book.pdf` returns 200 with `%PDF` body. (Per the Epic 3 retro, a visual feature needs a real run-the-app check before done.)

## Tasks
- [ ] Task 1 — add reportlab to requirements.txt + install (AC1).
- [ ] Task 2 — book reader route + foreword/epilogue LLM-guard wiring (shared helper) (AC2).
- [ ] Task 3 — `templates/chronicle_book.html` reader (cover/foreword/chapters+callouts/tree/epilogue/print CSS) (AC3).
- [ ] Task 4 — PDF route via reportlab Platypus (AC4).
- [ ] Task 5 — left-rail "Compile Chronicle" button (AC5).
- [ ] Task 6 — integration tests (AC6).
- [ ] Task 7 — pytest 576+new green; import clean; boot 8091 + both routes verified (AC7).

## Dev Notes
- **LLM guard pattern to mirror:** `blueprints/map.py:923-929` (`current_app.config.get('FLASK_APP_LLM_MODEL')`, `if llm_model is not None: llm_model.generate_content(...)`). Wrap the call in try/except and fall back to the deterministic generator on ANY error — the page must never 500 because of the LLM.
- **Imports:** `from models.chronicle_compiler import compile_chronicle` and `from utils.llm_prompts import build_foreword_prompt, generate_foreword_fallback, build_epilogue_prompt, generate_epilogue_fallback`.
- **Conventions:** `@login_required` on both routes; `url_for('blueprint.func')` in the template (never hardcoded URLs); `{{ svg | safe }}` for the server-side SVG strings; flash categories only `success|danger|info|warning`; `db.get_or_404`/`db.session.get` (SA 2.0), no legacy `.query.get()`. Logger `royal_succession.dynasty` (already in the file).
- **Templates extend base.html.** Don't override base fonts/CSS vars.
- **PDF gotchas (pdf skill):** reportlab built-in fonts lack Unicode sub/superscripts → don't use them. Build into `io.BytesIO`, return bytes — do not write a temp file.
- **Self-contained but spans backend+template+JS-free markup.** Per Epic 11 retro policy, run as a **single Sonnet subagent on live `main` (no worktree)** — sequential, no concurrent writer.
- Out of scope: caching/persisting compiled books (would be a schema change → Alembic); SVG-in-PDF; pagination beyond simple page breaks.

## References
- `models/chronicle_compiler.py` (`compile_chronicle`, `ChronicleBook`/`ChronicleChapter`/`ChronicleHighlight`).
- `utils/llm_prompts.py` (the 4 foreword/epilogue functions from 12-2).
- `blueprints/map.py:845-861` (existing chronicle route render pattern), `:923-929` (LLM guard).
- `templates/world_map.html:57-77` (`#game-left-rail`).
- `pdf` skill SKILL.md — reportlab Platypus usage (SimpleDocTemplate/Paragraph/Spacer/PageBreak).
- Design: `_bmad-output/implementation-artifacts/epic-12-design.md`.

## Dev Agent Record
### Agent Model Used
### Completion Notes List
### File List
### Change Log
| Date | Change |
|---|---|
| 2026-06-14 | spec(12-3); chronicle book reader + reportlab PDF + left-rail button (ready-for-dev) |
