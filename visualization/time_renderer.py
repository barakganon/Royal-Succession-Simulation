# visualization/time_renderer.py
"""
Visualization component for the time system.
Handles rendering of timelines, scheduled events, historical events,
and seasonal effects on the map.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from sqlalchemy.orm import Session
from models.db_models import (
    DynastyDB, HistoryLogEntryDB, Territory, Region, Province
)
from models.time_system import TimeSystem, Season, EventType

class TimeRenderer:
    """
    Renderer for time-related visualizations including timelines,
    scheduled events, historical events, and seasonal effects.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the time renderer.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.time_system = TimeSystem(session)
        
        # Create static directory if it doesn't exist
        self.static_dir = os.path.join('static', 'visualizations')
        os.makedirs(self.static_dir, exist_ok=True)
        
        # Color schemes for different event types
        self.event_colors = {
            "birth": "#4CAF50",  # Green
            "death": "#607D8B",  # Blue Grey
            "marriage": "#E91E63",  # Pink
            "succession": "#9C27B0",  # Purple
            "war_declared": "#F44336",  # Red
            "peace_treaty": "#8BC34A",  # Light Green
            "battle": "#FF9800",  # Orange
            "siege": "#795548",  # Brown
            "treaty_signed": "#2196F3",  # Blue
            "treaty_expired": "#9E9E9E",  # Grey
            "building_completed": "#00BCD4",  # Cyan
            "natural_disaster": "#FF5722",  # Deep Orange
            "year_end": "#BDBDBD",  # Light Grey
            "default": "#673AB7"  # Deep Purple
        }
        
        # Season colors for map rendering
        self.season_colors = {
            Season.SPRING: "#8BC34A",  # Light Green
            Season.SUMMER: "#FFEB3B",  # Yellow
            Season.AUTUMN: "#FF9800",  # Orange
            Season.WINTER: "#ECEFF1"   # Blue Grey Light
        }
    
    def render_timeline(self, dynasty_id: int, start_year: Optional[int] = None, 
                       end_year: Optional[int] = None, filename: Optional[str] = None) -> str:
        """
        Render a timeline visualization for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            start_year: Start year for the timeline (optional)
            end_year: End year for the timeline (optional)
            filename: Custom filename for the output image (optional)
            
        Returns:
            Path to the generated image file
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return ""
        
        # Set default years if not provided
        if start_year is None:
            start_year = dynasty.start_year
        if end_year is None:
            end_year = dynasty.current_simulation_year
        
        # Get historical events
        timeline_events = self.time_system.get_historical_timeline(dynasty_id, start_year, end_year)
        
        if not timeline_events:
            return ""
        
        # Create figure
        plt.figure(figsize=(12, 8))
        
        # Create timeline
        years = list(range(start_year, end_year + 1))
        y_positions = {}
        current_y = 0
        
        # Group events by year
        events_by_year = {}
        for event in timeline_events:
            year = event["year"]
            if year not in events_by_year:
                events_by_year[year] = []
            events_by_year[year].append(event)
        
        # Plot events
        for year in years:
            if year in events_by_year:
                events = events_by_year[year]
                # Plot a line for the year
                plt.axvline(x=year, color='#E0E0E0', linestyle='-', alpha=0.5)
                
                # Plot events for this year
                for i, event in enumerate(events):
                    event_type = event["event_type"] or "default"
                    color = self.event_colors.get(event_type, self.event_colors["default"])
                    
                    # Calculate y position to avoid overlap
                    y_pos = current_y - i * 0.5
                    y_positions[event["id"]] = y_pos
                    
                    # Plot event marker
                    plt.scatter(year, y_pos, color=color, s=100, zorder=5)
                    
                    # Add event text
                    plt.text(year + 0.1, y_pos, event["event_string"], 
                            fontsize=8, verticalalignment='center')
                
                current_y -= len(events) * 0.5 + 1
        
        # Set axis limits
        plt.xlim(start_year - 0.5, end_year + 0.5)
        plt.ylim(current_y - 1, 1)
        
        # Set labels and title
        plt.xlabel('Year')
        plt.title(f'Timeline for {dynasty.name} ({start_year}-{end_year})')
        
        # Remove y-axis ticks and labels
        plt.yticks([])
        
        # Add grid
        plt.grid(True, axis='x', linestyle='--', alpha=0.7)
        
        # Add legend for event types
        legend_elements = []
        for event_type, color in self.event_colors.items():
            if event_type != "default":
                from matplotlib.lines import Line2D
                legend_elements.append(Line2D([0], [0], marker='o', color='w', 
                                            markerfacecolor=color, markersize=8, 
                                            label=event_type.replace('_', ' ').title()))
        
        plt.legend(handles=legend_elements, loc='upper right', fontsize=8)
        
        # Save figure
        if filename is None:
            filename = f"timeline_{dynasty.name.replace(' ', '_')}_{start_year}_{end_year}.png"
        
        filepath = os.path.join(self.static_dir, filename)
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def render_scheduled_events(self, dynasty_id: int, filename: Optional[str] = None) -> str:
        """
        Render a visualization of scheduled events for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            filename: Custom filename for the output image (optional)
            
        Returns:
            Path to the generated image file
        """
        # Get dynasty
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return ""
        
        # Get scheduled events
        scheduled_events = self.time_system.get_scheduled_timeline(dynasty_id)
        
        if not scheduled_events:
            return ""
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Group events by year
        events_by_year = {}
        years = []
        
        for event in scheduled_events:
            year = event["year"]
            if year not in events_by_year:
                events_by_year[year] = []
                years.append(year)
            events_by_year[year].append(event)
        
        years.sort()
        
        # Plot events
        y_positions = []
        labels = []
        colors = []
        x_positions = []
        
        current_y = 0
        for year in years:
            events = events_by_year[year]
            
            for i, event in enumerate(events):
                event_type = event["type"]
                color = self.event_colors.get(event_type, self.event_colors["default"])
                
                # Calculate y position to avoid overlap
                y_pos = current_y - i * 0.5
                
                # Add to lists for plotting
                y_positions.append(y_pos)
                x_positions.append(year)
                colors.append(color)
                
                # Create label from event data
                if "action" in event["data"]:
                    label = f"{event_type}: {event['data']['action']}"
                else:
                    label = f"{event_type} event"
                
                labels.append(label)
                
            current_y -= len(events) * 0.5 + 1
        
        # Plot events
        plt.scatter(x_positions, y_positions, c=colors, s=100, zorder=5)
        
        # Add event labels
        for i, (x, y, label) in enumerate(zip(x_positions, y_positions, labels)):
            plt.text(x + 0.1, y, label, fontsize=8, verticalalignment='center')
        
        # Set axis limits
        plt.xlim(min(years) - 0.5, max(years) + 0.5)
        plt.ylim(min(y_positions) - 1, 1)
        
        # Set labels and title
        plt.xlabel('Year')
        plt.title(f'Scheduled Events for {dynasty.name}')
        
        # Remove y-axis ticks and labels
        plt.yticks([])
        
        # Add grid
        plt.grid(True, axis='x', linestyle='--', alpha=0.7)
        
        # Save figure
        if filename is None:
            filename = f"scheduled_events_{dynasty.name.replace(' ', '_')}.png"
        
        filepath = os.path.join(self.static_dir, filename)
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def render_seasonal_map(self, year: int, filename: Optional[str] = None) -> str:
        """
        Render a map visualization showing seasonal effects.
        
        Args:
            year: Current game year
            filename: Custom filename for the output image (optional)
            
        Returns:
            Path to the generated image file
        """
        # Get current season
        season = self.time_system.get_current_season(year)
        
        # Get all territories
        territories = self.session.query(Territory).all()
        
        if not territories:
            return ""
        
        # Create figure
        plt.figure(figsize=(12, 10))
        
        # Extract territory coordinates and colors
        x_coords = []
        y_coords = []
        colors = []
        sizes = []
        labels = []
        
        for territory in territories:
            x_coords.append(territory.x_coordinate)
            y_coords.append(territory.y_coordinate)
            
            # Get province and region for this territory
            province = self.session.query(Province).get(territory.province_id)
            if not province:
                continue
                
            region = self.session.query(Region).get(province.region_id)
            if not region:
                continue
            
            # Get weather for this region and season
            weather = self.time_system.get_weather_for_region(region.id, season)
            
            # Base color on season
            base_color = self.season_colors.get(season, "#FFFFFF")
            
            # Adjust color based on weather
            if weather == "clear":
                color = base_color
            elif weather == "rain":
                # Darker, more blue
                color = "#64B5F6"
            elif weather == "storm":
                # Dark blue
                color = "#1976D2"
            elif weather == "fog":
                # Grey
                color = "#BDBDBD"
            elif weather == "snow":
                # White
                color = "#FFFFFF"
            elif weather == "blizzard":
                # Light blue
                color = "#BBDEFB"
            elif weather == "drought":
                # Brown
                color = "#D7CCC8"
            else:
                color = base_color
            
            colors.append(color)
            
            # Size based on territory importance
            size = 100 + (territory.development_level * 20)
            sizes.append(size)
            
            # Label with territory name and weather
            labels.append(f"{territory.name}\n{weather}")
        
        # Plot territories
        scatter = plt.scatter(x_coords, y_coords, c=colors, s=sizes, alpha=0.7, edgecolors='black')
        
        # Add territory labels
        for i, (x, y, label) in enumerate(zip(x_coords, y_coords, labels)):
            plt.annotate(label, (x, y), fontsize=8, ha='center', va='center')
        
        # Set labels and title
        plt.title(f'Seasonal Map - {season.value.title()} of Year {year}')
        
        # Remove axis ticks and labels
        plt.xticks([])
        plt.yticks([])
        
        # Add legend for season
        plt.figtext(0.02, 0.02, f"Season: {season.value.title()}", fontsize=10)
        
        # Save figure
        if filename is None:
            filename = f"seasonal_map_{season.value}_{year}.png"
        
        filepath = os.path.join(self.static_dir, filename)
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
        
        return filepath