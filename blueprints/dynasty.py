"""Dynasty Blueprint — handles dynasty creation, viewing, turn advancement, and deletion."""

import io
import os
import json
import random
import datetime
import logging
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, session as flask_session, current_app, Response, abort
from flask_login import login_required, current_user

from flask import jsonify

from models.db_models import (
    db,
    db, DynastyDB, PersonDB, HistoryLogEntryDB, Territory,
    DiplomaticRelation, War, TradeRoute, Army
)
from models.game_manager import GameManager
from models.economy_system import EconomySystem
from models.military_system import MilitarySystem
from models.diplomacy_system import DiplomacySystem
from models.project_system import (
    InsufficientResourcesError, ProjectSystem,
)
from models.turn_processor import (
    process_dynasty_turn, get_succession_candidates, crown_heir,
    CIVIL_WAR_THRESHOLD,
)
from utils.theme_manager import get_all_theme_names, generate_theme_from_story_llm, get_theme, get_dynasty_theme_config
from utils.llm_prompts import (
    build_succession_card_prompt,
    generate_succession_card_fallback,
    build_coronation_prompt,
    generate_coronation_fallback,
    build_foreword_prompt,
    generate_foreword_fallback,
    build_epilogue_prompt,
    generate_epilogue_fallback,
)
from models.chronicle_compiler import compile_chronicle
from visualization.heraldry_renderer import generate_coat_of_arms

logger = logging.getLogger('royal_succession.dynasty')

dynasty_bp = Blueprint('dynasty', __name__)

# Starting strength of a pretender's claim when a default heir is passed over.
PRETENDER_START_STRENGTH = 10

# ---------------------------------------------------------------------------
# FLASK_APP_GOOGLE_API_KEY_PRESENT — resolved lazily from the Flask app config
# so that the blueprint does not need to import main_flask_app at module load time.
# ---------------------------------------------------------------------------

def _llm_available() -> bool:
    """Return True if the LLM API key is present in the running app."""
    from flask import current_app
    return current_app.config.get('FLASK_APP_GOOGLE_API_KEY_PRESENT', False)


def _succession_llm_flavor(prompt: str, fallback: str) -> str:
    """Generate succession/coronation flavor text via a guarded LLM call.

    Mirrors models/free_action_system._build_flavor: when the LLM is available
    and an API key is present, calls gemini-1.5-flash; ANY failure (or LLM off,
    or empty response) returns the deterministic ``fallback``. Story 5-2.
    """
    if _llm_available():
        try:
            import google.generativeai as genai
            api_key = (
                current_app.config.get("FLASK_APP_GOOGLE_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
            )
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "max_output_tokens": 120,
                        "temperature": 0.8,
                    },
                )
                text = response.text.strip() if response.text else ""
                if text:
                    return text
        except Exception as llm_exc:
            logger.warning("Succession LLM flavor failed: %s", llm_exc)
    return fallback


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
            dynasty = db.session.get(DynastyDB, dynasty_id)
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

        # Bootstrap a starting map so the world map isn't empty for a freshly
        # created dynasty. Runs only outside tests — the test suite creates
        # territories explicitly where it needs them, and a full map-gen on
        # every test dynasty would be slow and change territory-count fixtures.
        # Guarded so a generation failure never blocks dynasty creation.
        if not current_app.config.get('TESTING'):
            try:
                from models.map_system import MapGenerator, TerritoryManager
                if Territory.query.filter_by(controller_dynasty_id=new_dynasty.id).count() == 0:
                    MapGenerator(db.session).generate_procedural_map(
                        regions_count=2, provinces_per_region=2,
                        territories_per_province=4, map_width=900, map_height=700)
                    tm = TerritoryManager(db.session)
                    starting = Territory.query.filter_by(controller_dynasty_id=None).limit(6).all()
                    for idx, terr in enumerate(starting):
                        tm.assign_territory(terr.id, new_dynasty.id, is_capital=(idx == 0))
                    db.session.commit()
                    logger.info(
                        f"Generated starting map ({len(starting)} territories) "
                        f"for dynasty {new_dynasty.id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Starting-map generation failed for dynasty {new_dynasty.id}: {e}")

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
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Load theme configuration (cached per dynasty+theme string — Story 11-3)
    theme_config = get_dynasty_theme_config(dynasty)
    theme_description = theme_config.get('description', "Custom Theme") if theme_config else "Custom Theme"
    if dynasty.theme_identifier_or_json and not theme_config and dynasty.theme_identifier_or_json not in get_all_theme_names():
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

    # Ensure the inline family-tree SVG is populated (Story 8-3).
    # The template reads dynasty.family_tree_svg directly. If it's not yet
    # cached, generate it best-effort; a render failure must never abort the view.
    if not dynasty.family_tree_svg:
        try:
            from visualization.family_tree_svg import generate_family_tree_svg
            dynasty.family_tree_svg = generate_family_tree_svg(dynasty_id, db.session)
            db.session.add(dynasty)
            db.session.commit()
        except Exception as e:
            logger.error("Failed to generate family tree SVG for dynasty %s: %s",
                         dynasty_id, e, exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass

    return render_template('view_dynasty.html',
                           dynasty=dynasty,
                           theme_config=theme_config,
                           theme_description=theme_description,
                           current_monarch=current_monarch,
                           current_monarch_age=current_monarch_age,
                           living_nobles=living_nobles,
                           person_ages=person_ages,
                           recent_events=recent_events,
                           current_year=dynasty.current_simulation_year)


def _ai_turns_job(user_id):
    """Process AI dynasty turns for ``user_id``.

    Runs inside the background thread's app context (see
    ``utils.async_narration.run_in_background``). ``db.session`` here is a fresh
    thread-local session; only the scalar ``user_id`` is passed across the thread
    boundary — never ORM objects.
    """
    from models.game_manager import GameManager
    from models.db_models import db
    GameManager(db.session).process_ai_turns(user_id)


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
    # Frozen interface contract: XHR detection for animated turn (Story 3-5).
    is_xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        if is_xhr:
            return jsonify({
                "ok": False,
                "redirect": url_for('auth.dashboard'),
                "summary": None,
            })
        return redirect(url_for('auth.dashboard'))

    # Mark turn as in-progress to block concurrent submissions
    dynasty.is_turn_processing = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to set is_turn_processing for dynasty {dynasty.id}: {e}")
        flash("Could not start turn processing. Please try again.", "danger")
        if is_xhr:
            return jsonify({
                "ok": False,
                "redirect": url_for('dynasty.view_dynasty', dynasty_id=dynasty.id),
                "summary": None,
            })
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
            if is_xhr:
                return jsonify({
                    "ok": False,
                    "redirect": url_for('dynasty.view_dynasty', dynasty_id=dynasty.id),
                    "summary": None,
                })
            return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty.id))

        if not success:
            flash(f"Error advancing turn: {message}", 'danger')

        # Process all AI-controlled dynasties for the current user so that AI
        # dynasties make decisions every turn via AIController (LLM or rule-based
        # fallback).  process_ai_turns internally calls register_ai_dynasties, so
        # controllers are auto-created on first run.  A fresh GameManager is created
        # with the current db.session so it shares the same transaction context.
        try:
            from utils.async_narration import run_in_background, should_offload_ai_turns
            if should_offload_ai_turns(db.session, current_user.id):
                # Heavy + LLM-on: offload AI processing to a daemon thread so the
                # player's turn returns immediately. The thread re-queries with a
                # fresh thread-local session inside its own app context.
                run_in_background(
                    current_app._get_current_object(),
                    _ai_turns_job,
                    current_user.id,
                )
                flash('The wider world stirs; distant courts act in the background.', 'info')
            else:
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
        dynasty.last_played_at = datetime.datetime.now(datetime.timezone.utc)

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
            if is_xhr:
                return jsonify({
                    "ok": True,
                    "redirect": url_for('dynasty.victory', dynasty_id=dynasty.id),
                    "summary": turn_summary,
                })
            return redirect(url_for('dynasty.victory', dynasty_id=dynasty.id))
        flask_session['last_turn_summary'] = turn_summary
        flask_session['last_turn_dynasty_id'] = dynasty.id
        if is_xhr:
            return jsonify({
                "ok": True,
                "redirect": url_for('dynasty.turn_report', dynasty_id=dynasty.id),
                "summary": turn_summary,
            })
        return redirect(url_for('dynasty.turn_report', dynasty_id=dynasty.id))

    if is_xhr:
        return jsonify({
            "ok": False,
            "redirect": url_for('dynasty.view_dynasty', dynasty_id=dynasty.id),
            "summary": turn_summary or None,
        })
    return redirect(url_for('dynasty.view_dynasty', dynasty_id=dynasty.id))


@dynasty_bp.route('/dynasty/<int:dynasty_id>/turn_report')
@login_required
def turn_report(dynasty_id):
    """Display a rich summary of everything that happened during the last turn."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
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


@dynasty_bp.route('/dynasty/<int:dynasty_id>/submit_actions', methods=['POST'])
@login_required
@block_if_turn_processing
def submit_actions(dynasty_id):
    """Accept a JSON list of player actions, execute up to 3, then advance the turn."""
    # legacy: retained for tests / non-map submit
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({'error': 'Not authorized'}), 403

    actions = request.get_json() or []

    # Sprint 2 Story 2-3: recruit/build/develop become multi-year projects
    # via ProjectSystem.start_project. march/trade/war remain instant — Sprint 4
    # (Story 4-1 free_action endpoint) will split them out as free actions.
    _BUILDING_TYPE_TO_PROJECT_TYPE = {
        'farm': 'build_farm',
        'walls': 'build_walls',
        'cathedral': 'build_cathedral',
    }
    _UNIT_TYPE_TO_PROJECT_TYPE = {
        'infantry': 'recruit_infantry',
        'cavalry': 'recruit_cavalry',
    }

    ap_used = 0
    results = []
    for action in actions[:3]:
        action_type = action.get('type')
        params = action.get('params', {})
        try:
            if action_type == 'recruit':
                unit_type = params.get('unit_type', 'infantry')
                project_type = _UNIT_TYPE_TO_PROJECT_TYPE.get(unit_type)
                if project_type is None:
                    results.append({
                        'type': action_type, 'success': False,
                        'error': f"Unknown unit_type for project mapping: {unit_type!r}",
                    })
                    continue
                ps = ProjectSystem(db.session)
                project = ps.start_project(
                    dynasty_id, project_type, dynasty.current_simulation_year,
                    target_territory_id=params.get('territory_id'),
                    params={'size': int(params.get('size', 100))},
                )
                results.append({'type': action_type, 'success': True, 'project_id': project.id})
            elif action_type == 'build':
                building_type = params.get('building_type', 'farm')
                project_type = _BUILDING_TYPE_TO_PROJECT_TYPE.get(building_type)
                if project_type is None:
                    results.append({
                        'type': action_type, 'success': False,
                        'error': f"Unknown building_type for project mapping: {building_type!r}",
                    })
                    continue
                ps = ProjectSystem(db.session)
                project = ps.start_project(
                    dynasty_id, project_type, dynasty.current_simulation_year,
                    target_territory_id=params.get('territory_id'),
                )
                results.append({'type': action_type, 'success': True, 'project_id': project.id})
            elif action_type == 'develop':
                ps = ProjectSystem(db.session)
                project = ps.start_project(
                    dynasty_id, 'develop_territory', dynasty.current_simulation_year,
                    target_territory_id=params.get('territory_id'),
                )
                results.append({'type': action_type, 'success': True, 'project_id': project.id})
            elif action_type == 'march':
                # Sprint 4 free-action split owns this — keeping instant.
                army = Army.query.filter_by(id=params.get('army_id'), dynasty_id=dynasty_id).first()
                if army:
                    army.territory_id = params.get('territory_id')
                    db.session.commit()
                results.append({'type': action_type, 'success': bool(army)})
            elif action_type == 'trade':
                # Sprint 4 free-action split owns this — keeping instant.
                es = EconomySystem(db.session)
                es.establish_trade_route(params.get('source_id'), params.get('target_id'),
                                         params.get('resource_type', 'food'),
                                         int(params.get('amount', 50)))
                results.append({'type': action_type, 'success': True})
            elif action_type == 'war':
                # Sprint 4 free-action split owns this — keeping instant.
                ds = DiplomacySystem(db.session)
                ds.declare_war(dynasty_id, params.get('target_dynasty_id'),
                               params.get('casus_belli', 'conquest'))
                results.append({'type': action_type, 'success': True})
            else:
                results.append({'type': action_type, 'success': False, 'error': 'Unknown action type'})
                continue
            ap_used += 1
        except InsufficientResourcesError as e:
            logger.warning(f"Action {action_type} failed for dynasty {dynasty_id}: {e}")
            results.append({'type': action_type, 'success': False, 'error': str(e)})
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

        dynasty.last_played_at = datetime.datetime.now(datetime.timezone.utc)
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


@dynasty_bp.route('/dynasty/<int:dynasty_id>/free_action', methods=['POST'])
@login_required
@block_if_turn_processing
def free_action(dynasty_id):
    """Perform a single free (no-tick) action via the FreeActionSystem (Story 4-1).

    Free actions execute instantly without advancing the simulation year or
    consuming action points.  The request may be JSON or form-encoded and must
    include an ``action_type``; any remaining keys are forwarded as ``params``.

    Returns JSON ``{"ok": bool, "message": str}``.
    """
    # Lazy import: FreeActionSystem lives in a module owned by another agent and
    # may be absent in this worktree.  Importing it inside the route keeps the
    # blueprint (and the whole test suite) importable. Mirrors the existing
    # lazy-import pattern used elsewhere in this blueprint.
    from models.free_action_system import FreeActionSystem

    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"ok": False, "message": "Not authorized"}), 403

    data = request.get_json(silent=True) or request.form
    action_type = data.get('action_type')
    if not action_type:
        return jsonify({"ok": False, "message": "Missing action_type"}), 400

    # Build the params dict from the remaining keys; coerce known id fields to int.
    _INT_KEYS = {'target_dynasty_id', 'heir_person_id'}
    params = {}
    for key, value in data.items():
        if key == 'action_type':
            continue
        if key in _INT_KEYS and value not in (None, ''):
            try:
                params[key] = int(value)
            except (TypeError, ValueError):
                params[key] = value
        else:
            params[key] = value

    try:
        system = FreeActionSystem(db.session)
        ok, message = system.perform_free_action(dynasty_id, action_type, params)
        if ok:
            # Story 4-2: push the undo token for reversible actions onto the
            # per-session stack before committing (commit assigns nothing new —
            # the system already flushed the history-entry id).
            if system.last_undo_token is not None:
                stack = flask_session.get('free_action_undo_stack')
                if not isinstance(stack, list):
                    stack = []
                stack.append(system.last_undo_token)
                flask_session['free_action_undo_stack'] = stack
            db.session.commit()
            return jsonify({"ok": True, "message": message}), 200
        db.session.rollback()
        return jsonify({"ok": False, "message": message}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"free_action: error performing {action_type!r} for dynasty {dynasty_id}: {e}",
            exc_info=True,
        )
        return jsonify({"ok": False, "message": "An error occurred performing the action."}), 400


@dynasty_bp.route('/dynasty/<int:dynasty_id>/free_action_catalogue.json')
@login_required
def free_action_catalogue(dynasty_id):
    """Serve the free-action catalogue as JSON (Story 4-2).

    Returns one entry per VALID_FREE_ACTIONS with display label, category,
    whether the action needs a target dynasty, and whether it is undoable.
    """
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"error": "Not authorized"}), 403

    from models.free_action_system import VALID_FREE_ACTIONS

    # Static metadata per action (labels + classification).
    _META = {
        'declare_war':         ('Declare War',          'diplomacy', True,  False),
        'propose_treaty':      ('Propose Treaty',       'diplomacy', True,  False),
        'send_envoy':          ('Send Envoy',           'diplomacy', True,  False),
        'issue_ultimatum':     ('Issue Ultimatum',      'diplomacy', True,  False),
        'name_heir':           ('Name Heir',            'succession', False, True),
        'adopt_succession_law':('Adopt Succession Law', 'succession', False, True),
        'hold_feast':          ('Hold Feast',           'court',      False, True),
        'hold_tournament':     ('Hold Tournament',      'court',      False, True),
        'pardon_vassal':       ('Pardon Vassal',        'court',      False, True),
    }

    actions = []
    for action_type in VALID_FREE_ACTIONS:
        label, category, needs_target, undoable = _META.get(
            action_type,
            (action_type.replace('_', ' ').title(), 'court', False, False),
        )
        actions.append({
            "action_type": action_type,
            "label": label,
            "category": category,
            "needs_target": needs_target,
            "undoable": undoable,
        })
    return jsonify({"actions": actions})


@dynasty_bp.route('/dynasty/<int:dynasty_id>/free_action/undo', methods=['POST'])
@login_required
@block_if_turn_processing
def free_action_undo(dynasty_id):
    """Undo the most recent reversible free action (Story 4-2).

    Pops the last token off the per-session undo stack and reverses it via
    FreeActionSystem.undo_free_action. Empty stack → ``{"ok": false}`` (200).
    """
    from models.free_action_system import FreeActionSystem

    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"ok": False, "message": "Not authorized"}), 403

    stack = flask_session.get('free_action_undo_stack', [])
    if not isinstance(stack, list) or not stack:
        return jsonify({"ok": False, "message": "Nothing to undo"}), 200

    undo_token = stack.pop()

    try:
        ok, message = FreeActionSystem(db.session).undo_free_action(
            dynasty_id, undo_token
        )
        if ok:
            flask_session['free_action_undo_stack'] = stack
            db.session.commit()
            return jsonify({"ok": True, "message": message}), 200
        # Bad token — discard it but keep the rest of the stack intact.
        db.session.rollback()
        flask_session['free_action_undo_stack'] = stack
        return jsonify({"ok": False, "message": message}), 200
    except Exception as e:
        db.session.rollback()
        # Restore the popped token so the user can retry.
        stack.append(undo_token)
        flask_session['free_action_undo_stack'] = stack
        logger.error(
            f"free_action_undo: error undoing for dynasty {dynasty_id}: {e}",
            exc_info=True,
        )
        return jsonify({"ok": False, "message": "An error occurred undoing the action."}), 400


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
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
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
    dynasty = db.get_or_404(DynastyDB, dynasty_id)

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
                    (TradeRoute.source_dynasty_id == dynasty_id) |
                    (TradeRoute.target_dynasty_id == dynasty_id)
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
            # Also null out references INTO this dynasty's persons from OTHER dynasties
            # (cross-dynasty marriages leave a stranger spouse pointing back at a
            # deleted person → CircularDependencyError otherwise).
            person_ids = [
                pid for (pid,) in PersonDB.query.filter_by(dynasty_id=dynasty_id)
                .with_entities(PersonDB.id).all()
            ]
            if person_ids:
                for fk in ("spouse_sim_id", "mother_sim_id", "father_sim_id"):
                    PersonDB.query.filter(getattr(PersonDB, fk).in_(person_ids)).update(
                        {fk: None}, synchronize_session=False
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
    dynasty = db.session.get(DynastyDB, dynasty_id)
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


# ===========================================================================
# Succession (Story 5-1) — monarch-death interrupt + heir choice
# ===========================================================================

def _load_theme_config(dynasty: DynastyDB) -> dict:
    """Resolve a dynasty's theme config (predefined name or stored JSON)."""
    theme_config: dict = {}
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            theme_config = get_theme(dynasty.theme_identifier_or_json) or {}
        else:
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
            except (json.JSONDecodeError, TypeError):
                theme_config = {}
    return theme_config


def _find_pending_deceased(dynasty_id: int):
    """Return the pending-succession marker: a monarch of the dynasty that has died.

    The pending marker is a PersonDB with is_monarch=True and a non-null
    death_year. Returns None when no succession is pending.
    """
    return PersonDB.query.filter(
        PersonDB.dynasty_id == dynasty_id,
        PersonDB.is_monarch == True,
        PersonDB.death_year.isnot(None),
    ).first()


def _candidate_relation(deceased: PersonDB, candidate: PersonDB) -> str:
    """Classify a candidate's relation to the deceased monarch."""
    if deceased.id in (candidate.father_sim_id, candidate.mother_sim_id):
        return 'child'
    shares_parent = (
        (candidate.father_sim_id is not None and candidate.father_sim_id == deceased.father_sim_id) or
        (candidate.mother_sim_id is not None and candidate.mother_sim_id == deceased.mother_sim_id)
    )
    if shares_parent:
        return 'sibling'
    return 'kin'


def _default_candidate_id(dynasty: DynastyDB, candidates: list) -> int:
    """Pick the default heir: the designated heir if eligible, else the first candidate."""
    candidate_ids = [c.id for c in candidates]
    if dynasty.designated_heir_id in candidate_ids:
        return dynasty.designated_heir_id
    return candidates[0].id


@dynasty_bp.route('/dynasty/<int:dynasty_id>/succession_candidates.json')
@login_required
def succession_candidates_json(dynasty_id):
    """Return the pending-succession state and serialized heir candidates."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"error": "Not authorized."}), 403

    deceased = _find_pending_deceased(dynasty_id)
    if deceased is None:
        return jsonify({"pending": False, "candidates": []})

    theme_config = _load_theme_config(dynasty)
    candidates = get_succession_candidates(dynasty, deceased, theme_config)

    if not candidates:
        return jsonify({
            "pending": True,
            "deceased": {
                "id": deceased.id,
                "name": deceased.name,
                "surname": deceased.surname,
                "death_year": deceased.death_year,
            },
            "candidates": [],
        })

    default_id = _default_candidate_id(dynasty, candidates)

    recent_events = [
        e.event_string
        for e in HistoryLogEntryDB.query.filter_by(dynasty_id=dynasty_id)
        .order_by(HistoryLogEntryDB.year.desc(), HistoryLogEntryDB.id.desc())
        .limit(5)
        .all()
    ]
    monarch_name = f"{deceased.name} {deceased.surname or ''}".strip()

    serialized = []
    for c in candidates:
        portrait = c.portrait_svg
        if not portrait:
            try:
                portrait = c.generate_portrait()
            except Exception as e:
                logger.error(f"Error generating portrait for person {c.id}: {e}")
                portrait = ""
        traits = c.get_traits()
        age = deceased.death_year - c.birth_year
        relation = _candidate_relation(deceased, c)
        candidate_name = f"{c.name} {c.surname or ''}".strip()
        flavor = _succession_llm_flavor(
            build_succession_card_prompt(
                candidate_name=candidate_name,
                candidate_traits=traits,
                relation=relation,
                age=age,
                monarch_name=monarch_name,
                dynasty_name=dynasty.name,
                recent_events=recent_events,
            ),
            generate_succession_card_fallback(
                candidate_name=candidate_name,
                candidate_traits=traits,
                relation=relation,
                age=age,
            ),
        )
        serialized.append({
            "id": c.id,
            "name": c.name,
            "surname": c.surname,
            "portrait_svg": portrait,
            "traits": traits,
            "birth_year": c.birth_year,
            "age": age,
            "relation": relation,
            "is_default": c.id == default_id,
            "flavor": flavor,
        })

    return jsonify({
        "pending": True,
        "deceased": {
            "id": deceased.id,
            "name": deceased.name,
            "surname": deceased.surname,
            "death_year": deceased.death_year,
        },
        "candidates": serialized,
    })


@dynasty_bp.route('/dynasty/<int:dynasty_id>/succession_choice', methods=['POST'])
@login_required
@block_if_turn_processing
def succession_choice(dynasty_id):
    """Crown the player-chosen heir for a pending succession."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"error": "Not authorized."}), 403

    deceased = _find_pending_deceased(dynasty_id)
    if deceased is None:
        return jsonify({"ok": False, "message": "No succession is pending."}), 400

    # Accept heir_id from JSON body or form data
    raw_heir_id = None
    if request.is_json:
        raw_heir_id = (request.get_json(silent=True) or {}).get('heir_id')
    if raw_heir_id is None:
        raw_heir_id = request.form.get('heir_id')

    try:
        heir_id = int(raw_heir_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Invalid heir selection."}), 400

    theme_config = _load_theme_config(dynasty)
    candidates = get_succession_candidates(dynasty, deceased, theme_config)
    candidate_map = {c.id: c for c in candidates}

    if heir_id not in candidate_map:
        return jsonify({"ok": False, "message": "Selected heir is not an eligible candidate."}), 400

    heir = candidate_map[heir_id]
    try:
        crown_heir(dynasty, heir, deceased.death_year, theme_config)
        heir_name = f"{heir.name} {heir.surname or ''}".strip()
        coronation_text = _succession_llm_flavor(
            build_coronation_prompt(
                heir_name=heir_name,
                dynasty_name=dynasty.name,
                year=deceased.death_year,
                heir_traits=heir.get_traits(),
            ),
            generate_coronation_fallback(
                heir_name=heir_name,
                dynasty_name=dynasty.name,
                year=deceased.death_year,
            ),
        )
        db.session.add(HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=deceased.death_year,
            event_string=coronation_text,
            event_type='coronation',
            person1_sim_id=heir.id,
        ))

        # Flag the bypassed default candidate as a pretender when the player
        # crowns someone other than the default heir.
        default_id = _default_candidate_id(dynasty, candidates)
        if heir_id != default_id and default_id in candidate_map and default_id != heir_id:
            bypassed = candidate_map[default_id]
            bypassed.is_pretender = True
            bypassed.pretender_strength = PRETENDER_START_STRENGTH
            bypassed_name = f"{bypassed.name} {bypassed.surname or ''}".strip()
            db.session.add(HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=deceased.death_year,
                event_string=f"{bypassed_name}, passed over for the crown, nurses a rival claim.",
                event_type='pretender_claim',
                person1_sim_id=bypassed.id,
            ))

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error crowning heir {heir_id} for dynasty {dynasty_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "message": "Failed to crown the heir."}), 500

    return jsonify({"ok": True, "message": f"{heir.name} {heir.surname} has been crowned."})


def _find_pending_civil_war(dynasty_id: int):
    """Return the strongest living pretender at/above the civil-war threshold.

    Returns None when no civil war is pending for the dynasty.
    """
    pretenders = PersonDB.query.filter(
        PersonDB.dynasty_id == dynasty_id,
        PersonDB.is_pretender == True,
        PersonDB.death_year.is_(None),
        PersonDB.pretender_strength >= CIVIL_WAR_THRESHOLD,
    ).all()
    if not pretenders:
        return None
    return max(pretenders, key=lambda p: p.pretender_strength or 0)


@dynasty_bp.route('/dynasty/<int:dynasty_id>/civil_war_resolve', methods=['POST'])
@login_required
@block_if_turn_processing
def civil_war_resolve(dynasty_id):
    """Resolve a pending civil war by fighting, negotiating, or abdicating."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"error": "Not authorized."}), 403

    pretender = _find_pending_civil_war(dynasty_id)
    if pretender is None:
        return jsonify({"ok": False, "message": "No civil war to resolve."}), 400

    raw_choice = None
    if request.is_json:
        raw_choice = (request.get_json(silent=True) or {}).get('choice')
    if raw_choice is None:
        raw_choice = request.form.get('choice')
    choice = (raw_choice or '').strip().lower()

    if choice not in ('fight', 'negotiate', 'abdicate'):
        return jsonify({"ok": False, "message": "Invalid choice."}), 400

    theme_config = _load_theme_config(dynasty)
    pretender_name = f"{pretender.name} {pretender.surname or ''}".strip()
    year = dynasty.current_simulation_year

    try:
        if choice == 'fight':
            if (dynasty.prestige or 0) >= (pretender.pretender_strength or 0):
                # Loyalists win: the pretender is defeated and exiled.
                pretender.is_pretender = False
                pretender.pretender_strength = 0
                pretender.is_noble = False
                event_string = (
                    f"The loyalists of House {dynasty.name} crushed the rebellion; "
                    f"{pretender_name} was defeated and driven into exile."
                )
                message = f"The rebellion was crushed. {pretender_name} has been exiled."
            else:
                # Pretender wins: they seize the crown.
                crown_heir(dynasty, pretender, year, theme_config)
                pretender.is_pretender = False
                event_string = (
                    f"The rebellion of {pretender_name} triumphed; "
                    f"they seized the crown of House {dynasty.name} by force."
                )
                message = f"{pretender_name} won the war and seized the crown."
            db.session.add(HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=year,
                event_string=event_string,
                event_type='civil_war',
                person1_sim_id=pretender.id,
            ))

        elif choice == 'negotiate':
            payment = min(dynasty.current_wealth or 0, 100)
            dynasty.current_wealth = (dynasty.current_wealth or 0) - payment
            pretender.is_pretender = False
            pretender.pretender_strength = 0
            event_string = (
                f"A settlement of {payment} gold bought the loyalty of {pretender_name}, "
                f"ending their claim against House {dynasty.name}."
            )
            db.session.add(HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=year,
                event_string=event_string,
                event_type='civil_war',
                person1_sim_id=pretender.id,
            ))
            message = f"You paid {payment} gold to end the claim of {pretender_name}."

        else:  # abdicate
            crown_heir(dynasty, pretender, year, theme_config)
            pretender.is_pretender = False
            event_string = (
                f"The reigning monarch abdicated, peacefully ceding the crown of "
                f"House {dynasty.name} to {pretender_name} and ending the strife."
            )
            db.session.add(HistoryLogEntryDB(
                dynasty_id=dynasty_id,
                year=year,
                event_string=event_string,
                event_type='civil_war',
                person1_sim_id=pretender.id,
            ))
            message = f"You abdicated. {pretender_name} now wears the crown."

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resolving civil war for dynasty {dynasty_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "message": "Failed to resolve the civil war."}), 500

    return jsonify({"ok": True, "message": message})


def _apply_story_moment_effects(dynasty, effects: dict) -> None:
    """Apply a story-moment choice's mechanical effects to dynasty state (Story 10-3).

    Defensive by design: a missing/None ``effects`` is a no-op, one malformed
    effect never aborts the others, and this function never raises.

    Supported effects:
      - prestige_delta:int  -> dynasty.prestige clamped to >= 0
      - wealth_delta:int    -> dynasty.current_wealth clamped to >= 0
      - infamy_delta:int    -> dynasty.infamy clamped to >= 0
      - add_trait_to_monarch:str -> idempotently add the trait to the living monarch

    Narrative-only effects (NO state mutation, by contract — these generic
    vignettes are not bound to a concrete person/dynasty relationship):
      - chronicle_note  (already used as the chronicle event_string)
      - exile_person
      - relation_delta

    Unknown keys are ignored.
    """
    if not effects or not isinstance(effects, dict):
        return

    # prestige_delta
    try:
        if 'prestige_delta' in effects and effects['prestige_delta'] is not None:
            delta = int(effects['prestige_delta'])
            dynasty.prestige = max(0, (dynasty.prestige or 0) + delta)
    except Exception as e:
        logger.warning(f"story_moment prestige_delta failed: {e}")

    # wealth_delta
    try:
        if 'wealth_delta' in effects and effects['wealth_delta'] is not None:
            delta = int(effects['wealth_delta'])
            dynasty.current_wealth = max(0, (dynasty.current_wealth or 0) + delta)
    except Exception as e:
        logger.warning(f"story_moment wealth_delta failed: {e}")

    # infamy_delta
    try:
        if 'infamy_delta' in effects and effects['infamy_delta'] is not None:
            delta = int(effects['infamy_delta'])
            dynasty.infamy = max(0, (dynasty.infamy or 0) + delta)
    except Exception as e:
        logger.warning(f"story_moment infamy_delta failed: {e}")

    # add_trait_to_monarch (idempotent)
    try:
        trait = effects.get('add_trait_to_monarch')
        if trait:
            monarch = PersonDB.query.filter_by(
                dynasty_id=dynasty.id, is_monarch=True, death_year=None
            ).first()
            if monarch is not None:
                traits = monarch.get_traits()
                if trait not in traits:
                    traits.append(trait)
                    monarch.set_traits(traits)
    except Exception as e:
        logger.warning(f"story_moment add_trait_to_monarch failed: {e}")

    # chronicle_note / exile_person / relation_delta -> narrative-only, no-op.


@dynasty_bp.route('/dynasty/<int:dynasty_id>/story_moment_choice', methods=['POST'])
@login_required
@block_if_turn_processing
def story_moment_choice(dynasty_id):
    """Record and dismiss a story-moment choice (Story 10-2 / 10-3).

    Validates the chosen template + choice, applies the choice's mechanical
    effects to dynasty state (Story 10-3), and writes a single story_moment
    chronicle line.
    """
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"error": "Not authorized."}), 403

    data = request.get_json(silent=True) or request.form
    template_key = (data.get('template') or '').strip()
    choice_key = (data.get('choice') or '').strip()

    from models.story_moments import STORY_MOMENT_TEMPLATES

    tmpl = next((t for t in STORY_MOMENT_TEMPLATES if t['key'] == template_key), None)
    if tmpl is None:
        return jsonify({"ok": False, "message": "Unknown story moment."}), 400

    chosen = next(
        (c for c in tmpl['mechanical_choices'] if c['key'] == choice_key), None
    )
    if chosen is None:
        return jsonify({"ok": False, "message": "Invalid choice."}), 400

    try:
        _apply_story_moment_effects(dynasty, chosen.get('effects', {}))
        event_string = (
            chosen.get('effects', {}).get('chronicle_note')
            or chosen['description']
        )
        db.session.add(HistoryLogEntryDB(
            dynasty_id=dynasty_id,
            year=dynasty.current_simulation_year,
            event_type='story_moment',
            event_string=event_string,
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Error recording story moment choice for dynasty {dynasty_id}: {e}",
            exc_info=True,
        )
        return jsonify({"ok": False, "message": "Failed to record the choice."}), 500

    return jsonify({"ok": True, "message": chosen['label']})


@dynasty_bp.route('/dynasty/<int:dynasty_id>/family_tree')
@login_required
def family_tree(dynasty_id):
    """Render the interactive family tree page for a dynasty."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    from visualization.family_tree_svg import generate_family_tree_svg
    tree_svg = generate_family_tree_svg(dynasty_id, db.session, show_deceased=True)
    return render_template(
        'family_tree.html',
        dynasty=dynasty,
        current_year=dynasty.current_simulation_year,
        tree_svg=tree_svg,
    )


@dynasty_bp.route('/dynasty/<int:dynasty_id>/family_tree.svg')
@login_required
def family_tree_svg_route(dynasty_id):
    """Return the raw family-tree SVG for a dynasty."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"error": "Not authorized."}), 403

    raw = request.args.get('show_deceased')
    if raw is None:
        show_deceased = True
    elif raw.strip().lower() in ('1', 'true', 'yes'):
        show_deceased = True
    elif raw.strip().lower() in ('0', 'false', 'no'):
        show_deceased = False
    else:
        show_deceased = True

    from visualization.family_tree_svg import generate_family_tree_svg
    svg = generate_family_tree_svg(dynasty_id, db.session, show_deceased=show_deceased)
    return Response(svg, mimetype='image/svg+xml')


@dynasty_bp.route('/dynasty/<int:dynasty_id>/person/<int:person_id>.json')
@login_required
def person_detail_json(dynasty_id, person_id):
    """Return JSON details for a person belonging to (or married into) a dynasty."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.owner_user != current_user:
        return jsonify({"error": "Not authorized."}), 403

    person = db.session.get(PersonDB, person_id)
    if person is None:
        abort(404)

    belongs = person.dynasty_id == dynasty_id
    if not belongs:
        is_married_in = PersonDB.query.filter_by(
            dynasty_id=dynasty_id, spouse_sim_id=person_id
        ).first() is not None
        if not is_married_in:
            abort(404)

    current_year = dynasty.current_simulation_year
    age = (person.death_year or current_year) - person.birth_year

    return jsonify({
        "id": person.id,
        "name": person.name,
        "surname": person.surname,
        "gender": person.gender,
        "birth_year": person.birth_year,
        "death_year": person.death_year,
        "age": age,
        "traits": person.get_traits(),
        "titles": person.get_titles(),
        "is_monarch": bool(person.is_monarch),
        "is_pretender": bool(person.is_pretender),
        "reign_start_year": person.reign_start_year,
    })


# ---------------------------------------------------------------------------
# Story 12-3: Chronicle Book + PDF Export
# ---------------------------------------------------------------------------

def _build_chronicle_book(dynasty_id: int):
    """Shared helper: compile ChronicleBook and wire foreword/epilogue.

    Returns (dynasty, book) on success, or None if dynasty not found or
    compile_chronicle returns None.
    """
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    book = compile_chronicle(dynasty_id)
    if book is None:
        logger.warning("_build_chronicle_book: compile_chronicle returned None for dynasty %s", dynasty_id)
        return None

    # Gather context for foreword/epilogue prompts
    all_paragraphs = [p for ch in book.chapters for p in ch.paragraphs]
    first_paragraphs = all_paragraphs[:3]
    last_paragraphs = all_paragraphs[-5:] if len(all_paragraphs) >= 5 else all_paragraphs

    first_monarch_name = ""
    if book.chapters:
        first_monarch_name = book.chapters[0].monarch_name or ""

    founding_year = dynasty.start_year
    current_year = dynasty.current_simulation_year

    territory_count = Territory.query.filter_by(controller_dynasty_id=dynasty.id).count()
    living_monarch = PersonDB.query.filter_by(
        dynasty_id=dynasty.id, is_monarch=True, death_year=None
    ).first()
    current_state = {
        'prestige': dynasty.prestige,
        'territories': territory_count,
        'is_extinct': living_monarch is None,
    }

    llm_model = current_app.config.get('FLASK_APP_LLM_MODEL')

    # Foreword
    if llm_model is not None:
        try:
            prompt = build_foreword_prompt(dynasty.name, founding_year, first_paragraphs, first_monarch_name)
            response = llm_model.generate_content(
                prompt,
                generation_config={'max_output_tokens': 200}
            )
            book.foreword = response.text.strip()
        except Exception as e:
            logger.warning("Chronicle foreword LLM call failed for dynasty %s: %s", dynasty_id, e)
            book.foreword = generate_foreword_fallback(dynasty.name, founding_year, first_monarch_name)
    else:
        book.foreword = generate_foreword_fallback(dynasty.name, founding_year, first_monarch_name)

    # Epilogue
    if llm_model is not None:
        try:
            prompt = build_epilogue_prompt(dynasty.name, current_year, last_paragraphs, current_state)
            response = llm_model.generate_content(
                prompt,
                generation_config={'max_output_tokens': 200}
            )
            book.epilogue = response.text.strip()
        except Exception as e:
            logger.warning("Chronicle epilogue LLM call failed for dynasty %s: %s", dynasty_id, e)
            book.epilogue = generate_epilogue_fallback(dynasty.name, current_year, current_state)
    else:
        book.epilogue = generate_epilogue_fallback(dynasty.name, current_year, current_state)

    return dynasty, book


@dynasty_bp.route('/dynasty/<int:dynasty_id>/chronicle_book')
@login_required
def chronicle_book(dynasty_id):
    """Render the Chronicle Book reader page for a dynasty."""
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.user_id != current_user.id:
        flash("You do not have permission to view that dynasty's chronicle.", "warning")
        return redirect(url_for('auth.dashboard'))

    result = _build_chronicle_book(dynasty_id)
    if result is None:
        flash("Could not compile the Chronicle — no history recorded yet.", "danger")
        return redirect(url_for('auth.dashboard'))

    dynasty, book = result
    return render_template('chronicle_book.html', dynasty=dynasty, book=book)


@dynasty_bp.route('/dynasty/<int:dynasty_id>/chronicle_book.pdf')
@login_required
def chronicle_book_pdf(dynasty_id):
    """Return the Chronicle Book as a downloadable PDF (reportlab Platypus).

    SVG heraldry is intentionally NOT embedded: reportlab cannot render inline
    SVG without additional system dependencies (svglib + lxml) which are outside
    spec scope. The PDF is text-focused.
    """
    dynasty = db.get_or_404(DynastyDB, dynasty_id)
    if dynasty.user_id != current_user.id:
        flash("You do not have permission to download that dynasty's chronicle.", "warning")
        return redirect(url_for('auth.dashboard'))

    result = _build_chronicle_book(dynasty_id)
    if result is None:
        flash("Could not compile the Chronicle — no history recorded yet.", "danger")
        return redirect(url_for('auth.dashboard'))

    dynasty, book = result

    # Build PDF with reportlab Platypus
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = []

    # Title page
    story.append(Paragraph(f"The Chronicle of {book.dynasty_name}", styles['Title']))
    story.append(Spacer(1, 0.3 * inch))
    founding_year = dynasty.start_year
    current_year = dynasty.current_simulation_year
    story.append(Paragraph(f"{founding_year} - {current_year}", styles['Normal']))
    story.append(PageBreak())

    # Foreword
    if book.foreword:
        story.append(Paragraph("Foreword", styles['Heading1']))
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph(book.foreword, styles['Normal']))
        story.append(PageBreak())

    # Chapters
    for chapter in book.chapters:
        heading = chapter.monarch_name if chapter.monarch_name else "The Founding"
        end_label = str(chapter.end_year) if chapter.end_year else "present"
        story.append(Paragraph(heading, styles['Heading1']))
        story.append(Paragraph(f"Reign: {chapter.start_year} - {end_label}", styles['Normal']))
        story.append(Spacer(1, 0.15 * inch))

        for para in chapter.paragraphs:
            story.append(Paragraph(para, styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))

        if chapter.highlights:
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("Key Events of the Reign", styles['Heading2']))
            for hl in chapter.highlights:
                # Avoid Unicode sub/superscripts — use plain ASCII dashes only
                story.append(Paragraph(f"{hl.year} -- {hl.text}", styles['Normal']))
            story.append(Spacer(1, 0.15 * inch))

        story.append(PageBreak())

    # Epilogue
    if book.epilogue:
        story.append(Paragraph("Epilogue", styles['Heading1']))
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph(book.epilogue, styles['Normal']))

    doc.build(story)
    buf.seek(0)

    return Response(
        buf.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="chronicle_{dynasty_id}.pdf"'
        }
    )
