# models/traits.py
import random
from collections import defaultdict

class TraitDefinition:
    """Defines a character trait and its effects on gameplay."""
    def __init__(self, trait_id, name, description, category="personality"):
        self.trait_id = trait_id
        self.name = name
        self.description = description
        self.category = category  # personality, physical, acquired, etc.
        
        # Effect modifiers
        self.stat_modifiers = {}  # e.g., {"diplomacy": 2, "military": -1}
        self.event_chances = {}  # e.g., {"rebellion": 0.1, "feast_success": 0.2}
        self.opinion_modifiers = {}  # e.g., {"same_trait": 10, "opposite_trait": -15}
        
        # Trait relationships
        self.incompatible_with = []  # Traits that cannot coexist with this one
        self.leads_to = {}  # Traits this can evolve into, with conditions
        
        # Inheritance
        self.inheritance_chance = 0.0  # Base chance to inherit from parents
        self.is_genetic = False  # Whether trait is genetic
        
        # Acquisition
        self.acquisition_conditions = {}  # Conditions under which trait can be acquired
        
    def __repr__(self):
        return f"Trait({self.name}, {self.category})"


class TraitSystem:
    """Manages trait definitions and their effects on characters and events."""
    def __init__(self):
        self.trait_definitions = {}  # trait_id -> TraitDefinition
        self.trait_categories = defaultdict(list)  # category -> [trait_ids]
        
    def register_trait(self, trait_definition):
        """Register a trait definition in the system."""
        self.trait_definitions[trait_definition.trait_id] = trait_definition
        self.trait_categories[trait_definition.category].append(trait_definition.trait_id)
        
    def get_trait(self, trait_id):
        """Get a trait definition by ID."""
        return self.trait_definitions.get(trait_id)
    
    def get_traits_by_category(self, category):
        """Get all traits in a category."""
        trait_ids = self.trait_categories.get(category, [])
        return [self.trait_definitions[trait_id] for trait_id in trait_ids]
    
    def get_compatible_traits(self, existing_traits):
        """Get traits compatible with a character's existing traits."""
        incompatible_traits = set()
        for trait_id in existing_traits:
            trait_def = self.get_trait(trait_id)
            if trait_def:
                incompatible_traits.update(trait_def.incompatible_with)
        
        return [trait for trait_id, trait in self.trait_definitions.items() 
                if trait_id not in existing_traits and trait_id not in incompatible_traits]
    
    def calculate_inheritance(self, parent1_traits, parent2_traits):
        """Calculate which traits might be inherited by a child."""
        potential_traits = []
        
        # Check each parent's traits
        all_parent_traits = set(parent1_traits + parent2_traits)
        for trait_id in all_parent_traits:
            trait_def = self.get_trait(trait_id)
            if trait_def and trait_def.is_genetic:
                # Increase chance if both parents have the trait
                base_chance = trait_def.inheritance_chance
                if trait_id in parent1_traits and trait_id in parent2_traits:
                    chance = base_chance * 1.5  # 50% higher chance if both parents have it
                else:
                    chance = base_chance
                
                if random.random() < chance:
                    potential_traits.append(trait_id)
        
        return potential_traits
    
    def check_trait_acquisition(self, character, current_year, events=None):
        """Check if a character should acquire new traits based on conditions."""
        acquired_traits = []
        events = events or []
        
        # Get compatible traits
        compatible_traits = self.get_compatible_traits(character.traits)
        
        for trait in compatible_traits:
            conditions = trait.acquisition_conditions
            
            # Age-based acquisition
            if "min_age" in conditions and "max_age" in conditions:
                character_age = current_year - character.birth_year
                if conditions["min_age"] <= character_age <= conditions["max_age"]:
                    if random.random() < conditions.get("age_chance", 0.1):
                        acquired_traits.append(trait.trait_id)
                        continue
            
            # Event-based acquisition
            if "events" in conditions:
                for event in events:
                    if event["type"] in conditions["events"]:
                        if random.random() < conditions["events"][event["type"]]:
                            acquired_traits.append(trait.trait_id)
                            break
            
            # Role-based acquisition
            if "is_ruler" in conditions and character.is_monarch:
                if random.random() < conditions.get("ruler_chance", 0.1):
                    acquired_traits.append(trait.trait_id)
        
        return acquired_traits
    
    def calculate_opinion_modifier(self, character1_traits, character2_traits):
        """Calculate opinion modifier between two characters based on traits."""
        opinion_mod = 0
        
        # Check each trait of character1
        for trait_id in character1_traits:
            trait_def = self.get_trait(trait_id)
            if not trait_def:
                continue
            
            # Same trait bonus
            if trait_id in character2_traits and "same_trait" in trait_def.opinion_modifiers:
                opinion_mod += trait_def.opinion_modifiers["same_trait"]
            
            # Opposite trait penalty
            for opposite_trait in trait_def.incompatible_with:
                if opposite_trait in character2_traits and "opposite_trait" in trait_def.opinion_modifiers:
                    opinion_mod += trait_def.opinion_modifiers["opposite_trait"]
            
            # Specific trait opinions
            for other_trait, modifier in trait_def.opinion_modifiers.items():
                if other_trait in character2_traits and other_trait not in ["same_trait", "opposite_trait"]:
                    opinion_mod += modifier
        
        return opinion_mod
    
    def modify_event_chance(self, event_type, character_traits):
        """Modify the chance of an event based on character traits."""
        base_modifier = 0.0
        
        for trait_id in character_traits:
            trait_def = self.get_trait(trait_id)
            if trait_def and event_type in trait_def.event_chances:
                base_modifier += trait_def.event_chances[event_type]
        
        return base_modifier
    
    def get_stat_modifiers(self, character_traits):
        """Get stat modifiers from a character's traits."""
        modifiers = defaultdict(float)
        
        for trait_id in character_traits:
            trait_def = self.get_trait(trait_id)
            if trait_def:
                for stat, value in trait_def.stat_modifiers.items():
                    modifiers[stat] += value
        
        return dict(modifiers)


# Initialize the trait system with some example traits
def initialize_trait_system():
    """Initialize the trait system with a set of predefined traits."""
    system = TraitSystem()
    
    # --- Personality Traits ---
    
    # Brave
    brave = TraitDefinition("brave", "Brave", "Fearless in the face of danger", "personality")
    brave.stat_modifiers = {"military": 2, "personal_combat": 3}
    brave.event_chances = {"battle_victory": 0.1, "duel_victory": 0.15, "intimidate_success": 0.1}
    brave.opinion_modifiers = {"same_trait": 10, "craven": -15}
    brave.incompatible_with = ["craven"]
    brave.inheritance_chance = 0.15
    brave.is_genetic = True
    system.register_trait(brave)
    
    # Craven
    craven = TraitDefinition("craven", "Craven", "Fearful and cowardly", "personality")
    craven.stat_modifiers = {"military": -2, "personal_combat": -3, "intrigue": 1}
    craven.event_chances = {"battle_victory": -0.1, "flee_battle": 0.2, "assassination_target": 0.1}
    craven.opinion_modifiers = {"same_trait": 5, "brave": -15}
    craven.incompatible_with = ["brave"]
    craven.inheritance_chance = 0.1
    craven.is_genetic = True
    system.register_trait(craven)
    
    # Ambitious
    ambitious = TraitDefinition("ambitious", "Ambitious", "Driven to achieve greatness", "personality")
    ambitious.stat_modifiers = {"diplomacy": 1, "intrigue": 2, "stewardship": 1}
    ambitious.event_chances = {"usurp_attempt": 0.1, "faction_join": 0.15, "hard_work": 0.2}
    ambitious.opinion_modifiers = {"same_trait": -5, "ruler": -10}  # Ambitious people don't like other ambitious people or their rulers
    ambitious.incompatible_with = ["content"]
    ambitious.inheritance_chance = 0.2
    ambitious.is_genetic = True
    system.register_trait(ambitious)
    
    # Content
    content = TraitDefinition("content", "Content", "Satisfied with their station in life", "personality")
    content.stat_modifiers = {"diplomacy": 1, "intrigue": -1}
    content.event_chances = {"usurp_attempt": -0.1, "faction_join": -0.15, "stress_reduction": 0.2}
    content.opinion_modifiers = {"same_trait": 10, "ambitious": -5}
    content.incompatible_with = ["ambitious"]
    content.inheritance_chance = 0.1
    content.is_genetic = False
    system.register_trait(content)
    
    # Greedy
    greedy = TraitDefinition("greedy", "Greedy", "Desires wealth above all else", "personality")
    greedy.stat_modifiers = {"stewardship": 1, "diplomacy": -1}
    greedy.event_chances = {"embezzlement": 0.15, "tax_increase": 0.1, "gift_giving": -0.2}
    greedy.opinion_modifiers = {"same_trait": 5, "generous": -10}
    greedy.incompatible_with = ["generous"]
    greedy.inheritance_chance = 0.15
    greedy.is_genetic = True
    system.register_trait(greedy)
    
    # Generous
    generous = TraitDefinition("generous", "Generous", "Willing to share wealth with others", "personality")
    generous.stat_modifiers = {"diplomacy": 2, "stewardship": -1}
    generous.event_chances = {"gift_giving": 0.2, "charity": 0.15, "tax_increase": -0.1}
    generous.opinion_modifiers = {"same_trait": 10, "greedy": -10}
    generous.incompatible_with = ["greedy"]
    generous.inheritance_chance = 0.1
    generous.is_genetic = False
    system.register_trait(generous)
    
    # --- Physical Traits ---
    
    # Strong
    strong = TraitDefinition("strong", "Strong", "Physically powerful", "physical")
    strong.stat_modifiers = {"personal_combat": 5, "health": 1}
    strong.event_chances = {"duel_victory": 0.2, "disease_survival": 0.1}
    strong.opinion_modifiers = {"same_trait": 5, "weak": -5}
    strong.incompatible_with = ["weak", "frail"]
    strong.inheritance_chance = 0.25
    strong.is_genetic = True
    system.register_trait(strong)
    
    # Weak
    weak = TraitDefinition("weak", "Weak", "Physically feeble", "physical")
    weak.stat_modifiers = {"personal_combat": -3, "health": -1}
    weak.event_chances = {"duel_victory": -0.15, "disease_survival": -0.1}
    weak.opinion_modifiers = {"same_trait": 0, "strong": -5}
    weak.incompatible_with = ["strong"]
    weak.inheritance_chance = 0.2
    weak.is_genetic = True
    system.register_trait(weak)
    
    # Beautiful/Handsome
    attractive = TraitDefinition("attractive", "Attractive", "Physically appealing", "physical")
    attractive.stat_modifiers = {"diplomacy": 2}
    attractive.event_chances = {"marriage_offer": 0.2, "seduction_success": 0.15}
    attractive.opinion_modifiers = {"opposite_gender": 10}
    attractive.incompatible_with = ["ugly"]
    attractive.inheritance_chance = 0.3
    attractive.is_genetic = True
    system.register_trait(attractive)
    
    # Ugly
    ugly = TraitDefinition("ugly", "Ugly", "Physically unappealing", "physical")
    ugly.stat_modifiers = {"diplomacy": -1}
    ugly.event_chances = {"marriage_offer": -0.15, "seduction_success": -0.1}
    ugly.opinion_modifiers = {"opposite_gender": -5}
    ugly.incompatible_with = ["attractive"]
    ugly.inheritance_chance = 0.15
    ugly.is_genetic = True
    system.register_trait(ugly)
    
    # --- Acquired Traits ---
    
    # Stressed
    stressed = TraitDefinition("stressed", "Stressed", "Under significant mental strain", "health")
    stressed.stat_modifiers = {"health": -1, "intrigue": -1, "stewardship": -1}
    stressed.event_chances = {"mental_break": 0.1, "illness": 0.05}
    stressed.acquisition_conditions = {
        "events": {"major_defeat": 0.3, "family_death": 0.2, "betrayal": 0.4},
        "is_ruler": True,
        "ruler_chance": 0.05  # Chance per year for rulers
    }
    system.register_trait(stressed)
    
    # Wounded
    wounded = TraitDefinition("wounded", "Wounded", "Suffering from a significant injury", "health")
    wounded.stat_modifiers = {"health": -2, "personal_combat": -3}
    wounded.event_chances = {"death": 0.05, "infection": 0.1}
    wounded.leads_to = {"scarred": {"chance": 0.3, "min_years": 2}}  # Can become scarred after 2 years
    wounded.acquisition_conditions = {
        "events": {"battle": 0.1, "duel": 0.3, "assassination_attempt": 0.5}
    }
    system.register_trait(wounded)
    
    # Scarred
    scarred = TraitDefinition("scarred", "Scarred", "Bearing visible scars from past wounds", "health")
    scarred.stat_modifiers = {"personal_combat": 1, "intimidation": 2}
    scarred.opinion_modifiers = {"brave": 5}
    scarred.acquisition_conditions = {
        "from_trait": {"wounded": 0.3}  # Can be acquired from wounded trait
    }
    system.register_trait(scarred)
    
    # Drunkard
    drunkard = TraitDefinition("drunkard", "Drunkard", "Regularly overindulges in alcohol", "lifestyle")
    drunkard.stat_modifiers = {"diplomacy": -1, "stewardship": -2, "health": -1}
    drunkard.event_chances = {"embarrassing_incident": 0.2, "health_crisis": 0.1}
    drunkard.opinion_modifiers = {"same_trait": 10, "temperate": -10}
    drunkard.acquisition_conditions = {
        "events": {"feast": 0.05, "depression": 0.1},
        "min_age": 16,
        "max_age": 80,
        "age_chance": 0.01  # Small chance per year
    }
    system.register_trait(drunkard)
    
    # --- Leadership Traits ---
    
    # Just
    just = TraitDefinition("just", "Just", "Fair and equitable ruler", "leadership")
    just.stat_modifiers = {"diplomacy": 2, "stewardship": 1}
    just.event_chances = {"peasant_revolt": -0.1, "vassal_loyalty": 0.1}
    just.opinion_modifiers = {"subjects": 10, "cruel": -15}
    just.incompatible_with = ["cruel", "arbitrary"]
    just.acquisition_conditions = {
        "is_ruler": True,
        "ruler_chance": 0.05,
        "min_age": 20,
        "max_age": 50
    }
    system.register_trait(just)
    
    # Cruel
    cruel = TraitDefinition("cruel", "Cruel", "Harsh and merciless ruler", "leadership")
    cruel.stat_modifiers = {"intrigue": 2, "diplomacy": -2}
    cruel.event_chances = {"peasant_revolt": 0.1, "intimidate_success": 0.2}
    cruel.opinion_modifiers = {"subjects": -10, "just": -15}
    cruel.incompatible_with = ["just", "kind"]
    cruel.acquisition_conditions = {
        "is_ruler": True,
        "ruler_chance": 0.05,
        "events": {"execute_prisoner": 0.2, "torture": 0.5}
    }
    system.register_trait(cruel)
    
    return system


# Example usage
if __name__ == "__main__":
    # Initialize the trait system
    trait_system = initialize_trait_system()
    
    # Example: Calculate inheritance
    parent1_traits = ["brave", "strong", "ambitious"]
    parent2_traits = ["attractive", "just", "ambitious"]
    
    inherited_traits = trait_system.calculate_inheritance(parent1_traits, parent2_traits)
    print(f"Child inherited traits: {inherited_traits}")
    
    # Example: Calculate opinion modifier
    character1_traits = ["brave", "ambitious", "strong"]
    character2_traits = ["craven", "content", "weak"]
    
    opinion_mod = trait_system.calculate_opinion_modifier(character1_traits, character2_traits)
    print(f"Opinion modifier: {opinion_mod}")
    
    # Example: Modify event chance
    event_type = "battle_victory"
    character_traits = ["brave", "strong", "ambitious"]
    
    chance_mod = trait_system.modify_event_chance(event_type, character_traits)
    print(f"Event chance modifier for {event_type}: {chance_mod}")
    
    # Example: Get stat modifiers
    stat_mods = trait_system.get_stat_modifiers(character_traits)
    print(f"Stat modifiers: {stat_mods}")