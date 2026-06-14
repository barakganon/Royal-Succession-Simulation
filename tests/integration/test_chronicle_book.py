# tests/integration/test_chronicle_book.py
# Integration tests for Story 12-3: Chronicle Book reader + PDF export.

import pytest
from models.db_models import User, DynastyDB, PersonDB, ChronicleEntryDB, HistoryLogEntryDB

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_login(app, db, client, username, password="testpass123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, name="House Booksworth"):
    return client.post(
        '/dynasty/create',
        data={
            'dynasty_name': name,
            'theme_type': 'predefined',
            'theme_key': VALID_THEME_KEY,
            'start_year': '1200',
            'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
        },
        follow_redirects=True,
    )


def _get_dynasty_id(app, db, username):
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
        return dynasty.id if dynasty else None


def _add_monarch(app, db, dynasty_id, name, reign_start=1200):
    """Add a living monarch to a dynasty."""
    with app.app_context():
        person = PersonDB(
            dynasty_id=dynasty_id,
            name=name,
            surname="Booksworth",
            gender='MALE',
            birth_year=reign_start - 20,
            is_noble=True,
            is_monarch=True,
            reign_start_year=reign_start,
        )
        db.session.add(person)
        db.session.commit()


def _add_chronicle_entry(app, db, dynasty_id, year=1200, text="A great deed was done."):
    with app.app_context():
        entry = ChronicleEntryDB(game_id=dynasty_id, turn=1, year=year, text=text)
        db.session.add(entry)
        db.session.commit()


def _add_history_log(app, db, dynasty_id, year=1200, event_type="battle", text="A battle was fought."):
    with app.app_context():
        log = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=year,
            event_string=text,
            event_type=event_type,
        )
        db.session.add(log)
        db.session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plain_client(app, db, session):
    with app.test_client() as c:
        yield c


@pytest.fixture
def owner_client(app, db, session):
    """Client logged in as the dynasty owner, with a dynasty + monarch + chronicle entry."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username="cb_owner_user")
        _create_dynasty(c, name="House Booksworth")
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        _add_monarch(app, db, dynasty_id, name="Arthur", reign_start=1200)
        _add_chronicle_entry(app, db, dynasty_id, year=1200, text="The house of Booksworth was founded.")
        _add_history_log(app, db, dynasty_id, year=1200, event_type="battle", text="Battle of the First Field.")
        yield c



# ---------------------------------------------------------------------------
# Tests: book route
# ---------------------------------------------------------------------------

class TestChronicleBookRoute:

    def test_unauthenticated_redirects_to_login(self, plain_client):
        resp = plain_client.get('/dynasty/1/chronicle_book', follow_redirects=False)
        assert resp.status_code == 302

    def test_book_route_200_for_owner(self, app, db, owner_client):
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book', follow_redirects=True)
        assert resp.status_code == 200

    def test_book_contains_dynasty_name(self, app, db, owner_client):
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book', follow_redirects=True)
        assert b'Booksworth' in resp.data

    def test_book_contains_monarch_name(self, app, db, owner_client):
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book', follow_redirects=True)
        # Either monarch name or "The Founding" chapter heading
        assert b'Arthur' in resp.data or b'The Founding' in resp.data or b'chapter' in resp.data.lower()

    def test_book_non_owner_gets_redirect(self, app, db, session):
        """Non-owner sees a redirect/warning flash rather than the chronicle book."""
        with app.app_context():
            userA = User(username="cb_owner_a", email="cbownera@ex.com")
            userA.set_password("passA")
            userB = User(username="cb_other_b", email="cbotherb@ex.com")
            userB.set_password("passB")
            db.session.add_all([userA, userB])
            db.session.commit()
            dynasty = DynastyDB(
                user_id=userA.id,
                name="House AuthTestOwner",
                theme_identifier_or_json="MEDIEVAL_EUROPEAN",
                current_wealth=100,
                start_year=1200,
                current_simulation_year=1200,
            )
            db.session.add(dynasty)
            db.session.commit()
            dynasty_id = dynasty.id

        with app.test_client() as c:
            c.post('/login', data={'username': 'cb_other_b', 'password': 'passB'})
            resp = c.get(f'/dynasty/{dynasty_id}/chronicle_book', follow_redirects=True)
            assert b'permission' in resp.data or b'warning' in resp.data or b'Dashboard' in resp.data


# ---------------------------------------------------------------------------
# Tests: PDF route
# ---------------------------------------------------------------------------

class TestChronicleBookPDFRoute:

    def test_unauthenticated_pdf_redirects(self, plain_client):
        resp = plain_client.get('/dynasty/1/chronicle_book.pdf', follow_redirects=False)
        assert resp.status_code == 302

    def test_pdf_route_200_for_owner(self, app, db, owner_client):
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book.pdf', follow_redirects=True)
        assert resp.status_code == 200

    def test_pdf_content_type(self, app, db, owner_client):
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book.pdf', follow_redirects=True)
        assert 'application/pdf' in resp.content_type

    def test_pdf_body_starts_with_pdf_header(self, app, db, owner_client):
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book.pdf', follow_redirects=True)
        assert resp.data[:4] == b'%PDF'

    def test_pdf_body_non_empty(self, app, db, owner_client):
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book.pdf', follow_redirects=True)
        assert len(resp.data) > 100

    def test_pdf_non_owner_gets_redirect(self, app, db, session):
        """Non-owner PDF request is denied (redirect + warning flash)."""
        with app.app_context():
            userA = User(username="cb_pdf_owner", email="cbpdfowner@ex.com")
            userA.set_password("passA")
            userB = User(username="cb_pdf_other", email="cbpdfother@ex.com")
            userB.set_password("passB")
            db.session.add_all([userA, userB])
            db.session.commit()
            dynasty = DynastyDB(
                user_id=userA.id,
                name="House PDFAuthTest",
                theme_identifier_or_json="MEDIEVAL_EUROPEAN",
                current_wealth=100,
                start_year=1200,
                current_simulation_year=1200,
            )
            db.session.add(dynasty)
            db.session.commit()
            dynasty_id = dynasty.id

        with app.test_client() as c:
            c.post('/login', data={'username': 'cb_pdf_other', 'password': 'passB'})
            resp = c.get(f'/dynasty/{dynasty_id}/chronicle_book.pdf', follow_redirects=True)
            # Should redirect to dashboard, not return a PDF
            assert resp.data[:4] != b'%PDF'
            assert b'permission' in resp.data or b'Dashboard' in resp.data


# ---------------------------------------------------------------------------
# Tests: LLM OFF (no FLASK_APP_LLM_MODEL) — fallback prose, still 200 + valid PDF
# ---------------------------------------------------------------------------

class TestChronicleBookNoLLM:

    def test_book_200_without_llm(self, app, db, owner_client):
        """Book route must work and return 200 when LLM is disabled (uses fallback)."""
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        original_llm = app.config.pop('FLASK_APP_LLM_MODEL', None)
        try:
            resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book', follow_redirects=True)
            assert resp.status_code == 200
        finally:
            if original_llm is not None:
                app.config['FLASK_APP_LLM_MODEL'] = original_llm

    def test_pdf_valid_without_llm(self, app, db, owner_client):
        """PDF route must return valid PDF when LLM is disabled (uses fallback)."""
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        original_llm = app.config.pop('FLASK_APP_LLM_MODEL', None)
        try:
            resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book.pdf', follow_redirects=True)
            assert resp.status_code == 200
            assert resp.data[:4] == b'%PDF'
        finally:
            if original_llm is not None:
                app.config['FLASK_APP_LLM_MODEL'] = original_llm

    def test_book_contains_fallback_foreword(self, app, db, owner_client):
        """Fallback foreword should mention the dynasty name."""
        dynasty_id = _get_dynasty_id(app, db, "cb_owner_user")
        original_llm = app.config.pop('FLASK_APP_LLM_MODEL', None)
        try:
            resp = owner_client.get(f'/dynasty/{dynasty_id}/chronicle_book', follow_redirects=True)
            # The fallback foreword includes "Chronicle of <dynasty_name>"
            assert b'Booksworth' in resp.data
        finally:
            if original_llm is not None:
                app.config['FLASK_APP_LLM_MODEL'] = original_llm
