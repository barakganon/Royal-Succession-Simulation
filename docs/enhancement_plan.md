# Simulation Enhancement Plan

This document outlines the plan for enhancing the Royal Succession Simulation with deeper mechanics in three key areas:

## 1. Economic Systems

### Current State
The current system has a basic wealth attribute for dynasties that can increase or decrease based on events, but lacks a comprehensive economic model.

### Enhancement Plan

#### 1.1 Resource Management
- **Resource Types**: Implement multiple resource types (gold, grain, timber, etc.) based on cultural themes
- **Production**: Annual resource production based on dynasty holdings
- **Consumption**: Resource consumption based on population and lifestyle
- **Trade**: Allow trading resources with other dynasties or external entities

#### 1.2 Holdings System
- **Land Holdings**: Implement a system of land holdings that generate resources
- **Buildings**: Allow construction of buildings that improve resource production
- **Improvements**: Allow improvements to holdings that provide bonuses

#### 1.3 Economic Events
- **Market Fluctuations**: Events that affect resource values
- **Trade Opportunities**: Special events that allow profitable trade
- **Economic Crises**: Famines, inflation, or other economic challenges

#### 1.4 Implementation Approach
```python
# Example economic system structure
class EconomyManager:
    def __init__(self, dynasty):
        self.dynasty = dynasty
        self.resources = {
            "gold": 100,
            "grain": 500,
            "timber": 200,
            # Other resources based on cultural theme
        }
        self.holdings = []
        self.trade_agreements = []
        
    def yearly_update(self):
        # Calculate production from holdings
        self.calculate_production()
        # Calculate consumption
        self.calculate_consumption()
        # Process trade agreements
        self.process_trade()
        # Random economic events
        self.process_economic_events()
        
    def calculate_production(self):
        # Base production
        production = {resource: 0 for resource in self.resources}
        
        # Add production from holdings
        for holding in self.holdings:
            for resource, amount in holding.get_production().items():
                production[resource] += amount
                
        # Apply modifiers from traits, events, etc.
        # ...
        
        # Add to resources
        for resource, amount in production.items():
            self.resources[resource] += amount
            
        return production
```

## 2. Trait Impact Enhancement

### Current State
Characters have traits, but these have limited impact on gameplay beyond narrative flavor.

### Enhancement Plan

#### 2.1 Trait Effects System
- **Stat Modifiers**: Traits affect character capabilities (fertility, diplomacy, etc.)
- **Event Triggers**: Traits trigger specific events
- **Event Outcomes**: Traits modify event outcomes

#### 2.2 Trait Inheritance
- **Genetic Traits**: Some traits have a chance to be inherited from parents
- **Acquired Traits**: Characters can gain traits through events or age
- **Trait Conflicts**: Some traits are incompatible with others

#### 2.3 Trait-Based Decisions
- **Decision Options**: Available decisions based on traits
- **Decision Outcomes**: Success probability modified by traits

#### 2.4 Implementation Approach
```python
# Example trait system enhancement
class TraitSystem:
    def __init__(self):
        self.trait_definitions = {
            "Brave": {
                "stat_modifiers": {"military": 2, "health": 1},
                "event_chances": {"battle_victory": 0.2},
                "incompatible_with": ["Cowardly"],
                "inheritance_chance": 0.3
            },
            "Greedy": {
                "stat_modifiers": {"economy": 1, "diplomacy": -1},
                "event_chances": {"embezzlement": 0.1, "trade_bonus": 0.15},
                "incompatible_with": ["Generous"],
                "inheritance_chance": 0.2
            },
            # More traits...
        }
    
    def apply_trait_effects(self, person, event_type):
        """Calculate how traits affect an event outcome"""
        base_chance = 0.5  # Default chance
        
        for trait in person.traits:
            if trait in self.trait_definitions:
                trait_def = self.trait_definitions[trait]
                if event_type in trait_def.get("event_chances", {}):
                    base_chance += trait_def["event_chances"][event_type]
        
        return base_chance
```

## 3. Internal Politics Mechanics

### Current State
The simulation focuses on succession and family relationships but lacks internal political dynamics.

### Enhancement Plan

#### 3.1 Court System
- **Courtiers**: Non-family characters with roles in the dynasty
- **Factions**: Groups with shared interests that can support or oppose the ruler
- **Court Positions**: Appointable roles that provide bonuses and risks

#### 3.2 Loyalty and Opinion System
- **Character Opinions**: Each character has opinions of others
- **Loyalty Mechanics**: Characters' loyalty affects their actions
- **Relationship Development**: Relationships evolve based on interactions

#### 3.3 Political Events
- **Conspiracies**: Plots against the ruler or other characters
- **Power Struggles**: Conflicts between factions
- **Court Intrigue**: Events based on court dynamics

#### 3.4 Implementation Approach
```python
# Example court system
class Court:
    def __init__(self, dynasty):
        self.dynasty = dynasty
        self.positions = {
            "Steward": None,
            "Marshal": None,
            "Chancellor": None,
            "Spymaster": None,
            # More positions based on cultural theme
        }
        self.courtiers = []
        self.factions = []
        
    def yearly_update(self):
        # Update courtier opinions
        self.update_opinions()
        # Check for faction activities
        self.process_faction_activities()
        # Process court events
        self.process_court_events()
        
    def appoint_to_position(self, person, position):
        """Appoint a person to a court position"""
        if position in self.positions:
            # Remove current holder if any
            if self.positions[position]:
                old_holder = self.positions[position]
                old_holder.modify_opinion(self.dynasty.current_monarch, -10)  # Upset about removal
                
            # Set new holder
            self.positions[position] = person
            person.modify_opinion(self.dynasty.current_monarch, 15)  # Happy about appointment
            
            # Apply position effects
            self.apply_position_effects(position)
            
            return True
        return False
```

## Implementation Timeline

### Phase 1: Foundation (1-2 weeks)
- Design data structures for all three systems
- Update database models to support new features
- Create basic UI elements for the web interface

### Phase 2: Economic System (2-3 weeks)
- Implement resource types and production
- Add holdings system
- Create economic events
- Update UI to display economic information

### Phase 3: Trait System (2-3 weeks)
- Enhance trait definitions with effects
- Implement trait inheritance
- Add trait-based event modifications
- Update character UI to show trait impacts

### Phase 4: Politics System (3-4 weeks)
- Implement court and positions
- Add opinion and loyalty system
- Create faction mechanics
- Develop political events

### Phase 5: Integration and Testing (2-3 weeks)
- Integrate all systems
- Balance gameplay
- Fix bugs
- Optimize performance

## Expected Outcomes

These enhancements will significantly deepen the simulation by:

1. **Creating Economic Challenges**: Dynasties will face resource management decisions
2. **Making Characters More Unique**: Traits will meaningfully impact gameplay
3. **Adding Political Depth**: Internal politics will create new storytelling opportunities

The simulation will move from being primarily a family tree generator to a comprehensive dynasty management system with multiple interconnected systems that create emergent gameplay and storytelling.