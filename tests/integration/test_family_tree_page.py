# tests/integration/test_family_tree_page.py
# Story 8-2 (B)+(C)+(D) — Interactive family-tree page, SVG endpoint, person JSON
# endpoint, ownership guard, and the nav link on the dynasty view page.
#
# CONTRACT-FIRST integration tests written by Agent C in an isolated worktree.
# They pin the routes registered on the dynasty blueprint:
#   GET /dynasty/<id>/family_tree         -> HTML page (200) with the frozen DOM
#                                            ids ft-viewport / ft-show-deceased /
#                                            ft-search and an inline <svg>.
#   GET /dynasty/<id>/family_tree.svg      -> image/svg+xml, body startswith <svg>;
#                                            ?show_deceased=0 omits deceased members.
#   GET /dynasty/<id>/person/<pid>.json    -> exact key set; 404 for unknown id.
#   ownership: a second user is refused the HTML page ('Not authorized' / redirect).
#   /dynasty/<id>/view contains a '/family_tree' link (Story 8-2 (D) nav entry).
#
# Mirrors tests/integration/test_dynasty_routes.py: fixtures dynasty_client,
# helpers _register_and_login / _get_dynasty_id / _create_dynasty, and the
# ownership-forbidden pattern (test_dynasty_routes.py:229-255).
#
# Several assertions WILL FAIL in this isolated worktree until the backend agent
# adds the routes + the page agent adds family_tree.html / the nav link. That is
# EXPECTED and correct for a contract-first suite — do not weaken, stub, or skip.

import pytest

from models.db_models import User, DynastyDB, PersonDB

# The correct theme key as stored in cultural_themes.json
VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'

# The exact JSON key set the person_detail_json route must return.
EXPECTED_PERSON_KEYS = {
    'id', 'name', 'surname', 'gender', 'birth_year', 'death_year', 'age',
    'traits', 'titles', 'is_monarch', 'is_pretender', 'reign_start_year',
}


# ---------------------------------------------------------------------------
# Shared helpers (mirror tests/integration/test_dynasty_routes.py)
# ---------------------------------------------------------------------------

def _register_and_login(app, db, client, username="dyn_user", password="dynpass123"):
    """Create a user in the DB (inside app_context) and log in via the client."""
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, dynasty_name="House Ironwood", start_year="1200"):
    """Submit the create dynasty form and return the response."""
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


def _get_dynasty_id(app, db, username="dyn_user"):
    """Return the first dynasty id owned by the given user."""
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
        return dynasty.id if dynasty else None


def _add_couple_with_deceased(app, db, dynasty_id):
    """Add a living monarch + a DECEASED spouse to a dynasty.

    Returns (living_id, deceased_id, deceased_name). The deceased member is used
    to exercise the show_deceased=0 filter (their name is present by default but
    absent when deceased are hidden).
    """
    with app.app_context():
        living = PersonDB(
            dynasty_id=dynasty_id,
            name="Alaric",
            surname="Ironwood",
            gender="MALE",
            birth_year=1180,
            death_year=None,
            is_noble=True,
            is_monarch=True,
        )
        deceased = PersonDB(
            dynasty_id=dynasty_id,
            name="Wulfgang",
            surname="Ironwood",
            gender="MALE",
            birth_year=1140,
            death_year=1199,
            is_noble=True,
            is_monarch=False,
        )
        db.session.add_all([living, deceased])
        db.session.commit()
        return living.id, deceased.id, deceased.name


def _first_member_id(app, db, dynasty_id):
    """Return the id of an arbitrary member of the dynasty (or None)."""
    with app.app_context():
        person = (
            db.session.query(PersonDB)
            .filter_by(dynasty_id=dynasty_id)
            .first()
        )
        return person.id if person else None


# ---------------------------------------------------------------------------
# Fixtures (mirror test_dynasty_routes.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def plain_client(app, db, session):
    """Unauthenticated client with a clean DB."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def dynasty_client(app, db, session):
    """Client with a logged-in user who already owns one dynasty."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username="dyn_user")
        _create_dynasty(c)
        yield c


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/family_tree — interactive HTML page
# ---------------------------------------------------------------------------

class TestFamilyTreePage:
    def test_family_tree_page_returns_200(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        assert dynasty_id is not None
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/family_tree')
        assert response.status_code == 200

    def test_family_tree_page_contains_inline_svg(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/family_tree')
        assert b'<svg' in response.data

    def test_family_tree_page_has_frozen_dom_ids(self, dynasty_client, app, db):
        """The page exposes the frozen DOM ids the JS hooks into."""
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/family_tree')
        assert b'id="ft-viewport"' in response.data
        assert b'id="ft-show-deceased"' in response.data
        assert b'id="ft-search"' in response.data

    def test_family_tree_page_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/family_tree', follow_redirects=False)
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/family_tree.svg — raw SVG endpoint + show_deceased filter
# ---------------------------------------------------------------------------

class TestFamilyTreeSvgEndpoint:
    def test_svg_endpoint_returns_svg_content_type(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        _add_couple_with_deceased(app, db, dynasty_id)
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/family_tree.svg')
        assert response.status_code == 200
        assert 'image/svg+xml' in response.content_type
        assert response.data.startswith(b'<svg')

    def test_show_deceased_zero_hides_deceased_member(self, dynasty_client, app, db):
        """A deceased member's name is present by default but absent with ?show_deceased=0."""
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        _living_id, _deceased_id, deceased_name = _add_couple_with_deceased(
            app, db, dynasty_id
        )
        name_bytes = deceased_name.encode()

        default_resp = dynasty_client.get(f'/dynasty/{dynasty_id}/family_tree.svg')
        assert default_resp.status_code == 200
        assert name_bytes in default_resp.data, (
            "deceased member should appear in the default (show_deceased) SVG"
        )

        hidden_resp = dynasty_client.get(
            f'/dynasty/{dynasty_id}/family_tree.svg?show_deceased=0'
        )
        assert hidden_resp.status_code == 200
        assert name_bytes not in hidden_resp.data, (
            "deceased member must be hidden when show_deceased=0"
        )

    def test_svg_endpoint_unauthenticated_redirects(self, plain_client):
        response = plain_client.get('/dynasty/1/family_tree.svg', follow_redirects=False)
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# GET /dynasty/<id>/person/<pid>.json — per-person detail
# ---------------------------------------------------------------------------

class TestPersonDetailJson:
    def test_person_json_has_exact_key_set(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        living_id, _deceased_id, _name = _add_couple_with_deceased(
            app, db, dynasty_id
        )
        response = dynasty_client.get(
            f'/dynasty/{dynasty_id}/person/{living_id}.json'
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload is not None
        assert set(payload.keys()) == EXPECTED_PERSON_KEYS, (
            f"unexpected key set: {sorted(payload.keys())}"
        )
        assert payload['id'] == living_id
        assert isinstance(payload['traits'], list)
        assert isinstance(payload['titles'], list)
        assert isinstance(payload['is_monarch'], bool)
        assert isinstance(payload['is_pretender'], bool)

    def test_person_json_nonexistent_returns_404(self, dynasty_client, app, db):
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(
            f'/dynasty/{dynasty_id}/person/9999999.json'
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ownership guard — a second user cannot view another's family tree
# ---------------------------------------------------------------------------

class TestFamilyTreeOwnership:
    def test_other_user_family_tree_forbidden(self, app, db, session):
        """User A cannot view User B's family tree — 'Not authorized' flash / redirect."""
        with app.app_context():
            userA = User(username="ft_usr_a", email="fta@ex.com")
            userA.set_password("passA")
            userB = User(username="ft_usr_b", email="ftb@ex.com")
            userB.set_password("passB")
            db.session.add_all([userA, userB])
            db.session.commit()
            dynasty = DynastyDB(
                user_id=userB.id,
                name="House UserB Tree",
                theme_identifier_or_json="MEDIEVAL_EUROPEAN",
                current_wealth=100,
                start_year=1000,
                current_simulation_year=1000,
            )
            db.session.add(dynasty)
            db.session.commit()
            dynasty_id = dynasty.id

        with app.test_client() as c:
            c.post('/login', data={'username': 'ft_usr_a', 'password': 'passA'})
            response = c.get(
                f'/dynasty/{dynasty_id}/family_tree', follow_redirects=True
            )
            assert b'Not authorized' in response.data


# ---------------------------------------------------------------------------
# Nav entry on the dynasty view page (Story 8-2 (D))
# ---------------------------------------------------------------------------

class TestViewDynastyNavLink:
    def test_view_page_links_to_family_tree(self, dynasty_client, app, db):
        """The /dynasty/<id>/view page contains a link to the family tree."""
        dynasty_id = _get_dynasty_id(app, db, username="dyn_user")
        response = dynasty_client.get(f'/dynasty/{dynasty_id}/view')
        assert response.status_code == 200
        assert b'/family_tree' in response.data
