"""Turn processor — lifecycle simulation for a dynasty.

This module owns ALL of the per-year lifecycle logic that advances a dynasty:
- Death checks
- Marriage checks
- Childbirth checks
- Succession resolution
- World events
- Family-tree visualization snapshot

Sprint 1 of the master plan extracted this code from ``blueprints/dynasty.py``
without changing behavior, so that subsequent sprints (variable-length turns,
project model, succession drama) can extend it without bloating the route file.

Sprint 8 will replace ``generate_family_tree_visualization`` with an SVG-based
renderer; the function is kept here for now so the public ``process_dynasty_turn``
contract stays identical.

All public entry points return the same shapes they did when they lived in the
blueprint, so this is a pure refactor — no caller changes required other than
the import path.
"""

import os
import json
import random
import logging

from models.db_models import (
    db, DynastyDB, PersonDB, HistoryLogEntryDB
)
from models.banking_system import BankingSystem
from utils.theme_manager import get_all_theme_names, get_theme
from utils.llm_prompts import build_turn_story_prompt, generate_turn_story_fallback

logger = logging.getLogger('royal_succession.turn_processor')

INTERRUPT_REASONS = [
    'monarch_death',
    'heir_majority',
    'project_complete',
    'war_declared',
    'attack_received',
    'major_world_event',
    'story_moment',
    'quiet_period',
]


# ---------------------------------------------------------------------------
# LLM availability — resolved lazily so this module does not depend on Flask
# being imported at module load time.  Pure helper functions can still call
# the LLM by going through this indirection.
# ---------------------------------------------------------------------------

def _llm_available() -> bool:
    """Return True if the LLM API key is present in the running Flask app.

    Imports flask lazily so the module remains importable in pure-Python
    contexts (e.g. unit tests that don't spin up the app).
    """
    try:
        from flask import current_app
        return current_app.config.get('FLASK_APP_GOOGLE_API_KEY_PRESENT', False)
    except Exception:
        return False


# ===========================================================================
# Public entry point
# ===========================================================================

def process_dynasty_turn(dynasty_id: int, years_to_advance: int = 5):
    """Process a turn for the dynasty, advancing the simulation by the specified number of years.

    Returns ``(success: bool, message: str, turn_summary: dict | None)``.

    The 3-tuple shape is preserved exactly so existing callers in
    ``blueprints/dynasty.py`` (advance_turn, submit_actions) keep working.
    """
    dynasty = DynastyDB.query.get(dynasty_id)
    if not dynasty:
        return False, "Dynasty not found"

    # Load theme configuration
    theme_config = {}
    if dynasty.theme_identifier_or_json:
        if dynasty.theme_identifier_or_json in get_all_theme_names():
            # Predefined theme
            theme_config = get_theme(dynasty.theme_identifier_or_json)
        else:
            # Custom theme stored as JSON
            try:
                theme_config = json.loads(dynasty.theme_identifier_or_json)
            except json.JSONDecodeError:
                return False, "Invalid theme configuration"

    # Get all living persons in the dynasty
    living_persons = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        death_year=None
    ).all()

    # Get current monarch (queried but not used directly here — kept for parity
    # with the legacy flow; lifecycle helpers re-query as needed)
    _ = PersonDB.query.filter_by(
        dynasty_id=dynasty_id,
        is_monarch=True,
        death_year=None
    ).first()

    # Process each year — interrupt-driven loop (Sprint 1)
    start_year = dynasty.current_simulation_year
    interrupt = None
    years_advanced = 0

    while years_advanced < years_to_advance and interrupt is None:
        current_year = start_year + years_advanced
        try:
            # Process world events
            process_world_events(dynasty, current_year, theme_config)

            # Process each person's yearly events
            for person in living_persons:
                # Skip if person died in a previous year of this turn
                if person.death_year is not None:
                    continue

                # Process death check
                if process_death_check(person, current_year, theme_config):
                    # Person died, check if they were the monarch
                    if person.is_monarch:
                        process_succession(dynasty, person, current_year, theme_config)
                        interrupt = ('monarch_death', current_year)
                    continue

                # Process marriage for unmarried nobles
                if person.is_noble and person.spouse_sim_id is None:
                    process_marriage_check(dynasty, person, current_year, theme_config)

                # Process childbirth for married women
                if person.gender == "FEMALE" and person.spouse_sim_id is not None:
                    process_childbirth_check(dynasty, person, current_year, theme_config)

            # Update living persons list (remove those who died)
            living_persons = [p for p in living_persons if p.death_year is None]
        except Exception as year_exc:
            logger.error(f"Error processing year {current_year} for dynasty {dynasty_id}: {year_exc}", exc_info=True)
            # Continue to next year rather than aborting entire turn

        years_advanced += 1
        dynasty.current_simulation_year = current_year + 1

    if interrupt is None:
        interrupt = ('quiet_period', years_advanced)

    # Generate family tree visualization
    try:
        generate_family_tree_visualization(dynasty, theme_config)
    except Exception as e:
        logger.error(f"Error generating family tree: {e}", exc_info=True)

    try:
        db.session.commit()
    except Exception as commit_error:
        db.session.rollback()
        logger.error(f"Error committing changes: {commit_error}", exc_info=True)
        return False, f"Error advancing turn: {commit_error}", None

    # --- Banking: accrue interest on active loans ---
    try:
        banking = BankingSystem(db.session)
        banking.accrue_interest_for_dynasty(dynasty_id)
    except Exception as bank_exc:
        logger.error(f"Error accruing loan interest for dynasty {dynasty_id}: {bank_exc}", exc_info=True)

    # Collect events created during this turn from HistoryLogEntryDB
    new_events = HistoryLogEntryDB.query.filter(
        HistoryLogEntryDB.dynasty_id == dynasty_id,
        HistoryLogEntryDB.year >= start_year,
        HistoryLogEntryDB.year < dynasty.current_simulation_year
    ).order_by(HistoryLogEntryDB.year).all()

    # --- Epic Story Generation (one paragraph per turn) ---
    new_paragraph = ""
    try:
        event_texts = [e.event_string for e in new_events if e.event_string]
        monarch_obj = PersonDB.query.filter_by(
            dynasty_id=dynasty_id, is_monarch=True, death_year=None
        ).first()
        monarch_display = (
            f"{monarch_obj.name} {monarch_obj.surname}" if monarch_obj else dynasty.name
        )
        existing_story = dynasty.epic_story_text or ""
        if _llm_available():
            try:
                import google.generativeai as genai
                from flask import current_app
                api_key = current_app.config.get("FLASK_APP_GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    prompt = build_turn_story_prompt(
                        dynasty_name=dynasty.name,
                        start_year=start_year,
                        end_year=dynasty.current_simulation_year - 1,
                        events=event_texts,
                        monarch_name=monarch_display,
                        existing_story=existing_story,
                    )
                    response = model.generate_content(
                        prompt,
                        generation_config={"max_output_tokens": 300, "temperature": 0.85},
                    )
                    new_paragraph = response.text.strip() if response.text else ""
            except Exception:
                new_paragraph = ""
        if not new_paragraph:
            new_paragraph = generate_turn_story_fallback(
                dynasty.name, start_year, dynasty.current_simulation_year - 1, event_texts, monarch_display
            )
        if new_paragraph:
            separator = "\n\n" if existing_story.strip() else ""
            dynasty.epic_story_text = existing_story + separator + new_paragraph
            db.session.commit()
    except Exception as story_err:
        logger.error(f"Error generating turn story for dynasty {dynasty_id}: {story_err}", exc_info=True)

    living_count = PersonDB.query.filter_by(dynasty_id=dynasty_id, death_year=None).count()
    dynasty_obj = DynastyDB.query.get(dynasty_id)
    current_wealth = dynasty_obj.current_wealth if dynasty_obj else 0

    turn_summary = {
        'start_year': start_year,
        'end_year': dynasty.current_simulation_year,
        'years_advanced': years_advanced,
        'interrupt_reason': interrupt[0],
        'events': [
            {
                'type': e.event_type or 'event',
                'year': e.year,
                'text': e.event_string,
            }
            for e in new_events
        ],
        'living_count': living_count,
        'current_wealth': current_wealth,
        'new_story_paragraph': new_paragraph,
    }

    return True, f"Advanced {years_advanced} years from {start_year} to {dynasty.current_simulation_year}.", turn_summary


# ===========================================================================
# Lifecycle helpers
# ===========================================================================

def process_death_check(person: PersonDB, current_year: int, theme_config: dict):
    """Check if a person dies this year."""
    age = current_year - person.birth_year

    # Base mortality chance increases with age
    base_mortality = 0.01  # 1% base chance

    # Age modifiers
    if age < 5:
        # Child mortality
        base_mortality = 0.15 * theme_config.get("mortality_factor", 1.0)
    elif age > 60:
        # Elderly mortality increases
        base_mortality = 0.05 * theme_config.get("mortality_factor", 1.0)
        if age > 75:
            base_mortality += 0.15 * theme_config.get("mortality_factor", 1.0)

    # Check against themed max age
    max_age = 85 * theme_config.get("max_age_factor", 1.0)
    if age > max_age:
        base_mortality = 1.0  # Guaranteed death if past max age

    # Roll for death
    if random.random() < base_mortality:
        person.death_year = current_year

        # Log death
        death_log = HistoryLogEntryDB(
            dynasty_id=person.dynasty_id,
            year=current_year,
            event_string=f"{person.name} {person.surname} passed away at the age of {age}.",
            person1_sim_id=person.id,
            event_type="death"
        )
        db.session.add(death_log)
        return True

    return False


def process_marriage_check(dynasty: DynastyDB, person: PersonDB, current_year: int, theme_config: dict):
    """Check if an unmarried noble gets married this year."""
    age = current_year - person.birth_year

    # Check if person is of marriageable age
    min_marriage_age = 16
    max_marriage_age = 45 if person.gender == "FEMALE" else 55

    if age < min_marriage_age or age > max_marriage_age:
        return False

    # Base chance to seek marriage
    marriage_chance = 0.35

    # Roll for marriage
    if random.random() < marriage_chance:
        # Create a spouse
        spouse_gender = "FEMALE" if person.gender == "MALE" else "MALE"
        name_key = "names_male" if spouse_gender == "MALE" else "names_female"
        spouse_name = random.choice(theme_config.get(name_key, ["Spouse"]))

        # Choose a different surname for spouse
        available_surnames = theme_config.get("surnames_dynastic", ["OtherHouse"])
        spouse_surname = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "OtherHouse"

        # Determine spouse age
        spouse_age = random.randint(min_marriage_age, max_marriage_age)
        if person.gender == "MALE":
            # Males often marry younger females
            spouse_age = min(age - random.randint(0, 7), max_marriage_age)
        else:
            # Females often marry older males
            spouse_age = max(age + random.randint(0, 7), min_marriage_age)

        spouse_birth_year = current_year - spouse_age

        spouse = PersonDB(
            dynasty_id=dynasty.id,
            name=spouse_name,
            surname=spouse_surname,
            gender=spouse_gender,
            birth_year=spouse_birth_year,
            is_noble=person.is_noble
        )

        # Set spouse traits
        spouse_traits = []
        available_traits = theme_config.get("common_traits", ["Noble"])
        if available_traits:
            num_traits = min(2, len(available_traits))
            spouse_traits = random.sample(available_traits, num_traits)
        spouse.set_traits(spouse_traits)

        # Set spouse titles
        default_title_key = "default_noble_male" if spouse_gender == "MALE" else "default_noble_female"
        spouse_title = theme_config.get(default_title_key, "Noble")
        spouse.set_titles([spouse_title])

        db.session.add(spouse)
        db.session.flush()  # Get ID without committing
        spouse.generate_portrait()

        # Link spouse and person
        person.spouse_sim_id = spouse.id
        spouse.spouse_sim_id = person.id

        # Log marriage
        marriage_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{person.name} {person.surname} and {spouse.name} {spouse.surname} were united in marriage.",
            person1_sim_id=person.id,
            person2_sim_id=spouse.id,
            event_type="marriage"
        )
        db.session.add(marriage_log)
        return True

    return False


def process_childbirth_check(dynasty: DynastyDB, woman: PersonDB, current_year: int, theme_config: dict):
    """Check if a married woman has a child this year."""
    age = current_year - woman.birth_year

    # Check if woman is of childbearing age
    min_fertility_age = 18
    max_fertility_age = 45

    if age < min_fertility_age or age > max_fertility_age:
        return False

    # Check if spouse exists
    if woman.spouse_sim_id is None:
        return False

    spouse = PersonDB.query.get(woman.spouse_sim_id)
    if not spouse or spouse.death_year is not None:
        return False

    # Check max children
    existing_children = PersonDB.query.filter(
        (PersonDB.mother_sim_id == woman.id) |
        (PersonDB.father_sim_id == woman.id)
    ).count()

    max_children = 8 * theme_config.get("max_children_factor", 1.0)
    if existing_children >= max_children:
        return False

    # Base chance for pregnancy
    pregnancy_chance = 0.4 * theme_config.get("pregnancy_chance_factor", 1.0)

    # Roll for pregnancy
    if random.random() < pregnancy_chance:
        # Determine child's gender
        child_gender = random.choice(["MALE", "FEMALE"])

        # Generate child's name
        name_key = "names_male" if child_gender == "MALE" else "names_female"
        child_name = random.choice(theme_config.get(name_key, ["Child"]))

        # Determine surname based on convention
        surname_convention = theme_config.get("surname_convention", "INHERITED_PATRILINEAL")

        if surname_convention == "PATRONYMIC":
            suffix_key = "patronymic_suffix_male" if child_gender == "MALE" else "patronymic_suffix_female"
            suffix = theme_config.get(suffix_key, "son" if child_gender == "MALE" else "dottir")
            child_surname = f"{spouse.name}{suffix}"
        elif surname_convention == "MATRONYMIC":
            suffix_key = "matronymic_suffix_male" if child_gender == "MALE" else "matronymic_suffix_female"
            suffix = theme_config.get(suffix_key, "son" if child_gender == "MALE" else "dottir")
            child_surname = f"{woman.name}{suffix}"
        else:  # Default to patrilineal
            child_surname = spouse.surname if spouse.gender == "MALE" else woman.surname

        # Create child
        child = PersonDB(
            dynasty_id=dynasty.id,
            name=child_name,
            surname=child_surname,
            gender=child_gender,
            birth_year=current_year,
            mother_sim_id=woman.id,
            father_sim_id=spouse.id,
            is_noble=woman.is_noble or spouse.is_noble
        )

        # Set child traits
        child_traits = []
        available_traits = theme_config.get("common_traits", ["Noble"])
        if available_traits:
            num_traits = min(1, len(available_traits))
            child_traits = random.sample(available_traits, num_traits)
        child.set_traits(child_traits)

        db.session.add(child)
        db.session.flush()  # Ensure child.id is assigned before portrait generation
        child.generate_portrait()

        # Log birth
        birth_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{child_name} {child_surname} was born to {woman.name} {woman.surname} and {spouse.name} {spouse.surname}.",
            person1_sim_id=child.id,
            event_type="birth"
        )
        db.session.add(birth_log)

        # Child mortality check (15% chance)
        if random.random() < 0.15 * theme_config.get("mortality_factor", 1.0):
            child.death_year = current_year

            # Log infant death
            death_log = HistoryLogEntryDB(
                dynasty_id=dynasty.id,
                year=current_year,
                event_string=f"{child_name} {child_surname}, infant child of {woman.name} {woman.surname}, did not survive birth.",
                person1_sim_id=child.id,
                event_type="death"
            )
            db.session.add(death_log)

        return True

    return False


def process_succession(dynasty: DynastyDB, deceased_monarch: PersonDB, current_year: int, theme_config: dict):
    """Process succession after a monarch's death."""
    # Log the succession crisis
    succession_log = HistoryLogEntryDB(
        dynasty_id=dynasty.id,
        year=current_year,
        event_string=f"With the death of {deceased_monarch.name} {deceased_monarch.surname}, the matter of succession weighs heavily on House {dynasty.name}.",
        person1_sim_id=deceased_monarch.id,
        event_type="succession_start"
    )
    db.session.add(succession_log)

    # Get succession rule
    succession_rule = theme_config.get("succession_rule_default", "PRIMOGENITURE_MALE_PREFERENCE")

    # Find eligible heirs
    eligible_heirs = []

    # First, check for children of the deceased
    children = PersonDB.query.filter(
        (PersonDB.father_sim_id == deceased_monarch.id) |
        (PersonDB.mother_sim_id == deceased_monarch.id),
        PersonDB.death_year.is_(None),
        PersonDB.is_noble == True
    ).all()

    if children:
        if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
            # Sort by gender (males first) then by birth year (oldest first)
            children.sort(key=lambda c: (c.gender != "MALE", c.birth_year))
        elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
            # Sort by birth year only (oldest first)
            children.sort(key=lambda c: c.birth_year)
        elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
            # For simplicity, just sort by traits count and age
            children.sort(key=lambda c: (-len(c.get_traits()), c.birth_year))

        eligible_heirs = children

    # If no children, look for siblings
    if not eligible_heirs:
        siblings = PersonDB.query.filter(
            ((PersonDB.father_sim_id == deceased_monarch.father_sim_id) |
             (PersonDB.mother_sim_id == deceased_monarch.mother_sim_id)),
            PersonDB.id != deceased_monarch.id,
            PersonDB.death_year.is_(None),
            PersonDB.is_noble == True
        ).all()

        if siblings:
            if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                siblings.sort(key=lambda s: (s.gender != "MALE", s.birth_year))
            elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
                siblings.sort(key=lambda s: s.birth_year)
            elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
                siblings.sort(key=lambda s: (-len(s.get_traits()), s.birth_year))

            eligible_heirs = siblings

    # If still no heirs, look for any living noble in the dynasty
    if not eligible_heirs:
        nobles = PersonDB.query.filter_by(
            dynasty_id=dynasty.id,
            death_year=None,
            is_noble=True
        ).all()

        if nobles:
            if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                nobles.sort(key=lambda n: (n.gender != "MALE", n.birth_year))
            elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
                nobles.sort(key=lambda n: n.birth_year)
            elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
                nobles.sort(key=lambda n: (-len(n.get_traits()), n.birth_year))

            eligible_heirs = nobles

    # If we have an heir, make them the new monarch
    if eligible_heirs:
        new_monarch = eligible_heirs[0]
        new_monarch.is_monarch = True
        new_monarch.reign_start_year = current_year

        # Set monarch title
        title_key = "titles_male" if new_monarch.gender == "MALE" else "titles_female"
        titles = theme_config.get(title_key, ["Leader"])
        if titles:
            monarch_title = titles[0]
            current_titles = new_monarch.get_titles()
            if monarch_title not in current_titles:
                current_titles.insert(0, monarch_title)
                new_monarch.set_titles(current_titles)

        # Log succession
        succession_end_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"{new_monarch.name} {new_monarch.surname} has become the new {monarch_title} of House {dynasty.name}.",
            person1_sim_id=new_monarch.id,
            event_type="succession_end"
        )
        db.session.add(succession_end_log)
    else:
        # No heir found - dynasty in crisis
        crisis_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"House {dynasty.name} faces a succession crisis as no clear heir can be found.",
            event_type="succession_crisis"
        )
        db.session.add(crisis_log)


def process_world_events(dynasty: DynastyDB, current_year: int, theme_config: dict):
    """Process random world events for the year."""
    events = theme_config.get("events", [])
    if not events:
        return

    # Shuffle events for randomness
    random.shuffle(events)

    for event in events:
        # Check if event should trigger
        min_year = event.get("min_year", 0)
        max_year = event.get("max_year", 99999)
        chance = event.get("chance_per_year", 0.0)

        if min_year <= current_year <= max_year and random.random() < chance:
            # Event triggered
            event_name = event.get("name", "A Mysterious Happening")

            # Format narrative
            narrative = event.get("narrative", "Its consequences were felt.")
            narrative = narrative.replace("{dynasty_name}", dynasty.name)
            narrative = narrative.replace("{location_flavor}", theme_config.get("location_flavor", "these lands"))

            if "{rival_clan_name}" in narrative:
                available_surnames = theme_config.get("surnames_dynastic", ["Rivals"])
                rival_name = random.choice([s for s in available_surnames if s != dynasty.name]) if len(available_surnames) > 1 else "Rivals"
                narrative = narrative.replace("{rival_clan_name}", rival_name)

            # Apply wealth change if specified
            wealth_change = event.get("wealth_change", 0)
            if wealth_change != 0:
                dynasty.current_wealth = max(0, dynasty.current_wealth + wealth_change)

            # Log event
            event_log = HistoryLogEntryDB(
                dynasty_id=dynasty.id,
                year=current_year,
                event_string=f"{event_name}: {narrative}",
                event_type="generic_event"
            )
            db.session.add(event_log)

            # Only one world event per year
            break


# ===========================================================================
# Family-tree visualization (legacy — slated for replacement in Sprint 8)
# ===========================================================================

def generate_family_tree_visualization(dynasty: DynastyDB, theme_config: dict):
    """Generate a family tree visualization for the dynasty.

    NOTE: This is the legacy matplotlib-based renderer.  Sprint 8 of the
    master plan replaces it with a pure SVG renderer that fits the dark
    medieval theme and renders deceased ancestors properly.  Kept here as-is
    so this refactor introduces zero behavior change.
    """
    try:
        from visualization.plotter import visualize_family_tree_snapshot
        from models.family_tree import FamilyTree
        from models.person import Person

        # Create a directory for visualizations
        visualizations_dir = os.path.join('static', 'visualizations')
        os.makedirs(visualizations_dir, exist_ok=True)

        # Create a FamilyTree object from the database
        family_tree = FamilyTree(dynasty.name, theme_config)
        family_tree.current_year = dynasty.current_simulation_year

        # Load all persons from the database into the family tree
        persons = PersonDB.query.filter_by(dynasty_id=dynasty.id).all()

        # First pass: Create Person objects
        person_objects = {}
        for db_person in persons:
            # Create Person object with required parameters
            person = Person(
                name=db_person.name,
                gender=db_person.gender,
                birth_year=db_person.birth_year,
                theme_config=theme_config,
                is_noble=db_person.is_noble
            )

            # Set additional attributes
            person.surname = db_person.surname
            person.death_year = db_person.death_year
            person.is_monarch = db_person.is_monarch
            person.reign_start_year = db_person.reign_start_year
            person.reign_end_year = db_person.reign_end_year
            person.titles = db_person.get_titles()
            person.traits = db_person.get_traits()

            # Store the Person object with the database ID as the key
            person_objects[db_person.id] = person
            # Use the database ID as the key in the family tree members dictionary
            family_tree.members[db_person.id] = person

            if db_person.is_monarch and db_person.death_year is None:
                family_tree.current_monarch = person

        # Second pass: Set relationships
        for db_person in persons:
            person = person_objects.get(db_person.id)
            if not person:
                continue

            # Set parents
            if db_person.father_sim_id and db_person.father_sim_id in person_objects:
                person.father = person_objects[db_person.father_sim_id]
                if person not in person.father.children:
                    person.father.children.append(person)

            if db_person.mother_sim_id and db_person.mother_sim_id in person_objects:
                person.mother = person_objects[db_person.mother_sim_id]
                if person not in person.mother.children:
                    person.mother.children.append(person)

            # Set spouse
            if db_person.spouse_sim_id and db_person.spouse_sim_id in person_objects:
                person.spouse = person_objects[db_person.spouse_sim_id]

        # Generate the visualization
        visualize_family_tree_snapshot(
            family_tree_obj=family_tree,
            year=dynasty.current_simulation_year,
            display_mode="living_nobles"
        )

        logger.debug(f"Family tree visualization generated for {dynasty.name} in year {dynasty.current_simulation_year}")
        return True
    except Exception as e:
        logger.error(f"Error generating family tree visualization: {str(e)}", exc_info=True)
        return False
