# models/politics.py
import random
from collections import defaultdict

class CourtPosition:
    """Represents a position in the ruler's court."""
    def __init__(self, position_id, name, description):
        self.position_id = position_id
        self.name = name
        self.description = description
        
        # Effects of this position
        self.stat_bonuses = {}  # e.g., {"stewardship": 2} - bonuses to dynasty stats
        self.resource_bonuses = {}  # e.g., {"gold": 0.1} - percentage bonuses to resources
        self.event_modifiers = {}  # e.g., {"revolt": -0.05} - modifies event chances
        
        # Requirements
        self.min_stats = {}  # e.g., {"diplomacy": 8} - minimum stats required
        self.required_traits = []  # Traits required for this position
        self.forbidden_traits = []  # Traits that disqualify from this position
        
        # Risks
        self.corruption_chance = 0.0  # Chance of embezzlement
        self.betrayal_chance = 0.0  # Chance of betrayal
        
        # Compensation
        self.prestige_gain = 0  # Prestige gained by holder
        self.wealth_cost = 0  # Cost to the dynasty
        
    def __repr__(self):
        return f"CourtPosition({self.name})"


class Courtier:
    """Represents a non-family character in the court."""
    def __init__(self, courtier_id, name, gender, age, culture=None):
        self.courtier_id = courtier_id
        self.name = name
        self.gender = gender
        self.age = age
        self.culture = culture
        
        # Attributes
        self.stats = {
            "diplomacy": random.randint(1, 10),
            "martial": random.randint(1, 10),
            "stewardship": random.randint(1, 10),
            "intrigue": random.randint(1, 10),
            "learning": random.randint(1, 10)
        }
        self.traits = []
        
        # Relationships
        self.opinions = {}  # person_id -> opinion value
        self.relationships = {}  # person_id -> relationship type
        
        # Position
        self.position = None  # Current court position
        
        # Faction
        self.faction = None  # Current faction
        self.faction_role = None  # Role in faction
        
        # History
        self.joined_year = None
        self.events = []
        
    def calculate_competence(self, position):
        """Calculate how competent this courtier is for a position."""
        competence = 0
        
        # Check relevant stats
        for stat, value in position.min_stats.items():
            if stat in self.stats:
                # Add bonus for exceeding minimum
                if self.stats[stat] >= value:
                    competence += (self.stats[stat] - value) + 5
                else:
                    # Penalty for not meeting minimum
                    competence -= (value - self.stats[stat]) * 2
        
        # Check traits
        for trait in position.required_traits:
            if trait in self.traits:
                competence += 10
            else:
                competence -= 5
                
        for trait in position.forbidden_traits:
            if trait in self.traits:
                competence -= 15
        
        # Age factor - prime age is 30-50
        if 30 <= self.age <= 50:
            competence += 5
        elif self.age < 20:
            competence -= (20 - self.age) * 2
        elif self.age > 60:
            competence -= (self.age - 60)
        
        return max(0, competence)
    
    def calculate_loyalty(self, ruler_id, trait_system=None):
        """Calculate loyalty to the ruler."""
        base_loyalty = self.opinions.get(ruler_id, 0)
        
        # Trait effects
        if trait_system and self.traits:
            ruler_traits = []  # Would need to be passed in
            trait_opinion = trait_system.calculate_opinion_modifier(self.traits, ruler_traits)
            base_loyalty += trait_opinion
        
        # Position effect
        if self.position:
            base_loyalty += 10  # Holding a position increases loyalty
        
        # Faction effect
        if self.faction and self.faction.is_against_ruler:
            base_loyalty -= 20
        
        return base_loyalty
    
    def update_opinion(self, person_id, change):
        """Update opinion of another person."""
        current = self.opinions.get(person_id, 0)
        self.opinions[person_id] = max(-100, min(100, current + change))
        return self.opinions[person_id]
    
    def __repr__(self):
        position_str = f", {self.position.name}" if self.position else ""
        return f"Courtier({self.name}, {self.gender}, {self.age}{position_str})"


class Faction:
    """Represents a political faction within the court."""
    def __init__(self, faction_id, name, goal):
        self.faction_id = faction_id
        self.name = name
        self.goal = goal  # e.g., "replace_ruler", "change_policy", "independence"
        self.is_against_ruler = goal in ["replace_ruler", "independence"]
        
        self.leader_id = None
        self.members = {}  # courtier_id -> role
        self.power = 0  # Current faction power
        self.secrecy = 0  # How well the faction hides its activities (0-100)
        
        self.target_id = None  # Target of the faction (e.g., preferred new ruler)
        self.progress = 0  # Progress toward goal (0-100)
        
        self.active = True
        self.formed_year = None
        self.events = []
    
    def calculate_power(self, court):
        """Calculate the faction's power based on its members."""
        power = 0
        
        for courtier_id, role in self.members.items():
            courtier = court.get_courtier(courtier_id)
            if not courtier:
                continue
                
            # Base power from role
            role_power = {
                "leader": 10,
                "core": 5,
                "supporter": 2,
                "sympathizer": 1
            }.get(role, 0)
            
            # Add power from position
            if courtier.position:
                position_power = {
                    "chancellor": 8,
                    "marshal": 7,
                    "steward": 6,
                    "spymaster": 9,
                    "chaplain": 5
                }.get(courtier.position.position_id, 3)
                
                role_power += position_power
            
            power += role_power
        
        self.power = power
        return power
    
    def add_member(self, courtier_id, role="supporter"):
        """Add a member to the faction."""
        self.members[courtier_id] = role
        if role == "leader":
            self.leader_id = courtier_id
    
    def remove_member(self, courtier_id):
        """Remove a member from the faction."""
        if courtier_id in self.members:
            if courtier_id == self.leader_id:
                self.leader_id = None
            del self.members[courtier_id]
    
    def __repr__(self):
        return f"Faction({self.name}, goal={self.goal}, members={len(self.members)})"


class Court:
    """Manages the political court of a dynasty."""
    def __init__(self, dynasty_id, ruler_id=None):
        self.dynasty_id = dynasty_id
        self.ruler_id = ruler_id
        
        # Court members
        self.courtiers = {}  # courtier_id -> Courtier
        self.positions = {}  # position_id -> CourtPosition
        self.appointments = {}  # position_id -> courtier_id
        
        # Factions
        self.factions = {}  # faction_id -> Faction
        
        # Court stats
        self.stability = 100  # 0-100, affects faction formation
        self.efficiency = 100  # 0-100, affects position bonuses
        self.corruption = 0  # 0-100, affects resource drain
        
        # Court events
        self.event_history = []
        
        # Initialize court positions
        self._initialize_positions()
    
    def _initialize_positions(self):
        """Initialize standard court positions."""
        # Chancellor - diplomacy
        chancellor = CourtPosition("chancellor", "Chancellor", "Chief diplomat and advisor")
        chancellor.stat_bonuses = {"diplomacy": 3}
        chancellor.resource_bonuses = {"gold": 0.05}
        chancellor.min_stats = {"diplomacy": 8}
        self.positions["chancellor"] = chancellor
        
        # Marshal - military
        marshal = CourtPosition("marshal", "Marshal", "Military commander")
        marshal.stat_bonuses = {"martial": 3}
        marshal.resource_bonuses = {"levies": 0.1}
        marshal.min_stats = {"martial": 8}
        self.positions["marshal"] = marshal
        
        # Steward - economy
        steward = CourtPosition("steward", "Steward", "Economic administrator")
        steward.stat_bonuses = {"stewardship": 3}
        steward.resource_bonuses = {"gold": 0.1, "grain": 0.05}
        steward.min_stats = {"stewardship": 8}
        self.positions["steward"] = steward
        
        # Spymaster - intrigue
        spymaster = CourtPosition("spymaster", "Spymaster", "Intelligence gatherer")
        spymaster.stat_bonuses = {"intrigue": 3}
        spymaster.min_stats = {"intrigue": 8}
        self.positions["spymaster"] = spymaster
        
        # Court Chaplain - religion
        chaplain = CourtPosition("chaplain", "Court Chaplain", "Religious advisor")
        chaplain.stat_bonuses = {"learning": 3}
        chaplain.min_stats = {"learning": 8}
        self.positions["chaplain"] = chaplain
    
    def add_courtier(self, name, gender, age, culture=None, stats=None, traits=None):
        """Add a new courtier to the court."""
        courtier_id = len(self.courtiers) + 1
        courtier = Courtier(courtier_id, name, gender, age, culture)
        
        # Set custom stats if provided
        if stats:
            for stat, value in stats.items():
                if stat in courtier.stats:
                    courtier.stats[stat] = value
        
        # Set traits if provided
        if traits:
            courtier.traits = list(traits)
        
        self.courtiers[courtier_id] = courtier
        return courtier
    
    def get_courtier(self, courtier_id):
        """Get a courtier by ID."""
        return self.courtiers.get(courtier_id)
    
    def appoint_to_position(self, courtier_id, position_id):
        """Appoint a courtier to a position."""
        if position_id not in self.positions or courtier_id not in self.courtiers:
            return False
        
        # Remove current holder if any
        if position_id in self.appointments:
            old_holder_id = self.appointments[position_id]
            old_holder = self.courtiers.get(old_holder_id)
            if old_holder:
                old_holder.position = None
                if self.ruler_id:
                    old_holder.update_opinion(self.ruler_id, -10)  # Upset about removal
        
        # Set new holder
        courtier = self.courtiers[courtier_id]
        courtier.position = self.positions[position_id]
        self.appointments[position_id] = courtier_id
        
        # Update opinion of ruler
        if self.ruler_id:
            courtier.update_opinion(self.ruler_id, 15)  # Happy about appointment
        
        return True
    
    def yearly_update(self, current_year, trait_system=None):
        """Process yearly court updates."""
        events = []
        
        # Update court stats
        self._update_court_stats()
        
        # Update factions
        for faction in self.factions.values():
            if faction.active:
                faction.calculate_power(self)
        
        # Generate a random court event
        if random.random() < 0.2:  # 20% chance per year
            event_types = ["feast", "scandal", "diplomatic_mission", "court_intrigue"]
            event_type = random.choice(event_types)
            
            events.append({
                "type": event_type,
                "year": current_year,
                "description": f"A {event_type.replace('_', ' ')} occurred at court in year {current_year}."
            })
        
        return events
    
    def _update_court_stats(self):
        """Update court stats based on current situation."""
        # Simple implementation - random fluctuations
        self.stability = max(0, min(100, self.stability + random.randint(-5, 5)))
        self.efficiency = max(0, min(100, self.efficiency + random.randint(-3, 3)))
        self.corruption = max(0, min(100, self.corruption + random.randint(-2, 2)))
    
    def __repr__(self):
        return f"Court(dynasty={self.dynasty_id}, courtiers={len(self.courtiers)}, factions={len(self.factions)})"


# Example usage
if __name__ == "__main__":
    # Create a court
    court = Court(dynasty_id=1, ruler_id=100)
    
    # Add some courtiers
    chancellor = court.add_courtier("Lord Blackwood", "MALE", 45, traits=["ambitious", "deceitful"])
    chancellor.stats["diplomacy"] = 12
    
    marshal = court.add_courtier("Sir Redshield", "MALE", 38, traits=["brave", "strong"])
    marshal.stats["martial"] = 14
    
    # Appoint to positions
    court.appoint_to_position(chancellor.courtier_id, "chancellor")
    court.appoint_to_position(marshal.courtier_id, "marshal")
    
    # Create a faction
    faction = court.factions[1] = Faction(1, "Reform Faction", "change_policy")
    faction.add_member(chancellor.courtier_id, "leader")
    
    # Run a few years of simulation
    for year in range(1000, 1010):
        events = court.yearly_update(year)
        print(f"Year {year}:")
        for event in events:
            print(f"  {event['description']}")
        print(f"  Court stability: {court.stability}")
        print()