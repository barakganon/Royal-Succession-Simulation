# run_simple_simulation.py
import random
import os
from utils.theme_manager import load_cultural_themes, get_theme

def run_simple_simulation():
    """
    A simplified simulation runner that just prints dynasty information
    without trying to run the full simulation engine.
    """
    print("--- Simple Dynasty Simulation ---")
    
    # Load themes
    themes_data = load_cultural_themes()
    if not themes_data:
        print("Error: No themes found. Please check the themes directory.")
        return
    
    # Select a random theme
    theme_key = random.choice(list(themes_data.keys()))
    theme = themes_data[theme_key]
    
    print(f"\nSelected Theme: {theme_key}")
    print(f"Description: {theme.get('description', 'No description')}")
    print(f"Start Year: {theme.get('start_year_suggestion', 1000)}")
    print(f"Culture: {theme.get('social_structure', 'Unknown')} in {theme.get('location_flavor', 'Unknown')}")
    
    # Generate a dynasty name
    dynasty_name = random.choice(theme.get('surnames_dynastic', ['DefaultDynasty']))
    print(f"\nGenerated Dynasty: House {dynasty_name}")
    
    # Generate founder
    founder_gender = random.choice(["MALE", "FEMALE"])
    if founder_gender == "MALE":
        founder_name = random.choice(theme.get('names_male', ['Founder']))
        founder_title = theme.get('founder_title_male', 'Leader')
    else:
        founder_name = random.choice(theme.get('names_female', ['Founder']))
        founder_title = theme.get('founder_title_female', 'Leader')
    
    print(f"Founder: {founder_name} {dynasty_name}, {founder_title}")
    
    # Generate some traits
    traits = random.sample(theme.get('common_traits', ['Generic']), min(3, len(theme.get('common_traits', ['Generic']))))
    print(f"Traits: {', '.join(traits)}")
    
    # Generate spouse
    spouse_gender = "FEMALE" if founder_gender == "MALE" else "MALE"
    if spouse_gender == "MALE":
        spouse_name = random.choice(theme.get('names_male', ['Spouse']))
        spouse_title = theme.get('default_noble_male', 'Noble')
    else:
        spouse_name = random.choice(theme.get('names_female', ['Spouse']))
        spouse_title = theme.get('default_noble_female', 'Noble')
    
    # Generate a different surname for spouse
    available_surnames = [s for s in theme.get('surnames_dynastic', ['OtherHouse']) if s != dynasty_name]
    spouse_surname = random.choice(available_surnames) if available_surnames else "OtherHouse"
    
    print(f"Spouse: {spouse_name} {spouse_surname}, {spouse_title}")
    
    # Generate some children
    num_children = random.randint(1, 4)
    print(f"\nChildren ({num_children}):")
    
    for i in range(num_children):
        child_gender = random.choice(["MALE", "FEMALE"])
        if child_gender == "MALE":
            child_name = random.choice(theme.get('names_male', ['Child']))
        else:
            child_name = random.choice(theme.get('names_female', ['Child']))
        
        # Apply surname convention
        surname_convention = theme.get('surname_convention', 'INHERITED_PATRILINEAL')
        if surname_convention == "PATRONYMIC":
            suffix = theme.get('patronymic_suffix_male' if child_gender == "MALE" else 'patronymic_suffix_female', 'child')
            child_surname = f"{founder_name}{suffix}"
        else:
            child_surname = dynasty_name
        
        birth_year = theme.get('start_year_suggestion', 1000) + random.randint(0, 10)
        print(f"  {i+1}. {child_name} {child_surname} (Born: {birth_year})")
    
    # Generate some events
    print("\nSample Events:")
    events = theme.get('events', [])
    if events:
        for i in range(min(3, len(events))):
            event = random.choice(events)
            event_name = event.get('name', 'Unknown Event')
            narrative = event.get('narrative', 'Something happened.')
            narrative = narrative.replace('{dynasty_name}', dynasty_name)
            narrative = narrative.replace('{location_flavor}', theme.get('location_flavor', 'the land'))
            if '{rival_clan_name}' in narrative:
                rival_name = random.choice([s for s in theme.get('surnames_dynastic', ['Rivals']) if s != dynasty_name]) if len(theme.get('surnames_dynastic', ['Rivals'])) > 1 else "Rivals"
                narrative = narrative.replace('{rival_clan_name}', rival_name)
            print(f"  - {event_name}: {narrative}")
    else:
        print("  No events defined for this theme.")
    
    print("\nSimple simulation completed successfully!")

if __name__ == "__main__":
    run_simple_simulation()