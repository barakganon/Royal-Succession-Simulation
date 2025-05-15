# models/economy.py
import random
from collections import defaultdict

class Resource:
    """Represents a resource type in the economy system."""
    def __init__(self, name, base_value, volatility=0.1):
        self.name = name
        self.base_value = base_value  # Base value in gold
        self.current_value = base_value  # Current market value
        self.volatility = volatility  # How much the price can fluctuate
        
    def update_market_value(self):
        """Update the resource's market value based on volatility."""
        change = random.uniform(-self.volatility, self.volatility)
        self.current_value = max(0.1, self.base_value * (1 + change))
        return self.current_value
    
    def __repr__(self):
        return f"Resource({self.name}, value={self.current_value:.2f})"


class Holding:
    """Represents a land holding or property that generates resources."""
    def __init__(self, name, holding_type, size=1.0):
        self.name = name
        self.holding_type = holding_type  # farm, mine, forest, etc.
        self.size = size  # Size multiplier
        self.buildings = []  # Buildings constructed on this holding
        self.improvements = []  # Improvements made to this holding
        
        # Base production rates by holding type
        self.production_rates = {
            "farm": {"grain": 20, "livestock": 5},
            "mine": {"iron": 10, "silver": 2},
            "forest": {"timber": 15, "fur": 3},
            "coastal": {"fish": 15, "salt": 5},
            "urban": {"gold": 10, "luxuries": 2},
            "default": {"gold": 5}
        }
        
    def get_production(self):
        """Calculate the resource production for this holding."""
        # Get base production for this holding type
        base_production = self.production_rates.get(
            self.holding_type, 
            self.production_rates["default"]
        )
        
        # Apply size multiplier
        production = {k: v * self.size for k, v in base_production.items()}
        
        # Apply building bonuses
        for building in self.buildings:
            for resource, bonus in building.production_bonuses.items():
                if resource in production:
                    production[resource] += bonus
                else:
                    production[resource] = bonus
        
        # Apply improvement bonuses (percentage increases)
        for improvement in self.improvements:
            for resource, bonus_pct in improvement.bonus_percentages.items():
                if resource in production:
                    production[resource] *= (1 + bonus_pct)
        
        return production
    
    def __repr__(self):
        return f"Holding({self.name}, type={self.holding_type}, size={self.size})"


class Building:
    """Represents a building that can be constructed on a holding."""
    def __init__(self, name, cost, construction_time, production_bonuses=None):
        self.name = name
        self.cost = cost  # Cost in gold
        self.construction_time = construction_time  # Years to build
        self.production_bonuses = production_bonuses or {}  # Resource bonuses
        self.remaining_construction_time = construction_time
        self.is_complete = False
        
    def advance_construction(self):
        """Advance construction by one year."""
        if not self.is_complete:
            self.remaining_construction_time -= 1
            if self.remaining_construction_time <= 0:
                self.is_complete = True
                return True
        return False
    
    def __repr__(self):
        status = "complete" if self.is_complete else f"{self.remaining_construction_time} years remaining"
        return f"Building({self.name}, {status})"


class Improvement:
    """Represents an improvement to a holding that provides percentage bonuses."""
    def __init__(self, name, cost, bonus_percentages=None):
        self.name = name
        self.cost = cost  # Cost in gold
        self.bonus_percentages = bonus_percentages or {}  # Percentage bonuses
        
    def __repr__(self):
        return f"Improvement({self.name}, bonuses={self.bonus_percentages})"


class EconomyManager:
    """Manages the economic system for a dynasty."""
    def __init__(self, dynasty_id, theme_config=None):
        self.dynasty_id = dynasty_id
        self.theme_config = theme_config or {}
        
        # Initialize resources based on theme
        self.resources = self._initialize_resources()
        
        # Holdings
        self.holdings = []
        
        # Trade agreements
        self.trade_agreements = []
        
        # Market prices
        self.market = {}
        
        # Economic modifiers
        self.modifiers = {
            "production": 1.0,
            "consumption": 1.0,
            "trade": 1.0
        }
        
        # Economic events history
        self.event_history = []
        
    def _initialize_resources(self):
        """Initialize resources based on theme configuration."""
        resources = {
            "gold": 100  # Base currency always present
        }
        
        # Add resources from theme
        theme_resources = self.theme_config.get("common_resources", [])
        for resource_name in theme_resources:
            # Convert to lowercase and replace spaces with underscores for keys
            key = resource_name.lower().replace(" ", "_")
            # Don't overwrite gold if it's in the theme resources
            if key != "gold":
                resources[key] = 0
        
        # Ensure some basic resources exist
        for basic_resource in ["grain", "timber"]:
            if basic_resource not in resources:
                resources[basic_resource] = 0
                
        return resources
    
    def add_holding(self, name, holding_type, size=1.0):
        """Add a new holding to the dynasty."""
        holding = Holding(name, holding_type, size)
        self.holdings.append(holding)
        return holding
    
    def build_on_holding(self, holding_index, building_name, building_cost, construction_time, bonuses=None):
        """Start construction of a building on a holding."""
        if 0 <= holding_index < len(self.holdings):
            # Check if we can afford it
            if self.resources["gold"] >= building_cost:
                self.resources["gold"] -= building_cost
                building = Building(building_name, building_cost, construction_time, bonuses)
                self.holdings[holding_index].buildings.append(building)
                return True
        return False
    
    def improve_holding(self, holding_index, improvement_name, improvement_cost, bonuses=None):
        """Add an improvement to a holding."""
        if 0 <= holding_index < len(self.holdings):
            # Check if we can afford it
            if self.resources["gold"] >= improvement_cost:
                self.resources["gold"] -= improvement_cost
                improvement = Improvement(improvement_name, improvement_cost, bonuses)
                self.holdings[holding_index].improvements.append(improvement)
                return True
        return False
    
    def yearly_update(self, current_year, character_traits=None):
        """Process yearly economic updates."""
        # Update building construction
        self._update_construction()
        
        # Calculate production
        production = self._calculate_production(character_traits)
        
        # Calculate consumption
        consumption = self._calculate_consumption(character_traits)
        
        # Update resources
        for resource, amount in production.items():
            if resource in self.resources:
                self.resources[resource] += amount
        
        for resource, amount in consumption.items():
            if resource in self.resources:
                self.resources[resource] = max(0, self.resources[resource] - amount)
        
        # Process trade
        self._process_trade()
        
        # Random economic events
        event = self._process_economic_events(current_year, character_traits)
        
        # Update market values
        self._update_market()
        
        return {
            "production": production,
            "consumption": consumption,
            "event": event
        }
    
    def _update_construction(self):
        """Update construction progress on all buildings."""
        completed_buildings = []
        
        for holding in self.holdings:
            for building in holding.buildings:
                if not building.is_complete and building.advance_construction():
                    completed_buildings.append((holding.name, building.name))
        
        return completed_buildings
    
    def _calculate_production(self, character_traits=None):
        """Calculate resource production from all holdings."""
        production = defaultdict(float)
        
        # Base production from holdings
        for holding in self.holdings:
            holding_production = holding.get_production()
            for resource, amount in holding_production.items():
                production[resource] += amount
        
        # Apply trait modifiers
        if character_traits:
            # Example: "Industrious" trait increases production by 10%
            if "Industrious" in character_traits:
                for resource in production:
                    production[resource] *= 1.1
            
            # Example: "Lazy" trait decreases production by 10%
            if "Lazy" in character_traits:
                for resource in production:
                    production[resource] *= 0.9
        
        # Apply global production modifier
        for resource in production:
            production[resource] *= self.modifiers["production"]
        
        return dict(production)
    
    def _calculate_consumption(self, character_traits=None):
        """Calculate resource consumption."""
        # Basic consumption model - could be expanded based on population, etc.
        consumption = defaultdict(float)
        
        # Consume some basic resources
        if "grain" in self.resources:
            consumption["grain"] = 10  # Base grain consumption
        
        if "timber" in self.resources:
            consumption["timber"] = 5  # Base timber consumption
        
        # Apply trait modifiers
        if character_traits:
            # Example: "Frugal" trait decreases consumption by 15%
            if "Frugal" in character_traits:
                for resource in consumption:
                    consumption[resource] *= 0.85
            
            # Example: "Wasteful" trait increases consumption by 20%
            if "Wasteful" in character_traits:
                for resource in consumption:
                    consumption[resource] *= 1.2
        
        # Apply global consumption modifier
        for resource in consumption:
            consumption[resource] *= self.modifiers["consumption"]
        
        return dict(consumption)
    
    def _process_trade(self):
        """Process trade agreements and market transactions."""
        # Simple implementation for now
        # Could be expanded with actual trade partners, etc.
        pass
    
    def _process_economic_events(self, current_year, character_traits=None):
        """Process random economic events."""
        # Chance of an economic event
        if random.random() < 0.1:  # 10% chance per year
            event_types = [
                {"name": "Bountiful Harvest", "effect": {"grain": 20}, "chance": 0.3},
                {"name": "Trade Boom", "effect": {"gold": 15}, "chance": 0.2},
                {"name": "Resource Discovery", "effect": {"random": 25}, "chance": 0.1},
                {"name": "Market Crash", "effect": {"gold": -10}, "chance": 0.15},
                {"name": "Poor Harvest", "effect": {"grain": -15}, "chance": 0.25}
            ]
            
            # Weight by chance
            total_chance = sum(event["chance"] for event in event_types)
            roll = random.uniform(0, total_chance)
            
            current_total = 0
            selected_event = None
            for event in event_types:
                current_total += event["chance"]
                if roll <= current_total:
                    selected_event = event
                    break
            
            if selected_event:
                # Apply event effects
                effect = selected_event["effect"]
                event_description = f"{selected_event['name']} in year {current_year}"
                
                for resource, amount in effect.items():
                    if resource == "random":
                        # Pick a random resource to affect
                        resource_keys = list(self.resources.keys())
                        if resource_keys:
                            random_resource = random.choice(resource_keys)
                            self.resources[random_resource] += amount
                            event_description += f": {random_resource} +{amount}"
                    else:
                        if resource in self.resources:
                            self.resources[resource] += amount
                            event_description += f": {resource} {'+'if amount > 0 else ''}{amount}"
                
                # Record the event
                self.event_history.append({
                    "year": current_year,
                    "name": selected_event["name"],
                    "description": event_description
                })
                
                return selected_event["name"]
        
        return None
    
    def _update_market(self):
        """Update market prices for resources."""
        # Simple random fluctuation for now
        for resource_name in self.resources:
            if resource_name not in self.market:
                self.market[resource_name] = Resource(resource_name, 1.0)
            
            self.market[resource_name].update_market_value()
    
    def get_total_wealth(self):
        """Calculate the total wealth of the dynasty in gold equivalent."""
        total = self.resources.get("gold", 0)
        
        # Add value of other resources
        for resource_name, amount in self.resources.items():
            if resource_name != "gold" and resource_name in self.market:
                total += amount * self.market[resource_name].current_value
        
        # Add value of holdings (simple estimate)
        for holding in self.holdings:
            # Base value by type
            base_values = {
                "farm": 100,
                "mine": 150,
                "forest": 80,
                "coastal": 120,
                "urban": 200,
                "default": 50
            }
            holding_value = base_values.get(holding.holding_type, base_values["default"])
            
            # Adjust for size
            holding_value *= holding.size
            
            # Add building values
            for building in holding.buildings:
                if building.is_complete:
                    holding_value += building.cost * 1.5  # Buildings increase property value
            
            # Add improvement values
            for improvement in holding.improvements:
                holding_value += improvement.cost * 1.2  # Improvements increase property value
            
            total += holding_value
        
        return total
    
    def __repr__(self):
        resources_str = ", ".join(f"{k}: {v}" for k, v in self.resources.items())
        return f"EconomyManager(dynasty_id={self.dynasty_id}, resources={{{resources_str}}}, holdings={len(self.holdings)})"


# Example usage
if __name__ == "__main__":
    # Example theme config
    example_theme = {
        "common_resources": ["Grain", "Timber", "Iron", "Silver", "Wool"]
    }
    
    # Create economy manager
    economy = EconomyManager(dynasty_id=1, theme_config=example_theme)
    
    # Add some holdings
    economy.add_holding("Home Farm", "farm", 2.0)
    economy.add_holding("Northern Forest", "forest", 1.5)
    economy.add_holding("Silver Mine", "mine", 1.0)
    
    # Build on holdings
    economy.build_on_holding(0, "Mill", 50, 2, {"grain": 10})
    economy.improve_holding(1, "Logging Camp", 30, {"timber": 0.2})
    
    # Run a few years of simulation
    for year in range(1000, 1010):
        result = economy.yearly_update(year, ["Industrious"])
        print(f"Year {year}:")
        print(f"  Production: {result['production']}")
        print(f"  Consumption: {result['consumption']}")
        if result['event']:
            print(f"  Event: {result['event']}")
        print(f"  Total Wealth: {economy.get_total_wealth():.2f} gold")
        print(f"  Resources: {economy.resources}")
        print()