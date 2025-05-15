# visualization/military_renderer.py
"""
Military renderer for the multi-agent strategic game.
Handles visualization of military units, armies, battles, and sieges.
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
    Territory, MilitaryUnit, UnitType, Army, Battle, Siege, War,
    DynastyDB, PersonDB
)

class MilitaryRenderer:
    """
    Renders military units, armies, battles, and sieges for the web interface.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the military renderer.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        
        # Unit type colors
        self.unit_type_colors = {
            # Infantry
            UnitType.LEVY_SPEARMEN: '#8B4513',      # Brown
            UnitType.PROFESSIONAL_SWORDSMEN: '#A0522D',  # Sienna
            UnitType.ELITE_GUARDS: '#CD853F',       # Peru
            UnitType.ARCHERS: '#D2691E',            # Chocolate
            
            # Cavalry
            UnitType.LIGHT_CAVALRY: '#6B8E23',      # Olive Drab
            UnitType.HEAVY_CAVALRY: '#556B2F',      # Dark Olive Green
            UnitType.HORSE_ARCHERS: '#808000',      # Olive
            UnitType.KNIGHTS: '#BDB76B',            # Dark Khaki
            
            # Siege
            UnitType.BATTERING_RAM: '#B22222',      # Fire Brick
            UnitType.SIEGE_TOWER: '#8B0000',        # Dark Red
            UnitType.CATAPULT: '#A52A2A',           # Brown
            UnitType.TREBUCHET: '#800000',          # Maroon
            
            # Naval
            UnitType.TRANSPORT_SHIP: '#4682B4',     # Steel Blue
            UnitType.WAR_GALLEY: '#5F9EA0',         # Cadet Blue
            UnitType.HEAVY_WARSHIP: '#4169E1',      # Royal Blue
            UnitType.FIRE_SHIP: '#0000CD'           # Medium Blue
        }
        
        # Unit type markers
        self.unit_type_markers = {
            # Infantry
            UnitType.LEVY_SPEARMEN: 'o',            # Circle
            UnitType.PROFESSIONAL_SWORDSMEN: 'o',   # Circle
            UnitType.ELITE_GUARDS: 'o',             # Circle
            UnitType.ARCHERS: '^',                  # Triangle
            
            # Cavalry
            UnitType.LIGHT_CAVALRY: 's',            # Square
            UnitType.HEAVY_CAVALRY: 's',            # Square
            UnitType.HORSE_ARCHERS: 's',            # Square
            UnitType.KNIGHTS: 'D',                  # Diamond
            
            # Siege
            UnitType.BATTERING_RAM: 'X',            # X
            UnitType.SIEGE_TOWER: 'X',              # X
            UnitType.CATAPULT: 'X',                 # X
            UnitType.TREBUCHET: 'X',                # X
            
            # Naval
            UnitType.TRANSPORT_SHIP: 'p',           # Pentagon
            UnitType.WAR_GALLEY: 'p',               # Pentagon
            UnitType.HEAVY_WARSHIP: 'p',            # Pentagon
            UnitType.FIRE_SHIP: 'p'                 # Pentagon
        }
        
        # Dynasty colors (for armies)
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
    
    def render_army_composition(self, army_id: int, width: int = 8, height: int = 6) -> str:
        """
        Render a visualization of an army's composition.
        
        Args:
            army_id: ID of the army to visualize
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get army
        army = self.session.query(Army).get(army_id)
        if not army:
            return ""
        
        # Get units in army
        units = list(army.units)
        if not units:
            return ""
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(width, height))
        
        # Prepare data for pie chart (unit types)
        unit_types = {}
        for unit in units:
            unit_type = unit.unit_type.value
            if unit_type in unit_types:
                unit_types[unit_type] += unit.size
            else:
                unit_types[unit_type] = unit.size
        
        # Sort by size
        labels = list(unit_types.keys())
        sizes = list(unit_types.values())
        colors = [self.unit_type_colors.get(UnitType(label), '#333333') for label in labels]
        
        # Draw pie chart
        ax1.pie(sizes, labels=[label.replace('_', ' ').title() for label in labels], 
               colors=colors, autopct='%1.1f%%', startangle=90)
        ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
        ax1.set_title('Unit Type Distribution')
        
        # Prepare data for bar chart (unit sizes)
        unit_names = [unit.name or unit.unit_type.value.replace('_', ' ').title() for unit in units]
        unit_sizes = [unit.size for unit in units]
        unit_colors = [self.unit_type_colors.get(unit.unit_type, '#333333') for unit in units]
        
        # Sort by size
        sorted_indices = np.argsort(unit_sizes)[::-1]  # Descending order
        unit_names = [unit_names[i] for i in sorted_indices]
        unit_sizes = [unit_sizes[i] for i in sorted_indices]
        unit_colors = [unit_colors[i] for i in sorted_indices]
        
        # Draw bar chart
        bars = ax2.bar(unit_names, unit_sizes, color=unit_colors)
        ax2.set_title('Unit Sizes')
        ax2.set_ylabel('Number of Troops')
        ax2.tick_params(axis='x', rotation=45)
        
        # Add commander info if available
        if army.commander_id:
            commander = self.session.query(PersonDB).get(army.commander_id)
            if commander:
                commander_text = f"Commander: {commander.name} {commander.surname}\nMilitary Skill: {commander.military_skill}"
                fig.text(0.5, 0.02, commander_text, ha='center', fontsize=10, bbox=dict(facecolor='white', alpha=0.5))
        
        # Adjust layout
        plt.tight_layout()
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def render_battle_result(self, battle_id: int, width: int = 10, height: int = 8) -> str:
        """
        Render a visualization of a battle's result.
        
        Args:
            battle_id: ID of the battle to visualize
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get battle
        battle = self.session.query(Battle).get(battle_id)
        if not battle:
            return ""
        
        # Get battle details
        battle_details = battle.get_details()
        if not battle_details or 'rounds' not in battle_details:
            return ""
        
        # Create figure
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(width, height))
        
        # Extract data from battle rounds
        rounds = battle_details['rounds']
        round_numbers = [r['round'] for r in rounds]
        attacker_strengths = [r.get('attacker_strength', 0) for r in rounds]
        defender_strengths = [r.get('defender_strength', 0) for r in rounds]
        
        # Calculate casualties per round
        attacker_casualties = []
        defender_casualties = []
        attacker_remaining = []
        defender_remaining = []
        
        for i, r in enumerate(rounds):
            if i == 0:
                # First round has no casualties
                attacker_casualties.append(0)
                defender_casualties.append(0)
                attacker_remaining.append(r.get('attacker_troops', 0))
                defender_remaining.append(r.get('defender_troops', 0))
            else:
                attacker_casualties.append(r.get('attacker_casualties', 0))
                defender_casualties.append(r.get('defender_casualties', 0))
                attacker_remaining.append(r.get('attacker_remaining', 0))
                defender_remaining.append(r.get('defender_remaining', 0))
        
        # Plot strength over rounds
        ax1.plot(round_numbers, attacker_strengths, 'r-', label='Attacker Strength')
        ax1.plot(round_numbers, defender_strengths, 'b-', label='Defender Strength')
        ax1.set_title('Battle Strength by Round')
        ax1.set_xlabel('Round')
        ax1.set_ylabel('Strength')
        ax1.legend()
        ax1.grid(True)
        
        # Plot casualties per round
        ax2.bar(np.array(round_numbers) - 0.2, attacker_casualties, width=0.4, color='r', label='Attacker Casualties')
        ax2.bar(np.array(round_numbers) + 0.2, defender_casualties, width=0.4, color='b', label='Defender Casualties')
        ax2.set_title('Casualties by Round')
        ax2.set_xlabel('Round')
        ax2.set_ylabel('Casualties')
        ax2.legend()
        ax2.grid(True)
        
        # Plot remaining troops
        ax3.plot(round_numbers, attacker_remaining, 'r-', label='Attacker Remaining')
        ax3.plot(round_numbers, defender_remaining, 'b-', label='Defender Remaining')
        ax3.set_title('Remaining Troops by Round')
        ax3.set_xlabel('Round')
        ax3.set_ylabel('Troops')
        ax3.legend()
        ax3.grid(True)
        
        # Add battle outcome
        attacker_dynasty = self.session.query(DynastyDB).get(battle.attacker_dynasty_id)
        defender_dynasty = self.session.query(DynastyDB).get(battle.defender_dynasty_id)
        winner_dynasty = self.session.query(DynastyDB).get(battle.winner_dynasty_id) if battle.winner_dynasty_id else None
        
        if attacker_dynasty and defender_dynasty:
            battle_title = f"Battle between {attacker_dynasty.name} and {defender_dynasty.name}"
            if winner_dynasty:
                battle_title += f" - {winner_dynasty.name} Victorious"
            fig.suptitle(battle_title, fontsize=16)
        
        # Adjust layout
        plt.tight_layout()
        plt.subplots_adjust(top=0.9)
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def render_siege_progress(self, siege_id: int, width: int = 8, height: int = 6) -> str:
        """
        Render a visualization of a siege's progress.
        
        Args:
            siege_id: ID of the siege to visualize
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get siege
        siege = self.session.query(Siege).get(siege_id)
        if not siege:
            return ""
        
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Draw progress bar
        progress = siege.progress
        ax.barh(['Siege Progress'], [progress], color='r')
        ax.barh(['Siege Progress'], [1 - progress], left=[progress], color='gray', alpha=0.3)
        
        # Add percentage text
        ax.text(progress / 2, 0, f"{progress:.1%}", ha='center', va='center', color='white', fontweight='bold')
        
        # Set limits and labels
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xticklabels(['0%', '25%', '50%', '75%', '100%'])
        ax.set_yticks([])
        
        # Get territory and dynasties
        territory = self.session.query(Territory).get(siege.territory_id)
        attacker_dynasty = self.session.query(DynastyDB).get(siege.attacker_dynasty_id)
        defender_dynasty = self.session.query(DynastyDB).get(siege.defender_dynasty_id)
        
        # Add siege information
        if territory and attacker_dynasty and defender_dynasty:
            title = f"Siege of {territory.name}"
            subtitle = f"{attacker_dynasty.name} vs {defender_dynasty.name}"
            ax.set_title(f"{title}\n{subtitle}")
            
            # Add status text
            if siege.is_active:
                status = f"Active Siege - Progress: {progress:.1%}"
            elif siege.successful:
                status = f"Successful Siege - Territory Captured"
            else:
                status = f"Failed Siege - Attacker Withdrew"
            
            fig.text(0.5, 0.05, status, ha='center', fontsize=12)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def render_military_overview(self, dynasty_id: int, width: int = 10, height: int = 8) -> str:
        """
        Render an overview of a dynasty's military forces.
        
        Args:
            dynasty_id: ID of the dynasty
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return ""
        
        # Get military units
        units = self.session.query(MilitaryUnit).filter_by(dynasty_id=dynasty_id).all()
        if not units:
            return ""
        
        # Create figure
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(width, height))
        
        # 1. Unit Type Distribution
        unit_types = {}
        for unit in units:
            unit_type = unit.unit_type.value
            if unit_type in unit_types:
                unit_types[unit_type] += unit.size
            else:
                unit_types[unit_type] = unit.size
        
        # Sort by size
        labels = list(unit_types.keys())
        sizes = list(unit_types.values())
        colors = [self.unit_type_colors.get(UnitType(label), '#333333') for label in labels]
        
        # Draw pie chart
        ax1.pie(sizes, labels=[label.replace('_', ' ').title() for label in labels], 
               colors=colors, autopct='%1.1f%%', startangle=90)
        ax1.axis('equal')
        ax1.set_title('Unit Type Distribution')
        
        # 2. Unit Categories
        categories = {
            'Infantry': 0,
            'Cavalry': 0,
            'Siege': 0,
            'Naval': 0
        }
        
        for unit in units:
            unit_type = unit.unit_type
            if unit_type in [UnitType.LEVY_SPEARMEN, UnitType.PROFESSIONAL_SWORDSMEN, UnitType.ELITE_GUARDS, UnitType.ARCHERS]:
                categories['Infantry'] += unit.size
            elif unit_type in [UnitType.LIGHT_CAVALRY, UnitType.HEAVY_CAVALRY, UnitType.HORSE_ARCHERS, UnitType.KNIGHTS]:
                categories['Cavalry'] += unit.size
            elif unit_type in [UnitType.BATTERING_RAM, UnitType.SIEGE_TOWER, UnitType.CATAPULT, UnitType.TREBUCHET]:
                categories['Siege'] += unit.size
            elif unit_type in [UnitType.TRANSPORT_SHIP, UnitType.WAR_GALLEY, UnitType.HEAVY_WARSHIP, UnitType.FIRE_SHIP]:
                categories['Naval'] += unit.size
        
        # Draw bar chart
        category_names = list(categories.keys())
        category_sizes = list(categories.values())
        category_colors = ['#8B4513', '#6B8E23', '#B22222', '#4682B4']  # Brown, Olive, Red, Blue
        
        ax2.bar(category_names, category_sizes, color=category_colors)
        ax2.set_title('Unit Categories')
        ax2.set_ylabel('Number of Troops')
        
        # 3. Army Sizes
        armies = self.session.query(Army).filter_by(dynasty_id=dynasty_id).all()
        army_names = [army.name for army in armies]
        army_sizes = [sum(unit.size for unit in army.units) for army in armies]
        
        if armies:
            # Sort by size
            sorted_indices = np.argsort(army_sizes)[::-1]  # Descending order
            army_names = [army_names[i] for i in sorted_indices]
            army_sizes = [army_sizes[i] for i in sorted_indices]
            
            ax3.bar(army_names, army_sizes, color='#4169E1')  # Royal Blue
            ax3.set_title('Army Sizes')
            ax3.set_ylabel('Number of Troops')
            ax3.tick_params(axis='x', rotation=45)
        else:
            ax3.text(0.5, 0.5, 'No Armies', ha='center', va='center', fontsize=12)
            ax3.set_title('Army Sizes')
            ax3.set_xticks([])
            ax3.set_yticks([])
        
        # 4. Military Quality
        unit_qualities = [unit.quality for unit in units]
        unit_sizes = [unit.size for unit in units]
        
        # Calculate weighted average quality
        avg_quality = sum(q * s for q, s in zip(unit_qualities, unit_sizes)) / sum(unit_sizes) if unit_sizes else 0
        
        # Create quality gauge
        gauge_angles = np.linspace(0, 180, 100)
        gauge_radius = 0.8
        gauge_width = 0.2
        
        # Draw gauge background
        for i, angle in enumerate(gauge_angles[:-1]):
            angle_rad = np.deg2rad(angle)
            next_angle_rad = np.deg2rad(gauge_angles[i + 1])
            
            # Calculate points for the gauge segment
            x1 = gauge_radius * np.cos(angle_rad)
            y1 = gauge_radius * np.sin(angle_rad)
            x2 = gauge_radius * np.cos(next_angle_rad)
            y2 = gauge_radius * np.sin(next_angle_rad)
            
            x3 = (gauge_radius - gauge_width) * np.cos(next_angle_rad)
            y3 = (gauge_radius - gauge_width) * np.sin(next_angle_rad)
            x4 = (gauge_radius - gauge_width) * np.cos(angle_rad)
            y4 = (gauge_radius - gauge_width) * np.sin(angle_rad)
            
            # Determine color based on position
            position = i / len(gauge_angles)
            if position < 0.33:
                color = '#FF6347'  # Tomato (red)
            elif position < 0.67:
                color = '#FFD700'  # Gold (yellow)
            else:
                color = '#32CD32'  # Lime Green
            
            # Draw the segment
            ax4.fill([x1, x2, x3, x4], [y1, y2, y3, y4], color=color, alpha=0.7)
        
        # Draw needle
        quality_angle = 180 * avg_quality / 2.0  # Quality ranges from 0 to 2.0
        quality_rad = np.deg2rad(quality_angle)
        ax4.plot([0, gauge_radius * np.cos(quality_rad)], [0, gauge_radius * np.sin(quality_rad)], 'k-', linewidth=2)
        
        # Add quality text
        ax4.text(0, -0.2, f"Average Quality: {avg_quality:.2f}", ha='center', fontsize=10)
        
        # Set up the gauge axes
        ax4.set_xlim(-1, 1)
        ax4.set_ylim(-0.2, 1)
        ax4.set_aspect('equal')
        ax4.axis('off')
        ax4.set_title('Military Quality')
        
        # Add dynasty name as figure title
        fig.suptitle(f"{dynasty.name} Military Overview", fontsize=16)
        
        # Adjust layout
        plt.tight_layout()
        plt.subplots_adjust(top=0.9)
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str

def save_military_visualization_to_static(military_renderer: MilitaryRenderer, filename: str, **kwargs) -> str:
    """
    Save a military visualization to the static directory.
    
    Args:
        military_renderer: MilitaryRenderer instance
        filename: Name of the file to save
        **kwargs: Arguments to pass to the renderer method
    
    Returns:
        URL of the saved image
    """
    # Determine the method to call based on the filename
    if 'army_composition' in filename:
        img_str = military_renderer.render_army_composition(**kwargs)
    elif 'battle_result' in filename:
        img_str = military_renderer.render_battle_result(**kwargs)
    elif 'siege_progress' in filename:
        img_str = military_renderer.render_siege_progress(**kwargs)
    elif 'military_overview' in filename:
        img_str = military_renderer.render_military_overview(**kwargs)
    else:
        return ""
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.join('static', 'visualizations'), exist_ok=True)
    
    # Save image to file
    img_data = base64.b64decode(img_str)
    file_path = os.path.join('static', 'visualizations', filename)
    with open(file_path, 'wb') as f:
        f.write(img_data)
    
    # Return URL
    return f'/static/visualizations/{filename}'