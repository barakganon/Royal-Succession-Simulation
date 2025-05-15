# visualization/map_renderer.py
"""
Map renderer for the multi-agent strategic game.
Handles rendering the game map for the web interface.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import numpy as np
import io
import base64
import os
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy.orm import Session
from models.db_models import (
    Territory, Region, Province, TerrainType, Settlement,
    Resource, TerritoryResource, Building, MilitaryUnit, Army
)

class MapRenderer:
    """
    Renders the game map for the web interface.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the map renderer.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        
        # Color schemes for different map elements
        self.terrain_colors = {
            TerrainType.PLAINS: '#C2D59B',    # Light green
            TerrainType.HILLS: '#9BBF88',     # Medium green
            TerrainType.MOUNTAINS: '#8B7355', # Brown
            TerrainType.FOREST: '#228B22',    # Forest green
            TerrainType.DESERT: '#F4D03F',    # Sand yellow
            TerrainType.TUNDRA: '#E8E8E8',    # Light gray
            TerrainType.COASTAL: '#87CEFA',   # Light blue
            TerrainType.RIVER: '#1E90FF',     # Blue
            TerrainType.LAKE: '#4682B4',      # Steel blue
            TerrainType.SWAMP: '#2F4F4F'      # Dark slate gray
        }
        
        # Dynasty colors for territory control
        self.dynasty_colors = [
            '#FF0000',  # Red
            '#0000FF',  # Blue
            '#00FF00',  # Green
            '#FFFF00',  # Yellow
            '#FF00FF',  # Magenta
            '#00FFFF',  # Cyan
            '#FFA500',  # Orange
            '#800080',  # Purple
            '#008080',  # Teal
            '#800000',  # Maroon
            '#008000',  # Dark green
            '#000080',  # Navy
            '#FFC0CB',  # Pink
            '#A52A2A',  # Brown
            '#808080'   # Gray
        ]
        
        # Settlement markers
        self.settlement_markers = {
            'village': 'o',   # Circle
            'town': 's',      # Square
            'city': '*',      # Star
            'castle': '^'     # Triangle
        }
        
        # Military unit markers
        self.unit_markers = {
            'infantry': 'o',   # Circle
            'cavalry': 's',    # Square
            'siege': '^',      # Triangle
            'naval': 'D'       # Diamond
        }
    
    def render_world_map(self, width: int = 12, height: int = 10, 
                        show_terrain: bool = True, 
                        show_territories: bool = True,
                        show_settlements: bool = True,
                        show_resources: bool = False,
                        show_units: bool = False,
                        highlight_dynasty_id: Optional[int] = None) -> str:
        """
        Render the world map.
        
        Args:
            width: Width of the figure in inches
            height: Height of the figure in inches
            show_terrain: Whether to show terrain colors
            show_territories: Whether to show territory borders
            show_settlements: Whether to show settlements
            show_resources: Whether to show resources
            show_units: Whether to show military units
            highlight_dynasty_id: ID of the dynasty to highlight
            
        Returns:
            Base64 encoded PNG image
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Get all territories
        territories = self.session.query(Territory).all()
        
        # Get dynasty-color mapping
        dynasty_colors = self._get_dynasty_colors()
        
        # Draw territories
        for territory in territories:
            # Get territory position
            x, y = territory.x_coordinate, territory.y_coordinate
            
            # Determine territory color
            if show_terrain:
                # Use terrain color
                color = self.terrain_colors.get(territory.terrain_type, '#FFFFFF')
            else:
                # Use dynasty color if controlled
                if territory.controller_dynasty_id:
                    color = dynasty_colors.get(territory.controller_dynasty_id, '#FFFFFF')
                else:
                    color = '#FFFFFF'  # White for uncontrolled
            
            # Highlight dynasty territories if specified
            if highlight_dynasty_id and territory.controller_dynasty_id == highlight_dynasty_id:
                # Add highlight effect
                edge_color = '#000000'  # Black border
                linewidth = 2
                alpha = 1.0
            else:
                edge_color = '#666666'  # Gray border
                linewidth = 1
                alpha = 0.8 if highlight_dynasty_id else 1.0
            
            # Draw territory as circle
            territory_size = 300 * (0.5 + 0.5 * territory.development_level / 10)
            ax.scatter(x, y, s=territory_size, c=color, edgecolors=edge_color, 
                      linewidth=linewidth, alpha=alpha, zorder=1)
            
            # Add territory name for important territories
            if territory.is_capital or territory.development_level >= 5:
                ax.text(x, y, territory.name, fontsize=8, ha='center', va='center', 
                       zorder=3, color='black', fontweight='bold')
        
        # Draw settlements if enabled
        if show_settlements:
            settlements = self.session.query(Settlement).all()
            
            for settlement in settlements:
                # Get territory position
                territory = self.session.query(Territory).get(settlement.territory_id)
                if not territory:
                    continue
                
                x, y = territory.x_coordinate, territory.y_coordinate
                
                # Add small offset to avoid overlap with territory center
                x += np.random.uniform(-0.05, 0.05) * 50
                y += np.random.uniform(-0.05, 0.05) * 50
                
                # Determine marker
                marker = self.settlement_markers.get(settlement.settlement_type, 'o')
                
                # Determine size based on importance
                size = 50 + settlement.importance * 20
                
                # Draw settlement
                ax.scatter(x, y, s=size, c='black', marker=marker, edgecolors='white', 
                          linewidth=1, alpha=0.8, zorder=2)
        
        # Draw resources if enabled
        if show_resources:
            territory_resources = self.session.query(TerritoryResource).all()
            
            for tr in territory_resources:
                # Get territory position
                territory = self.session.query(Territory).get(tr.territory_id)
                if not territory:
                    continue
                
                # Get resource
                resource = self.session.query(Resource).get(tr.resource_id)
                if not resource:
                    continue
                
                x, y = territory.x_coordinate, territory.y_coordinate
                
                # Add offset to avoid overlap
                x += np.random.uniform(-0.1, 0.1) * 50
                y += np.random.uniform(-0.1, 0.1) * 50
                
                # Determine color based on resource type
                if resource.is_luxury:
                    color = 'gold'
                else:
                    color = 'silver'
                
                # Draw resource
                ax.scatter(x, y, s=30, c=color, marker='D', edgecolors='black', 
                          linewidth=1, alpha=0.8, zorder=2)
                
                # Add resource name for luxury resources
                if resource.is_luxury:
                    ax.text(x, y + 10, resource.name, fontsize=6, ha='center', 
                           zorder=3, color='black')
        
        # Draw military units if enabled
        if show_units:
            # Draw armies
            armies = self.session.query(Army).all()
            
            for army in armies:
                # Get territory position
                territory = self.session.query(Territory).get(army.territory_id)
                if not territory:
                    continue
                
                x, y = territory.x_coordinate, territory.y_coordinate
                
                # Add offset to avoid overlap
                x += np.random.uniform(-0.15, 0.15) * 50
                y += np.random.uniform(-0.15, 0.15) * 50
                
                # Determine color based on dynasty
                color = dynasty_colors.get(army.dynasty_id, '#000000')
                
                # Draw army
                ax.scatter(x, y, s=100, c=color, marker='X', edgecolors='black', 
                          linewidth=1, alpha=0.9, zorder=3)
                
                # Add army name
                ax.text(x, y + 15, army.name, fontsize=6, ha='center', 
                       zorder=3, color='black')
            
            # Draw individual units not in armies
            units = self.session.query(MilitaryUnit).filter_by(army_id=None).all()
            
            for unit in units:
                # Get territory position
                territory = self.session.query(Territory).get(unit.territory_id)
                if not territory:
                    continue
                
                x, y = territory.x_coordinate, territory.y_coordinate
                
                # Add offset to avoid overlap
                x += np.random.uniform(-0.15, 0.15) * 50
                y += np.random.uniform(-0.15, 0.15) * 50
                
                # Determine color based on dynasty
                color = dynasty_colors.get(unit.dynasty_id, '#000000')
                
                # Determine unit type category
                unit_category = 'infantry'  # Default
                if unit.unit_type.value in ['light_cavalry', 'heavy_cavalry', 'horse_archers', 'knights']:
                    unit_category = 'cavalry'
                elif unit.unit_type.value in ['battering_ram', 'siege_tower', 'catapult', 'trebuchet']:
                    unit_category = 'siege'
                elif unit.unit_type.value in ['transport_ship', 'war_galley', 'heavy_warship', 'fire_ship']:
                    unit_category = 'naval'
                
                # Determine marker
                marker = self.unit_markers.get(unit_category, 'o')
                
                # Draw unit
                ax.scatter(x, y, s=50, c=color, marker=marker, edgecolors='black', 
                          linewidth=1, alpha=0.8, zorder=3)
        
        # Create legend
        legend_elements = []
        
        # Terrain legend
        if show_terrain:
            for terrain_type, color in self.terrain_colors.items():
                legend_elements.append(
                    mpatches.Patch(color=color, label=terrain_type.value.capitalize())
                )
        
        # Dynasty legend
        if not show_terrain:
            for dynasty_id, color in dynasty_colors.items():
                # Get dynasty name
                from models.db_models import DynastyDB
                dynasty = self.session.query(DynastyDB).get(dynasty_id)
                if dynasty:
                    legend_elements.append(
                        mpatches.Patch(color=color, label=dynasty.name)
                    )
        
        # Settlement legend
        if show_settlements:
            for settlement_type, marker in self.settlement_markers.items():
                legend_elements.append(
                    plt.Line2D([0], [0], marker=marker, color='w', markerfacecolor='black',
                              markersize=8, label=settlement_type.capitalize())
                )
        
        # Add legend if we have elements
        if legend_elements:
            ax.legend(handles=legend_elements, loc='upper right', fontsize='small')
        
        # Set axis limits with some padding
        all_x = [t.x_coordinate for t in territories]
        all_y = [t.y_coordinate for t in territories]
        
        if all_x and all_y:
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            
            # Add padding
            padding_x = (max_x - min_x) * 0.1
            padding_y = (max_y - min_y) * 0.1
            
            ax.set_xlim(min_x - padding_x, max_x + padding_x)
            ax.set_ylim(min_y - padding_y, max_y + padding_y)
        
        # Set title
        ax.set_title('World Map')
        
        # Remove axis ticks and labels
        ax.set_xticks([])
        ax.set_yticks([])
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def render_territory_map(self, territory_id: int, width: int = 8, height: int = 6) -> str:
        """
        Render a detailed map of a specific territory.
        
        Args:
            territory_id: ID of the territory to render
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get territory
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return ""
        
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Get territory position
        x, y = territory.x_coordinate, territory.y_coordinate
        
        # Determine territory color based on terrain
        color = self.terrain_colors.get(territory.terrain_type, '#FFFFFF')
        
        # Draw territory as large circle
        ax.scatter(x, y, s=5000, c=color, edgecolors='black', linewidth=2, alpha=0.7, zorder=1)
        
        # Add territory name
        ax.text(x, y - 50, territory.name, fontsize=14, ha='center', va='center', 
               zorder=3, color='black', fontweight='bold')
        
        # Add terrain type
        ax.text(x, y - 30, f"Terrain: {territory.terrain_type.value.capitalize()}", 
               fontsize=10, ha='center', va='center', zorder=3, color='black')
        
        # Add development level
        ax.text(x, y - 10, f"Development: {territory.development_level}", 
               fontsize=10, ha='center', va='center', zorder=3, color='black')
        
        # Add population
        ax.text(x, y + 10, f"Population: {territory.population}", 
               fontsize=10, ha='center', va='center', zorder=3, color='black')
        
        # Add controller if any
        if territory.controller_dynasty_id:
            from models.db_models import DynastyDB
            dynasty = self.session.query(DynastyDB).get(territory.controller_dynasty_id)
            if dynasty:
                ax.text(x, y + 30, f"Controlled by: {dynasty.name}", 
                       fontsize=10, ha='center', va='center', zorder=3, color='black')
        
        # Get settlements in this territory
        settlements = self.session.query(Settlement).filter_by(territory_id=territory_id).all()
        
        # Draw settlements
        for i, settlement in enumerate(settlements):
            # Calculate position in a circle around territory center
            angle = 2 * np.pi * i / max(1, len(settlements))
            radius = 30
            sx = x + radius * np.cos(angle)
            sy = y + radius * np.sin(angle)
            
            # Determine marker
            marker = self.settlement_markers.get(settlement.settlement_type, 'o')
            
            # Determine size based on importance
            size = 100 + settlement.importance * 30
            
            # Draw settlement
            ax.scatter(sx, sy, s=size, c='black', marker=marker, edgecolors='white', 
                      linewidth=1, alpha=0.8, zorder=2)
            
            # Add settlement name
            ax.text(sx, sy + 10, settlement.name, fontsize=8, ha='center', 
                   zorder=3, color='black')
        
        # Get resources in this territory
        territory_resources = self.session.query(TerritoryResource).filter_by(territory_id=territory_id).all()
        
        # Draw resources
        for i, tr in enumerate(territory_resources):
            # Get resource
            resource = self.session.query(Resource).get(tr.resource_id)
            if not resource:
                continue
            
            # Calculate position in a circle around territory center
            angle = 2 * np.pi * i / max(1, len(territory_resources))
            radius = 60
            rx = x + radius * np.cos(angle)
            ry = y + radius * np.sin(angle)
            
            # Determine color based on resource type
            if resource.is_luxury:
                color = 'gold'
            else:
                color = 'silver'
            
            # Draw resource
            ax.scatter(rx, ry, s=80, c=color, marker='D', edgecolors='black', 
                      linewidth=1, alpha=0.8, zorder=2)
            
            # Add resource name
            ax.text(rx, ry + 10, resource.name, fontsize=8, ha='center', 
                   zorder=3, color='black')
            
            # Add production info
            ax.text(rx, ry - 10, f"Prod: {tr.base_production:.1f}", fontsize=6, ha='center', 
                   zorder=3, color='black')
        
        # Get buildings in this territory
        buildings = self.session.query(Building).filter_by(territory_id=territory_id).all()
        
        # Draw buildings
        for i, building in enumerate(buildings):
            # Calculate position in a circle around territory center
            angle = 2 * np.pi * i / max(1, len(buildings))
            radius = 90
            bx = x + radius * np.cos(angle)
            by = y + radius * np.sin(angle)
            
            # Draw building
            ax.scatter(bx, by, s=70, c='brown', marker='s', edgecolors='black', 
                      linewidth=1, alpha=0.8, zorder=2)
            
            # Add building name
            building_name = building.building_type.value.replace('_', ' ').title()
            ax.text(bx, by + 10, building_name, fontsize=7, ha='center', 
                   zorder=3, color='black')
            
            # Add level info
            ax.text(bx, by - 10, f"Level: {building.level}", fontsize=6, ha='center', 
                   zorder=3, color='black')
        
        # Set title
        ax.set_title(f'Territory Map: {territory.name}')
        
        # Remove axis ticks and labels
        ax.set_xticks([])
        ax.set_yticks([])
        
        # Set axis limits with padding
        padding = 100
        ax.set_xlim(x - padding, x + padding)
        ax.set_ylim(y - padding, y + padding)
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def _get_dynasty_colors(self) -> Dict[int, str]:
        """
        Get a mapping of dynasty IDs to colors.
        
        Returns:
            Dictionary mapping dynasty IDs to color strings
        """
        # Get all dynasties
        from models.db_models import DynastyDB
        dynasties = self.session.query(DynastyDB).all()
        
        # Create mapping
        dynasty_colors = {}
        
        for i, dynasty in enumerate(dynasties):
            # Use predefined colors if available, otherwise generate
            if i < len(self.dynasty_colors):
                color = self.dynasty_colors[i]
            else:
                # Generate a random color
                color = '#' + ''.join([f'{int(c*255):02x}' for c in mcolors.hsv_to_rgb([i/len(dynasties), 0.8, 0.8])])
            
            dynasty_colors[dynasty.id] = color
        
        return dynasty_colors


def save_map_to_static(map_renderer: MapRenderer, filename: str, **kwargs) -> str:
    """
    Save a map to the static directory.
    
    Args:
        map_renderer: MapRenderer instance
        filename: Filename to save as
        **kwargs: Arguments to pass to render_world_map
        
    Returns:
        Path to the saved file
    """
    # Generate map
    img_str = map_renderer.render_world_map(**kwargs)
    
    # Ensure static/maps directory exists
    os.makedirs('static/maps', exist_ok=True)
    
    # Save to file
    filepath = f'static/maps/{filename}'
    with open(filepath, 'wb') as f:
        f.write(base64.b64decode(img_str))
    
    return filepath