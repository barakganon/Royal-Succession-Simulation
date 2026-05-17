# tests/integration/test_project_turn_lifecycle.py
# Integration tests for Story 2-3: ProjectSystem wired into the turn loop +
# submit_actions migration. End-to-end: player POSTs a project-starter action,
# advance_turn loops through years, project completes, real effect fires.

import json
import pytest

from models.db_models import (
    Army, Building, BuildingType, DynastyDB, MilitaryUnit, PersonDB,
    Project, Region, Province, Territory, TerrainType, User,
)

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_and_login(app, db, client, username="proj_user", password="projpass123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty_with_monarch_and_territory(app, db, username, start_year=1300,
                                                wealth=500, iron=200, timber=200):
    """Create user + dynasty (with monarch + a controlled territory)."""
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        dynasty = DynastyDB(
            user_id=user.id,
            name="House Project",
            theme_identifier_or_json=VALID_THEME_KEY,
            current_wealth=wealth,
            current_iron=iron,
            current_timber=timber,
            start_year=start_year,
            current_simulation_year=start_year,
        )
        db.session.add(dynasty)
        db.session.commit()

        monarch = PersonDB(
            dynasty_id=dynasty.id,
            name="Aldric",
            surname="Project",
            gender="MALE",
            birth_year=start_year - 30,
            is_noble=True,
            is_monarch=True,
            reign_start_year=start_year,
        )
        db.session.add(monarch)

        region = Region(name="Test Region", description="x")
        db.session.add(region)
        db.session.commit()
        province = Province(
            region_id=region.id, name="Test Province",
            primary_terrain=TerrainType.PLAINS,
        )
        db.session.add(province)
        db.session.commit()
        territory = Territory(
            province_id=province.id,
            name="Test Hold",
            terrain_type=TerrainType.PLAINS,
            x_coordinate=0.0, y_coordinate=0.0,
            controller_dynasty_id=dynasty.id,
            development_level=2,
        )
        db.session.add(territory)
        db.session.commit()
        return dynasty.id, monarch.id, territory.id


@pytest.fixture
def project_client(app, db, session):
    """Client logged in as a fresh user, with a dynasty + monarch + territory."""
    with app.test_client() as c:
        _register_and_login(app, db, c, username="proj_user")
        ids = _create_dynasty_with_monarch_and_territory(app, db, username="proj_user")
        yield c, ids  # (client, (dynasty_id, monarch_id, territory_id))


class TestBuildProjectFullLifecycle:
    def test_build_action_creates_project_row(self, project_client, app, db):
        client, (dynasty_id, _, territory_id) = project_client
        response = client.post(
            f'/dynasty/{dynasty_id}/submit_actions',
            data=json.dumps([{
                'type': 'build',
                'params': {'territory_id': territory_id, 'building_type': 'farm'},
            }]),
            content_type='application/json',
            follow_redirects=True,
        )
        assert response.status_code == 200
        with app.app_context():
            projects = db.session.query(Project).filter_by(
                dynasty_id=dynasty_id, project_type='build_farm',
            ).all()
            assert len(projects) == 1
            project = projects[0]
            # The turn-loop advanced 5 years AND ticked the project, completing
            # it (build_farm duration = 2). Status is 'completed' and a Building
            # row exists.
            assert project.status == 'completed'
            farms = db.session.query(Building).filter_by(
                territory_id=territory_id,
                building_type=BuildingType.FARM,
            ).all()
            assert len(farms) == 1

    def test_recruit_action_creates_unit_after_completion(self, project_client, app, db):
        client, (dynasty_id, _, territory_id) = project_client
        response = client.post(
            f'/dynasty/{dynasty_id}/submit_actions',
            data=json.dumps([{
                'type': 'recruit',
                'params': {'territory_id': territory_id, 'size': 100},
            }]),
            content_type='application/json',
            follow_redirects=True,
        )
        assert response.status_code == 200
        with app.app_context():
            units = db.session.query(MilitaryUnit).filter_by(
                dynasty_id=dynasty_id, territory_id=territory_id,
            ).all()
            assert len(units) == 1  # recruit_infantry duration=1, well within 5-year turn

    def test_develop_action_raises_development_level(self, project_client, app, db):
        client, (dynasty_id, _, territory_id) = project_client
        response = client.post(
            f'/dynasty/{dynasty_id}/submit_actions',
            data=json.dumps([{
                'type': 'develop',
                'params': {'territory_id': territory_id},
            }]),
            content_type='application/json',
            follow_redirects=True,
        )
        assert response.status_code == 200
        with app.app_context():
            territory = db.session.get(Territory, territory_id)
            # develop_territory duration=3, fits within the 5-year turn → dev_level
            # bumps from 2 → 3.
            assert territory.development_level == 3


class TestInstantActionsStillWork:
    def test_march_action_still_instant(self, project_client, app, db):
        """AC5: march remains instant — no Project row created."""
        client, (dynasty_id, _, territory_id) = project_client
        # Set up an army at a different territory so march has somewhere to come from.
        with app.app_context():
            other_territory = Territory(
                province_id=db.session.query(Province).first().id,
                name="Source Hold",
                terrain_type=TerrainType.PLAINS,
                x_coordinate=1.0, y_coordinate=1.0,
                controller_dynasty_id=dynasty_id,
                development_level=1,
            )
            db.session.add(other_territory)
            db.session.commit()
            army = Army(
                dynasty_id=dynasty_id,
                name='Test Army',
                territory_id=other_territory.id,
                is_active=True,
                created_year=1300,
            )
            db.session.add(army)
            db.session.commit()
            army_id = army.id

        response = client.post(
            f'/dynasty/{dynasty_id}/submit_actions',
            data=json.dumps([{
                'type': 'march',
                'params': {'army_id': army_id, 'territory_id': territory_id},
            }]),
            content_type='application/json',
            follow_redirects=True,
        )
        assert response.status_code == 200
        with app.app_context():
            march_projects = db.session.query(Project).filter_by(
                dynasty_id=dynasty_id,
                project_type='march_army_cross_realm',
            ).all()
            assert march_projects == [], "march should remain instant, no project row"
