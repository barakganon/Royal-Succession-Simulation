"""Diplomacy Blueprint — handles diplomatic relations, treaties, wars, and peace negotiations."""

import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models.db_models import (
    db, DynastyDB, DiplomaticRelation, Treaty, TreatyType, War, WarGoal,
)
from models.diplomacy_system import DiplomacySystem
from visualization.diplomacy_renderer import DiplomacyRenderer

logger = logging.getLogger('royal_succession.diplomacy')

diplomacy_bp = Blueprint('diplomacy', __name__)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@diplomacy_bp.route('/dynasty/<int:dynasty_id>/diplomacy')
@login_required
def diplomacy_view(dynasty_id):
    """View and manage diplomatic relations for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get all other dynasties
    other_dynasties = DynastyDB.query.filter(DynastyDB.id != dynasty_id).all()

    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)

    # Get diplomatic relations
    relations = []
    for other_dynasty in other_dynasties:
        status, score = diplomacy_system.get_relation_status(dynasty_id, other_dynasty.id)
        relations.append({
            'dynasty': other_dynasty,
            'status': status,
            'score': score
        })

    # Get active treaties
    active_treaties = []
    for other_dynasty in other_dynasties:
        relation = diplomacy_system.get_diplomatic_relation(dynasty_id, other_dynasty.id, create_if_not_exists=False)
        if relation:
            treaties = Treaty.query.filter_by(diplomatic_relation_id=relation.id, active=True).all()
            for treaty in treaties:
                active_treaties.append({
                    'treaty': treaty,
                    'other_dynasty': other_dynasty,
                    'treaty_type': treaty.treaty_type.value.replace('_', ' ').title(),
                    'start_year': treaty.start_year,
                    'duration': treaty.duration
                })

    # Get active wars
    active_wars = []
    wars_as_attacker = War.query.filter_by(attacker_dynasty_id=dynasty_id, is_active=True).all()
    wars_as_defender = War.query.filter_by(defender_dynasty_id=dynasty_id, is_active=True).all()

    for war in wars_as_attacker:
        defender = DynastyDB.query.get(war.defender_dynasty_id)
        if defender:
            active_wars.append({
                'war': war,
                'other_dynasty': defender,
                'is_attacker': True,
                'war_goal': war.war_goal.value.replace('_', ' ').title(),
                'start_year': war.start_year,
                'war_score': war.attacker_war_score
            })

    for war in wars_as_defender:
        attacker = DynastyDB.query.get(war.attacker_dynasty_id)
        if attacker:
            active_wars.append({
                'war': war,
                'other_dynasty': attacker,
                'is_attacker': False,
                'war_goal': war.war_goal.value.replace('_', ' ').title(),
                'start_year': war.start_year,
                'war_score': war.defender_war_score
            })

    # Generate diplomatic relations visualization
    diplomacy_renderer = DiplomacyRenderer(db.session)
    relations_image = diplomacy_renderer.render_diplomatic_relations(dynasty_id=dynasty_id)
    treaty_image = diplomacy_renderer.render_treaty_network()
    history_image = diplomacy_renderer.render_diplomatic_history(dynasty_id=dynasty_id)

    # Get reputation metrics
    reputation = {
        'prestige': dynasty.prestige,
        'honor': dynasty.honor,
        'infamy': dynasty.infamy
    }

    return render_template('diplomacy_view.html',
                           dynasty=dynasty,
                           relations=relations,
                           active_treaties=active_treaties,
                           active_wars=active_wars,
                           reputation=reputation,
                           relations_image=relations_image,
                           treaty_image=treaty_image,
                           history_image=history_image)


@diplomacy_bp.route('/dynasty/<int:dynasty_id>/treaties')
@login_required
def treaty_view(dynasty_id):
    """View and manage treaties for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get all treaties
    treaties = []
    relations = DiplomaticRelation.query.filter((DiplomaticRelation.dynasty1_id == dynasty_id) |
                                               (DiplomaticRelation.dynasty2_id == dynasty_id)).all()

    for relation in relations:
        other_dynasty_id = relation.dynasty2_id if relation.dynasty1_id == dynasty_id else relation.dynasty1_id
        other_dynasty = DynastyDB.query.get(other_dynasty_id)

        if other_dynasty:
            relation_treaties = Treaty.query.filter_by(diplomatic_relation_id=relation.id).all()

            for treaty in relation_treaties:
                treaties.append({
                    'treaty': treaty,
                    'other_dynasty': other_dynasty,
                    'treaty_type': treaty.treaty_type.value.replace('_', ' ').title(),
                    'start_year': treaty.start_year,
                    'duration': treaty.duration,
                    'active': treaty.active,
                    'terms': treaty.get_terms() if hasattr(treaty, 'get_terms') else {}
                })

    # Generate treaty network visualization
    diplomacy_renderer = DiplomacyRenderer(db.session)
    treaty_image = diplomacy_renderer.render_treaty_network()

    return render_template('treaty_view.html',
                           dynasty=dynasty,
                           treaties=treaties,
                           treaty_image=treaty_image)


@diplomacy_bp.route('/dynasty/<int:dynasty_id>/diplomatic_action', methods=['POST'])
@login_required
def perform_diplomatic_action(dynasty_id):
    """Perform a diplomatic action."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    action_type = request.form.get('action_type')

    if not target_dynasty_id or not action_type:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))

    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)

    # Perform action
    success, message = diplomacy_system.perform_diplomatic_action(
        dynasty_id, target_dynasty_id, action_type
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))


@diplomacy_bp.route('/dynasty/<int:dynasty_id>/create_treaty', methods=['POST'])
@login_required
def create_treaty(dynasty_id):
    """Create a treaty between dynasties."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    treaty_type = request.form.get('treaty_type')
    duration = request.form.get('duration', type=int)

    if not target_dynasty_id or not treaty_type:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))

    # Convert treaty_type string to enum
    try:
        treaty_type_enum = TreatyType[treaty_type]
    except (KeyError, ValueError):
        flash("Invalid treaty type.", "danger")
        return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))

    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)

    # Create treaty
    success, message, _ = diplomacy_system.create_treaty(
        dynasty_id, target_dynasty_id, treaty_type_enum, duration
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))


@diplomacy_bp.route('/dynasty/<int:dynasty_id>/break_treaty/<int:treaty_id>', methods=['POST'])
@login_required
def break_treaty(dynasty_id, treaty_id):
    """Break a treaty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)

    # Break treaty
    success, message = diplomacy_system.break_treaty(treaty_id, dynasty_id)

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))


@diplomacy_bp.route('/dynasty/<int:dynasty_id>/declare_war', methods=['POST'])
@login_required
def declare_war(dynasty_id):
    """Declare war on another dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    war_goal = request.form.get('war_goal')
    target_territory_id = request.form.get('target_territory_id', type=int)

    if not target_dynasty_id or not war_goal:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))

    # Convert war_goal string to enum
    try:
        war_goal_enum = WarGoal[war_goal]
    except (KeyError, ValueError):
        flash("Invalid war goal.", "danger")
        return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))

    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)

    # Declare war
    success, message, _ = diplomacy_system.declare_war(
        dynasty_id, target_dynasty_id, war_goal_enum, target_territory_id
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))


@diplomacy_bp.route('/dynasty/<int:dynasty_id>/negotiate_peace/<int:war_id>', methods=['POST'])
@login_required
def negotiate_peace(dynasty_id, war_id):
    """Negotiate peace to end a war."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get war
    war = War.query.get_or_404(war_id)

    # Check if dynasty is involved in the war
    if war.attacker_dynasty_id != dynasty_id and war.defender_dynasty_id != dynasty_id:
        flash("Not authorized.", "warning")
        return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))

    # Determine if dynasty is attacker or defender
    is_attacker = (war.attacker_dynasty_id == dynasty_id)

    # Get form data
    terms = {}

    # Territory transfer
    territory_id = request.form.get('territory_id', type=int)
    if territory_id:
        terms['territory_transfer'] = territory_id

    # Gold payment
    gold_payment = request.form.get('gold_payment', type=int)
    if gold_payment:
        terms['gold_payment'] = gold_payment

    # Vassalization
    vassalize = request.form.get('vassalize') == 'on'
    if vassalize:
        terms['vassalize'] = True

    # Create diplomacy system
    diplomacy_system = DiplomacySystem(db.session)

    # Negotiate peace
    success, message = diplomacy_system.negotiate_peace(
        war_id, is_attacker, terms
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('diplomacy.diplomacy_view', dynasty_id=dynasty_id))
