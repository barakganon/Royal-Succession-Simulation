"""Economy Blueprint — handles economy viewing, building management, trade routes, and territory development."""

import json
import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models.db_models import (
    db, DynastyDB, HistoryLogEntryDB, Territory, TradeRoute, Resource,
    BuildingType, ResourceType,
)
from models.map_system import TerritoryManager
from utils.theme_manager import get_all_theme_names, get_theme

logger = logging.getLogger('royal_succession.economy')

economy_bp = Blueprint('economy', __name__)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@economy_bp.route('/dynasty/<int:dynasty_id>/economy')
@login_required
def dynasty_economy(dynasty_id):
    """View a dynasty's economic details."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

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
                pass

    # Get economy data for this dynasty
    economy_data = None
    production_chart_url = None
    trade_chart_url = None
    trends_chart_url = None
    try:
        # Import the economy system
        from models.economy_system import EconomySystem

        # Create economy system
        economy_system = EconomySystem(db.session)

        # Get economy data
        economy_data = economy_system.calculate_dynasty_economy(dynasty.id)

        # Generate visualizations
        from visualization.economy_renderer import EconomyRenderer
        economy_renderer = EconomyRenderer(db.session)

        # Generate resource production visualization
        production_chart = economy_renderer.render_resource_production(dynasty.id)
        production_chart_url = production_chart.replace('static/', '/static/')

        # Generate trade network visualization
        trade_chart = economy_renderer.render_trade_network(dynasty.id)
    except (ImportError, Exception) as e:
        # Economy system not available or error
        flash(f"Error loading economy system: {str(e)}", "warning")
        economy_data = None
        production_chart_url = None
        trade_chart_url = None
        trends_chart_url = None

    return render_template('economy_view.html',
                           dynasty=dynasty,
                           theme_config=theme_config,
                           economy_data=economy_data,
                           production_chart_url=production_chart_url,
                           trade_chart_url=trade_chart_url,
                           trends_chart_url=trends_chart_url,
                           ResourceType=ResourceType)


@economy_bp.route('/world/economy')
@login_required
def world_economy_view():
    """View the world economy and interactions between dynasties."""
    # Get all dynasties
    dynasties = DynastyDB.query.all()

    # Get global economy data
    trade_routes = []
    market_chart_url = None
    trade_network_url = None
    resources = []
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        from visualization.economy_renderer import EconomyRenderer

        # Create economy system and renderer
        economy_system = EconomySystem(db.session)
        economy_renderer = EconomyRenderer(db.session)

        # Get all trade routes
        trade_routes = db.session.query(TradeRoute).filter_by(is_active=True).all()

        # Generate market prices visualization
        market_chart = economy_renderer.render_market_prices()
        market_chart_url = market_chart.replace('static/', '/static/')

        # Generate global trade network visualization
        trade_network_chart = economy_renderer.render_trade_network()
        trade_network_url = trade_network_chart.replace('static/', '/static/')

        # Get resources
        resources = db.session.query(Resource).all()

    except (ImportError, Exception) as e:
        # Economy system not available or error
        flash(f"Error loading economy system: {str(e)}", "warning")
        trade_routes = []
        market_chart_url = None
        trade_network_url = None
        resources = []

    # Get recent economic events
    economic_events = db.session.query(HistoryLogEntryDB).filter(
        HistoryLogEntryDB.event_type.like('economic_%')
    ).order_by(HistoryLogEntryDB.year.desc()).limit(10).all()

    return render_template('world_economy.html',
                           dynasties=dynasties,
                           trade_routes=trade_routes,
                           market_chart_url=market_chart_url,
                           trade_network_url=trade_network_url,
                           resources=resources,
                           economic_events=economic_events)


@economy_bp.route('/dynasty/<int:dynasty_id>/construct_building', methods=['POST'])
@login_required
def construct_building(dynasty_id):
    """Construct a new building in a territory."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    territory_id = request.form.get('territory_id', type=int)
    building_type_str = request.form.get('building_type')

    if not territory_id or not building_type_str:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))

    try:
        # Convert string to BuildingType enum
        building_type = BuildingType[building_type_str.upper()]

        # Import the economy system
        from models.economy_system import EconomySystem

        # Create economy system
        economy_system = EconomySystem(db.session)

        # Construct building
        success, message = economy_system.construct_building(territory_id, building_type)

        if success:
            flash(message, "success")
        else:
            flash(message, "warning")

    except (ValueError, KeyError, ImportError, Exception) as e:
        flash(f"Error constructing building: {str(e)}", "danger")

    return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))


@economy_bp.route('/dynasty/<int:dynasty_id>/upgrade_building/<int:building_id>', methods=['POST'])
@login_required
def upgrade_building(dynasty_id, building_id):
    """Upgrade an existing building."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        # Import the economy system
        from models.economy_system import EconomySystem

        # Create economy system
        economy_system = EconomySystem(db.session)

        # Upgrade building
        success, message = economy_system.upgrade_building(building_id)

        if success:
            flash(message, "success")
        else:
            flash(message, "warning")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error upgrading building {building_id}: {e}")
        flash(f"Error upgrading building: {str(e)}", "danger")

    return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))


@economy_bp.route('/dynasty/<int:dynasty_id>/repair_building/<int:building_id>', methods=['POST'])
@login_required
def repair_building(dynasty_id, building_id):
    """Repair a damaged building."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        # Import the economy system
        from models.economy_system import EconomySystem

        # Create economy system
        economy_system = EconomySystem(db.session)

        # Repair building
        success, message = economy_system.repair_building(building_id)

        if success:
            flash(message, "success")
        else:
            flash(message, "warning")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error repairing building {building_id}: {e}")
        flash(f"Error repairing building: {str(e)}", "danger")

    return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))


@economy_bp.route('/dynasty/<int:dynasty_id>/develop_territory/<int:territory_id>', methods=['POST'])
@login_required
def develop_territory_economy(dynasty_id, territory_id):
    """Develop a territory to increase its development level."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        # Import the economy system
        from models.economy_system import EconomySystem

        # Create economy system
        economy_system = EconomySystem(db.session)

        # Develop territory
        success, message = economy_system.develop_territory(territory_id)

        if success:
            flash(message, "success")
        else:
            flash(message, "warning")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error developing territory {territory_id}: {e}")
        flash(f"Error developing territory: {str(e)}", "danger")

    return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))


@economy_bp.route('/dynasty/<int:dynasty_id>/establish_trade', methods=['POST'])
@login_required
def establish_trade(dynasty_id):
    """Establish a trade route with another dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    target_dynasty_id = request.form.get('target_dynasty_id', type=int)
    resource_type_str = request.form.get('resource_type')
    amount = request.form.get('amount', type=float)

    if not target_dynasty_id or not resource_type_str or not amount:
        flash("Missing required parameters.", "danger")
        return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))

    try:
        # Convert string to ResourceType enum
        resource_type = ResourceType[resource_type_str.upper()]

        # Import the economy system
        from models.economy_system import EconomySystem

        # Create economy system
        economy_system = EconomySystem(db.session)

        # Establish trade route
        success, message, _ = economy_system.establish_trade_route(
            dynasty_id, target_dynasty_id, resource_type, amount
        )

        if success:
            flash(message, "success")
        else:
            flash(message, "warning")

    except (ValueError, KeyError, ImportError, Exception) as e:
        flash(f"Error establishing trade route: {str(e)}", "danger")

    return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))


@economy_bp.route('/dynasty/<int:dynasty_id>/cancel_trade/<int:trade_route_id>', methods=['POST'])
@login_required
def cancel_trade(dynasty_id, trade_route_id):
    """Cancel an existing trade route."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    try:
        # Import the economy system
        from models.economy_system import EconomySystem

        # Create economy system
        economy_system = EconomySystem(db.session)

        # Cancel trade route
        success, message = economy_system.cancel_trade_route(trade_route_id, dynasty_id)

        if success:
            flash(message, "success")
        else:
            flash(message, "warning")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error canceling trade route {trade_route_id}: {e}")
        flash(f"Error canceling trade route: {str(e)}", "danger")

    return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))


@economy_bp.route('/territory/<int:territory_id>/economy')
@login_required
def territory_economy(territory_id):
    """View economic details for a specific territory."""
    territory = Territory.query.get_or_404(territory_id)

    # Check if user has access to this territory
    if territory.controller_dynasty_id:
        dynasty = DynastyDB.query.get(territory.controller_dynasty_id)
        if dynasty and dynasty.owner_user != current_user:
            flash("Not authorized.", "warning")
            return redirect(url_for('auth.dashboard'))

    production = {}
    consumption = {}
    tax_income = 0
    buildings = []
    economy_chart_url = None
    try:
        # Import the economy system
        from models.economy_system import EconomySystem
        from visualization.economy_renderer import EconomyRenderer

        # Create economy system and renderer
        economy_system = EconomySystem(db.session)
        economy_renderer = EconomyRenderer(db.session)

        # Get production and consumption data
        production = economy_system.calculate_territory_production(territory_id)
        consumption = economy_system.calculate_territory_consumption(territory_id)
        tax_income = economy_system.calculate_territory_tax_income(territory_id)
    except (ImportError, Exception) as e:
        # Economy system not available or error
        flash(f"Error loading economy data: {str(e)}", "warning")
        production = {}
        consumption = {}
        tax_income = 0
        buildings = []
        economy_chart_url = None

    return render_template('territory_economy.html',
                           territory=territory,
                           production=production,
                           consumption=consumption,
                           tax_income=tax_income,
                           buildings=buildings,
                           economy_chart_url=economy_chart_url)


@economy_bp.route('/dynasty/<int:dynasty_id>/develop_territory', methods=['POST'])
@login_required
def develop_territory(dynasty_id):
    """Develop a territory by increasing its development level or adding buildings."""
    # Get dynasty
    dynasty = DynastyDB.query.get_or_404(dynasty_id)

    # Check ownership
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    territory_id = request.form.get('territory_id', type=int)
    development_type = request.form.get('development_type')

    if not territory_id or not development_type:
        flash("Missing territory ID or development type.", "danger")
        return redirect(url_for('map.dynasty_territories', dynasty_id=dynasty_id))

    # Check if territory is controlled by this dynasty
    territory = Territory.query.get_or_404(territory_id)
    if territory.controller_dynasty_id != dynasty_id:
        flash("You don't control this territory.", "danger")
        return redirect(url_for('map.dynasty_territories', dynasty_id=dynasty_id))

    # Create territory manager
    territory_manager = TerritoryManager(db.session)

    try:
        # Develop territory
        territory_manager.develop_territory(territory_id, development_type)
        flash(f"Territory {territory.name} developed successfully.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to develop territory {territory_id}: {e}")
        flash(f"Failed to develop territory: {e}", "danger")

    # Redirect back to territory details page
    return redirect(url_for('map.territory_details', territory_id=territory_id))


@economy_bp.route('/dynasty/<int:dynasty_id>/add_holding', methods=['POST'])
@login_required
def add_holding(dynasty_id):
    """Add a new holding to a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash("Not authorized.", "warning")
        return redirect(url_for('auth.dashboard'))

    # Get form data
    name = request.form.get('name')
    holding_type = request.form.get('holding_type')
    size = float(request.form.get('size', 1.0))

    # Validate
    if not name or not holding_type:
        flash("Name and holding type are required.", "danger")
        return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))

    # Cost based on size and type
    base_costs = {
        "farm": 50,
        "mine": 100,
        "forest": 40,
        "coastal": 80,
        "urban": 150
    }

    cost = base_costs.get(holding_type, 50) * size

    # Check if dynasty can afford it
    if dynasty.current_wealth < cost:
        flash(f"Not enough wealth to purchase this holding. Cost: {cost}, Available: {dynasty.current_wealth}", "danger")
        return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))

    try:
        # Import the economy module
        from models.economy import EconomyManager

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

        # Create or get economy manager
        economy = EconomyManager(dynasty_id=dynasty.id, theme_config=theme_config)

        # Add the holding
        economy.add_holding(name, holding_type, size)

        # Deduct cost
        dynasty.current_wealth -= cost
        db.session.commit()

        flash(f"Added new {holding_type} holding: {name}", "success")
    except ImportError:
        flash("Economy system not available.", "danger")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding holding for dynasty {dynasty_id}: {e}")
        flash(f"Error adding holding: {str(e)}", "danger")

    return redirect(url_for('economy.dynasty_economy', dynasty_id=dynasty_id))


@economy_bp.route('/propose_trade', methods=['POST'])
@login_required
def propose_trade():
    """Propose a trade agreement with another dynasty."""
    flash("Trade proposal functionality will be implemented in a future update.", "info")
    return redirect(url_for('economy.world_economy_view'))


@economy_bp.route('/form_alliance', methods=['POST'])
@login_required
def form_alliance():
    """Form an alliance with another dynasty."""
    flash("Alliance formation functionality will be implemented in a future update.", "info")
    return redirect(url_for('economy.world_economy_view'))


# ---------------------------------------------------------------------------
# Banking routes
# ---------------------------------------------------------------------------

from models.banking_system import BankingSystem
from models.db_models import Loan


@economy_bp.route('/dynasty/<int:dynasty_id>/banking')
@login_required
def banking_view(dynasty_id):
    """Display the banking / loans overview for a dynasty."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash('Not authorized to view this dynasty.', 'danger')
        return redirect(url_for('auth.dashboard'))

    bs = BankingSystem(db.session)
    active_loans = bs.get_active_loans(dynasty_id)
    loan_history = bs.get_loan_history(dynasty_id)
    total_debt = bs.total_debt(dynasty_id)

    return render_template(
        'banking.html',
        dynasty=dynasty,
        active_loans=active_loans,
        loan_history=loan_history,
        total_debt=total_debt,
        max_loan=2000,
        min_loan=100,
        interest_rate=15,
    )


@economy_bp.route('/dynasty/<int:dynasty_id>/banking/borrow', methods=['POST'])
@login_required
def banking_borrow(dynasty_id):
    """Take out a new loan."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash('Not authorized.', 'danger')
        return redirect(url_for('auth.dashboard'))

    try:
        amount = int(request.form.get('amount', 0))
    except (ValueError, TypeError):
        flash('Invalid loan amount.', 'danger')
        return redirect(url_for('economy.banking_view', dynasty_id=dynasty_id))

    bs = BankingSystem(db.session)
    result = bs.borrow(dynasty_id, amount, dynasty.current_simulation_year)
    flash(result['message'], 'success' if result['success'] else 'danger')
    return redirect(url_for('economy.banking_view', dynasty_id=dynasty_id))


@economy_bp.route('/dynasty/<int:dynasty_id>/banking/repay', methods=['POST'])
@login_required
def banking_repay(dynasty_id):
    """Repay gold toward a specific loan."""
    dynasty = DynastyDB.query.get_or_404(dynasty_id)
    if dynasty.owner_user != current_user:
        flash('Not authorized.', 'danger')
        return redirect(url_for('auth.dashboard'))

    try:
        loan_id = int(request.form.get('loan_id', 0))
        amount = int(request.form.get('amount', 0))
    except (ValueError, TypeError):
        flash('Invalid repayment values.', 'danger')
        return redirect(url_for('economy.banking_view', dynasty_id=dynasty_id))

    bs = BankingSystem(db.session)
    result = bs.repay(dynasty_id, loan_id, amount, dynasty.current_simulation_year)
    flash(result['message'], 'success' if result['success'] else 'danger')
    return redirect(url_for('economy.banking_view', dynasty_id=dynasty_id))
