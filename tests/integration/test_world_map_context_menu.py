# tests/integration/test_world_map_context_menu.py
# Sprint 3 Story 3-2: right-click context menu + /project_catalogue.json endpoint.

import pytest

from models.db_models import DynastyDB, User

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_and_login(app, db, client, username):
    with app.app_context():
        user = User(username=username, email=f"{username}@x.test")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': 'password123'})


def _create_dynasty(client, name='House Context'):
    client.post('/dynasty/create', data={
        'dynasty_name': name,
        'theme_type': 'predefined',
        'theme_key': VALID_THEME_KEY,
        'start_year': '1300',
        'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
    }, follow_redirects=True)


@pytest.fixture
def ctx_client(app, db, session):
    with app.test_client() as c:
        _register_and_login(app, db, c, username='ctx_user')
        _create_dynasty(c)
        yield c


class TestProjectCatalogueEndpoint:
    def test_project_catalogue_json_returns_expected_shape(self, app, db, ctx_client):
        with app.app_context():
            d = DynastyDB.query.filter_by(name='House Context').first()
            dynasty_id = d.id
        response = ctx_client.get(f'/game/{dynasty_id}/project_catalogue.json')
        assert response.status_code == 200
        payload = response.get_json()
        assert 'projects' in payload
        projects = payload['projects']
        assert len(projects) >= 5  # at least the core catalogue rows

        # Canonical order assertion — first build_* then recruit_* then develop / envoy.
        types = [p['project_type'] for p in projects]
        # build_farm/walls/cathedral first (in some order all before recruit)
        first_recruit = next(i for i, t in enumerate(types) if t.startswith('recruit_'))
        last_build = max(
            (i for i, t in enumerate(types) if t.startswith('build_')),
            default=-1,
        )
        assert last_build < first_recruit

        # Required keys on every entry
        required = {
            'project_type', 'label', 'duration_years',
            'yearly_cost_gold', 'yearly_cost_iron', 'yearly_cost_timber',
            'requires_building',
        }
        for p in projects:
            assert required.issubset(p.keys()), f"missing keys on {p}"

        # Spot-check: build_farm has a label and a 2y duration.
        farms = [p for p in projects if p['project_type'] == 'build_farm']
        assert len(farms) == 1
        farm = farms[0]
        assert farm['label'] == 'Build Farm'
        assert farm['duration_years'] == 2
        assert farm['yearly_cost_gold'] == 30
        assert farm['yearly_cost_timber'] == 20

        # recruit_cavalry has requires_building = 'Stables'
        cavs = [p for p in projects if p['project_type'] == 'recruit_cavalry']
        assert len(cavs) == 1
        assert cavs[0]['requires_building'] == 'Stables'

    def test_project_catalogue_rejects_other_users_dynasty(self, app, db, ctx_client):
        # Create a second user + dynasty via direct DB writes (avoids
        # juggling two test_clients with overlapping cookie/session state,
        # which is fragile in this codebase's auth setup).
        with app.app_context():
            other = User(username='ctx_other', email='ctx_other@x.test')
            other.set_password('password123')
            db.session.add(other)
            db.session.commit()
            other_dynasty = DynastyDB(
                user_id=other.id,
                name='House Foreign',
                theme_identifier_or_json='MEDIEVAL_EUROPEAN',
                current_wealth=100,
                start_year=1300,
                current_simulation_year=1300,
            )
            db.session.add(other_dynasty)
            db.session.commit()
            other_dynasty_id = other_dynasty.id

        # ctx_user (logged-in via ctx_client) tries to read the other user's
        # catalogue → must be rejected.
        response = ctx_client.get(f'/game/{other_dynasty_id}/project_catalogue.json')
        assert response.status_code == 403

    def test_project_catalogue_requires_login(self, app, db):
        # Unauthenticated request — Flask-Login redirects (302) to login.
        with app.app_context():
            user = User(username='ctx_login_check', email='clc@x.test')
            user.set_password('p')
            db.session.add(user)
            db.session.commit()
        with app.test_client() as anon_client:
            anon_client.post('/login', data={'username': 'ctx_login_check', 'password': 'p'})
            _create_dynasty(anon_client, name='House Login')
            with app.app_context():
                dynasty_id = DynastyDB.query.filter_by(name='House Login').first().id

        with app.test_client() as fresh_anon:
            response = fresh_anon.get(f'/game/{dynasty_id}/project_catalogue.json',
                                       follow_redirects=False)
            # Flask-Login default behavior is a 302 redirect to /login.
            assert response.status_code in (302, 401)


class TestWorldMapContextMenuDOM:
    def test_world_map_includes_context_menu_dom(self, ctx_client):
        response = ctx_client.get('/world/map')
        assert response.status_code == 200
        # Container exists
        assert b'id="game-context-menu"' in response.data
        # Header placeholders for territory name + id
        assert b'id="ctx-terr-name"' in response.data
        assert b'id="ctx-terr-id"' in response.data
        # Rows container (populated by JS)
        assert b'id="ctx-rows"' in response.data

    def test_world_map_wires_contextmenu_handler(self, ctx_client):
        # Sanity-check that the JS handler text is in the rendered template.
        response = ctx_client.get('/world/map')
        # The script binds the canvas contextmenu event with preventDefault.
        assert b"addEventListener('contextmenu'" in response.data
        assert b'project_catalogue.json' in response.data
