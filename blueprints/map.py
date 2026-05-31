"""Map Blueprint — handles world map, territory, time, seasonal, chronicle, and advisor routes."""

import logging

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, jsonify, session as flask_session, current_app
)
from flask_login import login_required, current_user

from models.db_models import (
    db, DynastyDB, Territory, ChronicleEntryDB,
    War, DiplomaticRelation, Treaty, TreatyType
)
from models.map_system import MapGenerator, TerritoryManager, BorderSystem
from visualization.map_renderer import MapRenderer

logger = logging.getLogger('royal_succession.map')

map_bp = Blueprint('map', __name__)


# ---------------------------------------------------------------------------
# Map / territory routes
# ---------------------------------------------------------------------------

@map_bp.route('/generate_initial_map')
@login_required
def generate_initial_map():
    """Generate a new map and assign a territory to the user's dynasty."""
    # Get user dynasties
    user_dynasties = DynastyDB.query.filter_by(user_id=current_user.id).all()

    # Create a map generator
    map_generator = MapGenerator(db.session)

    # Generate a procedural map
    map_data = map_generator.generate_procedural_map()

    # Assign some territories to user dynasties
    territory_manager = TerritoryManager(db.session)

    # For each user dynasty, assign a random territory as capital
    for dynasty in user_dynasties:
        # Get a random territory
        territory = Territory.query.order_by(db.func.random()).first()
        if territory:
            territory_manager.assign_territory(territory.id, dynasty.id, is_capital=True)

    flash("Map generated and territory assigned to your dynasty.", "success")
    return redirect(url_for('map.world_map'))


@map_bp.route('/game/<int:dynasty_id>/map.geojson')
@login_required
def map_geojson(dynasty_id):
    """Serve territory map data as GeoJSON for the canvas map.

    Pass ``?hex=true`` to receive col/row grid properties suitable for the
    full-viewport hex canvas renderer in world_map.html.
    """
    from visualization.map_renderer import generate_geojson
    hex_mode = request.args.get('hex', '').lower() in ('true', '1', 'yes')
    try:
        data = generate_geojson(dynasty_id, db.session, hex_mode=hex_mode)
        return jsonify(data)
    except Exception as e:
        logger.error(f"GeoJSON generation failed: {e}")
        return jsonify({'type': 'FeatureCollection', 'features': []}), 200


@map_bp.route('/world/map')
@login_required
def world_map():
    """Display the full-viewport interactive hex-canvas world map."""
    from models.db_models import HistoryLogEntryDB, PersonDB

    dynasty = DynastyDB.query.filter_by(user_id=current_user.id).first()
    dynasty_id = dynasty.id if dynasty else None

    # --- Recent chronicle events for the side-panel feed ---
    recent_events = []
    if dynasty_id:
        try:
            entries = (
                HistoryLogEntryDB.query
                .filter_by(dynasty_id=dynasty_id)
                .order_by(HistoryLogEntryDB.id.desc())
                .limit(5)
                .all()
            )
            recent_events = [
                {
                    'year': e.year,
                    'text': e.event_string,
                    'event_type': e.event_type or 'general',
                }
                for e in entries
            ]
        except Exception as e:
            logger.warning(f"Could not load recent events for dynasty {dynasty_id}: {e}")

    # --- Economy snapshot ---
    economy = {}
    if dynasty_id:
        try:
            from models.economy_system import EconomySystem
            eco = EconomySystem(db.session)
            economy = eco.calculate_dynasty_economy(dynasty_id)
            # Flatten ResourceType enum keys to strings for template serialisation
            if economy:
                simple = {}
                for k, v in economy.items():
                    simple[str(k)] = v
                economy = simple
        except Exception as e:
            logger.warning(f"Could not load economy for dynasty {dynasty_id}: {e}")

    # --- Current monarch mini-card ---
    current_monarch = None
    if dynasty_id:
        try:
            monarch = (
                PersonDB.query
                .filter_by(dynasty_id=dynasty_id, is_monarch=True, death_year=None)
                .first()
            )
            if monarch:
                current_year = dynasty.current_simulation_year if dynasty else 0
                age = (current_year - monarch.birth_year) if monarch.birth_year else 0
                # Story 3-3 review: wire traits into the monarch payload so
                # the detail panel's Traits section is no longer dead code.
                try:
                    traits = monarch.get_traits()
                except Exception:
                    traits = []
                current_monarch = {
                    'name': monarch.name,
                    'surname': monarch.surname,
                    'age': age,
                    'portrait_svg': monarch.portrait_svg or '',
                    'traits': traits,
                }
        except Exception as e:
            logger.warning(f"Could not load monarch for dynasty {dynasty_id}: {e}")

    # --- Dynasty wealth shortcut ---
    gold = dynasty.current_wealth if dynasty else 0

    # --- Active projects for the left-rail slot pills (Sprint 3 Story 3-1) ---
    # Serialize to plain dicts because templates can't safely access raw ORM
    # objects (project-context.md rule). Cap at 3 (the player's slot count)
    # sorted by started_year for deterministic ordering.
    active_projects = []
    if dynasty_id:
        try:
            from models.project_system import ProjectSystem
            ps = ProjectSystem(db.session)
            projects = ps.get_active_projects(dynasty_id)
            projects.sort(key=lambda p: p.started_year)
            active_projects = [
                {
                    'id': p.id,
                    'project_type': p.project_type,
                    'started_year': p.started_year,
                    'completion_year': p.completion_year,
                }
                for p in projects[:3]
            ]
        except Exception as e:
            logger.warning(f"Could not load active projects for dynasty {dynasty_id}: {e}")

    # --- Active wars involving the player dynasty (Sprint 3 Story 3-3 AC6) ---
    # Used by the slide-in detail panel's "war" view. Serialized to plain
    # dicts (template never sees raw ORM objects).
    active_wars = []
    if dynasty_id:
        try:
            from sqlalchemy import or_
            wars = (
                War.query
                .filter(
                    War.is_active == True,
                    or_(
                        War.attacker_dynasty_id == dynasty_id,
                        War.defender_dynasty_id == dynasty_id,
                    ),
                )
                .all()
            )
            for w in wars:
                attacker = DynastyDB.query.get(w.attacker_dynasty_id)
                defender = DynastyDB.query.get(w.defender_dynasty_id)
                active_wars.append({
                    'id': w.id,
                    'attacker_dynasty_id': w.attacker_dynasty_id,
                    'attacker_name': attacker.name if attacker else 'Unknown',
                    'defender_dynasty_id': w.defender_dynasty_id,
                    'defender_name': defender.name if defender else 'Unknown',
                    'start_year': w.start_year,
                })
        except Exception as e:
            logger.warning(f"Could not load active wars for dynasty {dynasty_id}: {e}")

    return render_template(
        'world_map.html',
        dynasty=dynasty,
        dynasty_id=dynasty_id,
        player_dynasty_id=dynasty_id,
        recent_events=recent_events,
        economy=economy,
        current_monarch=current_monarch,
        gold=gold,
        active_projects=active_projects,
        active_wars=active_wars,
    )


@map_bp.route('/game/<int:dynasty_id>/project_catalogue.json')
@login_required
def project_catalogue(dynasty_id):
    """Serve the project type catalogue as JSON for the right-click menu.

    Sprint 3 Story 3-2 — the world_map context menu populates its rows + cost
    preview from this endpoint instead of inlining the catalogue in the
    template. The data is canonical and shared with `models.project_system`.
    """
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    from models.project_system import PROJECT_TYPE_CATALOGUE
    from utils.llm_prompts import project_menu_label

    # Canonical order (matches Story 3-2 spec); `march_army_cross_realm` is in
    # the catalogue for completeness but omitted from the menu — Sprint 4
    # wires that one as a free action initiated from an army token.
    canonical_order = [
        'build_farm',
        'build_walls',
        'build_cathedral',
        'recruit_infantry',
        'recruit_cavalry',
        'develop_territory',
        'envoy_mission',
    ]
    projects = []
    for project_type in canonical_order:
        meta = PROJECT_TYPE_CATALOGUE.get(project_type)
        if meta is None:
            continue
        projects.append({
            'project_type': project_type,
            'label': project_menu_label(project_type),
            'duration_years': meta['duration_years'],
            'yearly_cost_gold': meta['yearly_cost_gold'],
            'yearly_cost_iron': meta['yearly_cost_iron'],
            'yearly_cost_timber': meta['yearly_cost_timber'],
            'requires_building': meta['requires_building'],
        })
    return jsonify({'projects': projects})


@map_bp.route('/territory/<int:territory_id>/details.json')
@login_required
def territory_details_json(territory_id):
    """Serve territory detail data as JSON for the slide-in detail panel.

    Sprint 3 Story 3-3 AC2. Any logged-in player may inspect any hex; the
    `is_player_owned` flag is derived from the current_user's dynasties so
    the frontend can render an "OWNED" badge / action affordances.

    Returns 404 if the territory does not exist.
    """
    from models.db_models import Building, MilitaryUnit, Project

    territory = Territory.query.get_or_404(territory_id)

    # Resolve player ownership against ALL of the current user's dynasties
    # (a user can in theory own more than one — same convention as the
    # existing territory_details route below).
    user_dynasty_ids = {
        d.id for d in DynastyDB.query.filter_by(user_id=current_user.id).all()
    }
    is_player_owned = (
        territory.controller_dynasty_id is not None
        and territory.controller_dynasty_id in user_dynasty_ids
    )

    # Controller dict (or null when the hex is unclaimed).
    controller = None
    if territory.controller_dynasty_id is not None:
        controller_dyn = DynastyDB.query.get(territory.controller_dynasty_id)
        if controller_dyn is not None:
            controller = {'id': controller_dyn.id, 'name': controller_dyn.name}

    terrain_val = (
        territory.terrain_type.value
        if hasattr(territory.terrain_type, 'value')
        else str(territory.terrain_type)
    )

    buildings = Building.query.filter_by(territory_id=territory_id).all()
    buildings_payload = [
        {
            'building_type': (
                b.building_type.value
                if hasattr(b.building_type, 'value')
                else str(b.building_type)
            ),
            'name': b.name,
            'level': b.level,
            'condition': float(b.condition) if b.condition is not None else 1.0,
        }
        for b in buildings
    ]

    # Garrison = ALL military units physically in the territory whose dynasty
    # matches the controller dynasty. (Foreign units present here would be a
    # besieging army; spec doesn't ask us to surface those separately yet.)
    if territory.controller_dynasty_id is not None:
        garrison_units = (
            MilitaryUnit.query
            .filter_by(territory_id=territory_id)
            .filter_by(dynasty_id=territory.controller_dynasty_id)
            .all()
        )
    else:
        garrison_units = []
    garrison_payload = [
        {
            'unit_type': (
                u.unit_type.value
                if hasattr(u.unit_type, 'value')
                else str(u.unit_type)
            ),
            'size': int(u.size or 0),
            'morale': float(u.morale) if u.morale is not None else 1.0,
            'quality': float(u.quality) if u.quality is not None else 1.0,
        }
        for u in garrison_units
    ]

    # Active player-owned project targeting this territory (earliest by
    # started_year) — mirrors the GeoJSON enrichment rule.
    active_project_payload = None
    if user_dynasty_ids:
        proj = (
            Project.query
            .filter(Project.status == 'active')
            .filter(Project.dynasty_id.in_(user_dynasty_ids))
            .filter(Project.target_territory_id == territory_id)
            .order_by(Project.started_year.asc())
            .first()
        )
        if proj is not None:
            active_project_payload = {
                'id': proj.id,
                'project_type': proj.project_type,
                'started_year': proj.started_year,
                'completion_year': proj.completion_year,
            }

    return jsonify({
        'territory': {
            'id': territory.id,
            'name': territory.name,
            'terrain_type': terrain_val,
            'population': int(getattr(territory, 'population', 0) or 0),
            'development_level': int(getattr(territory, 'development_level', 0) or 0),
            'is_capital': bool(getattr(territory, 'is_capital', False)),
            'base_tax': int(getattr(territory, 'base_tax', 0) or 0),
            'fortification_level': int(getattr(territory, 'fortification_level', 0) or 0),
            'controller': controller,
            'is_player_owned': is_player_owned,
        },
        'buildings': buildings_payload,
        'garrison': garrison_payload,
        'active_project': active_project_payload,
    })


@map_bp.route('/territory/<int:territory_id>')
@login_required
def territory_details(territory_id):
    """View details of a specific territory."""
    # Get territory
    territory = Territory.query.get_or_404(territory_id)

    # Check if territory is controlled by user's dynasty
    user_dynasties = DynastyDB.query.filter_by(user_id=current_user.id).all()
    user_dynasty_ids = [d.id for d in user_dynasties]

    is_owned = territory.controller_dynasty_id in user_dynasty_ids

    # Get settlements in this territory
    settlements = territory.settlements

    # Get resources in this territory
    resources = territory.resources

    # Get buildings in this territory
    buildings = territory.buildings

    # Get units in this territory
    units = territory.units_present

    # Get armies in this territory
    armies = territory.armies_present

    # Create map renderer
    map_renderer = MapRenderer(db.session)

    # Render territory map
    territory_image = None
    try:
        territory_image = map_renderer.render_territory_map(territory_id)
    except Exception as e:
        logger.error(f"Error rendering territory map: {e}", exc_info=True)

    return render_template('territory_details.html',
                           territory=territory,
                           is_owned=is_owned,
                           settlements=settlements,
                           resources=resources,
                           buildings=buildings,
                           units=units,
                           armies=armies,
                           territory_image=territory_image)


@map_bp.route('/dynasty/<int:dynasty_id>/territories')
@login_required
def dynasty_territories(dynasty_id):
    """View and manage territories controlled by a dynasty."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)

    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get territories controlled by this dynasty
    territories = Territory.query.filter_by(controller_dynasty_id=dynasty_id).all()

    # Get border territories
    border_system = BorderSystem(db.session)
    border_territories = border_system.get_border_territories(dynasty_id)

    # Get contested territories (territories at borders with potential conflicts)
    contested_territories = []
    try:
        for territory in border_territories:
            neighbors = border_system.get_neighboring_territories(territory.id)
            for neighbor in neighbors:
                if neighbor.controller_dynasty_id and neighbor.controller_dynasty_id != dynasty_id:
                    contested_territories.append(territory)
                    break
    except Exception as e:
        logger.error(f"Error determining contested territories: {e}", exc_info=True)

    # Create map renderer
    map_renderer = MapRenderer(db.session)

    # Render map highlighting dynasty territories
    dynasty_map = None
    try:
        dynasty_map = map_renderer.render_world_map(
            show_terrain=False,
            show_territories=True,
            show_settlements=True,
            show_units=True,
            highlight_dynasty_id=dynasty_id
        )
    except Exception as e:
        logger.error(f"Error rendering dynasty map: {e}", exc_info=True)

    return render_template('dynasty_territories.html',
                           dynasty=dynasty,
                           territories=territories,
                           border_territories=border_territories,
                           contested_territories=contested_territories,
                           dynasty_map=dynasty_map)


@map_bp.route('/generate_map', methods=['POST'])
@login_required
def generate_map():
    """Generate a new map."""
    # Only allow admins to generate maps
    if current_user.username != 'admin':
        flash("Only administrators can generate maps.", "danger")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    template_name = request.form.get('template_name', 'default')

    # Create map generator
    map_generator = MapGenerator(db.session)

    try:
        # Generate map
        if template_name != 'default':
            map_data = map_generator.generate_predefined_map(template_name)
        else:
            map_data = map_generator.generate_procedural_map()

        flash(f"Map generated successfully with {len(map_data['territories'])} territories.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to generate map: {e}")
        flash(f"Failed to generate map: {e}", "danger")

    # Redirect to world map
    return redirect(url_for('map.world_map'))


# ---------------------------------------------------------------------------
# Time / season routes
# ---------------------------------------------------------------------------

@map_bp.route('/dynasty/<int:dynasty_id>/time')
@login_required
def time_view(dynasty_id):
    """View time management interface for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get current year and season
    current_year = dynasty.current_simulation_year

    try:
        from models.time_system import TimeSystem, Season
        from visualization.time_renderer import TimeRenderer

        time_system = TimeSystem(db.session)
        time_renderer = TimeRenderer(db.session)

        current_season = time_system.get_current_season(current_year)

        timeline_events = time_system.get_historical_timeline(
            dynasty_id,
            start_year=current_year - 10 if current_year > dynasty.start_year + 10 else dynasty.start_year,
            end_year=current_year
        )

        scheduled_events = time_system.get_scheduled_timeline(dynasty_id)

        timeline_image = time_renderer.render_timeline(
            dynasty_id,
            start_year=current_year - 10 if current_year > dynasty.start_year + 10 else dynasty.start_year,
            end_year=current_year
        )
        timeline_image_url = timeline_image.replace('static/', '/static/') if timeline_image else None

        if scheduled_events:
            scheduled_events_image = time_renderer.render_scheduled_events(dynasty_id)
            scheduled_events_image_url = (
                scheduled_events_image.replace('static/', '/static/')
                if scheduled_events_image else None
            )
        else:
            scheduled_events_image_url = None

        seasonal_map_image = time_renderer.render_seasonal_map(current_year)
        seasonal_map_image_url = (
            seasonal_map_image.replace('static/', '/static/')
            if seasonal_map_image else None
        )

        action_points = time_system.calculate_action_points(dynasty_id)
        population_growth_rates = time_system.get_population_growth_rates()

    except Exception as e:
        flash(f"Error loading time system: {str(e)}", "danger")
        return render_template('time_view.html',
                               dynasty=dynasty,
                               current_year=current_year,
                               current_season=None,
                               timeline_events=[],
                               scheduled_events=[],
                               timeline_image_url=None,
                               scheduled_events_image_url=None,
                               seasonal_map_image_url=None,
                               action_points=0,
                               population_growth_rates={})

    return render_template('time_view.html',
                           dynasty=dynasty,
                           current_year=current_year,
                           current_season=current_season,
                           timeline_events=timeline_events,
                           scheduled_events=scheduled_events,
                           timeline_image_url=timeline_image_url,
                           scheduled_events_image_url=scheduled_events_image_url,
                           seasonal_map_image_url=seasonal_map_image_url,
                           action_points=action_points,
                           population_growth_rates=population_growth_rates)


@map_bp.route('/dynasty/<int:dynasty_id>/advance_time', methods=['POST'])
@login_required
def advance_time(dynasty_id):
    """Advance time for a dynasty by processing a turn."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        from models.time_system import TimeSystem

        time_system = TimeSystem(db.session)
        success, message = time_system.process_turn(dynasty_id)

        if success:
            flash(message, "success")
        else:
            flash(f"Error advancing time: {message}", "danger")

    except Exception as e:
        flash(f"Error advancing time: {str(e)}", "danger")

    return redirect(url_for('map.time_view', dynasty_id=dynasty_id))


@map_bp.route('/dynasty/<int:dynasty_id>/schedule_event', methods=['POST'])
@login_required
def schedule_event(dynasty_id):
    """Schedule a new event for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        from models.time_system import TimeSystem, EventType, EventPriority

        event_type_str = request.form.get('event_type')
        year = request.form.get('year')
        priority_str = request.form.get('priority', 'MEDIUM')
        action = request.form.get('action')
        target_dynasty_id = request.form.get('target_dynasty_id')
        territory_id = request.form.get('territory_id')

        if not event_type_str or not year or not action:
            flash("Missing required fields for scheduling an event.", "danger")
            return redirect(url_for('map.time_view', dynasty_id=dynasty_id))

        try:
            year = int(year)
        except ValueError:
            flash("Year must be a number.", "danger")
            return redirect(url_for('map.time_view', dynasty_id=dynasty_id))

        if year <= dynasty.current_simulation_year:
            flash("Events can only be scheduled for future years.", "danger")
            return redirect(url_for('map.time_view', dynasty_id=dynasty_id))

        event_data = {
            "action": action,
            "actor_dynasty_id": dynasty_id
        }

        if target_dynasty_id:
            event_data["target_dynasty_id"] = int(target_dynasty_id)

        if territory_id:
            event_data["territory_id"] = int(territory_id)

        time_system = TimeSystem(db.session)
        event_id = time_system.schedule_event(
            event_type=EventType[event_type_str],
            year=year,
            data=event_data,
            priority=EventPriority[priority_str]
        )

        flash(f"Event scheduled successfully for year {year}.", "success")

    except Exception as e:
        flash(f"Error scheduling event: {str(e)}", "danger")

    return redirect(url_for('map.time_view', dynasty_id=dynasty_id))


@map_bp.route('/dynasty/<int:dynasty_id>/cancel_event/<int:event_id>', methods=['POST'])
@login_required
def cancel_event(dynasty_id, event_id):
    """Cancel a scheduled event."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        from models.time_system import TimeSystem

        time_system = TimeSystem(db.session)
        success = time_system.cancel_event(event_id)

        if success:
            flash("Event cancelled successfully.", "success")
        else:
            flash("Event not found or already processed.", "warning")

    except Exception as e:
        flash(f"Error cancelling event: {str(e)}", "danger")

    return redirect(url_for('map.time_view', dynasty_id=dynasty_id))


@map_bp.route('/dynasty/<int:dynasty_id>/timeline')
@login_required
def timeline_view(dynasty_id):
    """View the historical timeline for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    start_year = request.args.get('start_year')
    end_year = request.args.get('end_year')

    if start_year:
        try:
            start_year = int(start_year)
        except ValueError:
            start_year = dynasty.start_year
    else:
        start_year = dynasty.start_year

    if end_year:
        try:
            end_year = int(end_year)
        except ValueError:
            end_year = dynasty.current_simulation_year
    else:
        end_year = dynasty.current_simulation_year

    try:
        from models.time_system import TimeSystem
        from visualization.time_renderer import TimeRenderer

        time_system = TimeSystem(db.session)
        time_renderer = TimeRenderer(db.session)

        timeline_events = time_system.get_historical_timeline(dynasty_id, start_year, end_year)

        timeline_image = time_renderer.render_timeline(dynasty_id, start_year, end_year)
        timeline_image_url = timeline_image.replace('static/', '/static/') if timeline_image else None

    except Exception as e:
        flash(f"Error loading timeline: {str(e)}", "danger")
        return render_template('timeline_view.html',
                               dynasty=dynasty,
                               start_year=start_year,
                               end_year=end_year,
                               timeline_events=[],
                               timeline_image_url=None)

    return render_template('timeline_view.html',
                           dynasty=dynasty,
                           start_year=start_year,
                           end_year=end_year,
                           timeline_events=timeline_events,
                           timeline_image_url=timeline_image_url)


@map_bp.route('/world/seasons/<int:year>')
@login_required
def seasonal_map(year):
    """View the seasonal map for a specific year."""
    try:
        from models.time_system import TimeSystem
        from visualization.time_renderer import TimeRenderer

        time_system = TimeSystem(db.session)
        time_renderer = TimeRenderer(db.session)

        current_season = time_system.get_current_season(year)

        seasonal_map_image = time_renderer.render_seasonal_map(year)
        seasonal_map_image_url = (
            seasonal_map_image.replace('static/', '/static/')
            if seasonal_map_image else None
        )

    except Exception as e:
        flash(f"Error generating seasonal map: {str(e)}", "danger")
        return render_template('seasonal_map.html',
                               year=year,
                               current_season=None,
                               seasonal_map_image_url=None)

    return render_template('seasonal_map.html',
                           year=year,
                           current_season=current_season,
                           seasonal_map_image_url=seasonal_map_image_url)


@map_bp.route('/world/synchronize_turns', methods=['POST'])
@login_required
def synchronize_turns():
    """Synchronize turns for multiple dynasties."""
    dynasty_ids = request.form.getlist('dynasty_ids')

    if not dynasty_ids:
        flash("No dynasties selected for synchronization.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        dynasty_ids = [int(did) for did in dynasty_ids]
    except ValueError:
        flash("Invalid dynasty IDs.", "danger")
        return redirect(url_for('auth.dashboard'))

    for dynasty_id in dynasty_ids:
        dynasty = DynastyDB.query.get(dynasty_id)
        if not dynasty or dynasty.owner_user != current_user:
            flash("You can only synchronize dynasties that you own.", "warning")
            return redirect(url_for('auth.dashboard'))

    try:
        from models.time_system import TimeSystem

        time_system = TimeSystem(db.session)
        success, message = time_system.synchronize_turns(dynasty_ids)

        if success:
            flash(message, "success")
        else:
            flash(f"Error synchronizing turns: {message}", "danger")

    except Exception as e:
        flash(f"Error synchronizing turns: {str(e)}", "danger")

    return redirect(url_for('auth.dashboard'))


# ---------------------------------------------------------------------------
# Chronicle route
# ---------------------------------------------------------------------------

@map_bp.route('/game/<int:dynasty_id>/chronicle')
@login_required
def view_chronicle(dynasty_id):
    """Display the LLM-narrated living chronicle for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.dashboard'))
    entries = ChronicleEntryDB.query.filter_by(game_id=dynasty_id).order_by(
        ChronicleEntryDB.turn.desc()
    ).all()
    return render_template('chronicle.html', dynasty=dynasty, entries=entries)


# ---------------------------------------------------------------------------
# AI Advisor route
# ---------------------------------------------------------------------------

@map_bp.route('/game/<int:dynasty_id>/advisor')
@login_required
def game_advisor(dynasty_id):
    """Return JSON with 2-3 strategic suggestions from the AI advisor.

    Caches the result in Flask session keyed by (dynasty_id, turn) to avoid
    redundant LLM calls on page refresh.
    """
    from utils.llm_prompts import build_advisor_prompt, generate_advisor_fallback

    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    # Build cache key using current simulation year as turn proxy
    current_turn = getattr(dynasty, 'current_simulation_year', 0) or 0
    cache_key = f'advisor_{dynasty_id}_{current_turn}'

    # Check Flask session cache
    if cache_key in flask_session:
        return jsonify({'suggestions': flask_session[cache_key]})

    # Build game state summary
    treasury = getattr(dynasty, 'current_wealth', 0) or 0
    year = getattr(dynasty, 'current_simulation_year', 1000) or 1000
    season = 'Spring'  # DynastyDB has no season field; use a sensible default

    active_wars = War.query.filter(
        (War.attacker_dynasty_id == dynasty_id) | (War.defender_dynasty_id == dynasty_id),
        War.is_active == True
    ).count()

    alliance_types = [TreatyType.DEFENSIVE_ALLIANCE, TreatyType.MILITARY_ALLIANCE]
    allies = (
        Treaty.query
        .join(DiplomaticRelation, Treaty.diplomatic_relation_id == DiplomaticRelation.id)
        .filter(
            (DiplomaticRelation.dynasty1_id == dynasty_id) | (DiplomaticRelation.dynasty2_id == dynasty_id),
            Treaty.treaty_type.in_(alliance_types),
            Treaty.active == True
        )
        .count()
    )

    neighbours = DynastyDB.query.filter(DynastyDB.id != dynasty_id).all()

    def _dynasty_strength(d):
        return sum(
            unit.calculate_strength()
            for unit in d.military_units.all()
        )

    strongest = max(neighbours, key=_dynasty_strength, default=None)
    strongest_name = strongest.name if strongest else 'unknown'

    # Resolve LLM model from app config
    llm_model = current_app.config.get('FLASK_APP_LLM_MODEL')

    suggestions = []
    if llm_model is not None:
        try:
            prompt = build_advisor_prompt(dynasty.name, year, season, treasury, strongest_name, active_wars)
            response = llm_model.generate_content(
                prompt,
                generation_config={'max_output_tokens': 200}
            )
            text = response.text.strip()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            suggestions = [l.lstrip('123. ').strip() for l in lines if l and l[0].isdigit()][:3]
        except Exception as e:
            logger.warning(f"Advisor LLM call failed for dynasty {dynasty_id}: {e}")

    if not suggestions:
        suggestions = generate_advisor_fallback(treasury, active_wars, allies > 0)

    # Cache in Flask session
    flask_session[cache_key] = suggestions
    flask_session.modified = True

    return jsonify({'suggestions': suggestions})
