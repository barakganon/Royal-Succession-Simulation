# visualization/economy_renderer.py
"""
Visualization component for the economy system.
Handles rendering of resource production and consumption, trade networks,
market prices, economic buildings, and economic statistics.
"""

import os
import json
import math
import random
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import numpy as np
from typing import List, Dict, Tuple, Optional, Union, Any
from sqlalchemy.orm import Session
from models.db_models import (
    DynastyDB, Territory, ResourceType, Resource, TerritoryResource,
    Building, BuildingType, TradeRoute
)
from models.economy_system import EconomySystem

class EconomyRenderer:
    """
    Visualization component for the economy system.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the economy renderer.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.economy_system = EconomySystem(session)
        
        # Create visualizations directory if it doesn't exist
        os.makedirs(os.path.join('static', 'visualizations'), exist_ok=True)
        
        # Color maps for different resource types
        self.resource_colors = {
            ResourceType.FOOD: '#8BC34A',     # Green
            ResourceType.TIMBER: '#795548',   # Brown
            ResourceType.STONE: '#9E9E9E',    # Grey
            ResourceType.IRON: '#607D8B',     # Blue Grey
            ResourceType.GOLD: '#FFC107',     # Amber
            ResourceType.SPICES: '#FF5722',   # Deep Orange
            ResourceType.WINE: '#9C27B0',     # Purple
            ResourceType.SILK: '#E91E63',     # Pink
            ResourceType.JEWELRY: '#F44336'   # Red
        }
        
        # Building icons (simplified as colored squares for now)
        self.building_colors = {
            BuildingType.FARM: '#8BC34A',           # Green
            BuildingType.MINE: '#607D8B',           # Blue Grey
            BuildingType.LUMBER_CAMP: '#795548',    # Brown
            BuildingType.WORKSHOP: '#FF9800',       # Orange
            BuildingType.MARKET: '#FFC107',         # Amber
            BuildingType.PORT: '#03A9F4',           # Light Blue
            BuildingType.WAREHOUSE: '#9E9E9E',      # Grey
            BuildingType.TRADE_POST: '#3F51B5',     # Indigo
            BuildingType.ROADS: '#9E9E9E',          # Grey
            BuildingType.IRRIGATION: '#00BCD4',     # Cyan
            BuildingType.GUILD_HALL: '#673AB7',     # Deep Purple
            BuildingType.BANK: '#FFC107'            # Amber
        }
    
    def render_resource_production(self, dynasty_id: int, save_path: Optional[str] = None) -> str:
        """
        Render resource production and consumption for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            save_path: Path to save the visualization (optional)
            
        Returns:
            Path to the saved visualization
        """
        # Get dynasty data
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            raise ValueError(f"Dynasty with ID {dynasty_id} not found")
        
        # Get economy data
        economy_data = self.economy_system.calculate_dynasty_economy(dynasty_id)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Extract production and consumption data
        production = economy_data.get("total_production", {})
        consumption = economy_data.get("total_consumption", {})
        net_production = economy_data.get("net_production", {})
        
        # Prepare data for plotting
        resources = list(set(list(production.keys()) + list(consumption.keys())))
        resources.sort(key=lambda x: x.value if hasattr(x, 'value') else str(x))
        
        resource_names = [r.value if hasattr(r, 'value') else str(r) for r in resources]
        production_values = [production.get(r, 0) for r in resources]
        consumption_values = [consumption.get(r, 0) for r in resources]
        net_values = [net_production.get(r, 0) for r in resources]
        
        # Set up bar positions
        x = np.arange(len(resources))
        width = 0.25
        
        # Create bars
        ax.bar(x - width, production_values, width, label='Production', color='green', alpha=0.7)
        ax.bar(x, consumption_values, width, label='Consumption', color='red', alpha=0.7)
        ax.bar(x + width, net_values, width, label='Net', color='blue', alpha=0.7)
        
        # Add labels and title
        ax.set_xlabel('Resources')
        ax.set_ylabel('Amount')
        ax.set_title(f'Resource Production and Consumption for {dynasty.name}')
        ax.set_xticks(x)
        ax.set_xticklabels(resource_names, rotation=45, ha='right')
        ax.legend()
        
        # Add grid
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save figure
        if save_path is None:
            save_path = os.path.join('static', 'visualizations', f'economy_production_{dynasty_id}.png')
        
        plt.savefig(save_path)
        plt.close()
        
        return save_path
    
    def render_trade_network(self, dynasty_id: Optional[int] = None, save_path: Optional[str] = None) -> str:
        """
        Render trade network visualization.
        
        Args:
            dynasty_id: ID of the dynasty to focus on (optional)
            save_path: Path to save the visualization (optional)
            
        Returns:
            Path to the saved visualization
        """
        # Get all active trade routes
        query = self.session.query(TradeRoute).filter_by(is_active=True)
        
        # Filter by dynasty if provided
        if dynasty_id is not None:
            query = query.filter(
                (TradeRoute.source_dynasty_id == dynasty_id) | 
                (TradeRoute.target_dynasty_id == dynasty_id)
            )
        
        trade_routes = query.all()
        
        # Get all dynasties involved in trade
        dynasty_ids = set()
        for route in trade_routes:
            dynasty_ids.add(route.source_dynasty_id)
            dynasty_ids.add(route.target_dynasty_id)
        
        dynasties = self.session.query(DynastyDB).filter(DynastyDB.id.in_(dynasty_ids)).all()
        dynasty_map = {d.id: d for d in dynasties}
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Create a layout for dynasty nodes
        # For simplicity, we'll use a circular layout
        num_dynasties = len(dynasties)
        radius = 5
        dynasty_positions = {}
        
        for i, dynasty in enumerate(dynasties):
            angle = 2 * math.pi * i / num_dynasties
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            dynasty_positions[dynasty.id] = (x, y)
        
        # Draw dynasty nodes
        for dynasty_id, (x, y) in dynasty_positions.items():
            dynasty = dynasty_map[dynasty_id]
            
            # Highlight the focus dynasty if provided
            if dynasty_id == dynasty_id:
                node_color = 'red'
                node_size = 1000
            else:
                node_color = 'blue'
                node_size = 700
            
            ax.scatter(x, y, s=node_size, color=node_color, alpha=0.7, edgecolors='black')
            ax.text(x, y, dynasty.name, ha='center', va='center', fontweight='bold')
        
        # Draw trade routes
        for route in trade_routes:
            source_pos = dynasty_positions[route.source_dynasty_id]
            target_pos = dynasty_positions[route.target_dynasty_id]
            
            # Get resource color
            resource_color = self.resource_colors.get(route.resource_type, 'gray')
            
            # Draw arrow
            ax.annotate('', 
                       xy=target_pos, xycoords='data',
                       xytext=source_pos, textcoords='data',
                       arrowprops=dict(arrowstyle='->', lw=2, color=resource_color, alpha=0.7,
                                      connectionstyle='arc3,rad=0.1'))
            
            # Add resource label
            mid_x = (source_pos[0] + target_pos[0]) / 2
            mid_y = (source_pos[1] + target_pos[1]) / 2
            
            # Add a small offset to avoid overlapping with the arrow
            offset_x = (target_pos[1] - source_pos[1]) * 0.1
            offset_y = (source_pos[0] - target_pos[0]) * 0.1
            
            ax.text(mid_x + offset_x, mid_y + offset_y, 
                   f"{route.resource_type.value}: {route.resource_amount:.1f}",
                   ha='center', va='center', bbox=dict(facecolor='white', alpha=0.7))
        
        # Set up plot
        ax.set_title('Trade Network Visualization')
        ax.set_xlim(-radius * 1.2, radius * 1.2)
        ax.set_ylim(-radius * 1.2, radius * 1.2)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Save figure
        if save_path is None:
            if dynasty_id is not None:
                save_path = os.path.join('static', 'visualizations', f'trade_network_{dynasty_id}.png')
            else:
                save_path = os.path.join('static', 'visualizations', 'trade_network_global.png')
        
        plt.savefig(save_path)
        plt.close()
        
        return save_path
    
    def render_market_prices(self, save_path: Optional[str] = None) -> str:
        """
        Render market prices visualization.
        
        Args:
            save_path: Path to save the visualization (optional)
            
        Returns:
            Path to the saved visualization
        """
        # Get all resources
        resources = self.session.query(Resource).all()
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Prepare data for plotting
        resource_names = [r.name for r in resources]
        base_values = [r.base_value for r in resources]
        current_values = []
        
        # Get current values from global market
        for resource in resources:
            market_data = self.economy_system.global_market_prices.get(resource.resource_type, {})
            current_values.append(market_data.get("current_price", resource.base_value))
        
        # Set up bar positions
        x = np.arange(len(resources))
        width = 0.35
        
        # Create bars
        ax.bar(x - width/2, base_values, width, label='Base Value', color='blue', alpha=0.7)
        ax.bar(x + width/2, current_values, width, label='Current Value', color='green', alpha=0.7)
        
        # Add labels and title
        ax.set_xlabel('Resources')
        ax.set_ylabel('Value (Gold)')
        ax.set_title('Market Prices')
        ax.set_xticks(x)
        ax.set_xticklabels(resource_names, rotation=45, ha='right')
        ax.legend()
        
        # Add grid
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save figure
        if save_path is None:
            save_path = os.path.join('static', 'visualizations', 'market_prices.png')
        
        plt.savefig(save_path)
        plt.close()
        
        return save_path
    
    def render_territory_economy(self, territory_id: int, save_path: Optional[str] = None) -> str:
        """
        Render economic visualization for a specific territory.
        
        Args:
            territory_id: ID of the territory
            save_path: Path to save the visualization (optional)
            
        Returns:
            Path to the saved visualization
        """
        # Get territory data
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            raise ValueError(f"Territory with ID {territory_id} not found")
        
        # Get production and consumption data
        production = self.economy_system.calculate_territory_production(territory_id)
        consumption = self.economy_system.calculate_territory_consumption(territory_id)
        
        # Get buildings in territory
        buildings = self.session.query(Building).filter_by(territory_id=territory_id).all()
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
        
        # Plot 1: Production and Consumption
        resources = list(set(list(production.keys()) + list(consumption.keys())))
        resources.sort(key=lambda x: x.value if hasattr(x, 'value') else str(x))
        
        resource_names = [r.value if hasattr(r, 'value') else str(r) for r in resources]
        production_values = [production.get(r, 0) for r in resources]
        consumption_values = [consumption.get(r, 0) for r in resources]
        
        # Set up bar positions
        x = np.arange(len(resources))
        width = 0.35
        
        # Create bars
        ax1.bar(x - width/2, production_values, width, label='Production', color='green', alpha=0.7)
        ax1.bar(x + width/2, consumption_values, width, label='Consumption', color='red', alpha=0.7)
        
        # Add labels and title
        ax1.set_xlabel('Resources')
        ax1.set_ylabel('Amount')
        ax1.set_title(f'Resource Production and Consumption in {territory.name}')
        ax1.set_xticks(x)
        ax1.set_xticklabels(resource_names, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, linestyle='--', alpha=0.7)
        
        # Plot 2: Buildings
        if buildings:
            building_types = [b.building_type for b in buildings]
            building_names = [b.name for b in buildings]
            building_levels = [b.level for b in buildings]
            building_conditions = [b.condition for b in buildings]
            
            # Set up bar positions
            x = np.arange(len(buildings))
            
            # Create bars for levels
            bars = ax2.bar(x, building_levels, width, label='Level', alpha=0.7)
            
            # Color bars by building type
            for i, bar in enumerate(bars):
                bar.set_color(self.building_colors.get(building_types[i], 'gray'))
            
            # Add condition as text
            for i, (level, condition) in enumerate(zip(building_levels, building_conditions)):
                ax2.text(i, level + 0.1, f"{condition:.1f}", ha='center', va='bottom')
            
            # Add labels and title
            ax2.set_xlabel('Buildings')
            ax2.set_ylabel('Level')
            ax2.set_title(f'Buildings in {territory.name}')
            ax2.set_xticks(x)
            ax2.set_xticklabels(building_names, rotation=45, ha='right')
            ax2.set_ylim(0, 6)  # Max level is 5
            ax2.grid(True, linestyle='--', alpha=0.7)
        else:
            ax2.text(0.5, 0.5, 'No buildings in this territory', ha='center', va='center', fontsize=12)
            ax2.set_title(f'Buildings in {territory.name}')
            ax2.axis('off')
        
        # Add territory info
        plt.suptitle(f"Territory: {territory.name} (Development Level: {territory.development_level}, Population: {territory.population})")
        
        # Adjust layout
        plt.tight_layout()
        plt.subplots_adjust(top=0.9)
        
        # Save figure
        if save_path is None:
            save_path = os.path.join('static', 'visualizations', f'territory_economy_{territory_id}.png')
        
        plt.savefig(save_path)
        plt.close()
        
        return save_path
    
    def render_economic_trends(self, dynasty_id: int, years: int = 10, save_path: Optional[str] = None) -> str:
        """
        Render economic trends over time for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            years: Number of years to show in the trend
            save_path: Path to save the visualization (optional)
            
        Returns:
            Path to the saved visualization
        """
        # Get dynasty data
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            raise ValueError(f"Dynasty with ID {dynasty_id} not found")
        
        # For this example, we'll generate some simulated trend data
        # In a real implementation, this would come from historical data
        
        # Generate years
        current_year = dynasty.current_simulation_year
        year_range = list(range(current_year - years + 1, current_year + 1))
        
        # Generate simulated data
        np.random.seed(dynasty_id)  # For reproducibility
        
        # Treasury trend
        treasury_base = dynasty.current_wealth
        treasury_trend = [max(0, treasury_base * (1 + 0.1 * i + 0.2 * np.random.randn())) for i in range(years)]
        treasury_trend[-1] = treasury_base  # Set last value to current treasury
        
        # Income trend
        income_base = treasury_base * 0.1  # 10% of treasury as base income
        income_trend = [max(0, income_base * (1 + 0.05 * i + 0.3 * np.random.randn())) for i in range(years)]
        
        # Population trend
        total_population = sum(t.population for t in self.session.query(Territory).filter_by(controller_dynasty_id=dynasty_id).all())
        population_base = total_population
        population_trend = [max(100, int(population_base * (1 + 0.02 * i + 0.1 * np.random.randn()))) for i in range(years)]
        population_trend[-1] = total_population  # Set last value to current population
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        
        # Plot 1: Treasury and Income
        ax1.plot(year_range, treasury_trend, 'b-', label='Treasury', linewidth=2)
        ax1.set_ylabel('Treasury (Gold)', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        
        ax1_twin = ax1.twinx()
        ax1_twin.plot(year_range, income_trend, 'g-', label='Income', linewidth=2)
        ax1_twin.set_ylabel('Income (Gold/Year)', color='g')
        ax1_twin.tick_params(axis='y', labelcolor='g')
        
        ax1.set_title(f'Economic Trends for {dynasty.name}')
        ax1.grid(True, linestyle='--', alpha=0.7)
        
        # Add legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        # Plot 2: Population
        ax2.plot(year_range, population_trend, 'r-', label='Population', linewidth=2)
        ax2.set_ylabel('Population')
        ax2.set_xlabel('Year')
        ax2.grid(True, linestyle='--', alpha=0.7)
        ax2.legend(loc='upper left')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save figure
        if save_path is None:
            save_path = os.path.join('static', 'visualizations', f'economic_trends_{dynasty_id}.png')
        
        plt.savefig(save_path)
        plt.close()
        
        return save_path