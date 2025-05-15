# visualization/diplomacy_renderer.py
"""
Diplomacy renderer for the multi-agent strategic game.
Handles visualization of diplomatic relations, treaties, and reputation.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import networkx as nx
import numpy as np
import io
import base64
import os
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy.orm import Session
from models.db_models import (
    DynastyDB, DiplomaticRelation, Treaty, TreatyType, War
)
from models.diplomacy_system import DiplomacySystem

class DiplomacyRenderer:
    """
    Renders diplomatic relations, treaties, and reputation for the web interface.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the diplomacy renderer.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.diplomacy_system = DiplomacySystem(session)
        
        # Relation status colors
        self.relation_colors = {
            "Allied": '#00AA00',      # Green
            "Friendly": '#88CC00',    # Light green
            "Cordial": '#CCFF00',     # Yellow-green
            "Neutral": '#CCCCCC',     # Gray
            "Unfriendly": '#FFCC00',  # Orange
            "Hostile": '#FF6600',     # Dark orange
            "Nemesis": '#FF0000'      # Red
        }
        
        # Treaty type colors
        self.treaty_colors = {
            TreatyType.NON_AGGRESSION: '#AAAAFF',       # Light blue
            TreatyType.DEFENSIVE_ALLIANCE: '#0000FF',   # Blue
            TreatyType.MILITARY_ALLIANCE: '#000088',    # Dark blue
            TreatyType.VASSALAGE: '#8800FF',            # Purple
            TreatyType.TRADE_AGREEMENT: '#FFFF00',      # Yellow
            TreatyType.MARKET_ACCESS: '#FFCC00',        # Orange
            TreatyType.RESOURCE_EXCHANGE: '#FF8800',    # Dark orange
            TreatyType.ECONOMIC_UNION: '#FF0000',       # Red
            TreatyType.CULTURAL_EXCHANGE: '#00FFFF',    # Cyan
            TreatyType.ROYAL_MARRIAGE: '#FF00FF'        # Magenta
        }
        
        # War colors
        self.war_color = '#FF0000'  # Red
    
    def render_diplomatic_relations(self, dynasty_id: Optional[int] = None, 
                                   width: int = 10, height: int = 8) -> str:
        """
        Render a network graph of diplomatic relations between dynasties.
        
        Args:
            dynasty_id: ID of the dynasty to focus on (optional)
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get all dynasties
        dynasties = self.session.query(DynastyDB).all()
        if not dynasties:
            return ""
            
        # Create graph
        G = nx.Graph()
        
        # Add nodes (dynasties)
        for dynasty in dynasties:
            G.add_node(dynasty.id, name=dynasty.name, prestige=dynasty.prestige)
        
        # Add edges (diplomatic relations)
        relations = self.session.query(DiplomaticRelation).all()
        
        for relation in relations:
            # Get relation status
            status, score = self.diplomacy_system.get_relation_status(relation.dynasty1_id, relation.dynasty2_id)
            
            # Add edge with attributes
            G.add_edge(relation.dynasty1_id, relation.dynasty2_id, 
                      status=status, score=score, 
                      color=self.relation_colors.get(status, '#CCCCCC'))
        
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Determine layout
        if dynasty_id and dynasty_id in G:
            # Ego-centric layout with focus dynasty at center
            pos = nx.spring_layout(G, seed=42, k=0.3)
            
            # Adjust position to put focus dynasty at center
            center_x = pos[dynasty_id][0]
            center_y = pos[dynasty_id][1]
            
            for node in pos:
                pos[node][0] -= center_x
                pos[node][1] -= center_y
                
            pos[dynasty_id] = np.array([0, 0])
        else:
            # Standard spring layout
            pos = nx.spring_layout(G, seed=42, k=0.3)
        
        # Draw edges with colors based on relation status
        for u, v, data in G.edges(data=True):
            nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], width=2, 
                                  alpha=0.7, edge_color=data.get('color', '#CCCCCC'))
        
        # Draw nodes with size based on prestige
        node_sizes = [100 + G.nodes[node].get('prestige', 0) / 5 for node in G.nodes()]
        nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color='skyblue', 
                              alpha=0.8, linewidths=2, edgecolors='black')
        
        # Draw labels
        nx.draw_networkx_labels(G, pos, labels={node: G.nodes[node]['name'] for node in G.nodes()}, 
                               font_size=10, font_weight='bold')
        
        # Highlight focus dynasty if specified
        if dynasty_id and dynasty_id in G:
            nx.draw_networkx_nodes(G, pos, nodelist=[dynasty_id], node_size=node_sizes[list(G.nodes()).index(dynasty_id)], 
                                  node_color='red', alpha=0.8, linewidths=2, edgecolors='black')
        
        # Add relation status legend
        legend_elements = []
        for status, color in self.relation_colors.items():
            legend_elements.append(
                mpatches.Patch(color=color, label=status)
            )
        
        ax.legend(handles=legend_elements, loc='upper right', title="Relation Status")
        
        # Set title
        if dynasty_id:
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if dynasty:
                ax.set_title(f"Diplomatic Relations for {dynasty.name}")
            else:
                ax.set_title("Diplomatic Relations Network")
        else:
            ax.set_title("Diplomatic Relations Network")
        
        # Remove axis
        ax.axis('off')
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def render_treaty_network(self, treaty_type: Optional[TreatyType] = None, 
                             width: int = 10, height: int = 8) -> str:
        """
        Render a network graph of treaties between dynasties.
        
        Args:
            treaty_type: Type of treaty to focus on (optional)
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get all dynasties
        dynasties = self.session.query(DynastyDB).all()
        if not dynasties:
            return ""
            
        # Create graph
        G = nx.Graph()
        
        # Add nodes (dynasties)
        for dynasty in dynasties:
            G.add_node(dynasty.id, name=dynasty.name)
        
        # Get all active treaties
        if treaty_type:
            treaties = self.session.query(Treaty).filter_by(treaty_type=treaty_type, active=True).all()
        else:
            treaties = self.session.query(Treaty).filter_by(active=True).all()
        
        # Add edges (treaties)
        for treaty in treaties:
            # Get diplomatic relation
            relation = self.session.query(DiplomaticRelation).get(treaty.diplomatic_relation_id)
            if not relation:
                continue
                
            # Add edge with attributes
            G.add_edge(relation.dynasty1_id, relation.dynasty2_id, 
                      treaty_type=treaty.treaty_type, 
                      color=self.treaty_colors.get(treaty.treaty_type, '#CCCCCC'))
        
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Determine layout
        pos = nx.spring_layout(G, seed=42, k=0.3)
        
        # Draw edges with colors based on treaty type
        for u, v, data in G.edges(data=True):
            nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], width=2, 
                                  alpha=0.7, edge_color=data.get('color', '#CCCCCC'))
        
        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_size=300, node_color='skyblue', 
                              alpha=0.8, linewidths=2, edgecolors='black')
        
        # Draw labels
        nx.draw_networkx_labels(G, pos, labels={node: G.nodes[node]['name'] for node in G.nodes()}, 
                               font_size=10, font_weight='bold')
        
        # Add treaty type legend
        legend_elements = []
        
        if treaty_type:
            # Only show the selected treaty type
            legend_elements.append(
                mpatches.Patch(color=self.treaty_colors.get(treaty_type, '#CCCCCC'), 
                              label=treaty_type.value.replace('_', ' ').title())
            )
        else:
            # Show all treaty types that are present in the graph
            treaty_types_present = set()
            for _, _, data in G.edges(data=True):
                if 'treaty_type' in data:
                    treaty_types_present.add(data['treaty_type'])
            
            for tt in treaty_types_present:
                legend_elements.append(
                    mpatches.Patch(color=self.treaty_colors.get(tt, '#CCCCCC'), 
                                  label=tt.value.replace('_', ' ').title())
                )
        
        if legend_elements:
            ax.legend(handles=legend_elements, loc='upper right', title="Treaty Types")
        
        # Set title
        if treaty_type:
            ax.set_title(f"{treaty_type.value.replace('_', ' ').title()} Treaties Network")
        else:
            ax.set_title("Treaty Network")
        
        # Remove axis
        ax.axis('off')
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def render_reputation_chart(self, dynasty_ids: List[int], width: int = 10, height: int = 6) -> str:
        """
        Render a bar chart comparing reputation metrics for selected dynasties.
        
        Args:
            dynasty_ids: List of dynasty IDs to include
            width: Width of the figure in inches
            height: Height of the figure in inches
            
        Returns:
            Base64 encoded PNG image
        """
        # Get dynasties
        dynasties = []
        for dynasty_id in dynasty_ids:
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if dynasty:
                dynasties.append(dynasty)
        
        if not dynasties:
            return ""
            
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Prepare data
        dynasty_names = [dynasty.name for dynasty in dynasties]
        prestige_values = [dynasty.prestige for dynasty in dynasties]
        honor_values = [dynasty.honor for dynasty in dynasties]
        infamy_values = [dynasty.infamy for dynasty in dynasties]
        
        # Set up bar positions
        x = np.arange(len(dynasties))
        width = 0.25
        
        # Create bars
        ax.bar(x - width, prestige_values, width, label='Prestige', color='gold')
        ax.bar(x, honor_values, width, label='Honor', color='blue')
        ax.bar(x + width, infamy_values, width, label='Infamy', color='red')
        
        # Add labels and title
        ax.set_xlabel('Dynasty')
        ax.set_ylabel('Value')
        ax.set_title('Dynasty Reputation Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(dynasty_names)
        ax.legend()
        
        # Add grid
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str
    
    def render_diplomatic_history(self, dynasty_id: int, width: int = 10, height: int = 6) -> str:
        """
        Render a timeline of significant diplomatic events for a dynasty.
        
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
            
        # Get diplomatic history events
        from models.db_models import HistoryLogEntryDB
        
        diplomatic_events = self.session.query(HistoryLogEntryDB).filter(
            HistoryLogEntryDB.dynasty_id == dynasty_id,
            HistoryLogEntryDB.event_type.like('diplomatic_%') | 
            HistoryLogEntryDB.event_type.like('%_treaty') |
            HistoryLogEntryDB.event_type.like('war_%')
        ).order_by(HistoryLogEntryDB.year).all()
        
        if not diplomatic_events:
            return ""
            
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Prepare data
        years = [event.year for event in diplomatic_events]
        events = [event.event_string for event in diplomatic_events]
        event_types = [event.event_type for event in diplomatic_events]
        
        # Define colors for different event types
        event_colors = {
            'diplomatic_send_envoy': 'blue',
            'diplomatic_arrange_marriage': 'purple',
            'diplomatic_declare_rivalry': 'red',
            'diplomatic_gift': 'green',
            'diplomatic_insult': 'orange',
            'treaty_signed': 'blue',
            'treaty_broken': 'red',
            'war_declared': 'red',
            'peace_treaty': 'green'
        }
        
        # Default color for other event types
        default_color = 'gray'
        
        # Create scatter plot with events
        for i, (year, event, event_type) in enumerate(zip(years, events, event_types)):
            color = next((event_colors[key] for key in event_colors if key in event_type), default_color)
            ax.scatter(year, i, c=color, s=100, edgecolors='black', zorder=2)
            ax.text(year + 0.5, i, event, fontsize=8, va='center')
        
        # Add horizontal lines connecting events
        ax.hlines(range(len(years)), min(years) - 1, max(years) + 1, colors='gray', linestyles='dashed', alpha=0.3, zorder=1)
        
        # Set labels and title
        ax.set_xlabel('Year')
        ax.set_title(f'Diplomatic History Timeline for {dynasty.name}')
        
        # Remove y-axis ticks and labels
        ax.set_yticks([])
        
        # Set x-axis limits with some padding
        ax.set_xlim(min(years) - 5, max(years) + 15)
        
        # Add grid
        ax.grid(True, axis='x', linestyle='--', alpha=0.7)
        
        # Create legend for event types
        legend_elements = []
        for event_type, color in event_colors.items():
            # Clean up the event type name for display
            display_name = event_type.replace('diplomatic_', '').replace('_', ' ').title()
            legend_elements.append(
                plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color, 
                          markersize=10, label=display_name)
            )
        
        ax.legend(handles=legend_elements, loc='upper right', title="Event Types")
        
        # Save figure to memory
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_str

def save_diplomacy_visualization_to_static(diplomacy_renderer: DiplomacyRenderer, filename: str, **kwargs) -> str:
    """
    Save a diplomacy visualization to the static directory.
    
    Args:
        diplomacy_renderer: DiplomacyRenderer instance
        filename: Name of the file to save
        **kwargs: Arguments to pass to the renderer method
        
    Returns:
        URL path to the saved image
    """
    # Determine which renderer method to use based on filename
    if 'relations' in filename:
        img_str = diplomacy_renderer.render_diplomatic_relations(**kwargs)
    elif 'treaty' in filename:
        img_str = diplomacy_renderer.render_treaty_network(**kwargs)
    elif 'reputation' in filename:
        img_str = diplomacy_renderer.render_reputation_chart(**kwargs)
    elif 'history' in filename:
        img_str = diplomacy_renderer.render_diplomatic_history(**kwargs)
    else:
        # Default to relations
        img_str = diplomacy_renderer.render_diplomatic_relations(**kwargs)
    
    if not img_str:
        return ""
    
    # Ensure directory exists
    os.makedirs('static/visualizations', exist_ok=True)
    
    # Save image
    img_data = base64.b64decode(img_str)
    file_path = os.path.join('static', 'visualizations', filename)
    
    with open(file_path, 'wb') as f:
        f.write(img_data)
    
    # Return URL path
    return f'/static/visualizations/{filename}'