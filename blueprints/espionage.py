"""Espionage Blueprint — dispatch spy missions, view active operations and intel reports."""

import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models.db_models import (
    db, DynastyDB, PersonDB, Territory, Building, HistoryLogEntryDB,
)
from models.espionage_system import EspionageSystem, MISSION_TYPES
from models.project_system import ProjectSystem

logger = logging.getLogger('royal_succession.espionage')

espionage_bp = Blueprint('espionage', __name__)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@espionage_bp.route('/dynasty/<int:dynasty_id>/espionage')
@login_required
def espionage_view(dynasty_id):
    """View the espionage dashboard for a dynasty."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.user_id != current_user.id:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Serialize the dynasty (minimal)
    dynasty_data = {
        'id': dynasty.id,
        'name': dynasty.name,
        'coat_of_arms_svg': dynasty.coat_of_arms_svg,
        'current_simulation_year': dynasty.current_simulation_year,
        'current_wealth': dynasty.current_wealth,
    }

    # Agents: living members of this dynasty
    living_members = (
        db.session.query(PersonDB)
        .filter(PersonDB.dynasty_id == dynasty_id, PersonDB.death_year.is_(None))
        .all()
    )
    agents = [
        {
            'id': p.id,
            'name': f"{p.name} {p.surname or ''}".strip(),
            'espionage_skill': p.espionage_skill if p.espionage_skill is not None else 0,
        }
        for p in living_members
    ]

    # Enemy dynasties
    other_dynasties = DynastyDB.query.filter(DynastyDB.id != dynasty_id).all()
    enemy_dynasties = [{'id': d.id, 'name': d.name} for d in other_dynasties]

    # Enemy targets: persons and buildings per enemy dynasty
    enemy_targets = {}
    for other in other_dynasties:
        living_nobles = (
            db.session.query(PersonDB)
            .filter(PersonDB.dynasty_id == other.id, PersonDB.death_year.is_(None))
            .all()
        )
        persons = [
            {'id': p.id, 'name': f"{p.name} {p.surname or ''}".strip()}
            for p in living_nobles
        ]

        # Buildings via territories the dynasty controls
        controlled_territories = (
            db.session.query(Territory)
            .filter(Territory.controller_dynasty_id == other.id)
            .all()
        )
        buildings = []
        for t in controlled_territories:
            for b in db.session.query(Building).filter(Building.territory_id == t.id).all():
                buildings.append({
                    'id': b.id,
                    'name': b.name,
                    'territory_name': t.name,
                })

        enemy_targets[other.id] = {
            'dynasty_id': other.id,
            'dynasty_name': other.name,
            'persons': persons,
            'buildings': buildings,
        }

    # Active espionage missions
    project_system = ProjectSystem(db.session)
    all_projects = project_system.get_active_projects(dynasty_id)
    espionage_projects = [p for p in all_projects if p.project_type.startswith('espionage_')]
    active_missions = []
    for proj in espionage_projects:
        target_dynasty = db.session.get(DynastyDB, proj.target_dynasty_id) if proj.target_dynasty_id else None
        target_name = target_dynasty.name if target_dynasty else 'Unknown'
        years_remaining = (proj.completion_year or 0) - dynasty.current_simulation_year
        active_missions.append({
            'mission_type': proj.project_type,
            'target_dynasty_name': target_name,
            'completion_year': proj.completion_year,
            'years_remaining': max(0, years_remaining),
        })

    # Intel reports
    raw_reports = (
        db.session.query(HistoryLogEntryDB)
        .filter(
            HistoryLogEntryDB.dynasty_id == dynasty_id,
            HistoryLogEntryDB.event_type == 'intel_report',
        )
        .order_by(HistoryLogEntryDB.year.desc())
        .all()
    )
    intel_reports = [{'year': r.year, 'text': r.event_string} for r in raw_reports]

    # Mission costs from MISSION_TYPES constant
    mission_costs = {
        k: {
            'gold_cost': v['gold_cost'],
            'duration_years': v['duration_years'],
            'base_success': int(v['base_success'] * 100),
        }
        for k, v in MISSION_TYPES.items()
    }

    # Flatten all enemy persons and buildings for cross-dynasty selects
    all_enemy_persons = []
    all_enemy_buildings = []
    for targets in enemy_targets.values():
        for p in targets['persons']:
            all_enemy_persons.append({'id': p['id'], 'name': f"{p['name']} ({targets['dynasty_name']})"})
        for b in targets['buildings']:
            all_enemy_buildings.append({'id': b['id'], 'name': f"{b['name']} @ {b['territory_name']} ({targets['dynasty_name']})"})

    return render_template(
        'espionage.html',
        dynasty=dynasty_data,
        agents=agents,
        enemy_dynasties=enemy_dynasties,
        enemy_targets=enemy_targets,
        active_missions=active_missions,
        intel_reports=intel_reports,
        mission_costs=mission_costs,
        all_enemy_persons=all_enemy_persons,
        all_enemy_buildings=all_enemy_buildings,
    )


@espionage_bp.route('/dynasty/<int:dynasty_id>/espionage/dispatch', methods=['POST'])
@login_required
def dispatch_mission(dynasty_id):
    """Dispatch a spy mission."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.user_id != current_user.id:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    mission_type = request.form.get('mission_type', '')
    agent_person_id = request.form.get('agent_person_id', type=int)
    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    target_person_id = request.form.get('target_person_id', type=int) or None
    building_id = request.form.get('building_id', type=int) or None

    if not agent_person_id or not target_dynasty_id:
        flash("Missing required parameters.", "warning")
        return redirect(url_for('espionage.espionage_view', dynasty_id=dynasty_id))

    try:
        espionage_system = EspionageSystem(db.session)
        ok, msg = espionage_system.dispatch_mission(
            actor_dynasty_id=dynasty_id,
            mission_type=mission_type,
            agent_person_id=agent_person_id,
            target_dynasty_id=target_dynasty_id,
            target_person_id=target_person_id,
            building_id=building_id,
        )
        if ok:
            flash(msg, 'success')
        else:
            flash(msg, 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error("Error dispatching espionage mission for dynasty %s: %s", dynasty_id, e)
        flash("An unexpected error occurred while dispatching the mission.", "danger")

    return redirect(url_for('espionage.espionage_view', dynasty_id=dynasty_id))
