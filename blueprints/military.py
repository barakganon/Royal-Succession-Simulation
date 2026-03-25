"""Military Blueprint — handles military management, recruitment, armies, battles, sieges, and naval combat."""

import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models.db_models import (
    db, DynastyDB, PersonDB, Territory,
    MilitaryUnit, UnitType, Army, Battle, Siege
)
from models.military_system import MilitarySystem
from models.map_system import MovementSystem
from models.time_system import TimeSystem
from models.game_manager import GameManager

logger = logging.getLogger('royal_succession.military')

military_bp = Blueprint('military', __name__)


# Military routes
@military_bp.route('/dynasty/<int:dynasty_id>/military')
@login_required
def military_view(dynasty_id):
    """View and manage military units and armies for a dynasty."""
    logger.info(f"Rendering military_view for dynasty_id: {dynasty_id}")
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get military units and armies
    units = MilitaryUnit.query.filter_by(dynasty_id=dynasty_id, army_id=None).all()
    armies = Army.query.filter_by(dynasty_id=dynasty_id).all()

    # Get potential commanders
    commanders = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        death_year=None
    ).all()

    # Filter to those who can lead armies
    potential_commanders = [p for p in commanders if p.can_lead_army()]

    # Get controlled territories for recruitment
    territories = Territory.query.filter_by(controller_dynasty_id=dynasty_id).all()

    # Get military overview visualization
    from visualization.military_renderer import MilitaryRenderer
    military_renderer = MilitaryRenderer(db.session)
    military_overview = military_renderer.render_military_overview(dynasty_id)

    return render_template('military_view.html',
                          dynasty=dynasty,
                          units=units,
                          armies=armies,
                          potential_commanders=potential_commanders,
                          territories=territories,
                          military_overview=military_overview)


@military_bp.route('/dynasty/<int:dynasty_id>/recruit_unit', methods=['POST'])
@login_required
def recruit_unit(dynasty_id):
    """Recruit a new military unit."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    unit_type_str = request.form.get('unit_type')
    size = request.form.get('size', type=int)
    territory_id = request.form.get('territory_id', type=int)
    name = request.form.get('name')

    # Validate data
    if not unit_type_str or not size or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))

    try:
        unit_type = UnitType(unit_type_str)
    except ValueError:
        flash("Invalid unit type.", "danger")
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))
    from flask import current_app
    current_app.logger.info(f"Recruit unit called with dynasty_id={dynasty_id}, unit_type={unit_type_str}, size={size}, territory_id={territory_id}, name={name}")

    # Recruit unit
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, unit = military_system.recruit_unit(
        dynasty_id=dynasty_id,
        unit_type=unit_type,
        size=size,
        territory_id=territory_id,
        name=name
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('military.military_view', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/form_army', methods=['POST'])
@login_required
def form_army(dynasty_id):
    """Form a new army from individual units."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    unit_ids = request.form.getlist('unit_ids', type=int)
    name = request.form.get('name')
    commander_id = request.form.get('commander_id', type=int)

    # Validate data
    if not unit_ids or not name:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))

    # Form army
    military_system = MilitarySystem(db.session)
    success, message, army = military_system.form_army(
        dynasty_id=dynasty_id,
        unit_ids=unit_ids,
        name=name,
        commander_id=commander_id
    )

    logger.info(f"form_army: unit_ids={unit_ids}, name='{name}', commander_id={commander_id}, success={success}, message='{message}'")

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('military.military_view', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/assign_commander', methods=['POST'])
@login_required
def assign_commander(dynasty_id):
    """Assign a commander to an army."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    army_id = request.form.get('army_id', type=int)
    commander_id = request.form.get('commander_id', type=int)

    # Validate data
    if not army_id or not commander_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))

    # Assign commander
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message = military_system.assign_commander(
        army_id=army_id,
        commander_id=commander_id
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('military.military_view', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/military_gameplay')
@login_required
def military_gameplay(dynasty_id):
    """Interactive military gameplay view that combines the map with military actions."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get military units and armies
    units = MilitaryUnit.query.filter_by(dynasty_id=dynasty_id, army_id=None).all()
    armies = Army.query.filter_by(dynasty_id=dynasty_id).all()

    # Get potential commanders
    commanders = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        death_year=None
    ).all()

    # Filter to those who can lead armies
    potential_commanders = [p for p in commanders if p.can_lead_army()]

    # Get controlled territories for recruitment
    territories = Territory.query.all()

    # Get current game phase
    current_phase = "Planning"  # Default phase
    try:
        time_system = TimeSystem(db.session)
        phase_info = time_system.get_current_phase(dynasty_id)
        if phase_info:
            current_phase = phase_info.name
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error getting current phase: {str(e)}")

    # Get world map visualization
    from visualization.map_renderer import MapRenderer
    map_renderer = MapRenderer(db.session)

    # Render map with military units
    map_image = None
    try:
        map_image = map_renderer.render_world_map(
            show_terrain=True,
            show_territories=True,
            show_settlements=True,
            show_units=True,
            highlight_dynasty_id=dynasty_id
        )
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error rendering map: {str(e)}")

    return render_template('military_gameplay.html',
                          dynasty=dynasty,
                          units=units,
                          armies=armies,
                          potential_commanders=potential_commanders,
                          territories=territories,
                          map_image=map_image,
                          current_phase=current_phase)


@military_bp.route('/dynasty/<int:dynasty_id>/move_unit_gameplay', methods=['POST'])
@login_required
def move_unit_gameplay(dynasty_id):
    """Move a military unit to a target territory from the gameplay view."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    entity_type = request.form.get('entity_type')
    entity_id = request.form.get('entity_id', type=int)
    target_territory_id = request.form.get('target_territory_id', type=int)

    if not entity_type or not entity_id or not target_territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))

    # Create movement system
    movement_system = MovementSystem(db.session)

    # Move entity based on type
    if entity_type == 'unit':
        success, message = movement_system.move_unit(entity_id, target_territory_id)
    elif entity_type == 'army':
        success, message = movement_system.move_army(entity_id, target_territory_id)
    else:
        flash("Invalid entity type.", "danger")
        return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))

    if success:
        flash(message, "success")
    else:
        flash(f"Failed to move: {message}", "danger")

    return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/attack_gameplay', methods=['POST'])
@login_required
def attack_gameplay(dynasty_id):
    """Initiate a battle between two armies from the gameplay view."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    attacker_army_id = request.form.get('attacker_army_id', type=int)
    defender_army_id = request.form.get('defender_army_id', type=int)
    territory_id = request.form.get('territory_id', type=int)

    # Validate data
    if not attacker_army_id or not defender_army_id or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))

    # Initiate battle
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, battle = military_system.initiate_battle(
        attacker_army_id=attacker_army_id,
        defender_army_id=defender_army_id,
        territory_id=territory_id
    )

    if success:
        flash(message, "success")
        if battle:
            return redirect(url_for('military.battle_details', battle_id=battle.id))
    else:
        flash(message, "danger")

    return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/siege_gameplay', methods=['POST'])
@login_required
def siege_gameplay(dynasty_id):
    """Initiate a siege of a territory from the gameplay view."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    army_id = request.form.get('army_id', type=int)
    territory_id = request.form.get('territory_id', type=int)

    # Validate data
    if not army_id or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))

    # Initiate siege
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, siege = military_system.initiate_siege(
        army_id=army_id,
        territory_id=territory_id
    )

    if success:
        flash(message, "success")
        if siege:
            return redirect(url_for('military.siege_details', siege_id=siege.id))
    else:
        flash(message, "danger")

    return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/end_turn', methods=['POST'])
@login_required
def end_turn(dynasty_id):
    """End the current turn and process game events."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Process turn
    try:
        game_manager = GameManager(db.session)
        success, message, result = game_manager.process_turn(dynasty_id)

        if success:
            flash(message, "success")
        else:
            flash(message, "warning")
    except Exception as e:
        flash(f"Error processing turn: {str(e)}", "danger")

    return redirect(url_for('military.military_gameplay', dynasty_id=dynasty_id))


@military_bp.route('/army/<int:army_id>')
@login_required
def army_details(army_id):
    """View details of an army."""
    army = Army.query.get_or_404(army_id)
    dynasty = DynastyDB.query.get_or_404(army.dynasty_id)

    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get army composition visualization
    from visualization.military_renderer import MilitaryRenderer
    military_renderer = MilitaryRenderer(db.session)
    army_composition = military_renderer.render_army_composition(army_id)

    # Get potential commanders
    commanders = PersonDB.query.filter_by(
        dynasty_id=dynasty.id,
        death_year=None
    ).all()

    # Filter to those who can lead armies
    potential_commanders = [p for p in commanders if p.can_lead_army()]

    return render_template('army_details.html',
                          army=army,
                          dynasty=dynasty,
                          army_composition=army_composition,
                          potential_commanders=potential_commanders)


@military_bp.route('/battle/<int:battle_id>')
@login_required
def battle_details(battle_id):
    """View details of a battle."""
    battle = Battle.query.get_or_404(battle_id)

    # Check if user has access to this battle
    attacker_dynasty = DynastyDB.query.get(battle.attacker_dynasty_id)
    defender_dynasty = DynastyDB.query.get(battle.defender_dynasty_id)

    if (attacker_dynasty and attacker_dynasty.owner_user == current_user) or \
       (defender_dynasty and defender_dynasty.owner_user == current_user):
        # Get battle visualization
        from visualization.military_renderer import MilitaryRenderer
        military_renderer = MilitaryRenderer(db.session)
        battle_result = military_renderer.render_battle_result(battle_id)

        return render_template('battle_details.html',
                              battle=battle,
                              attacker_dynasty=attacker_dynasty,
                              defender_dynasty=defender_dynasty,
                              battle_result=battle_result)
    else:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))


@military_bp.route('/siege/<int:siege_id>')
@login_required
def siege_details(siege_id):
    """View details of a siege."""
    siege = Siege.query.get_or_404(siege_id)

    # Check if user has access to this siege
    attacker_dynasty = DynastyDB.query.get(siege.attacker_dynasty_id)
    defender_dynasty = DynastyDB.query.get(siege.defender_dynasty_id)

    if (attacker_dynasty and attacker_dynasty.owner_user == current_user) or \
       (defender_dynasty and defender_dynasty.owner_user == current_user):
        # Get siege visualization
        from visualization.military_renderer import MilitaryRenderer
        military_renderer = MilitaryRenderer(db.session)
        siege_progress = military_renderer.render_siege_progress(siege_id)

        return render_template('siege_details.html',
                              siege=siege,
                              attacker_dynasty=attacker_dynasty,
                              defender_dynasty=defender_dynasty,
                              siege_progress=siege_progress)
    else:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))


@military_bp.route('/dynasty/<int:dynasty_id>/initiate_battle', methods=['POST'])
@login_required
def initiate_battle(dynasty_id):
    """Initiate a battle between two armies."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    attacker_army_id = request.form.get('attacker_army_id', type=int)
    defender_army_id = request.form.get('defender_army_id', type=int)
    territory_id = request.form.get('territory_id', type=int)
    war_id = request.form.get('war_id', type=int)

    # Validate data
    if not attacker_army_id or not defender_army_id or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))

    # Initiate battle
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, battle = military_system.initiate_battle(
        attacker_army_id=attacker_army_id,
        defender_army_id=defender_army_id,
        territory_id=territory_id,
        war_id=war_id
    )

    if success:
        flash(message, "success")
        if battle:
            return redirect(url_for('military.battle_details', battle_id=battle.id))
    else:
        flash(message, "danger")

    return redirect(url_for('military.military_view', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/initiate_siege', methods=['POST'])
@login_required
def initiate_siege(dynasty_id):
    """Initiate a siege of a territory."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    army_id = request.form.get('army_id', type=int)
    territory_id = request.form.get('territory_id', type=int)
    war_id = request.form.get('war_id', type=int)

    # Validate data
    if not army_id or not territory_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))

    # Initiate siege
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, siege = military_system.initiate_siege(
        army_id=army_id,
        territory_id=territory_id,
        war_id=war_id
    )

    if success:
        flash(message, "success")
        if siege:
            return redirect(url_for('military.siege_details', siege_id=siege.id))
    else:
        flash(message, "danger")

    return redirect(url_for('military.military_view', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/naval_battle', methods=['POST'])
@login_required
def naval_battle(dynasty_id):
    """Resolve a naval battle between two armies."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.dashboard'))

    attacker_army_id = request.form.get('attacker_army_id', type=int)
    defender_army_id = request.form.get('defender_army_id', type=int)

    if not attacker_army_id or not defender_army_id:
        flash('Both attacker and defender armies are required.', 'danger')
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))

    try:
        military = MilitarySystem(db.session)
        result = military.resolve_naval_battle(attacker_army_id, defender_army_id)
        if result['is_blockade']:
            flash('Naval battle resolved: Blockade established!', 'info')
        elif result['winner_army_id'] is None:
            flash('No naval units on either side — no battle occurred.', 'info')
        else:
            flash(f"Naval battle resolved after {result['rounds']} round(s).", 'info')
        dynasty_data = {
            'id': dynasty.id,
            'name': dynasty.name,
        }
        return render_template('naval_battle_result.html', result=result, dynasty=dynasty_data)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Naval battle error for dynasty {dynasty_id}: {e}")
        flash('An error occurred resolving the naval battle.', 'danger')
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/update_siege/<int:siege_id>')
@login_required
def update_siege(dynasty_id, siege_id):
    """Update the progress of a siege."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Update siege
    from models.military_system import MilitarySystem
    military_system = MilitarySystem(db.session)
    success, message, siege = military_system.update_siege(siege_id=siege_id)

    if success:
        flash(message, "success")
        if siege:
            return redirect(url_for('military.siege_details', siege_id=siege.id))
    else:
        flash("Siege update failed: " + message, "danger")
        return redirect(url_for('military.military_view', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/move_unit', methods=['POST'])
@login_required
def move_unit(dynasty_id):
    """Move a military unit to a target territory."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)

    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    unit_id = request.form.get('unit_id', type=int)
    target_territory_id = request.form.get('target_territory_id', type=int)

    if not unit_id or not target_territory_id:
        flash("Missing unit ID or target territory ID.", "danger")
        return redirect(url_for('map.dynasty_territories', dynasty_id=dynasty_id))

    # Create movement system
    movement_system = MovementSystem(db.session)

    # Move unit
    success, message = movement_system.move_unit(unit_id, target_territory_id)

    if success:
        flash(message, "success")
    else:
        flash(f"Failed to move unit: {message}", "danger")

    # Redirect back to territories page
    return redirect(url_for('map.dynasty_territories', dynasty_id=dynasty_id))


@military_bp.route('/dynasty/<int:dynasty_id>/move_army', methods=['POST'])
@login_required
def move_army(dynasty_id):
    """Move an army to a target territory."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)

    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    army_id = request.form.get('army_id', type=int)
    target_territory_id = request.form.get('target_territory_id', type=int)

    if not army_id or not target_territory_id:
        flash("Missing army ID or target territory ID.", "danger")
        return redirect(url_for('map.dynasty_territories', dynasty_id=dynasty_id))

    # Create movement system
    movement_system = MovementSystem(db.session)

    # Move army
    success, message = movement_system.move_army(army_id, target_territory_id)

    if success:
        flash(message, "success")
    else:
        flash(f"Failed to move army: {message}", "danger")

    # Redirect back to territories page
    return redirect(url_for('map.dynasty_territories', dynasty_id=dynasty_id))
