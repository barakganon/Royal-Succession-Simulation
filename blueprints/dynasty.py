"""Dynasty Blueprint — handles dynasty creation, viewing, turn advancement, and deletion."""

import os
import json
import random
import datetime
import logging
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, session as flask_session
from flask_login import login_required, current_user

from flask import jsonify

from models.db_models import (
    db, DynastyDB, PersonDB, HistoryLogEntryDB, Territory,
    DiplomaticRelation, War, TradeRoute, Army
)
from models.game_manager import GameManager
from models.economy_system import EconomySystem
from models.military_system import MilitarySystem
from models.diplomacy_system import DiplomacySystem
from utils.theme_manager import get_all_theme_names, generate_theme_from_story_llm, get_theme
from utils.llm_prompts import build_turn_story_prompt, generate_turn_story_fallback
from visualization.heraldry_renderer import generate_coat_of_arms

logger = logging.getLogger('royal_succession.dynasty')

dynasty_bp = Blueprint('dynasty', __name__)

# ---------------------------------------------------------------------------
# FLASK_APP_GOOGLE_API_KEY_PRESENT — resolved lazily from the Flask app config
# so that the blueprint does not need to import main_flask_app at module load time.
# ---------------------------------------------------------------------------

def _llm_available() -> bool:
    """Return True if the LLM API key is present in the running app."""
    from flask import current_app
    return current_app.config.get('FLASK_APP_GOOGLE_API_KEY_PRESENT', False)


# ---------------------------------------------------------------------------
# Helper decorator
# ---------------------------------------------------------------------------

def block_if_turn_processing(f):
    """Decorator: blocks the route if the dynasty's turn is currently being processed.

    Prevents double-submission and concurrent turn advancement.  The decorated
    route must receive ``dynasty_id`` as a URL keyword argument.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        dynasty_id = kwargs.get('dynasty_id')
        if dynasty_id:
            dynasty = DynastyDB.query.get(dynasty_id)
            if dynasty and dynasty.is_turn_processing:
                flash("A turn is already in progress. Please wait until it completes.", "warning")
                return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty_id))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@dynasty_bp.route('/dynasty/create', methods=['GET', 'POST'])
@login_required
def create_dynasty():
    """Handles dynasty creation with theme selection or custom story."""
    if request.method == 'POST':
        # Process form data
        dynasty_name = request.form.get('dynasty_name')
        theme_type = request.form.get('theme_type')  # 'predefined' or 'custom'

        # Validate dynasty name
        if not dynasty_name or len(dynasty_name) < 2:
            flash('Please provide a valid dynasty name (at least 2 characters).', 'danger')
            return redirect(url_for('dynasty.create_dynasty'))

        # Get theme configuration
        theme_config = None
        theme_key = None

        if theme_type == 'predefined':
            theme_key = request.form.get('theme_key')
            theme_config = get_theme(theme_key)
            if not theme_config:
                flash('Selected theme not found. Please try again.', 'danger')
                return redirect(url_for('dynasty.create_dynasty'))
        else:  # custom
            user_story = request.form.get('user_story')
            if not user_story or len(user_story) < 50:
                flash('Please provide a more detailed story for custom theme generation (at least 50 characters).', 'danger')
                return redirect(url_for('dynasty.create_dynasty'))

            theme_config = generate_theme_from_story_llm(user_story)
            if not theme_config:
                flash('Failed to generate theme from story. Please try again or select a predefined theme.', 'danger')
                return redirect(url_for('dynasty.create_dynasty'))

        # Get simulation settings
        start_year = request.form.get('start_year')
        if start_year and start_year.isdigit():
            start_year = int(start_year)
        else:
            start_year = theme_config.get('start_year_suggestion', 1000)

        succession_rule = request.form.get('succession_rule')
        if not succession_rule:
            succession_rule = theme_config.get('succession_rule_default', 'PRIMOGENITURE_MALE_PREFERENCE')

        # Create dynasty in database
        new_dynasty = DynastyDB(
            user_id=current_user.id,
            name=dynasty_name,
            theme_identifier_or_json=theme_key if theme_type == 'predefined' else json.dumps(theme_config),
            current_wealth=int(theme_config.get('starting_wealth_modifier', 1.0) * 100),
            start_year=start_year,
            current_simulation_year=start_year
        )
        db.session.add(new_dynasty)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating dynasty '{dynasty_name}': {e}")
            flash("An error occurred while creating the dynasty.", "danger")
            return redirect(url_for('dynasty.create_dynasty'))

        # Generate and store procedural coat of arms
        try:
            new_dynasty.coat_of_arms_svg = generate_coat_of_arms(new_dynasty.id, new_dynasty.name)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to generate coat of arms for dynasty {new_dynasty.id}: {e}")

        # Initialize founder and spouse
        initialize_dynasty_founder(new_dynasty.id, theme_config, start_year, succession_rule)

        flash(f'Dynasty "{dynasty_name}" created successfully!', 'success')
        return redirect(url_for('dynasty.view_dynasty', dynasty_id=new_dynasty.id))

    # GET request - show form
    all_themes = get_all_theme_names()
    return render_template('create_dynasty.html',
                           themes=all_themes,
                           llm_available=_llm_available())


@dynasty_bp.route('/dynasty/<int:dynasty_id>/view')
@login_required
def view_dynasty(dynasty_id):
    """View a dynasty's details and family tree."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Load theme configuration
    theme_config = {}
    theme_description = "Custom Theme"
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            # Predefined theme
            theme_config = get_theme(dynasty.theme_identifier_or_json)
            theme_description = theme_config.get('description', dynasty.theme_identifier_or_json)
        else:
            # Custom theme stored as JSON
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
                theme_description = theme_config.get('description', "Custom Theme")
            except json.JSONDecodeError:
                theme_description = "Invalid Theme Configuration"

    # Get current monarch
    current_monarch = None
    current_monarch_age = 0
    monarch_query = PersonDB.query.filter_by(
        dynasty_id=dynasty.id,
        is_monarch=True,
        death_year=None
    ).first()

    if monarch_query:
        current_monarch = monarch_query
        current_monarch_age = dynasty.current_simulation_year - current_monarch.birth_year

    # Get living nobles (capped at 50 to prevent large-game performance issues)
    living_nobles = PersonDB.query.filter_by(
        dynasty_id=dynasty.id,
        is_noble=True,
        death_year=None
    ).order_by(PersonDB.birth_year).limit(50).all()

    # Calculate ages for all living nobles
    person_ages = {}
    for person in living_nobles:
        person_ages[person.id] = dynasty.current_simulation_year - person.birth_year

    # Get recent events
    recent_events = HistoryLogEntryDB.query.filter_by(
        dynasty_id=dynasty.id
    ).order_by(HistoryLogEntryDB.year.desc()).limit(10).all()

    # Check if family tree visualization exists
    family_tree_image = None
    tree_filename = f"family_tree_{dynasty.name.replace(' ', '_')}_year_{dynasty.current_simulation_year}_living_nobles.png"
    tree_path = os.path.join('static', 'visualizations', tree_filename)
    if os.path.exists(tree_path):
        family_tree_image = url_for('static', filename=f'visualizations/{tree_filename}')

    return render_template('view_dynasty.html',
                           dynasty=dynasty,
                           theme_config=theme_config,
                           theme_description=theme_description,
                           current_monarch=current_monarch,
                           current_monarch_age=current_monarch_age,
                           living_nobles=living_nobles,
                           person_ages=person_ages,
                           recent_events=recent_events,
                           family_tree_image=family_tree_image,
                           current_year=dynasty.current_simulation_year)


@dynasty_bp.route('/dynasty/<int:dynasty_id>/advance_turn')
@login_required
@block_if_turn_processing
def advance_turn(dynasty_id):
    """Advance the simulation by one turn (5 years by default).

    After processing the human player's dynasty, all AI-controlled dynasties
    belonging to the same user are processed via :class:`~models.game_manager.GameManager`
    so that every turn AI dynasties make personality-driven decisions.

    Turn-order enforcement: ``is_turn_processing`` is set to True at the start
    and cleared in a finally block to prevent double-submission or concurrent
    processing.
    """
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Mark turn as in-progress to block concurrent submissions
    dynasty.is_turn_processing = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to set is_turn_processing for dynasty {dynasty.id}: {e}")
        flash("Could not start turn processing. Please try again.", "danger")
        return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty.id))

    # Number of years to advance per turn
    years_per_turn = 5

    turn_summary = None
    success = False
    message = ""

    try:
        # Process the human dynasty's turn
        try:
            result = process_dynasty_turn(dynasty.id, years_per_turn)
            # Unpack 3-tuple (success, message, summary) or 2-tuple (legacy)
            if len(result) == 3:
                success, message, turn_summary = result
            else:
                success, message = result
                turn_summary = None
        except Exception as e:
            logger.error(f"Unhandled error in advance_turn for dynasty {dynasty.id}: {e}", exc_info=True)
            db.session.rollback()
            flash(f"An unexpected error occurred while advancing the turn: {type(e).__name__}: {e}", 'danger')
            return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty.id))

        if not success:
            flash(f"Error advancing turn: {message}", 'danger')

        # Process all AI-controlled dynasties for the current user so that AI
        # dynasties make decisions every turn via AIController (LLM or rule-based
        # fallback).  process_ai_turns internally calls register_ai_dynasties, so
        # controllers are auto-created on first run.  A fresh GameManager is created
        # with the current db.session so it shares the same transaction context.
        try:
            game_manager = GameManager(db.session)
            ai_success, ai_message = game_manager.process_ai_turns(user_id=current_user.id)
            if not ai_success:
                logger.warning(
                    f"advance_turn: process_ai_turns returned failure for user "
                    f"{current_user.id}: {ai_message}"
                )
            else:
                logger.info(
                    f"advance_turn: AI turns complete for user {current_user.id}"
                )
        except Exception as e:
            # AI turn failure must not abort the human player's turn result
            logger.error(
                f"advance_turn: error processing AI turns for user {current_user.id}: {e}",
                exc_info=True,
            )

        # Update last played timestamp
        dynasty.last_played_at = datetime.datetime.utcnow()

    finally:
        # Always release the processing lock, even if an exception propagated
        dynasty.is_turn_processing = False
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error releasing is_turn_processing lock for dynasty {dynasty.id}: {e}")

    if success and turn_summary:
        # Check victory conditions before redirecting to turn report
        victory_data = check_victory_conditions(dynasty, dynasty.current_simulation_year)
        if victory_data:
            flask_session['victory'] = victory_data
            return redirect(url_for('dynasty.victory', dynasty_id=dynasty.id))
        flask_session['last_turn_summary'] = turn_summary
        flask_session['last_turn_dynasty_id'] = dynasty.id
        return redirect(url_for('dynasty.turn_report', dynasty_id=dynasty.id))

    return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty.id))


@dynasty_bp.route('/dynasty/<int:dynasty_id>/turn_report')
@login_required
def turn_report(dynasty_id):
    """Display a rich summary of everything that happened during the last turn."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        return redirect(url_for('auth.dashboard'))

    summary = flask_session.pop('last_turn_summary', None)
    if not summary:
        # No pending summary — fall back to dynasty view
        return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty_id))

    start_year = summary.get('start_year', 0)

    # Collect up to 5 AI dynasties and their recent events for the World News panel
    ai_dynasties = DynastyDB.query.filter(
        DynastyDB.user_id != current_user.id
    ).all()

    ai_news = []
    for ai_d in ai_dynasties[:5]:
        ai_events = HistoryLogEntryDB.query.filter(
            HistoryLogEntryDB.dynasty_id == ai_d.id,
            HistoryLogEntryDB.year >= start_year,
        ).order_by(HistoryLogEntryDB.year.desc()).limit(3).all()
        if ai_events:
            ai_news.append({
                'dynasty_name': ai_d.name,
                'events': [
                    {
                        'year': e.year,
                        'text': e.event_string,
                        'type': e.event_type or 'event',
                    }
                    for e in ai_events
                ],
            })

    return render_template(
        'turn_report.html',
        dynasty=dynasty,
        summary=summary,
        ai_news=ai_news,
    )


@dynasty_bp.route('/dynasty/<int:dynasty_id>/action_phase')
@login_required
@block_if_turn_processing
def action_phase(dynasty_id):
    """Show the action-phase planning screen for the dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Load theme configuration
    theme_config = {}
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            theme_config = get_theme(dynasty.theme_identifier_or_json)
        else:
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
            except json.JSONDecodeError:
                pass

    # Current monarch
    current_monarch = None
    current_monarch_age = 0
    monarch_query = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        is_monarch=True,
        death_year=None
    ).first()
    if monarch_query:
        current_monarch = {
            'id': monarch_query.id,
            'name': monarch_query.name,
            'surname': monarch_query.surname,
            'portrait_svg': monarch_query.portrait_svg if hasattr(monarch_query, 'portrait_svg') else None,
            'traits': monarch_query.get_traits() if hasattr(monarch_query, 'get_traits') else [],
        }
        current_monarch_age = dynasty.current_simulation_year - monarch_query.birth_year

    # Territories
    territory_objs = Territory.query.filter_by(controller_dynasty_id=dynasty_id).all()
    territories = [
        {
            'id': t.id,
            'name': t.name,
            'terrain_type': t.terrain_type if hasattr(t, 'terrain_type') else '',
            'population': t.population if hasattr(t, 'population') else 0,
            'development_level': t.development_level if hasattr(t, 'development_level') else 0,
            'fortification_level': t.fortification_level if hasattr(t, 'fortification_level') else 0,
            'is_capital': t.is_capital if hasattr(t, 'is_capital') else False,
        }
        for t in territory_objs
    ]

    # Armies
    army_objs = Army.query.filter_by(dynasty_id=dynasty_id, is_active=True).all()
    armies = [
        {
            'id': a.id,
            'name': a.name,
            'territory_id': a.territory_id if hasattr(a, 'territory_id') else None,
            'unit_count': len(a.units) if hasattr(a, 'units') else 0,
        }
        for a in army_objs
    ]

    # Unmarried nobles
    unmarried_objs = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        death_year=None,
        is_noble=True,
        spouse_sim_id=None
    ).all()
    unmarried_nobles = [
        {
            'id': p.id,
            'name': p.name,
            'surname': p.surname,
            'gender': p.gender,
            'age': dynasty.current_simulation_year - p.birth_year,
        }
        for p in unmarried_objs
    ]

    # Economy
    try:
        es = EconomySystem(db.session)
        economy = es.calculate_dynasty_economy(dynasty_id)
        # Normalise keys so the template can always use economy.gold etc.
        if economy and 'gold' not in economy:
            economy['gold'] = economy.get('current_treasury', dynasty.current_wealth)
            economy['food'] = 0
            economy['iron'] = dynasty.current_iron if hasattr(dynasty, 'current_iron') else 0
            economy['timber'] = dynasty.current_timber if hasattr(dynasty, 'current_timber') else 0
            economy['manpower'] = 0
    except Exception as e:
        logger.warning(f"action_phase: economy calculation failed for dynasty {dynasty_id}: {e}")
        economy = {
            'gold': dynasty.current_wealth,
            'food': 0,
            'iron': dynasty.current_iron if hasattr(dynasty, 'current_iron') else 0,
            'timber': dynasty.current_timber if hasattr(dynasty, 'current_timber') else 0,
            'manpower': 0,
        }

    # Neighbouring dynasties (other dynasties owned by this user — visible targets)
    neighbour_objs = DynastyDB.query.filter(
        DynastyDB.id != dynasty_id,
        DynastyDB.user_id == current_user.id
    ).all()
    neighboring_dynasties = [{'id': d.id, 'name': d.name} for d in neighbour_objs]

    dynasty_data = {
        'id': dynasty.id,
        'name': dynasty.name,
        'current_wealth': dynasty.current_wealth,
        'current_simulation_year': dynasty.current_simulation_year,
        'coat_of_arms_svg': dynasty.coat_of_arms_svg,
    }

    return render_template(
        'action_phase.html',
        dynasty=dynasty_data,
        current_monarch=current_monarch,
        current_monarch_age=current_monarch_age,
        territories=territories,
        armies=armies,
        unmarried_nobles=unmarried_nobles,
        economy=economy,
        neighboring_dynasties=neighboring_dynasties,
        action_points=3,
        theme_config=theme_config,
        current_year=dynasty.current_simulation_year,
    )


@dynasty_bp.route('/dynasty/<int:dynasty_id>/submit_actions', methods=['POST'])
@login_required
@block_if_turn_processing
def submit_actions(dynasty_id):
    """Accept a JSON list of player actions, execute up to 3, then advance the turn."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({'error': 'Not authorized'}), 403

    actions = request.get_json() or []

    ap_used = 0
    results = []
    for action in actions[:3]:
        action_type = action.get('type')
        params = action.get('params', {})
        try:
            if action_type == 'recruit':
                ms = MilitarySystem(db.session)
                ms.recruit_unit(dynasty_id, params.get('unit_type', 'infantry'),
                                int(params.get('size', 100)), params.get('territory_id'))
                results.append({'type': action_type, 'success': True})
            elif action_type == 'build':
                es = EconomySystem(db.session)
                es.construct_building(params.get('territory_id'), params.get('building_type', 'farm'))
                results.append({'type': action_type, 'success': True})
            elif action_type == 'develop':
                es = EconomySystem(db.session)
                es.develop_territory(params.get('territory_id'), dynasty_id)
                results.append({'type': action_type, 'success': True})
            elif action_type == 'march':
                army = Army.query.filter_by(id=params.get('army_id'), dynasty_id=dynasty_id).first()
                if army:
                    army.territory_id = params.get('territory_id')
                    db.session.commit()
                results.append({'type': action_type, 'success': bool(army)})
            elif action_type == 'trade':
                es = EconomySystem(db.session)
                es.establish_trade_route(params.get('source_id'), params.get('target_id'),
                                         params.get('resource_type', 'food'),
                                         int(params.get('amount', 50)))
                results.append({'type': action_type, 'success': True})
            elif action_type == 'war':
                ds = DiplomacySystem(db.session)
                ds.declare_war(dynasty_id, params.get('target_dynasty_id'),
                               params.get('casus_belli', 'conquest'))
                results.append({'type': action_type, 'success': True})
            else:
                results.append({'type': action_type, 'success': False, 'error': 'Unknown action type'})
                continue
            ap_used += 1
        except Exception as e:
            logger.warning(f"Action {action_type} failed for dynasty {dynasty_id}: {e}")
            results.append({'type': action_type, 'success': False, 'error': str(e)})

    # Mark turn as processing
    dynasty.is_turn_processing = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"submit_actions: failed to set is_turn_processing for dynasty {dynasty_id}: {e}")
        return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty_id))

    turn_summary = None
    success = False
    try:
        result = process_dynasty_turn(dynasty_id, years_to_advance=5)
        if len(result) == 3:
            success, message, turn_summary = result
        else:
            success, message = result
            turn_summary = None

        # Process AI turns
        try:
            game_manager = GameManager(db.session)
            game_manager.process_ai_turns(user_id=current_user.id)
        except Exception as e:
            logger.error(f"submit_actions: AI turn error for user {current_user.id}: {e}", exc_info=True)

        dynasty.last_played_at = datetime.datetime.utcnow()
    finally:
        dynasty.is_turn_processing = False
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"submit_actions: error releasing lock for dynasty {dynasty_id}: {e}")

    if success and turn_summary:
        # Check victory conditions before redirecting to turn report
        victory_data = check_victory_conditions(dynasty, dynasty.current_simulation_year)
        if victory_data:
            flask_session['victory'] = victory_data
            return redirect(url_for('dynasty.victory', dynasty_id=dynasty_id))
        flask_session['last_turn_summary'] = turn_summary
        flask_session['last_turn_dynasty_id'] = dynasty_id
        return redirect(url_for('dynasty.turn_report', dynasty_id=dynasty_id))

    return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty_id))


def check_victory_conditions(dynasty, current_year):
    """Check if the dynasty has achieved a victory condition.

    Returns None if no victory has been achieved, or a dict with keys:
    ``condition``, ``title``, ``description``.
    """
    age = current_year - dynasty.start_year

    # 1. Dynasty Legacy — survived 200+ years
    if age >= 200:
        return {
            'condition': 'legacy',
            'title': 'An Enduring Legacy',
            'description': (
                f'House {dynasty.name} has endured for {age} years, '
                f'outlasting empires and catastrophes alike.'
            ),
        }

    # 2. Great Wealth — treasury >= 10,000
    if dynasty.current_wealth >= 10000:
        return {
            'condition': 'wealth',
            'title': 'Lords of Coin',
            'description': (
                f'The coffers of House {dynasty.name} overflow with '
                f'{dynasty.current_wealth} gold — the envy of all realms.'
            ),
        }

    # 3. Populous Dynasty — 20+ living members
    living_count = PersonDB.query.filter_by(dynasty_id=dynasty.id, death_year=None).count()
    if living_count >= 20:
        return {
            'condition': 'dynasty',
            'title': 'A Great House',
            'description': (
                f'House {dynasty.name} now counts {living_count} living souls '
                f'— a dynasty that shall never be forgotten.'
            ),
        }

    # 4. Territorial Dominion — controls 10+ territories
    territory_count = Territory.query.filter_by(controller_dynasty_id=dynasty.id).count()
    if territory_count >= 10:
        return {
            'condition': 'conquest',
            'title': 'Masters of the Realm',
            'description': (
                f'House {dynasty.name} rules over {territory_count} territories, '
                f'their banners flying across the land.'
            ),
        }

    return None


@dynasty_bp.route('/dynasty/<int:dynasty_id>/victory')
@login_required
def victory(dynasty_id):
    """Display the victory screen for a dynasty that has achieved a win condition."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        return redirect(url_for('auth.dashboard'))
    victory_data = flask_session.pop('victory', None)
    if not victory_data:
        return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty_id))
    return render_template(
        'victory.html',
        dynasty=dynasty,
        victory=victory_data,
        current_year=dynasty.current_simulation_year,
    )


@dynasty_bp.route('/dynasty/<int:dynasty_id>/delete', methods=['GET', 'POST'])
@login_required
def delete_dynasty(dynasty_id):
    """Delete a dynasty and all associated data."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)

    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        dynasty_name = dynasty.name  # Store for flash message

        try:
            logger.info(f"Deleting dynasty {dynasty_name} (ID: {dynasty_id})")

            # Delete related entities that might not be covered by cascade
            # This ensures clean deletion and prevents orphaned records

            # 1. Delete diplomatic relations
            logger.debug(f"Deleting diplomatic relations for dynasty {dynasty_id}")
            DiplomaticRelation.query.filter(
                (DiplomaticRelation.dynasty1_id == dynasty_id) |
                (DiplomaticRelation.dynasty2_id == dynasty_id)
            ).delete(synchronize_session=False)

            # 2. Delete wars
            logger.debug(f"Deleting wars for dynasty {dynasty_id}")
            War.query.filter(
                (War.attacker_dynasty_id == dynasty_id) |
                (War.defender_dynasty_id == dynasty_id)
            ).delete(synchronize_session=False)

            # 3. Delete trade routes
            logger.debug(f"Deleting trade routes for dynasty {dynasty_id}")
            try:
                TradeRoute.query.filter(
                    (TradeRoute.exporter_dynasty_id == dynasty_id) |
                    (TradeRoute.importer_dynasty_id == dynasty_id)
                ).delete(synchronize_session=False)
            except Exception as trade_error:
                logger.warning(f"Error deleting trade routes: {str(trade_error)}")

            # 4. Release controlled territories
            logger.debug(f"Releasing territories controlled by dynasty {dynasty_id}")
            Territory.query.filter_by(controller_dynasty_id=dynasty_id).update(
                {"controller_dynasty_id": None}, synchronize_session=False
            )

            # 5. Null out the founder FK and self-referential person FKs to break circular dependencies
            if dynasty.founder_person_db_id is not None:
                logger.debug(f"Nullifying founder FK for dynasty {dynasty_id}")
                dynasty.founder_person_db_id = None
                db.session.flush()

            # Null out PersonDB self-referential FKs (spouse, mother, father) for all dynasty persons
            # to break the circular dependency that causes CircularDependencyError on cascade delete
            logger.debug(f"Nullifying self-referential person FKs for dynasty {dynasty_id}")
            PersonDB.query.filter_by(dynasty_id=dynasty_id).update(
                {"spouse_sim_id": None, "mother_sim_id": None, "father_sim_id": None},
                synchronize_session=False
            )
            db.session.flush()

            # 6. Delete the dynasty - this will cascade to persons and history logs
            # thanks to the cascade="all, delete-orphan" setting in the relationships
            logger.info(f"Deleting dynasty {dynasty_id} from database")
            db.session.delete(dynasty)
            db.session.commit()

            flash(f'Dynasty "{dynasty_name}" has been permanently deleted.', 'success')
            logger.info(f"Dynasty {dynasty_name} successfully deleted")
            return redirect(url_for('auth.dashboard'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting dynasty {dynasty_id}: {str(e)}", exc_info=True)
            flash(f'Error deleting dynasty: {str(e)}', 'danger')
            return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty_id))

    # GET request - show confirmation page
    return render_template('delete_dynasty.html', dynasty=dynasty)


# ---------------------------------------------------------------------------
# Helper functions (called only by dynasty routes)
# ---------------------------------------------------------------------------

def initialize_dynasty_founder(dynasty_id: int, theme_config: dict, start_year: int, succession_rule: str):
    """Initialize the founder and spouse for a newly created dynasty."""
    dynasty = DynastyDB.query.get(dynasty_id)
    if not dynasty:
        return False, "Dynasty not found"

    # Create a history log for the dynasty
    history_log = HistoryLogEntryDB(
        dynasty_id=dynasty_id,
        year=None,
        event_string=f"The saga of House {dynasty.name} begins in the year {start_year}.",
        event_type="foundation"
    )
    db.session.add(history_log)

    # Determine founder gender randomly
    founder_gender = random.choice(["MALE", "FEMALE"])

    # Generate founder name
    name_key = "names_male" if founder_gender == "MALE" else "names_female"
    founder_name = random.choice(theme_config.get(name_key, ["Founder"]))

    # Create founder
    founder = PersonDB(
        dynasty_id=dynasty_id,
        name=founder_name,
        surname=dynasty.name,
        gender=founder_gender,
        birth_year=start_year - random.randint(25, 40),  # Founder is an adult
        is_noble=True,
        is_monarch=True,
        reign_start_year=start_year
    )

    # Set founder traits
    founder_traits = []
    available_traits = theme_config.get("common_traits", ["Noble"])
    if available_traits:
        num_traits = min(2, len(available_traits))
        founder_traits = random.sample(available_traits, num_traits)
    founder.set_traits(founder_traits)

    # Set founder titles
    founder_title_key = "founder_title_male" if founder_gender == "MALE" else "founder_title_female"
    founder_title = theme_config.get(founder_title_key, "Leader")
    founder.set_titles([founder_title])

    db.session.add(founder)
    db.session.flush()  # Get ID without committing
    founder.generate_portrait()

    # Set founder as the dynasty founder
    dynasty.founder_person_db_id = founder.id

    # Create spouse (80% chance)
    if random.random() < 0.8:
        spouse_gender = "FEMALE" if founder_gender == "MALE" else "MALE"
        name_key = "names_male" if spouse_gender == "MALE" else "names_female"
        spouse_name = random.choice(theme_config.get(name_key, ["Spouse"]))

        # Choose a different surname for spouse
        available_surnames = theme_config.get("surnames_dynastic", ["OtherHouse"])
        spouse_surname = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "OtherHouse"

        spouse = PersonDB(
            dynasty_id=dynasty_id,
            name=spouse_name,
            surname=spouse_surname,
            gender=spouse_gender,
            birth_year=start_year - random.randint(18, 35),  # Spouse is an adult
            is_noble=True
        )

        # Set spouse traits
        spouse_traits = []
        if available_traits:
            num_traits = min(2, len(available_traits))
            spouse_traits = random.sample(available_traits, num_traits)
        spouse.set_traits(spouse_traits)

        # Set spouse titles
        default_title_key = "default_noble_male" if spouse_gender == "MALE" else "default_noble_female"
        spouse_title = theme_config.get(default_title_key, "Noble")
        spouse.set_titles([spouse_title])

        db.session.add(spouse)
        db.session.flush()  # Get ID without committing
        spouse.generate_portrait()

        # Link spouse and founder
        founder.spouse_sim_id = spouse.id
        spouse.spouse_sim_id = founder.id

        # Log marriage
        marriage_log = HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=start_year,
            event_string=f"{founder.name} {founder.surname} and {spouse.name} {spouse.surname} were united in marriage.",
            person1_sim_id=founder.id,
            person2_sim_id=spouse.id,
            event_type="marriage"
        )
        db.session.add(marriage_log)

    # Log founder's rise to power
    founder_log = HistoryLogEntryDB(
        dynasty_id=dynasty_id,
        year=start_year,
        event_string=f"{founder.name} {founder.surname} became the first {founder_title} of House {dynasty.name}.",
        person1_sim_id=founder.id,
        event_type="succession_end"
    )
    db.session.add(founder_log)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error initializing dynasty founder for dynasty {dynasty_id}: {e}")
        return False
    return True


def process_dynasty_turn(dynasty_id: int, years_to_advance: int = 5):
    """Process a turn for the dynasty, advancing the simulation by the specified number of years."""
    dynasty = DynastyDB.query.get(dynasty_id)
    if not dynasty:
        return False, "Dynasty not found"

    # Load theme configuration
    theme_config = {}
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            # Predefined theme
            theme_config = get_theme(dynasty.theme_identifier_or_json)
        else:
            # Custom theme stored as JSON
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
            except json.JSONDecodeError:
                return False, "Invalid theme configuration"

    # Get all living persons in the dynasty
    living_persons = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        death_year=None
    ).all()

    # Get current monarch
    current_monarch = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        is_monarch=True,
        death_year=None
    ).first()

    # Process each year
    start_year = dynasty.current_simulation_year
    end_year = start_year + years_to_advance

    for current_year in range(start_year, end_year):
        try:
            # Process world events
            process_world_events(dynasty, current_year, theme_config)

            # Process each person's yearly events
            for person in living_persons:
                # Skip if person died in a previous year of this turn
                if person.death_year is not None:
                    continue

                # Process death check
                if process_death_check(person, current_year, theme_config):
                    # Person died, check if they were the monarch
                    if person.is_monarch:
                        process_succession(dynasty, person, current_year, theme_config)
                    continue

                # Process marriage for unmarried nobles
                if person.is_noble and person.spouse_sim_id is None:
                    process_marriage_check(dynasty, person, current_year, theme_config)

                # Process childbirth for married women
                if person.gender == "FEMALE" and person.spouse_sim_id is not None:
                    process_childbirth_check(dynasty, person, current_year, theme_config)

            # Update living persons list (remove those who died)
            living_persons = [p for p in living_persons if p.death_year is None]
        except Exception as year_exc:
            logger.error(f"Error processing year {current_year} for dynasty {dynasty_id}: {year_exc}", exc_info=True)
            # Continue to next year rather than aborting entire turn

        # Update dynasty's current year
        dynasty.current_simulation_year = current_year + 1

    # Generate family tree visualization
    try:
        generate_family_tree_visualization(dynasty, theme_config)
    except Exception as e:
        logger.error(f"Error generating family tree: {e}", exc_info=True)

    try:
        db.session.commit()
    except Exception as commit_error:
        db.session.rollback()
        logger.error(f"Error committing changes: {commit_error}", exc_info=True)
        return False, f"Error advancing turn: {commit_error}", None

    # Collect events created during this turn from HistoryLogEntryDB
    new_events = HistoryLogEntryDB.query.filter(
        HistoryLogEntryDB.dynasty_id == dynasty_id,
        HistoryLogEntryDB.year >= start_year,
        HistoryLogEntryDB.year < end_year
    ).order_by(HistoryLogEntryDB.year).all()

    # --- Epic Story Generation (one paragraph per turn) ---
    try:
        event_texts = [e.event_string for e in new_events if e.event_string]
        monarch_obj = PersonDB.query.filter_by(
            dynasty_id=dynasty_id, is_monarch=True, death_year=None
        ).first()
        monarch_display = (
            f"{monarch_obj.name} {monarch_obj.surname}" if monarch_obj else dynasty.name
        )
        existing_story = dynasty.epic_story_text or ""
        llm_ok = _llm_available()
        new_paragraph = ""
        if llm_ok:
            try:
                import google.generativeai as genai
                from flask import current_app
                api_key = current_app.config.get("FLASK_APP_GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    prompt = build_turn_story_prompt(
                        dynasty_name=dynasty.name,
                        start_year=start_year,
                        end_year=end_year - 1,
                        events=event_texts,
                        monarch_name=monarch_display,
                        existing_story=existing_story,
                    )
                    response = model.generate_content(
                        prompt,
                        generation_config={"max_output_tokens": 300, "temperature": 0.85},
                    )
                    new_paragraph = response.text.strip() if response.text else ""
            except Exception:
                new_paragraph = ""
        if not new_paragraph:
            new_paragraph = generate_turn_story_fallback(
                dynasty.name, start_year, end_year - 1, event_texts, monarch_display
            )
        if new_paragraph:
            separator = "\n\n" if existing_story.strip() else ""
            dynasty.epic_story_text = existing_story + separator + new_paragraph
            db.session.commit()
    except Exception as story_err:
        logger.error(f"Error generating turn story for dynasty {dynasty_id}: {story_err}", exc_info=True)

    living_count = PersonDB.query.filter_by(dynasty_id=dynasty_id, death_year=None).count()
    dynasty_obj = DynastyDB.query.get(dynasty_id)
    current_wealth = dynasty_obj.current_wealth if dynasty_obj else 0

    turn_summary = {
        'start_year': start_year,
        'end_year': end_year,
        'years_advanced': years_to_advance,
        'events': [
            {
                'type': e.event_type or 'event',
                'year': e.year,
                'text': e.event_string,
            }
            for e in new_events
        ],
        'living_count': living_count,
        'current_wealth': current_wealth,
        'new_story_paragraph': new_paragraph if 'new_paragraph' in dir() else '',
    }

    return True, f"Advanced {years_to_advance} years from {start_year} to {end_year}.", turn_summary


def process_death_check(person: PersonDB, current_year: int, theme_config: dict):
    """Check if a person dies this year."""
    age = current_year - person.birth_year

    # Base mortality chance increases with age
    base_mortality = 0.01  # 1% base chance

    # Age modifiers
    if age < 5:
        # Child mortality
        base_mortality = 0.15 * theme_config.get("mortality_factor", 1.0)
    elif age > 60:
        # Elderly mortality increases
        base_mortality = 0.05 * theme_config.get("mortality_factor", 1.0)
        if age > 75:
            base_mortality += 0.15 * theme_config.get("mortality_factor", 1.0)

    # Check against themed max age
    max_age = 85 * theme_config.get("max_age_factor", 1.0)
    if age > max_age:
        base_mortality = 1.0  # Guaranteed death if past max age

    # Roll for death
    if random.random() < base_mortality:
        person.death_year = current_year

        # Log death
        death_log = HistoryLogEntryDB(
            dynasty_id=person.dynasty_id,
            year=current_year,
            event_string=f"{person.name} {person.surname} passed away at the age of {age}.",
            person1_sim_id=person.id,
            event_type="death"
        )
        db.session.add(death_log)
        return True

    return False


def process_marriage_check(dynasty: DynastyDB, person: PersonDB, current_year: int, theme_config: dict):
    """Check if an unmarried noble gets married this year."""
    age = current_year - person.birth_year

    # Check if person is of marriageable age
    min_marriage_age = 16
    max_marriage_age = 45 if person.gender == "FEMALE" else 55

    if age < min_marriage_age or age > max_marriage_age:
        return False

    # Base chance to seek marriage
    marriage_chance = 0.35

    # Roll for marriage
    if random.random() < marriage_chance:
        # Create a spouse
        spouse_gender = "FEMALE" if person.gender == "MALE" else "MALE"
        name_key = "names_male" if spouse_gender == "MALE" else "names_female"
        spouse_name = random.choice(theme_config.get(name_key, ["Spouse"]))

        # Choose a different surname for spouse
        available_surnames = theme_config.get("surnames_dynastic", ["OtherHouse"])
        spouse_surname = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "OtherHouse"

        # Determine spouse age
        spouse_age = random.randint(min_marriage_age, max_marriage_age)
        if person.gender == "MALE":
            # Males often marry younger females
            spouse_age = min(age - random.randint(0, 7), max_marriage_age)
        else:
            # Females often marry older males
            spouse_age = max(age + random.randint(0, 7), min_marriage_age)

        spouse_birth_year = current_year - spouse_age

        spouse = PersonDB(
            dynasty_id=dynasty.id,
            name=spouse_name,
            surname=spouse_surname,
            gender=spouse_gender,
            birth_year=spouse_birth_year,
            is_noble=person.is_noble
        )

        # Set spouse traits
        spouse_traits = []
        available_traits = theme_config.get("common_traits", ["Noble"])
        if available_traits:
            num_traits = min(2, len(available_traits))
            spouse_traits = random.sample(available_traits, num_traits)
        spouse.set_traits(spouse_traits)

        # Set spouse titles
        default_title_key = "default_noble_male" if spouse_gender == "MALE" else "default_noble_female"
        spouse_title = theme_config.get(default_title_key, "Noble")
        spouse.set_titles([spouse_title])

        db.session.add(spouse)
        db.session.flush()  # Get ID without committing
        spouse.generate_portrait()

        # Link spouse and person
        person.spouse_sim_id = spouse.id
        spouse.spouse_sim_id = person.id

        # Log marriage
        marriage_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{person.name} {person.surname} and {spouse.name} {spouse.surname} were united in marriage.",
            person1_sim_id=person.id,
            person2_sim_id=spouse.id,
            event_type="marriage"
        )
        db.session.add(marriage_log)
        return True

    return False


def process_childbirth_check(dynasty: DynastyDB, woman: PersonDB, current_year: int, theme_config: dict):
    """Check if a married woman has a child this year."""
    age = current_year - woman.birth_year

    # Check if woman is of childbearing age
    min_fertility_age = 18
    max_fertility_age = 45

    if age < min_fertility_age or age > max_fertility_age:
        return False

    # Check if spouse exists
    if woman.spouse_sim_id is None:
        return False

    spouse = PersonDB.query.get(woman.spouse_sim_id)
    if not spouse or spouse.death_year is not None:
        return False

    # Check max children
    existing_children = PersonDB.query.filter(
        (PersonDB.mother_sim_id == woman.id) |
        (PersonDB.father_sim_id == woman.id)
    ).count()

    max_children = 8 * theme_config.get("max_children_factor", 1.0)
    if existing_children >= max_children:
        return False

    # Base chance for pregnancy
    pregnancy_chance = 0.4 * theme_config.get("pregnancy_chance_factor", 1.0)

    # Roll for pregnancy
    if random.random() < pregnancy_chance:
        # Determine child's gender
        child_gender = random.choice(["MALE", "FEMALE"])

        # Generate child's name
        name_key = "names_male" if child_gender == "MALE" else "names_female"
        child_name = random.choice(theme_config.get(name_key, ["Child"]))

        # Determine surname based on convention
        surname_convention = theme_config.get("surname_convention", "INHERITED_PATRILINEAL")

        if surname_convention == "PATRONYMIC":
            suffix_key = "patronymic_suffix_male" if child_gender == "MALE" else "patronymic_suffix_female"
            suffix = theme_config.get(suffix_key, "son" if child_gender == "MALE" else "dottir")
            child_surname = f"{spouse.name}{suffix}"
        elif surname_convention == "MATRONYMIC":
            suffix_key = "matronymic_suffix_male" if child_gender == "MALE" else "matronymic_suffix_female"
            suffix = theme_config.get(suffix_key, "son" if child_gender == "MALE" else "dottir")
            child_surname = f"{woman.name}{suffix}"
        else:  # Default to patrilineal
            child_surname = spouse.surname if spouse.gender == "MALE" else woman.surname

        # Create child
        child = PersonDB(
            dynasty_id=dynasty.id,
            name=child_name,
            surname=child_surname,
            gender=child_gender,
            birth_year=current_year,
            mother_sim_id=woman.id,
            father_sim_id=spouse.id,
            is_noble=woman.is_noble or spouse.is_noble
        )

        # Set child traits
        child_traits = []
        available_traits = theme_config.get("common_traits", ["Noble"])
        if available_traits:
            num_traits = min(1, len(available_traits))
            child_traits = random.sample(available_traits, num_traits)
        child.set_traits(child_traits)

        db.session.add(child)
        db.session.flush()  # Ensure child.id is assigned before portrait generation
        child.generate_portrait()

        # Log birth
        birth_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{child_name} {child_surname} was born to {woman.name} {woman.surname} and {spouse.name} {spouse.surname}.",
            person1_sim_id=child.id,
            event_type="birth"
        )
        db.session.add(birth_log)

        # Child mortality check (15% chance)
        if random.random() < 0.15 * theme_config.get("mortality_factor", 1.0):
            child.death_year = current_year

            # Log infant death
            death_log = HistoryLogEntryDB(
                dynasty_id=dynasty.id,
                year=current_year,
                event_string=f"{child_name} {child_surname}, infant child of {woman.name} {woman.surname}, did not survive birth.",
                person1_sim_id=child.id,
                event_type="death"
            )
            db.session.add(death_log)

        return True

    return False


def process_succession(dynasty: DynastyDB, deceased_monarch: PersonDB, current_year: int, theme_config: dict):
    """Process succession after a monarch's death."""
    # Log the succession crisis
    succession_log = HistoryLogEntryDB(
        dynasty_id=dynasty.id,
        year=current_year,
        event_string=f"With the death of {deceased_monarch.name} {deceased_monarch.surname}, the matter of succession weighs heavily on House {dynasty.name}.",
        person1_sim_id=deceased_monarch.id,
        event_type="succession_start"
    )
    db.session.add(succession_log)

    # Get succession rule
    succession_rule = theme_config.get("succession_rule_default", "PRIMOGENITURE_MALE_PREFERENCE")

    # Find eligible heirs
    eligible_heirs = []

    # First, check for children of the deceased
    children = PersonDB.query.filter(
        (PersonDB.father_sim_id == deceased_monarch.id) |
        (PersonDB.mother_sim_id == deceased_monarch.id),
        PersonDB.death_year.is_(None),
        PersonDB.is_noble == True
    ).all()

    if children:
        if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
            # Sort by gender (males first) then by birth year (oldest first)
            children.sort(key=lambda c: (c.gender != "MALE", c.birth_year))
        elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
            # Sort by birth year only (oldest first)
            children.sort(key=lambda c: c.birth_year)
        elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
            # For simplicity, just sort by traits count and age
            children.sort(key=lambda c: (-len(c.get_traits()), c.birth_year))

        eligible_heirs = children

    # If no children, look for siblings
    if not eligible_heirs:
        siblings = PersonDB.query.filter(
            ((PersonDB.father_sim_id == deceased_monarch.father_sim_id) |
             (PersonDB.mother_sim_id == deceased_monarch.mother_sim_id)),
            PersonDB.id != deceased_monarch.id,
            PersonDB.death_year.is_(None),
            PersonDB.is_noble == True
        ).all()

        if siblings:
            if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                siblings.sort(key=lambda s: (s.gender != "MALE", s.birth_year))
            elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
                siblings.sort(key=lambda s: s.birth_year)
            elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
                siblings.sort(key=lambda s: (-len(s.get_traits()), s.birth_year))

            eligible_heirs = siblings

    # If still no heirs, look for any living noble in the dynasty
    if not eligible_heirs:
        nobles = PersonDB.query.filter_by(
            dynasty_id=dynasty.id,
            death_year=None,
            is_noble=True
        ).all()

        if nobles:
            if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                nobles.sort(key=lambda n: (n.gender != "MALE", n.birth_year))
            elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
                nobles.sort(key=lambda n: n.birth_year)
            elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
                nobles.sort(key=lambda n: (-len(n.get_traits()), n.birth_year))

            eligible_heirs = nobles

    # If we have an heir, make them the new monarch
    if eligible_heirs:
        new_monarch = eligible_heirs[0]
        new_monarch.is_monarch = True
        new_monarch.reign_start_year = current_year

        # Set monarch title
        title_key = "titles_male" if new_monarch.gender == "MALE" else "titles_female"
        titles = theme_config.get(title_key, ["Leader"])
        if titles:
            monarch_title = titles[0]
            current_titles = new_monarch.get_titles()
            if monarch_title not in current_titles:
                current_titles.insert(0, monarch_title)
                new_monarch.set_titles(current_titles)

        # Log succession
        succession_end_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{new_monarch.name} {new_monarch.surname} has become the new {monarch_title} of House {dynasty.name}.",
            person1_sim_id=new_monarch.id,
            event_type="succession_end"
        )
        db.session.add(succession_end_log)
    else:
        # No heir found - dynasty in crisis
        crisis_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"House {dynasty.name} faces a succession crisis as no clear heir can be found.",
            event_type="succession_crisis"
        )
        db.session.add(crisis_log)


def process_world_events(dynasty: DynastyDB, current_year: int, theme_config: dict):
    """Process random world events for the year."""
    events = theme_config.get("events", [])
    if not events:
        return

    # Shuffle events for randomness
    random.shuffle(events)

    for event in events:
        # Check if event should trigger
        min_year = event.get("min_year", 0)
        max_year = event.get("max_year", 99999)
        chance = event.get("chance_per_year", 0.0)

        if min_year <= current_year <= max_year and random.random() < chance:
            # Event triggered
            event_name = event.get("name", "A Mysterious Happening")

            # Format narrative
            narrative = event.get("narrative", "Its consequences were felt.")
            narrative = narrative.replace("{dynasty_name}", dynasty.name)
            narrative = narrative.replace("{location_flavor}", theme_config.get("location_flavor", "these lands"))

            if "{rival_clan_name}" in narrative:
                available_surnames = theme_config.get("surnames_dynastic", ["Rivals"])
                rival_name = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "Rivals"
                narrative = narrative.replace("{rival_clan_name}", rival_name)

            # Apply wealth change if specified
            wealth_change = event.get("wealth_change", 0)
            if wealth_change != 0:
                dynasty.current_wealth = max(0, dynasty.current_wealth + wealth_change)

            # Log event
            event_log = HistoryLogEntryDB(
                dynasty_id=dynasty.id,
                year=current_year,
                event_string=f"{event_name}: {narrative}",
                event_type="generic_event"
            )
            db.session.add(event_log)

            # Only one world event per year
            break


def generate_family_tree_visualization(dynasty: DynastyDB, theme_config: dict):
    """Generate a family tree visualization for the dynasty."""
    try:
        from visualization.plotter import visualize_family_tree_snapshot
        from models.family_tree import FamilyTree
        from models.person import Person

        # Create a directory for visualizations
        visualizations_dir = os.path.join('static', 'visualizations')
        os.makedirs(visualizations_dir, exist_ok=True)

        # Create a FamilyTree object from the database
        family_tree = FamilyTree(dynasty.name, theme_config)
        family_tree.current_year = dynasty.current_simulation_year

        # Load all persons from the database into the family tree
        persons = PersonDB.query.filter_by(dynasty_id=dynasty.id).all()

        # First pass: Create Person objects
        person_objects = {}
        for db_person in persons:
            # Create Person object with required parameters
            person = Person(
                name=db_person.name,
                gender=db_person.gender,
                birth_year=db_person.birth_year,
                theme_config=theme_config,
                is_noble=db_person.is_noble
            )

            # Set additional attributes
            person.surname = db_person.surname
            person.death_year = db_person.death_year
            person.is_monarch = db_person.is_monarch
            person.reign_start_year = db_person.reign_start_year
            person.reign_end_year = db_person.reign_end_year
            person.titles = db_person.get_titles()
            person.traits = db_person.get_traits()

            # Store the Person object with the database ID as the key
            person_objects[db_person.id] = person
            # Use the database ID as the key in the family tree members dictionary
            family_tree.members[db_person.id] = person

            if db_person.is_monarch and db_person.death_year is None:
                family_tree.current_monarch = person

        # Second pass: Set relationships
        for db_person in persons:
            person = person_objects.get(db_person.id)
            if not person:
                continue

            # Set parents
            if db_person.father_sim_id and db_person.father_sim_id in person_objects:
                person.father = person_objects[db_person.father_sim_id]
                if person not in person.father.children:
                    person.father.children.append(person)

            if db_person.mother_sim_id and db_person.mother_sim_id in person_objects:
                person.mother = person_objects[db_person.mother_sim_id]
                if person not in person.mother.children:
                    person.mother.children.append(person)

            # Set spouse
            if db_person.spouse_sim_id and db_person.spouse_sim_id in person_objects:
                person.spouse = person_objects[db_person.spouse_sim_id]

        # Generate the visualization
        visualize_family_tree_snapshot(
            family_tree_obj=family_tree,
            year=dynasty.current_simulation_year,
            display_mode="living_nobles"
        )

        logger.debug(f"Family tree visualization generated for {dynasty.name} in year {dynasty.current_simulation_year}")
        return True
    except Exception as e:
        logger.error(f"Error generating family tree visualization: {str(e)}", exc_info=True)
        return False
