# models/map_system.py
"""
Map system for the multi-agent strategic game.
Handles map generation, territory management, resource distribution,
movement mechanics, and pathfinding algorithms.
"""

import random
import math
import heapq
import numpy as np
from typing import List, Dict, Tuple, Set, Optional, Union, Any
from sqlalchemy.orm import Session
from models.db_models import (
    db, Region, Province, Territory, TerrainType, Settlement,
    Resource, ResourceType, TerritoryResource, Building, BuildingType,
    MilitaryUnit, Army, UnitType, War
)

class MapGenerator:
    """
    Handles the generation of game maps, either procedurally or from predefined templates.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the map generator.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        
    def generate_procedural_map(self, 
                               regions_count: int = 5, 
                               provinces_per_region: int = 4,
                               territories_per_province: int = 5,
                               map_width: int = 1000,
                               map_height: int = 1000) -> Dict[str, Any]:
        """
        Generate a procedural map with regions, provinces, and territories.
        
        Args:
            regions_count: Number of regions to generate
            provinces_per_region: Average number of provinces per region
            territories_per_province: Average number of territories per province
            map_width: Width of the map in coordinate units
            map_height: Height of the map in coordinate units
            
        Returns:
            Dictionary with information about the generated map
        """
        # Create regions
        regions = []
        region_centers = []
        
        # Generate region centers with good distribution
        for i in range(regions_count):
            if i == 0:
                # First region center is random
                x = random.uniform(map_width * 0.1, map_width * 0.9)
                y = random.uniform(map_height * 0.1, map_height * 0.9)
            else:
                # Other region centers try to maximize distance from existing centers
                best_pos = None
                best_min_dist = -1
                
                # Try multiple positions and pick the one with maximum minimum distance
                for _ in range(20):
                    test_x = random.uniform(map_width * 0.1, map_width * 0.9)
                    test_y = random.uniform(map_height * 0.1, map_height * 0.9)
                    
                    min_dist = float('inf')
                    for rx, ry in region_centers:
                        dist = math.sqrt((test_x - rx)**2 + (test_y - ry)**2)
                        min_dist = min(min_dist, dist)
                    
                    if min_dist > best_min_dist:
                        best_min_dist = min_dist
                        best_pos = (test_x, test_y)
                
                x, y = best_pos
            
            region_centers.append((x, y))
            
            # Create region
            climate_types = ["temperate", "tropical", "arid", "cold", "mediterranean"]
            region = Region(
                name=f"Region {i+1}",
                description=f"A {random.choice(climate_types)} region with varied terrain.",
                base_climate=random.choice(climate_types)
            )
            self.session.add(region)
            self.session.flush()  # Get ID
            regions.append(region)
        
        # Create provinces within regions
        provinces = []
        province_centers = []
        
        for region_idx, region in enumerate(regions):
            # Determine number of provinces for this region (with some variation)
            num_provinces = max(2, round(provinces_per_region * random.uniform(0.7, 1.3)))
            
            # Generate province centers around the region center
            region_x, region_y = region_centers[region_idx]
            region_radius = min(map_width, map_height) / (regions_count * 0.8)
            
            for i in range(num_provinces):
                # Generate province center with some randomness but within region
                angle = 2 * math.pi * i / num_provinces + random.uniform(-0.2, 0.2)
                distance = region_radius * random.uniform(0.3, 0.7)
                
                province_x = region_x + distance * math.cos(angle)
                province_y = region_y + distance * math.sin(angle)
                
                # Ensure within map bounds
                province_x = max(0, min(map_width, province_x))
                province_y = max(0, min(map_height, province_y))
                
                province_centers.append((province_x, province_y))
                
                # Determine terrain type based on region climate and position
                terrain_weights = self._get_terrain_weights_for_climate(region.base_climate)
                terrain_type = random.choices(
                    list(TerrainType), 
                    weights=[terrain_weights.get(t.value, 1) for t in TerrainType],
                    k=1
                )[0]
                
                # Create province
                province = Province(
                    region_id=region.id,
                    name=f"{region.name} Province {i+1}",
                    description=f"A province with {terrain_type.value} terrain.",
                    primary_terrain=terrain_type
                )
                self.session.add(province)
                self.session.flush()  # Get ID
                provinces.append(province)
        
        # Create territories within provinces
        territories = []
        
        for province_idx, province in enumerate(provinces):
            # Determine number of territories for this province (with some variation)
            num_territories = max(2, round(territories_per_province * random.uniform(0.7, 1.3)))
            
            # Generate territory positions around the province center
            province_x, province_y = province_centers[province_idx]
            province_radius = min(map_width, map_height) / (len(provinces) * 0.8)
            
            for i in range(num_territories):
                # Generate territory position with some randomness but within province
                angle = 2 * math.pi * i / num_territories + random.uniform(-0.3, 0.3)
                distance = province_radius * random.uniform(0.2, 0.6)
                
                territory_x = province_x + distance * math.cos(angle)
                territory_y = province_y + distance * math.sin(angle)
                
                # Ensure within map bounds
                territory_x = max(0, min(map_width, territory_x))
                territory_y = max(0, min(map_height, territory_y))
                
                # Determine terrain type - usually similar to province but with variation
                if random.random() < 0.7:
                    # 70% chance to inherit province terrain
                    terrain_type = province.primary_terrain
                else:
                    # 30% chance for different terrain
                    terrain_weights = self._get_terrain_weights_for_climate(
                        self.session.query(Region).get(province.region_id).base_climate
                    )
                    terrain_type = random.choices(
                        list(TerrainType), 
                        weights=[terrain_weights.get(t.value, 1) for t in TerrainType],
                        k=1
                    )[0]
                
                # Create territory
                territory = Territory(
                    province_id=province.id,
                    name=f"{province.name} Territory {i+1}",
                    description=f"A territory with {terrain_type.value} terrain.",
                    terrain_type=terrain_type,
                    x_coordinate=territory_x,
                    y_coordinate=territory_y,
                    base_tax=random.randint(1, 5),
                    base_manpower=random.randint(80, 150) * 10,
                    development_level=random.randint(1, 3),
                    population=random.randint(800, 1500)
                )
                self.session.add(territory)
                self.session.flush()  # Get ID
                territories.append(territory)
                
                # Add settlement to territory
                settlement_type = random.choice(["village", "town", "city", "castle"])
                settlement_population = {
                    "village": random.randint(100, 500),
                    "town": random.randint(500, 2000),
                    "city": random.randint(2000, 10000),
                    "castle": random.randint(200, 800)
                }
                
                settlement = Settlement(
                    territory_id=territory.id,
                    name=f"{territory.name} {settlement_type.capitalize()}",
                    settlement_type=settlement_type,
                    population=settlement_population[settlement_type],
                    importance=random.randint(1, 5) if settlement_type in ["city", "castle"] else random.randint(1, 3),
                    trade_value=random.randint(5, 20) if settlement_type in ["city", "town"] else random.randint(1, 5)
                )
                self.session.add(settlement)
        
        # Distribute resources across territories
        self._distribute_resources(territories)
        
        # Commit all changes
        self.session.commit()
        
        return {
            "regions": regions,
            "provinces": provinces,
            "territories": territories,
            "width": map_width,
            "height": map_height
        }
    
    def generate_predefined_map(self, template_name: str) -> Dict[str, Any]:
        """
        Generate a map from a predefined template.
        
        Args:
            template_name: Name of the template to use
            
        Returns:
            Dictionary with information about the generated map
        """
        import logging
        
        # Define available templates with their parameters
        templates = {
            "small_continent": {
                "regions_count": 3,
                "provinces_per_region": 3,
                "territories_per_province": 4,
                "map_width": 800,
                "map_height": 800
            },
            "large_continent": {
                "regions_count": 7,
                "provinces_per_region": 5,
                "territories_per_province": 6,
                "map_width": 1500,
                "map_height": 1500
            },
            "archipelago": {
                "regions_count": 10,
                "provinces_per_region": 2,
                "territories_per_province": 3,
                "map_width": 1200,
                "map_height": 1200
            },
            "default": {
                "regions_count": 4,
                "provinces_per_region": 3,
                "territories_per_province": 4,
                "map_width": 1000,
                "map_height": 1000
            }
        }
        
        # Validate template name
        if template_name not in templates:
            logging.warning(f"Unknown map template '{template_name}'. Using default template.")
            template_name = "default"
        
        try:
            # Get template parameters
            template_params = templates[template_name]
            
            # Generate map using template parameters
            map_data = self.generate_procedural_map(
                regions_count=template_params["regions_count"],
                provinces_per_region=template_params["provinces_per_region"],
                territories_per_province=template_params["territories_per_province"],
                map_width=template_params["map_width"],
                map_height=template_params["map_height"]
            )
            
            # Validate generated map
            if not map_data or not map_data.get("territories"):
                logging.error(f"Map generation failed for template '{template_name}'. Using fallback.")
                return self._generate_fallback_map()
                
            return map_data
            
        except Exception as e:
            logging.error(f"Error generating map with template '{template_name}': {str(e)}")
            return self._generate_fallback_map()
    
    def _generate_fallback_map(self) -> Dict[str, Any]:
        """
        Generate a minimal fallback map when normal generation fails.
        
        Returns:
            Dictionary with information about the generated fallback map
        """
        import logging
        logging.warning("Using fallback map generation")
        
        try:
            # Create a minimal map with just enough regions, provinces, and territories
            # to allow the game to function
            
            # Create a single region
            region = Region(
                name="Emergency Region",
                description="An emergency region created as fallback",
                base_climate="temperate"
            )
            self.session.add(region)
            self.session.flush()  # Get ID
            
            # Create provinces in the region
            provinces = []
            for i in range(3):  # Create 3 provinces
                province = Province(
                    region_id=region.id,
                    name=f"Emergency Province {i+1}",
                    description=f"An emergency province created as fallback",
                    primary_terrain=random.choice(list(TerrainType))
                )
                self.session.add(province)
                self.session.flush()  # Get ID
                provinces.append(province)
            
            # Create territories in each province
            territories = []
            for i, province in enumerate(provinces):
                for j in range(4):  # Create 4 territories per province
                    territory = Territory(
                        province_id=province.id,
                        name=f"Emergency Territory {i*4+j+1}",
                        description=f"An emergency territory created as fallback",
                        terrain_type=province.primary_terrain,
                        x_coordinate=100 + i*200 + random.uniform(-50, 50),
                        y_coordinate=100 + j*200 + random.uniform(-50, 50),
                        base_tax=random.randint(1, 3),
                        base_manpower=random.randint(80, 120) * 10,
                        development_level=random.randint(1, 2),
                        population=random.randint(800, 1200)
                    )
                    self.session.add(territory)
                    self.session.flush()  # Get ID
                    territories.append(territory)
                    
                    # Add settlement to territory
                    settlement_type = random.choice(["village", "town"])
                    settlement = Settlement(
                        territory_id=territory.id,
                        name=f"{territory.name} {settlement_type.capitalize()}",
                        settlement_type=settlement_type,
                        population=random.randint(300, 800),
                        importance=random.randint(1, 3),
                        trade_value=random.randint(1, 5)
                    )
                    self.session.add(settlement)
            
            # Distribute resources
            self._distribute_resources(territories)
            
            # Commit changes
            self.session.commit()
            
            return {
                "regions": [region],
                "provinces": provinces,
                "territories": territories,
                "width": 1000,
                "height": 1000
            }
            
        except Exception as e:
            logging.critical(f"Fallback map generation failed: {str(e)}")
            # Create an absolute minimum map as last resort
            try:
                # Create one region
                emergency_region = Region(
                    name="Critical Emergency Region",
                    description="A critical emergency region",
                    base_climate="temperate"
                )
                self.session.add(emergency_region)
                self.session.flush()
                
                # Create one province
                emergency_province = Province(
                    region_id=emergency_region.id,
                    name="Critical Emergency Province",
                    description="A critical emergency province",
                    primary_terrain=TerrainType.PLAINS
                )
                self.session.add(emergency_province)
                self.session.flush()
                
                # Create minimum territories (one per expected dynasty)
                emergency_territories = []
                for i in range(10):  # Create enough for worst case
                    emergency_territory = Territory(
                        province_id=emergency_province.id,
                        name=f"Critical Territory {i+1}",
                        description="A critical emergency territory",
                        terrain_type=TerrainType.PLAINS,
                        x_coordinate=100 + i*100,
                        y_coordinate=500,
                        base_tax=1,
                        base_manpower=100,
                        development_level=1,
                        population=1000
                    )
                    self.session.add(emergency_territory)
                    self.session.flush()
                    emergency_territories.append(emergency_territory)
                    
                    # Add basic settlement
                    emergency_settlement = Settlement(
                        territory_id=emergency_territory.id,
                        name=f"Emergency Settlement {i+1}",
                        settlement_type="village",
                        population=500,
                        importance=1,
                        trade_value=1
                    )
                    self.session.add(emergency_settlement)
                
                self.session.commit()
                
                return {
                    "regions": [emergency_region],
                    "provinces": [emergency_province],
                    "territories": emergency_territories,
                    "width": 1000,
                    "height": 500
                }
                
            except Exception as critical_error:
                logging.critical(f"Critical emergency map generation failed: {str(critical_error)}")
                # Return empty map structure as absolute last resort
                return {
                    "regions": [],
                    "provinces": [],
                    "territories": [],
                    "width": 100,
                    "height": 100
                }
    
    def _get_terrain_weights_for_climate(self, climate: str) -> Dict[str, float]:
        """
        Get terrain type weights based on climate.
        
        Args:
            climate: Climate type
            
        Returns:
            Dictionary mapping terrain types to weight values
        """
        # Default weights
        weights = {
            "plains": 1.0,
            "hills": 1.0,
            "mountains": 1.0,
            "forest": 1.0,
            "desert": 1.0,
            "tundra": 1.0,
            "coastal": 1.0,
            "river": 1.0,
            "lake": 1.0,
            "swamp": 1.0
        }
        
        # Adjust weights based on climate
        if climate == "temperate":
            weights.update({
                "plains": 2.0,
                "hills": 1.5,
                "forest": 1.8,
                "river": 1.5,
                "desert": 0.2,
                "tundra": 0.2
            })
        elif climate == "tropical":
            weights.update({
                "forest": 2.5,
                "swamp": 1.8,
                "river": 1.8,
                "coastal": 1.5,
                "desert": 0.5,
                "tundra": 0.0
            })
        elif climate == "arid":
            weights.update({
                "desert": 2.5,
                "plains": 1.5,
                "hills": 1.2,
                "mountains": 1.0,
                "forest": 0.3,
                "swamp": 0.1,
                "tundra": 0.0
            })
        elif climate == "cold":
            weights.update({
                "tundra": 2.5,
                "mountains": 1.8,
                "forest": 1.5,
                "lake": 1.2,
                "desert": 0.0
            })
        elif climate == "mediterranean":
            weights.update({
                "plains": 2.0,
                "hills": 1.8,
                "coastal": 2.0,
                "forest": 1.2,
                "tundra": 0.0,
                "swamp": 0.3
            })
            
        return weights
        
    def _distribute_resources(self, territories: List[Territory]) -> None:
        """
        Distribute resources across territories based on terrain types.
        
        Args:
            territories: List of territories to distribute resources to
        """
        # Get all resources from the database
        resources = self.session.query(Resource).all()
        
        # If no resources exist, create them
        if not resources:
            resources = self._create_default_resources()
            
        # Get existing territory-resource mappings to avoid duplicates
        existing_territory_resources = {}
        for tr in self.session.query(TerritoryResource).all():
            if tr.territory_id not in existing_territory_resources:
                existing_territory_resources[tr.territory_id] = set()
            existing_territory_resources[tr.territory_id].add(tr.resource_id)
        
        # Resource distribution by terrain type
        terrain_resource_affinities = {
            TerrainType.PLAINS: {
                ResourceType.FOOD: 2.0,
                ResourceType.GOLD: 0.3,
                ResourceType.TIMBER: 0.5
            },
            TerrainType.HILLS: {
                ResourceType.STONE: 1.5,
                ResourceType.IRON: 1.2,
                ResourceType.FOOD: 0.7
            },
            TerrainType.MOUNTAINS: {
                ResourceType.STONE: 2.0,
                ResourceType.IRON: 1.5,
                ResourceType.GOLD: 1.0
            },
            TerrainType.FOREST: {
                ResourceType.TIMBER: 2.5,
                ResourceType.FOOD: 0.8,
                ResourceType.SPICES: 0.5
            },
            TerrainType.DESERT: {
                ResourceType.GOLD: 0.7,
                ResourceType.SPICES: 0.5,
                ResourceType.FOOD: 0.2
            },
            TerrainType.TUNDRA: {
                ResourceType.TIMBER: 1.0,
                ResourceType.FOOD: 0.3,
                ResourceType.IRON: 0.5
            },
            TerrainType.COASTAL: {
                ResourceType.FOOD: 1.5,
                ResourceType.GOLD: 1.0,
                ResourceType.SILK: 0.7
            },
            TerrainType.RIVER: {
                ResourceType.FOOD: 1.8,
                ResourceType.GOLD: 0.8,
                ResourceType.TIMBER: 0.7
            },
            TerrainType.LAKE: {
                ResourceType.FOOD: 1.5,
                ResourceType.STONE: 0.5
            },
            TerrainType.SWAMP: {
                ResourceType.TIMBER: 0.8,
                ResourceType.SPICES: 0.6
            }
        }
        
        # Resource objects by type for quick lookup
        resource_by_type = {r.resource_type: r for r in resources}
        
        # Distribute resources to territories
        for territory in territories:
            # Get resource affinities for this terrain
            affinities = terrain_resource_affinities.get(territory.terrain_type, {})
            
            # Always add at least one basic resource
            basic_resources = [
                ResourceType.FOOD,
                ResourceType.TIMBER,
                ResourceType.STONE,
                ResourceType.IRON
            ]
            
            # Filter to resources that have some affinity for this terrain
            valid_basic = [r for r in basic_resources if r in affinities]
            
            # If no valid basics (unlikely), use any basic
            if not valid_basic:
                valid_basic = basic_resources
            
            # Add 1-2 basic resources
            num_basic = random.randint(1, 2)
            for _ in range(num_basic):
                resource_type = random.choice(valid_basic)
                resource = resource_by_type[resource_type]
                
                # Base production based on affinity
                base_production = random.uniform(0.5, 1.5) * affinities.get(resource_type, 0.5)
                
                # Check if this territory already has this resource
                territory_resources = existing_territory_resources.get(territory.id, set())
                if resource.id not in territory_resources:
                    territory_resource = TerritoryResource(
                        territory_id=territory.id,
                        resource_id=resource.id,
                        base_production=base_production,
                        quality=random.uniform(0.8, 1.2),
                        depletion_rate=random.uniform(0.01, 0.05) if resource_type != ResourceType.FOOD else 0.0
                    )
                    self.session.add(territory_resource)
                    
                    # Update our tracking of existing resources
                    if territory.id not in existing_territory_resources:
                        existing_territory_resources[territory.id] = set()
                    existing_territory_resources[territory.id].add(resource.id)
            
            # Small chance for luxury resource
            if random.random() < 0.15:  # 15% chance
                luxury_resources = [
                    ResourceType.SPICES,
                    ResourceType.WINE,
                    ResourceType.SILK,
                    ResourceType.JEWELRY
                ]
                
                # Filter to resources that have some affinity for this terrain
                valid_luxury = [r for r in luxury_resources if r in affinities]
                
                # If any valid luxury resources for this terrain
                if valid_luxury:
                    resource_type = random.choice(valid_luxury)
                    resource = resource_by_type.get(resource_type)
                    
                    if resource:
                        # Lower base production for luxury resources
                        base_production = random.uniform(0.2, 0.6) * affinities.get(resource_type, 0.3)
                        
                        # Check if this territory already has this resource
                        territory_resources = existing_territory_resources.get(territory.id, set())
                        if resource.id not in territory_resources:
                            territory_resource = TerritoryResource(
                                territory_id=territory.id,
                                resource_id=resource.id,
                                base_production=base_production,
                                quality=random.uniform(0.9, 1.5),  # Higher quality for luxury
                                depletion_rate=random.uniform(0.02, 0.08)  # Luxury resources deplete faster
                            )
                            self.session.add(territory_resource)
                            
                            # Update our tracking of existing resources
                            if territory.id not in existing_territory_resources:
                                existing_territory_resources[territory.id] = set()
                            existing_territory_resources[territory.id].add(resource.id)
    
    def _create_default_resources(self) -> List[Resource]:
        """
        Create default resources in the database.
        
        Returns:
            List of created resources
        """
        resources = []
        
        # Basic resources
        resources.append(Resource(
            name="Food",
            resource_type=ResourceType.FOOD,
            base_value=10,
            volatility=0.2,
            perishability=0.5,
            is_luxury=False,
            scarcity=0.1
        ))
        
        resources.append(Resource(
            name="Timber",
            resource_type=ResourceType.TIMBER,
            base_value=15,
            volatility=0.1,
            perishability=0.0,
            is_luxury=False,
            scarcity=0.3
        ))
        
        resources.append(Resource(
            name="Stone",
            resource_type=ResourceType.STONE,
            base_value=20,
            volatility=0.05,
            perishability=0.0,
            is_luxury=False,
            scarcity=0.4
        ))
        
        resources.append(Resource(
            name="Iron",
            resource_type=ResourceType.IRON,
            base_value=30,
            volatility=0.15,
            perishability=0.0,
            is_luxury=False,
            scarcity=0.6
        ))
        
        resources.append(Resource(
            name="Gold",
            resource_type=ResourceType.GOLD,
            base_value=50,
            volatility=0.2,
            perishability=0.0,
            is_luxury=False,
            scarcity=0.8
        ))
        
        # Luxury resources
        resources.append(Resource(
            name="Spices",
            resource_type=ResourceType.SPICES,
            base_value=40,
            volatility=0.3,
            perishability=0.2,
            is_luxury=True,
            scarcity=0.7
        ))
        
        resources.append(Resource(
            name="Wine",
            resource_type=ResourceType.WINE,
            base_value=35,
            volatility=0.25,
            perishability=0.3,
            is_luxury=True,
            scarcity=0.6
        ))
        
        resources.append(Resource(
            name="Silk",
            resource_type=ResourceType.SILK,
            base_value=60,
            volatility=0.2,
            perishability=0.1,
            is_luxury=True,
            scarcity=0.8
        ))
        
        resources.append(Resource(
            name="Jewelry",
            resource_type=ResourceType.JEWELRY,
            base_value=80,
            volatility=0.3,
            perishability=0.0,
            is_luxury=True,
            scarcity=0.9
        ))
        
        # Add to session
        for resource in resources:
            self.session.add(resource)
        
        self.session.flush()
        return resources


class TerritoryManager:
    """
    Manages territory ownership, control, and development.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the territory manager.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
    
    def assign_territory(self, territory_id: int, dynasty_id: int, is_capital: bool = False) -> Territory:
        """
        Assign a territory to a dynasty.
        
        Args:
            territory_id: ID of the territory to assign
            dynasty_id: ID of the dynasty to assign the territory to
            is_capital: Whether this territory should be the dynasty's capital
            
        Returns:
            The updated territory
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            raise ValueError(f"Territory with ID {territory_id} not found")
        
        # Update territory control
        territory.controller_dynasty_id = dynasty_id
        territory.is_capital = is_capital
        
        # If this is the capital, update the dynasty's capital territory
        if is_capital:
            from models.db_models import DynastyDB
            dynasty = self.session.query(DynastyDB).get(dynasty_id)
            if dynasty:
                dynasty.capital_territory_id = territory_id
        
        self.session.commit()
        return territory
    
    def develop_territory(self, territory_id: int, development_type: str) -> Territory:
        """
        Develop a territory by increasing its development level or adding buildings.
        
        Args:
            territory_id: ID of the territory to develop
            development_type: Type of development ('level', 'building', 'infrastructure')
            
        Returns:
            The updated territory
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            raise ValueError(f"Territory with ID {territory_id} not found")
        
        if development_type == 'level':
            # Increase development level
            territory.development_level += 1
            territory.base_tax = int(territory.base_tax * 1.2)
            territory.base_manpower = int(territory.base_manpower * 1.15)
            territory.population = int(territory.population * 1.1)
        
        elif development_type == 'building':
            # Add a random building based on terrain
            building_options = self._get_suitable_buildings_for_terrain(territory.terrain_type)
            if building_options:
                building_type = random.choice(building_options)
                
                # Check if building of this type already exists
                existing = self.session.query(Building).filter_by(
                    territory_id=territory_id,
                    building_type=building_type
                ).first()
                
                if existing:
                    # Upgrade existing building
                    existing.level += 1
                    existing.condition = min(1.0, existing.condition + 0.2)
                else:
                    # Create new building
                    building = Building(
                        territory_id=territory_id,
                        building_type=building_type,
                        name=f"{building_type.value.replace('_', ' ').title()}",
                        level=1,
                        condition=1.0,
                        construction_year=2023,  # This should be the current game year
                        maintenance_cost=self._get_building_maintenance_cost(building_type)
                    )
                    self.session.add(building)
        
        elif development_type == 'infrastructure':
            # Add infrastructure (roads, irrigation, etc.)
            infra_options = [
                BuildingType.ROADS,
                BuildingType.IRRIGATION,
                BuildingType.GUILD_HALL,
                BuildingType.BANK
            ]
            
            building_type = random.choice(infra_options)
            
            # Check if infrastructure of this type already exists
            existing = self.session.query(Building).filter_by(
                territory_id=territory_id,
                building_type=building_type
            ).first()
            
            if existing:
                # Upgrade existing infrastructure
                existing.level += 1
                existing.condition = min(1.0, existing.condition + 0.2)
            else:
                # Create new infrastructure
                building = Building(
                    territory_id=territory_id,
                    building_type=building_type,
                    name=f"{building_type.value.replace('_', ' ').title()}",
                    level=1,
                    condition=1.0,
                    construction_year=2023,  # This should be the current game year
                    maintenance_cost=self._get_building_maintenance_cost(building_type)
                )
                self.session.add(building)
        
        self.session.commit()
        return territory
    
    def _get_suitable_buildings_for_terrain(self, terrain_type: TerrainType) -> List[BuildingType]:
        """
        Get suitable building types for a given terrain.
        
        Args:
            terrain_type: Terrain type
            
        Returns:
            List of suitable building types
        """
        # Base buildings suitable for all terrains
        suitable = [
            BuildingType.MARKET,
            BuildingType.WAREHOUSE
        ]
        
        # Add terrain-specific buildings
        if terrain_type == TerrainType.PLAINS:
            suitable.extend([
                BuildingType.FARM,
                BuildingType.BARRACKS,
                BuildingType.TRAINING_GROUND
            ])
        elif terrain_type == TerrainType.HILLS:
            suitable.extend([
                BuildingType.MINE,
                BuildingType.FORTRESS
            ])
        elif terrain_type == TerrainType.MOUNTAINS:
            suitable.extend([
                BuildingType.MINE,
                BuildingType.FORTRESS
            ])
        elif terrain_type == TerrainType.FOREST:
            suitable.extend([
                BuildingType.LUMBER_CAMP,
                BuildingType.WORKSHOP
            ])
        elif terrain_type == TerrainType.DESERT:
            suitable.extend([
                BuildingType.TRADE_POST
            ])
        elif terrain_type == TerrainType.COASTAL:
            suitable.extend([
                BuildingType.PORT,
                BuildingType.TRADE_POST,
                BuildingType.FARM
            ])
        elif terrain_type == TerrainType.RIVER:
            suitable.extend([
                BuildingType.FARM,
                BuildingType.WORKSHOP,
                BuildingType.PORT
            ])
        
        return suitable
    
    def _get_building_maintenance_cost(self, building_type: BuildingType) -> int:
        """
        Get the maintenance cost for a building type.
        
        Args:
            building_type: Building type
            
        Returns:
            Maintenance cost
        """
        # Base costs
        costs = {
            BuildingType.FARM: 1,
            BuildingType.MINE: 2,
            BuildingType.LUMBER_CAMP: 1,
            BuildingType.WORKSHOP: 2,
            BuildingType.MARKET: 2,
            BuildingType.PORT: 3,
            BuildingType.WAREHOUSE: 1,
            BuildingType.TRADE_POST: 2,
            BuildingType.BARRACKS: 3,
            BuildingType.STABLE: 3,
            BuildingType.TRAINING_GROUND: 4,
            BuildingType.FORTRESS: 5,
            BuildingType.ROADS: 2,
            BuildingType.IRRIGATION: 2,
            BuildingType.GUILD_HALL: 3,
            BuildingType.BANK: 3
        }
        
        return costs.get(building_type, 2)
        
        return weights
class MovementSystem:
    """
    Handles movement and travel mechanics for units and armies.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the movement system.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        
        # Movement costs by terrain type (base cost in movement points)
        self.terrain_movement_costs = {
            TerrainType.PLAINS: 1.0,
            TerrainType.HILLS: 1.5,
            TerrainType.MOUNTAINS: 3.0,
            TerrainType.FOREST: 1.8,
            TerrainType.DESERT: 2.0,
            TerrainType.TUNDRA: 2.2,
            TerrainType.COASTAL: 1.2,
            TerrainType.RIVER: 1.5,
            TerrainType.LAKE: 5.0,  # Hard to cross without ships
            TerrainType.SWAMP: 2.5
        }
        
        # Movement modifiers by unit type
        self.unit_movement_modifiers = {
            'infantry': {
                TerrainType.MOUNTAINS: 1.5,  # Infantry is better at mountains than cavalry
                TerrainType.FOREST: 1.2,     # Infantry is better at forests than cavalry
                TerrainType.SWAMP: 1.3       # Infantry is better at swamps than cavalry
            },
            'cavalry': {
                TerrainType.PLAINS: 0.7,     # Cavalry is faster on plains
                TerrainType.HILLS: 0.9,      # Cavalry is faster on hills
                TerrainType.DESERT: 1.2,     # Cavalry is slower in desert
                TerrainType.FOREST: 1.5,     # Cavalry is slower in forest
                TerrainType.SWAMP: 2.0       # Cavalry is much slower in swamp
            },
            'siege': {
                TerrainType.PLAINS: 1.5,     # Siege units are slower everywhere
                TerrainType.HILLS: 2.0,
                TerrainType.MOUNTAINS: 3.0,
                TerrainType.FOREST: 2.5,
                TerrainType.DESERT: 2.0,
                TerrainType.TUNDRA: 2.5,
                TerrainType.COASTAL: 1.8,
                TerrainType.RIVER: 2.5,
                TerrainType.SWAMP: 3.5
            }
        }
    
    def move_unit(self, unit_id: int, target_territory_id: int) -> Tuple[bool, str]:
        """
        Move a military unit to a target territory.
        
        Args:
            unit_id: ID of the unit to move
            target_territory_id: ID of the target territory
            
        Returns:
            Tuple of (success, message)
        """
        unit = self.session.query(MilitaryUnit).get(unit_id)
        if not unit:
            return False, f"Unit with ID {unit_id} not found"
        
        target_territory = self.session.query(Territory).get(target_territory_id)
        if not target_territory:
            return False, f"Territory with ID {target_territory_id} not found"
        
        # Check if unit is already in target territory
        if unit.territory_id == target_territory_id:
            return True, "Unit is already in the target territory"
        
        # Check if unit is part of an army
        if unit.army_id:
            return False, "Unit is part of an army and cannot move independently"
        
        # Get current territory
        current_territory = self.session.query(Territory).get(unit.territory_id) if unit.territory_id else None
        if not current_territory:
            # Unit is not currently on the map, can be placed anywhere
            unit.territory_id = target_territory_id
            self.session.commit()
            return True, f"Unit deployed to {target_territory.name}"
        
        # Check if territories are adjacent
        if not self.are_territories_adjacent(current_territory.id, target_territory.id):
            return False, "Territories are not adjacent"
        
        # Check if target territory is controlled by an enemy
        if (target_territory.controller_dynasty_id and 
            target_territory.controller_dynasty_id != unit.dynasty_id):
            # Moving into enemy territory requires a declaration of war
            # This would be handled by the diplomacy system
            # For now, we'll just allow it but note it
            pass
        
        # Calculate movement cost
        movement_cost = self.calculate_movement_cost(unit, current_territory, target_territory)
        
        # Update unit location
        unit.territory_id = target_territory_id
        self.session.commit()
        
        return True, f"Unit moved to {target_territory.name} (Cost: {movement_cost:.1f} movement points)"
    
    def move_army(self, army_id: int, target_territory_id: int) -> Tuple[bool, str]:
        """
        Move an army to a target territory.
        
        Args:
            army_id: ID of the army to move
            target_territory_id: ID of the target territory
            
        Returns:
            Tuple of (success, message)
        """
        army = self.session.query(Army).get(army_id)
        if not army:
            return False, f"Army with ID {army_id} not found"
        
        target_territory = self.session.query(Territory).get(target_territory_id)
        if not target_territory:
            return False, f"Territory with ID {target_territory_id} not found"
        
        # Check if army is already in target territory
        if army.territory_id == target_territory_id:
            return True, "Army is already in the target territory"
        
        # Get current territory
        current_territory = self.session.query(Territory).get(army.territory_id) if army.territory_id else None
        if not current_territory:
            # Army is not currently on the map, can be placed anywhere
            army.territory_id = target_territory_id
            
            # Move all units in the army
            for unit in army.units:
                unit.territory_id = target_territory_id
            
            self.session.commit()
            return True, f"Army deployed to {target_territory.name}"
        
        # Check if territories are adjacent
        if not self.are_territories_adjacent(current_territory.id, target_territory.id):
            return False, "Territories are not adjacent"
        
        # Check if target territory is controlled by an enemy
        if (target_territory.controller_dynasty_id and 
            target_territory.controller_dynasty_id != army.dynasty_id):
            # Moving into enemy territory requires a declaration of war
            # This would be handled by the diplomacy system
            # For now, we'll just allow it but note it
            pass
        
        # Calculate movement cost (use the slowest unit in the army)
        max_movement_cost = 0
        for unit in army.units:
            cost = self.calculate_movement_cost(unit, current_territory, target_territory)
            max_movement_cost = max(max_movement_cost, cost)
        
        # Update army and all units' location
        army.territory_id = target_territory_id
        for unit in army.units:
            unit.territory_id = target_territory_id
        
        self.session.commit()
        
        return True, f"Army moved to {target_territory.name} (Cost: {max_movement_cost:.1f} movement points)"
    
    def calculate_movement_cost(self, unit: MilitaryUnit, from_territory: Territory, to_territory: Territory) -> float:
        """
        Calculate the movement cost for a unit moving between territories.
        
        Args:
            unit: The military unit
            from_territory: The origin territory
            to_territory: The destination territory
            
        Returns:
            Movement cost in movement points
        """
        # Base cost from terrain
        base_cost = self.terrain_movement_costs.get(to_territory.terrain_type, 1.0)
        
        # Determine unit type category
        unit_category = 'infantry'  # Default
        if unit.unit_type in [UnitType.LIGHT_CAVALRY, UnitType.HEAVY_CAVALRY, UnitType.HORSE_ARCHERS, UnitType.KNIGHTS]:
            unit_category = 'cavalry'
        elif unit.unit_type in [UnitType.BATTERING_RAM, UnitType.SIEGE_TOWER, UnitType.CATAPULT, UnitType.TREBUCHET]:
            unit_category = 'siege'
        
        # Apply unit type modifier
        type_modifier = self.unit_movement_modifiers.get(unit_category, {}).get(to_territory.terrain_type, 1.0)
        
        # Check for roads (reduces movement cost)
        has_roads = False
        for building in to_territory.buildings:
            if building.building_type == BuildingType.ROADS:
                has_roads = True
                break
        
        road_modifier = 0.7 if has_roads else 1.0
        
        # Calculate final cost
        movement_cost = base_cost * type_modifier * road_modifier
        
        # Minimum cost is 0.5
        return max(0.5, movement_cost)
    
    def are_territories_adjacent(self, territory1_id: int, territory2_id: int) -> bool:
        """
        Check if two territories are adjacent.
        
        Args:
            territory1_id: ID of the first territory
            territory2_id: ID of the second territory
            
        Returns:
            True if territories are adjacent, False otherwise
        """
        # In a real implementation, this would check a territory adjacency graph
        # For now, we'll use a simple distance-based approach
        territory1 = self.session.query(Territory).get(territory1_id)
        territory2 = self.session.query(Territory).get(territory2_id)
        
        if not territory1 or not territory2:
            return False
        
        # Calculate Euclidean distance
        distance = math.sqrt(
            (territory1.x_coordinate - territory2.x_coordinate) ** 2 +
            (territory1.y_coordinate - territory2.y_coordinate) ** 2
        )
        
        # Territories are adjacent if they are close enough
        # This threshold would depend on the map scale
        return distance < 100  # Arbitrary threshold
    
    def find_path(self, start_territory_id: int, end_territory_id: int, unit_id: int = None) -> List[int]:
        """
        Find the shortest path between two territories for a given unit.
        Uses A* pathfinding algorithm.
        
        Args:
            start_territory_id: ID of the starting territory
            end_territory_id: ID of the destination territory
            unit_id: Optional ID of the unit to calculate movement costs for
            
        Returns:
            List of territory IDs representing the path
        """
        # Get territories
        start_territory = self.session.query(Territory).get(start_territory_id)
        end_territory = self.session.query(Territory).get(end_territory_id)
        
        if not start_territory or not end_territory:
            return []
        
        # Get unit if provided
        unit = None
        if unit_id:
            unit = self.session.query(MilitaryUnit).get(unit_id)
        
        # A* algorithm
        open_set = []
        closed_set = set()
        
        # Dictionary to store g scores (cost from start to current)
        g_score = {start_territory_id: 0}
        
        # Dictionary to store f scores (g score + heuristic)
        f_score = {start_territory_id: self._heuristic(start_territory, end_territory)}
        
        # Dictionary to store parent nodes for path reconstruction
        came_from = {}
        
        # Add start node to open set
        heapq.heappush(open_set, (f_score[start_territory_id], start_territory_id))
        
        while open_set:
            # Get territory with lowest f score
            _, current_id = heapq.heappop(open_set)
            
            # If we reached the destination
            if current_id == end_territory_id:
                # Reconstruct path
                path = [current_id]
                while current_id in came_from:
                    current_id = came_from[current_id]
                    path.append(current_id)
                path.reverse()
                return path
            
            # Mark current territory as processed
            closed_set.add(current_id)
            
            # Get current territory
            current_territory = self.session.query(Territory).get(current_id)
            
            # Get all territories
            all_territories = self.session.query(Territory).all()
            
            # Process neighbors
            for neighbor in all_territories:
                # Skip if already processed
                if neighbor.id in closed_set:
                    continue
                
                # Check if territories are adjacent
                if not self.are_territories_adjacent(current_id, neighbor.id):
                    continue
                
                # Calculate movement cost
                if unit:
                    movement_cost = self.calculate_movement_cost(unit, current_territory, neighbor)
                else:
                    # Default cost if no unit specified
                    movement_cost = self.terrain_movement_costs.get(neighbor.terrain_type, 1.0)
                
                # Calculate tentative g score
                tentative_g_score = g_score[current_id] + movement_cost
                
                # If neighbor not in open set or we found a better path
                if neighbor.id not in g_score or tentative_g_score < g_score[neighbor.id]:
                    # Update path
                    came_from[neighbor.id] = current_id
                    g_score[neighbor.id] = tentative_g_score
                    f_score[neighbor.id] = tentative_g_score + self._heuristic(neighbor, end_territory)
                    
                    # Add to open set if not already there
                    if neighbor.id not in [item[1] for item in open_set]:
                        heapq.heappush(open_set, (f_score[neighbor.id], neighbor.id))
        
        # No path found
        return []
    
    def _heuristic(self, territory1: Territory, territory2: Territory) -> float:
        """
        Calculate heuristic distance between two territories.
        Uses Euclidean distance.
        
        Args:
            territory1: First territory
            territory2: Second territory
            
        Returns:
            Heuristic distance value
        """
        return math.sqrt(
            (territory1.x_coordinate - territory2.x_coordinate) ** 2 +
            (territory1.y_coordinate - territory2.y_coordinate) ** 2
        )


class BorderSystem:
    """
    Manages territory borders and contested areas.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the border system.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
    
    def get_border_territories(self, dynasty_id: int) -> List[Territory]:
        """
        Get all territories that are on the border of a dynasty's realm.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            List of border territories
        """
        # Get all territories controlled by the dynasty
        controlled_territories = self.session.query(Territory).filter_by(
            controller_dynasty_id=dynasty_id
        ).all()
        
        # Get IDs of controlled territories for faster lookup
        controlled_ids = {t.id for t in controlled_territories}
        
        # Find border territories
        border_territories = []
        
        for territory in controlled_territories:
            # Get all territories
            all_territories = self.session.query(Territory).all()
            
            # Check if any adjacent territory is not controlled by this dynasty
            for other in all_territories:
                if other.id in controlled_ids:
                    continue
                
                # Calculate distance
                distance = math.sqrt(
                    (territory.x_coordinate - other.x_coordinate) ** 2 +
                    (territory.y_coordinate - other.y_coordinate) ** 2
                )
                
                # If territories are adjacent and other is not controlled by this dynasty
                if distance < 100:  # Same threshold as in MovementSystem.are_territories_adjacent
                    border_territories.append(territory)
                    break
        
        return border_territories
    
    def get_contested_territories(self) -> List[Territory]:
        """
        Get all territories that are contested (multiple dynasties have claims).
        
        Returns:
            List of contested territories
        """
        # In a real implementation, this would check territory claims
        # For now, we'll just return territories with active wars over them
        contested = self.session.query(Territory).join(
            War, Territory.id == War.target_territory_id
        ).filter(
            War.is_active == True
        ).all()
        
        return contested