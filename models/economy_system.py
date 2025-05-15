# models/economy_system.py
"""
Enhanced economy system for the multi-agent strategic game.
Handles resource production and consumption, trade and market mechanics,
building construction and management, territory development, population
and workforce management, taxation and treasury management, and economic
policies and decisions.
"""

import random
import math
import datetime
import json
from typing import List, Dict, Tuple, Optional, Union, Any, Set
from sqlalchemy.orm import Session
from models.db_models import (
    db, DynastyDB, PersonDB, Territory, TerrainType, Settlement,
    Resource, ResourceType, TerritoryResource, Building, BuildingType,
    TradeRoute, Region, Province
)
from models.map_system import TerritoryManager

class EconomySystem:
    """
    Core economy system that handles resource production and consumption,
    trade and market mechanics, building construction and management,
    territory development, population and workforce management, taxation
    and treasury management, and economic policies and decisions.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the economy system.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.territory_manager = TerritoryManager(session)
        
        # Resource production rates by terrain type
        self.terrain_production_rates = {
            TerrainType.PLAINS: {
                ResourceType.FOOD: 2.0,
                ResourceType.TIMBER: 0.5,
                ResourceType.GOLD: 0.3
            },
            TerrainType.HILLS: {
                ResourceType.FOOD: 0.7,
                ResourceType.STONE: 1.5,
                ResourceType.IRON: 1.2
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
        
        # Building production bonuses
        self.building_production_bonuses = {
            BuildingType.FARM: {
                ResourceType.FOOD: 1.5
            },
            BuildingType.MINE: {
                ResourceType.IRON: 1.5,
                ResourceType.STONE: 1.2,
                ResourceType.GOLD: 0.8
            },
            BuildingType.LUMBER_CAMP: {
                ResourceType.TIMBER: 1.8
            },
            BuildingType.WORKSHOP: {
                ResourceType.GOLD: 1.2
            },
            BuildingType.MARKET: {
                ResourceType.GOLD: 1.5,
                "trade_efficiency": 0.2
            },
            BuildingType.PORT: {
                ResourceType.GOLD: 1.3,
                "trade_range": 2.0,
                "trade_efficiency": 0.3
            },
            BuildingType.WAREHOUSE: {
                "storage_capacity": 2.0,
                "resource_decay": -0.5  # Reduces decay by 50%
            },
            BuildingType.TRADE_POST: {
                "trade_efficiency": 0.4,
                ResourceType.GOLD: 1.1
            },
            BuildingType.ROADS: {
                "trade_efficiency": 0.3,
                "movement_cost": -0.2  # Reduces movement cost by 20%
            },
            BuildingType.IRRIGATION: {
                ResourceType.FOOD: 1.4
            },
            BuildingType.GUILD_HALL: {
                ResourceType.GOLD: 1.3,
                "production_efficiency": 0.2
            },
            BuildingType.BANK: {
                ResourceType.GOLD: 1.5,
                "interest_rate": 0.05  # 5% interest on treasury
            }
        }
        
        # Building construction costs
        self.building_construction_costs = {
            BuildingType.FARM: {
                "gold": 50,
                "timber": 20
            },
            BuildingType.MINE: {
                "gold": 100,
                "timber": 30,
                "stone": 20
            },
            BuildingType.LUMBER_CAMP: {
                "gold": 60,
                "timber": 10
            },
            BuildingType.WORKSHOP: {
                "gold": 80,
                "timber": 30,
                "stone": 10
            },
            BuildingType.MARKET: {
                "gold": 120,
                "timber": 40,
                "stone": 30
            },
            BuildingType.PORT: {
                "gold": 200,
                "timber": 80,
                "stone": 50
            },
            BuildingType.WAREHOUSE: {
                "gold": 100,
                "timber": 50,
                "stone": 20
            },
            BuildingType.TRADE_POST: {
                "gold": 150,
                "timber": 30,
                "stone": 20
            },
            BuildingType.ROADS: {
                "gold": 80,
                "stone": 40
            },
            BuildingType.IRRIGATION: {
                "gold": 70,
                "timber": 20
            },
            BuildingType.GUILD_HALL: {
                "gold": 150,
                "timber": 40,
                "stone": 40
            },
            BuildingType.BANK: {
                "gold": 200,
                "stone": 60
            }
        }
        
        # Building construction time (in years)
        self.building_construction_time = {
            BuildingType.FARM: 1,
            BuildingType.MINE: 2,
            BuildingType.LUMBER_CAMP: 1,
            BuildingType.WORKSHOP: 1,
            BuildingType.MARKET: 2,
            BuildingType.PORT: 3,
            BuildingType.WAREHOUSE: 1,
            BuildingType.TRADE_POST: 2,
            BuildingType.ROADS: 2,
            BuildingType.IRRIGATION: 2,
            BuildingType.GUILD_HALL: 2,
            BuildingType.BANK: 3
        }
        
        # Building maintenance costs per year
        self.building_maintenance_costs = {
            BuildingType.FARM: {
                "gold": 5
            },
            BuildingType.MINE: {
                "gold": 10
            },
            BuildingType.LUMBER_CAMP: {
                "gold": 5
            },
            BuildingType.WORKSHOP: {
                "gold": 8
            },
            BuildingType.MARKET: {
                "gold": 12
            },
            BuildingType.PORT: {
                "gold": 20
            },
            BuildingType.WAREHOUSE: {
                "gold": 8
            },
            BuildingType.TRADE_POST: {
                "gold": 15
            },
            BuildingType.ROADS: {
                "gold": 5
            },
            BuildingType.IRRIGATION: {
                "gold": 7
            },
            BuildingType.GUILD_HALL: {
                "gold": 15
            },
            BuildingType.BANK: {
                "gold": 20
            }
        }
        
        # Tax rates by development level
        self.base_tax_rates = {
            1: 0.05,  # 5% for level 1
            2: 0.06,
            3: 0.07,
            4: 0.08,
            5: 0.09,
            6: 0.10,
            7: 0.11,
            8: 0.12,
            9: 0.13,
            10: 0.15  # 15% for level 10
        }
        
        # Population growth rates by development level
        self.population_growth_rates = {
            1: 0.01,  # 1% for level 1
            2: 0.012,
            3: 0.014,
            4: 0.016,
            5: 0.018,
            6: 0.02,
            7: 0.022,
            8: 0.024,
            9: 0.026,
            10: 0.03  # 3% for level 10
        }
        
        # Resource consumption per population unit
        self.resource_consumption_per_capita = {
            ResourceType.FOOD: 0.5,  # 0.5 units per person per year
            ResourceType.TIMBER: 0.1,
            ResourceType.STONE: 0.05,
            ResourceType.IRON: 0.02
        }
        
        # Global market prices (base values)
        self.global_market_prices = {}
        self._initialize_global_market()
    
    def _initialize_global_market(self):
        """Initialize the global market with base prices for all resources."""
        resources = self.session.query(Resource).all()
        
        for resource in resources:
            self.global_market_prices[resource.resource_type] = {
                "base_price": resource.base_value,
                "current_price": resource.base_value,
                "supply": 0,
                "demand": 0,
                "volatility": resource.volatility
            }
    
    def calculate_territory_production(self, territory_id: int) -> Dict[ResourceType, float]:
        """
        Calculate resource production for a territory.
        
        Args:
            territory_id: ID of the territory
            
        Returns:
            Dictionary mapping resource types to production amounts
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return {}
        
        production = {}
        
        # Get base production from terrain
        terrain_production = self.terrain_production_rates.get(territory.terrain_type, {})
        for resource_type, base_rate in terrain_production.items():
            production[resource_type] = base_rate * territory.development_level
        
        # Get production from territory resources
        territory_resources = self.session.query(TerritoryResource).filter_by(territory_id=territory_id).all()
        for tr in territory_resources:
            resource = self.session.query(Resource).get(tr.resource_id)
            if resource:
                resource_type = resource.resource_type
                base_production = tr.base_production * (1.0 - tr.current_depletion)
                quality_modifier = tr.quality
                
                if resource_type in production:
                    production[resource_type] += base_production * quality_modifier
                else:
                    production[resource_type] = base_production * quality_modifier
        
        # Apply building bonuses
        buildings = self.session.query(Building).filter_by(territory_id=territory_id).all()
        for building in buildings:
            if building.condition < 0.5:  # Buildings in poor condition provide reduced bonuses
                continue
                
            bonuses = self.building_production_bonuses.get(building.building_type, {})
            for resource_type, bonus in bonuses.items():
                if isinstance(resource_type, ResourceType):
                    if resource_type in production:
                        production[resource_type] *= bonus
                    else:
                        # Only apply bonus if there's a base production to modify
                        pass
        
        # Apply population modifier
        population_modifier = min(1.0, territory.population / 1000)  # Cap at 1.0
        for resource_type in production:
            production[resource_type] *= population_modifier
        
        # Apply governor bonus if present
        if territory.governor_id:
            governor = self.session.query(PersonDB).get(territory.governor_id)
            if governor:
                stewardship_bonus = 1.0 + (governor.stewardship_skill * 0.01)  # +1% per point
                for resource_type in production:
                    production[resource_type] *= stewardship_bonus
        
        return production
    
    def calculate_territory_consumption(self, territory_id: int) -> Dict[ResourceType, float]:
        """
        Calculate resource consumption for a territory.
        
        Args:
            territory_id: ID of the territory
            
        Returns:
            Dictionary mapping resource types to consumption amounts
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return {}
        
        consumption = {}
        
        # Population-based consumption
        for resource_type, per_capita in self.resource_consumption_per_capita.items():
            consumption[resource_type] = territory.population * per_capita / 1000  # Scale by 1000
        
        # Building maintenance consumption
        buildings = self.session.query(Building).filter_by(territory_id=territory_id).all()
        for building in buildings:
            maintenance = self.building_maintenance_costs.get(building.building_type, {})
            for resource_type, amount in maintenance.items():
                if resource_type in consumption:
                    consumption[resource_type] += amount
                else:
                    consumption[resource_type] = amount
        
        # Military unit consumption
        military_units = territory.units_present
        for unit in military_units:
            # Assuming military units consume food and gold
            if ResourceType.FOOD in consumption:
                consumption[ResourceType.FOOD] += unit.food_consumption
            else:
                consumption[ResourceType.FOOD] = unit.food_consumption
                
            if ResourceType.GOLD in consumption:
                consumption[ResourceType.GOLD] += unit.maintenance_cost
            else:
                consumption[ResourceType.GOLD] = unit.maintenance_cost
        
        return consumption
    
    def calculate_territory_tax_income(self, territory_id: int) -> float:
        """
        Calculate tax income from a territory.
        
        Args:
            territory_id: ID of the territory
            
        Returns:
            Tax income in gold
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return 0.0
        
        # Base tax from territory
        base_tax = territory.base_tax * territory.development_level
        
        # Apply population modifier
        population_modifier = min(2.0, territory.population / 1000)  # Cap at 2.0
        tax_income = base_tax * population_modifier
        
        # Apply tax rate based on development level
        tax_rate = self.base_tax_rates.get(territory.development_level, 0.05)
        tax_income *= tax_rate
        
        # Apply governor bonus if present
        if territory.governor_id:
            governor = self.session.query(PersonDB).get(territory.governor_id)
            if governor:
                stewardship_bonus = 1.0 + (governor.stewardship_skill * 0.02)  # +2% per point
                tax_income *= stewardship_bonus
        
        # Apply settlement bonus
        settlements = self.session.query(Settlement).filter_by(territory_id=territory_id).all()
        for settlement in settlements:
            if settlement.settlement_type == "city":
                tax_income *= 1.5  # Cities provide 50% more tax
            elif settlement.settlement_type == "town":
                tax_income *= 1.2  # Towns provide 20% more tax
def calculate_dynasty_economy(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Calculate the overall economy for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Dictionary with economic data
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return {}
        
        # Get all territories controlled by the dynasty
        territories = self.session.query(Territory).filter_by(controller_dynasty_id=dynasty_id).all()
        
        total_production = {}
        total_consumption = {}
        total_tax_income = 0.0
        territory_data = []
        
        for territory in territories:
            # Calculate production
            production = self.calculate_territory_production(territory.id)
            
            # Calculate consumption
            consumption = self.calculate_territory_consumption(territory.id)
            
            # Calculate tax income
            tax_income = self.calculate_territory_tax_income(territory.id)
            total_tax_income += tax_income
            
            # Add to totals
            for resource_type, amount in production.items():
                if resource_type in total_production:
                    total_production[resource_type] = total_production.get(resource_type, 0) + amount
                else:
                    total_production[resource_type] = amount
            
            for resource_type, amount in consumption.items():
                if resource_type in total_consumption:
                    total_consumption[resource_type] = total_consumption.get(resource_type, 0) + amount
                else:
                    total_consumption[resource_type] = amount
            
            # Store territory data
            territory_data.append({
                "id": territory.id,
                "name": territory.name,
                "production": production,
                "consumption": consumption,
                "tax_income": tax_income,
                "population": territory.population,
                "development_level": territory.development_level
            })
        
        # Calculate net production (production - consumption)
        net_production = {}
        for resource_type in set(list(total_production.keys()) + list(total_consumption.keys())):
            production_amount = total_production.get(resource_type, 0)
            consumption_amount = total_consumption.get(resource_type, 0)
            net_production[resource_type] = production_amount - consumption_amount
        
        # Calculate trade income
        trade_routes = self.session.query(TradeRoute).filter(
            (TradeRoute.source_dynasty_id == dynasty_id) | 
            (TradeRoute.target_dynasty_id == dynasty_id)
        ).all()
        
        trade_income = 0.0
        trade_data = []
        
        for route in trade_routes:
            if route.source_dynasty_id == dynasty_id:
                # Export route
                trade_income += route.profit_source
                trade_data.append({
                    "id": route.id,
                    "type": "export",
                    "partner": self.session.query(DynastyDB).get(route.target_dynasty_id).name,
                    "resource": route.resource_type.value,
                    "amount": route.resource_amount,
                    "profit": route.profit_source
                })
            else:
                # Import route
                trade_income += route.profit_target
                trade_data.append({
                    "id": route.id,
                    "type": "import",
                    "partner": self.session.query(DynastyDB).get(route.source_dynasty_id).name,
                    "resource": route.resource_type.value,
                    "amount": route.resource_amount,
                    "profit": route.profit_target
                })
        
        # Calculate total income and expenses
        total_income = total_tax_income + trade_income
        
        # Military maintenance is already included in territory consumption
        
        # Calculate treasury change
        treasury_change = total_income - total_consumption.get(ResourceType.GOLD, 0)
        
        return {
            "dynasty_id": dynasty_id,
            "dynasty_name": dynasty.name,
            "territories": territory_data,
            "total_production": total_production,
            "total_consumption": total_consumption,
            "net_production": net_production,
            "tax_income": total_tax_income,
            "trade_income": trade_income,
            "total_income": total_income,
            "treasury_change": treasury_change,
            "current_treasury": dynasty.current_wealth,
            "trade_routes": trade_data
        }
    
def update_dynasty_economy(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Update the economy for a dynasty for one turn.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Dictionary with updated economic data
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return {"success": False, "message": "Dynasty not found"}
        
        # Calculate economy
        economy_data = self.calculate_dynasty_economy(dynasty_id)
        
        # Update treasury
        dynasty.current_wealth += economy_data["treasury_change"]
        
        # Update resources in territories
        territories = self.session.query(Territory).filter_by(controller_dynasty_id=dynasty_id).all()
        
        for territory in territories:
            # Update population
            growth_rate = self.population_growth_rates.get(territory.development_level, 0.01)
            
            # Adjust growth rate based on food availability
            production = self.calculate_territory_production(territory.id)
            consumption = self.calculate_territory_consumption(territory.id)
            
            food_production = production.get(ResourceType.FOOD, 0)
            food_consumption = consumption.get(ResourceType.FOOD, 0)
            
            if food_production < food_consumption:
                # Food shortage reduces growth or causes decline
                food_ratio = food_production / food_consumption if food_consumption > 0 else 0
                growth_rate = growth_rate * (food_ratio - 0.5)  # Can go negative
            
            # Apply growth
            territory.population = max(100, int(territory.population * (1 + growth_rate)))
            
            # Update territory resources
            territory_resources = self.session.query(TerritoryResource).filter_by(territory_id=territory.id).all()
            for tr in territory_resources:
                # Apply depletion
                tr.current_depletion = min(1.0, tr.current_depletion + tr.depletion_rate)
            
            # Update buildings
            buildings = self.session.query(Building).filter_by(territory_id=territory.id).all()
            for building in buildings:
                # Deteriorate condition slightly
                building.condition = max(0, building.condition - 0.05)
                
                # Complete construction if needed
                if building.is_under_construction and dynasty.current_simulation_year >= building.completion_year:
                    building.is_under_construction = False
                    if building.level < 5:  # If this was an upgrade
                        building.level += 1
        
        # Update trade routes
        trade_routes = self.session.query(TradeRoute).filter(
            (TradeRoute.source_dynasty_id == dynasty_id) | 
            (TradeRoute.target_dynasty_id == dynasty_id)
        ).all()
        
        for route in trade_routes:
            # Fluctuate profits slightly
            if route.source_dynasty_id == dynasty_id:
                route.profit_source *= random.uniform(0.9, 1.1)
            else:
                route.profit_target *= random.uniform(0.9, 1.1)
        
        # Update global market
        self._update_global_market()
        
        # Commit changes
        self.session.commit()
        
        return {
            "success": True,
            "message": "Economy updated successfully",
            "economy_data": economy_data
        }
    
def _update_global_market(self):
        """Update the global market prices based on supply and demand."""
        for resource_type, data in self.global_market_prices.items():
            # Calculate price change based on supply and demand
            supply = data["supply"]
            demand = data["demand"]
            
            if supply > 0 and demand > 0:
                ratio = demand / supply
                price_change = (ratio - 1.0) * 0.2  # 20% of the ratio difference
            else:
                # Random fluctuation if no supply or demand data
                price_change = random.uniform(-0.1, 0.1)
            
            # Apply volatility
            price_change *= data["volatility"]
            
            # Update price
            data["current_price"] = max(0.1, data["base_price"] * (1 + price_change))
            
def construct_building(self, territory_id: int, building_type: BuildingType) -> Tuple[bool, str]:
        """
        Start construction of a building in a territory.
        
        Args:
            territory_id: ID of the territory
            building_type: Type of building to construct
            
        Returns:
            Tuple of (success, message)
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return False, "Territory not found"
        
        # Check if territory has a controller
        if not territory.controller_dynasty_id:
            return False, "Territory has no controller"
        
        dynasty = self.session.query(DynastyDB).get(territory.controller_dynasty_id)
        if not dynasty:
            return False, "Controlling dynasty not found"
        
        # Check if building already exists
        existing_building = self.session.query(Building).filter_by(
            territory_id=territory_id,
            building_type=building_type
        ).first()
        
        if existing_building:
            return False, f"A {building_type.value} already exists in this territory"
        
        # Check if we can afford it
        costs = self.building_construction_costs.get(building_type, {"gold": 100})
        
        if dynasty.current_wealth < costs.get("gold", 0):
            return False, "Not enough gold"
        
        # Check for other resources
        for resource_name, amount in costs.items():
            if resource_name != "gold":
                # This is simplified - in a real implementation, you'd check
                # the dynasty's resource stockpile
                pass
        
        # Deduct costs
        dynasty.current_wealth -= costs.get("gold", 0)
        
        # Create building
        construction_time = self.building_construction_time.get(building_type, 1)
        
        new_building = Building(
            territory_id=territory_id,
            building_type=building_type,
            name=f"{building_type.value.replace('_', ' ').title()}",
            level=1,
            condition=1.0,
            construction_year=dynasty.current_simulation_year,
            completion_year=dynasty.current_simulation_year + construction_time,
            is_under_construction=True
        )
        
        # Set effects JSON
        effects = self.building_production_bonuses.get(building_type, {})
        effects_dict = {}
        
        for key, value in effects.items():
            if isinstance(key, ResourceType):
                effects_dict[key.value] = value
            else:
                effects_dict[key] = value
        
        new_building.effects_json = json.dumps(effects_dict)
        
        # Add to database
        self.session.add(new_building)
        self.session.commit()
        
        return True, f"Started construction of {building_type.value.replace('_', ' ').title()}"
    
def upgrade_building(self, building_id: int) -> Tuple[bool, str]:
        """
        Upgrade an existing building.
        
        Args:
            building_id: ID of the building to upgrade
            
        Returns:
            Tuple of (success, message)
        """
        building = self.session.query(Building).get(building_id)
        if not building:
            return False, "Building not found"
        
        # Check if building is under construction
        if building.is_under_construction:
            return False, "Building is still under construction"
        
        # Check if building is at max level
        if building.level >= 5:
            return False, "Building is already at maximum level"
        
        territory = self.session.query(Territory).get(building.territory_id)
        if not territory:
            return False, "Territory not found"
        
        dynasty = self.session.query(DynastyDB).get(territory.controller_dynasty_id)
        if not dynasty:
            return False, "Controlling dynasty not found"
        
        # Calculate upgrade cost (increases with level)
        base_costs = self.building_construction_costs.get(building.building_type, {"gold": 100})
        upgrade_multiplier = 1.0 + (building.level * 0.5)  # 50% more expensive per level
        
        upgrade_costs = {}
        for resource, amount in base_costs.items():
            upgrade_costs[resource] = amount * upgrade_multiplier
        
        # Check if we can afford it
        if dynasty.current_wealth < upgrade_costs.get("gold", 0):
            return False, "Not enough gold"
        
        # Deduct costs
        dynasty.current_wealth -= upgrade_costs.get("gold", 0)
        
        # Set building under construction for upgrade
        building.is_under_construction = True
        building.completion_year = dynasty.current_simulation_year + 1  # Upgrades take 1 year
        
        # Commit changes
        self.session.commit()
        
        return True, f"Started upgrade of {building.name} to level {building.level + 1}"
    
def repair_building(self, building_id: int) -> Tuple[bool, str]:
        """
        Repair a damaged building.
        
        Args:
            building_id: ID of the building to repair
            
        Returns:
            Tuple of (success, message)
        """
        building = self.session.query(Building).get(building_id)
        if not building:
            return False, "Building not found"
        
        # Check if building needs repair
        if building.condition >= 0.9:
            return False, "Building doesn't need repair"
        
        territory = self.session.query(Territory).get(building.territory_id)
        if not territory:
            return False, "Territory not found"
        
        dynasty = self.session.query(DynastyDB).get(territory.controller_dynasty_id)
        if not dynasty:
            return False, "Controlling dynasty not found"
        
        # Calculate repair cost based on damage
        damage = 1.0 - building.condition
        base_costs = self.building_construction_costs.get(building.building_type, {"gold": 100})
        
        repair_costs = {}
        for resource, amount in base_costs.items():
            repair_costs[resource] = amount * damage * 0.5  # 50% of original cost * damage percentage
        
        # Check if we can afford it
        if dynasty.current_wealth < repair_costs.get("gold", 0):
            return False, "Not enough gold"
        
        # Deduct costs
        dynasty.current_wealth -= repair_costs.get("gold", 0)
        
        # Repair building
        building.condition = 1.0
        
        # Commit changes
        self.session.commit()
        
        return True, f"Repaired {building.name}"
    
def establish_trade_route(self, source_dynasty_id: int, target_dynasty_id: int,
                             resource_type: ResourceType, amount: float) -> Tuple[bool, str, Optional[TradeRoute]]:
        """
        Establish a trade route between two dynasties.
        
        Args:
            source_dynasty_id: ID of the source dynasty (exporter)
            target_dynasty_id: ID of the target dynasty (importer)
            resource_type: Type of resource to trade
            amount: Amount of resource to trade per year
            
        Returns:
            Tuple of (success, message, trade_route)
        """
        # Check dynasties
        source_dynasty = self.session.query(DynastyDB).get(source_dynasty_id)
        target_dynasty = self.session.query(DynastyDB).get(target_dynasty_id)
        
        if not source_dynasty or not target_dynasty:
            return False, "One or both dynasties not found", None
        
        # Check if dynasties are at war
        wars = self.session.query(War).filter(
            ((War.attacker_dynasty_id == source_dynasty_id) & (War.defender_dynasty_id == target_dynasty_id)) |
            ((War.attacker_dynasty_id == target_dynasty_id) & (War.defender_dynasty_id == source_dynasty_id))
        ).filter_by(end_year=None).first()
        
        if wars:
            return False, "Cannot establish trade routes with enemies during war", None
        
        # Check if source dynasty produces enough of the resource
        source_economy = self.calculate_dynasty_economy(source_dynasty_id)
        net_production = source_economy.get("net_production", {})
        
        if resource_type not in net_production or net_production[resource_type] < amount:
            return False, f"Source dynasty doesn't produce enough {resource_type.value}", None
        
        # Calculate base price for the resource
        resource = self.session.query(Resource).filter_by(resource_type=resource_type).first()
        if not resource:
            return False, f"Resource {resource_type.value} not found in database", None
        
        base_price = resource.base_value
        
        # Calculate profits for both sides
        # Source gets profit from selling
        source_profit = base_price * amount * 0.8  # 80% of value
        
        # Target gets profit from value-added activities
        target_profit = base_price * amount * 0.3  # 30% of value
        
        # Create trade route
        trade_route = TradeRoute(
            source_dynasty_id=source_dynasty_id,
            target_dynasty_id=target_dynasty_id,
            resource_type=resource_type,
            resource_amount=amount,
            base_price=base_price,
            profit_source=source_profit,
            profit_target=target_profit,
            established_year=source_dynasty.current_simulation_year,
            is_active=True
        )
        
        # Add to database
        self.session.add(trade_route)
        self.session.commit()
        
        return True, f"Established trade route for {amount} {resource_type.value} per year", trade_route
    
def cancel_trade_route(self, trade_route_id: int, dynasty_id: int) -> Tuple[bool, str]:
        """
        Cancel an existing trade route.
        
        Args:
            trade_route_id: ID of the trade route to cancel
            dynasty_id: ID of the dynasty canceling the route
            
        Returns:
            Tuple of (success, message)
        """
        trade_route = self.session.query(TradeRoute).get(trade_route_id)
        if not trade_route:
            return False, "Trade route not found"
        
        # Check if dynasty is involved in the trade route
        if trade_route.source_dynasty_id != dynasty_id and trade_route.target_dynasty_id != dynasty_id:
            return False, "Dynasty is not involved in this trade route"
        
        # Deactivate the trade route
        trade_route.is_active = False
        
        # Commit changes
        self.session.commit()
        
        return True, "Trade route canceled"
    
def develop_territory(self, territory_id: int) -> Tuple[bool, str]:
        """
        Increase the development level of a territory.
        
        Args:
            territory_id: ID of the territory to develop
            
        Returns:
            Tuple of (success, message)
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return False, "Territory not found"
        
        # Check if territory has a controller
        if not territory.controller_dynasty_id:
            return False, "Territory has no controller"
        
        dynasty = self.session.query(DynastyDB).get(territory.controller_dynasty_id)
        if not dynasty:
            return False, "Controlling dynasty not found"
        
        # Check if territory is at max development
        if territory.development_level >= 10:
            return False, "Territory is already at maximum development level"
        
        # Calculate development cost (increases with level)
        base_cost = 100  # Base cost in gold
        level_multiplier = 1.0 + (territory.development_level * 0.5)  # 50% more expensive per level
        
        development_cost = base_cost * level_multiplier
        
        # Check if we can afford it
        if dynasty.current_wealth < development_cost:
            return False, f"Not enough gold. Required: {development_cost}, Available: {dynasty.current_wealth}"
        
        # Deduct costs
        dynasty.current_wealth -= development_cost
        
        # Increase development level
        territory.development_level += 1
        
        # Commit changes
        self.session.commit()
        
        return True, f"Increased development level of {territory.name} to {territory.development_level}"
    
def set_tax_policy(self, dynasty_id: int, tax_modifier: float) -> Tuple[bool, str]:
        """
        Set the tax policy for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            tax_modifier: Tax modifier (0.5 to 1.5, where 1.0 is normal)
            
        Returns:
            Tuple of (success, message)
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return False, "Dynasty not found"
        
        # Validate tax modifier
        if tax_modifier < 0.5 or tax_modifier > 1.5:
            return False, "Tax modifier must be between 0.5 and 1.5"
        
        # Store tax policy in dynasty
        # This would require adding a tax_modifier field to the DynastyDB model
        # For now, we'll just return success
        
def integrate_with_map_system(self, territory_id: int) -> Dict[str, Any]:
        """
        Integrate the economy system with the map system for a territory.
        
        Args:
            territory_id: ID of the territory
            
        Returns:
            Dictionary with integrated data
        """
        territory = self.session.query(Territory).get(territory_id)
        if not territory:
            return {"success": False, "message": "Territory not found"}
        
        # Get territory production and consumption
        production = self.calculate_territory_production(territory_id)
        consumption = self.calculate_territory_consumption(territory_id)
        
        # Get territory resources
        territory_resources = self.session.query(TerritoryResource).filter_by(territory_id=territory_id).all()
        
        # Get buildings
        buildings = self.session.query(Building).filter_by(territory_id=territory_id).all()
        
        # Calculate resource efficiency based on terrain
        terrain_efficiency = {}
        for resource_type, base_rate in self.terrain_production_rates.get(territory.terrain_type, {}).items():
            terrain_efficiency[resource_type] = base_rate / 2.0  # Normalize to a 0-1 scale
        
        return {
            "success": True,
            "territory_id": territory_id,
            "territory_name": territory.name,
            "production": production,
            "consumption": consumption,
            "resources": territory_resources,
            "buildings": buildings,
            "terrain_efficiency": terrain_efficiency
        }
    
def integrate_with_military_system(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Integrate the economy system with the military system for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Dictionary with integrated data
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return {"success": False, "message": "Dynasty not found"}
        
        # Get military units
        military_units = self.session.query(MilitaryUnit).filter_by(dynasty_id=dynasty_id).all()
        
        # Calculate maintenance costs
        total_gold_maintenance = sum(unit.maintenance_cost for unit in military_units)
        total_food_maintenance = sum(unit.food_consumption for unit in military_units)
        
        # Get economy data
        economy_data = self.calculate_dynasty_economy(dynasty_id)
        
        # Check if dynasty can afford maintenance
        can_afford_maintenance = dynasty.current_wealth >= total_gold_maintenance
        
        # Check if dynasty has enough food
        food_production = economy_data.get("total_production", {}).get(ResourceType.FOOD, 0)
        food_consumption = economy_data.get("total_consumption", {}).get(ResourceType.FOOD, 0)
        has_enough_food = food_production >= food_consumption
        
        return {
            "success": True,
            "dynasty_id": dynasty_id,
            "dynasty_name": dynasty.name,
            "military_units": military_units,
            "total_gold_maintenance": total_gold_maintenance,
            "total_food_maintenance": total_food_maintenance,
            "can_afford_maintenance": can_afford_maintenance,
            "has_enough_food": has_enough_food,
            "treasury": dynasty.current_wealth,
            "food_production": food_production,
            "food_consumption": food_consumption
        }
    
def integrate_with_diplomacy_system(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Integrate the economy system with the diplomacy system for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Dictionary with integrated data
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return {"success": False, "message": "Dynasty not found"}
        
        # Get trade routes
        trade_routes = self.session.query(TradeRoute).filter(
            (TradeRoute.source_dynasty_id == dynasty_id) | 
            (TradeRoute.target_dynasty_id == dynasty_id)
        ).filter_by(is_active=True).all()
        
        # Get treaties
        diplomatic_relations = self.session.query(DiplomaticRelation).filter(
            (DiplomaticRelation.dynasty1_id == dynasty_id) | 
            (DiplomaticRelation.dynasty2_id == dynasty_id)
        ).all()
        
        treaties = []
        for relation in diplomatic_relations:
            relation_treaties = self.session.query(Treaty).filter_by(
                diplomatic_relation_id=relation.id,
                active=True
            ).all()
            treaties.extend(relation_treaties)
        
        # Calculate trade income
        trade_income = 0.0
        for route in trade_routes:
            if route.source_dynasty_id == dynasty_id:
                trade_income += route.profit_source
            else:
                trade_income += route.profit_target
        
        # Calculate treaty effects
        treaty_effects = {}
        for treaty in treaties:
            if treaty.treaty_type == TreatyType.TRADE_AGREEMENT:
                treaty_effects["trade_efficiency"] = treaty_effects.get("trade_efficiency", 1.0) + 0.1
            elif treaty.treaty_type == TreatyType.MARKET_ACCESS:
                treaty_effects["market_access"] = True
            elif treaty.treaty_type == TreatyType.RESOURCE_EXCHANGE:
                treaty_effects["resource_exchange"] = True
            elif treaty.treaty_type == TreatyType.ECONOMIC_UNION:
                treaty_effects["trade_efficiency"] = treaty_effects.get("trade_efficiency", 1.0) + 0.2
                treaty_effects["market_access"] = True
                treaty_effects["resource_exchange"] = True
        
        return {
            "success": True,
            "dynasty_id": dynasty_id,
            "dynasty_name": dynasty.name,
            "trade_routes": trade_routes,
            "treaties": treaties,
            "trade_income": trade_income,
            "treaty_effects": treaty_effects
        }
    
def integrate_with_character_system(self, dynasty_id: int) -> Dict[str, Any]:
        """
        Integrate the economy system with the character system for a dynasty.
        
        Args:
            dynasty_id: ID of the dynasty
            
        Returns:
            Dictionary with integrated data
        """
        dynasty = self.session.query(DynastyDB).get(dynasty_id)
        if not dynasty:
            return {"success": False, "message": "Dynasty not found"}
        
        # Get characters
        characters = self.session.query(PersonDB).filter_by(
            dynasty_id=dynasty_id,
            death_year=None  # Only living characters
        ).all()
        
        # Get territories with governors
        territories = self.session.query(Territory).filter_by(
            controller_dynasty_id=dynasty_id
        ).all()
        
        # Calculate character bonuses
        character_bonuses = {}
        for character in characters:
            # Stewardship skill affects economy
            if character.stewardship_skill > 0:
                character_bonuses[character.id] = {
                    "name": f"{character.name} {character.surname}",
                    "stewardship_skill": character.stewardship_skill,
                    "production_bonus": character.stewardship_skill * 0.01,  # +1% per point
                    "tax_bonus": character.stewardship_skill * 0.02,  # +2% per point
                    "traits": character.get_traits()
                }
        
        # Calculate governor effects
        governor_effects = {}
        for territory in territories:
            if territory.governor_id:
                governor = self.session.query(PersonDB).get(territory.governor_id)
                if governor:
                    governor_effects[territory.id] = {
                        "territory_name": territory.name,
                        "governor_name": f"{governor.name} {governor.surname}",
                        "stewardship_skill": governor.stewardship_skill,
                        "production_bonus": governor.stewardship_skill * 0.01,
                        "tax_bonus": governor.stewardship_skill * 0.02,
                        "traits": governor.get_traits()
                    }
        
        return {
            "success": True,
            "dynasty_id": dynasty_id,
            "dynasty_name": dynasty.name,
            "characters": characters,
            "character_bonuses": character_bonuses,
            "governor_effects": governor_effects
        }
        return True, f"Set tax policy to {tax_modifier * 100:.0f}% of normal"