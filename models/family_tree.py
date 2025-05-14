# models/family_tree.py
import random
import networkx as nx  # type: ignore
from collections import defaultdict

# Assuming Person class is in models.person and History in models.history
from .person import Person

# History is passed as an instance, type hint with string if needed for type checker
# from .history import History

# Assuming helper functions are in utils.helpers
# These relative imports work when the project is structured as a package.
try:
    from ..utils.helpers import generate_name, generate_narrative_flair
except ImportError:  # Fallback for simpler execution context or testing
    print("Warning (family_tree.py): Could not import from utils.helpers. Using placeholders.")


    def generate_name(g, tc):
        return "PlaceholderName"


    def generate_narrative_flair(cat, tc, sn="", on="", yr=None, dt=None):
        return f"Placeholder Flair: {cat} for {sn}"

# BASE constants - these should ideally be managed in a central config file
# and passed to instances or accessed via a config object.
# For modularity, FamilyTree now receives many of these via theme_config or uses its own pre-calced versions.
# These globals() calls in __init__ are to fetch them from the scope of simulation_engine.py where it's run.
VERBOSE_LOGGING = True  # Placeholder, will be set by main script
VERBOSE_EVENT_LOGGING = True  # Placeholder


class FamilyTree:
    """
    Manages the collection of Person objects, their relationships,
    dynastic succession, and major life cycle events.
    """

    def __init__(self, history_logger_instance: 'History', theme_config: dict,
                 succession_rule: str = "PRIMOGENITURE_MALE_PREFERENCE"):
        self.members: dict[int, Person] = {}  # person_id: Person_object
        self.graph: nx.DiGraph = nx.DiGraph()  # For relationship visualization: child_id -> parent_id
        self.current_monarch: Person | None = None  # The current leader of the dynasty
        self.all_monarchs_ever_ids: list[int] = []  # Historical list of leaders

        self.history: 'History' = history_logger_instance  # Instance of the History class
        self.theme_config: dict = theme_config  # The cultural theme for this dynasty
        self.succession_rule: str = succession_rule  # e.g., "PRIMOGENITURE_MALE_PREFERENCE"

        surnames_list = self.theme_config.get("surnames_dynastic", ["GreatHouseDefaultName"])
        self.dynasty_name: str = random.choice(surnames_list) if surnames_list else "GreatHouseDefaultName"

        # Simulation's current year, managed by the main simulation loop, but initialized here
        self.current_year: int = int(
            self.theme_config.get("start_year_suggestion", globals().get("BASE_START_YEAR", 1000)))

        # Pre-calculate some themed values based on global BASE_ constants and theme factors for efficiency
        # globals().get() is used here assuming BASE_ constants are defined in the script that creates FamilyTree
        self.themed_max_age: float = globals().get("BASE_MAX_AGE", 85.0) * self.theme_config.get("max_age_factor", 1.0)
        self.themed_adult_mortality_base: float = globals().get("BASE_ADULT_MORTALITY_BASE_PER_YEAR",
                                                                0.01) * self.theme_config.get("mortality_factor", 1.0)
        self.themed_pregnancy_chance: float = globals().get("BASE_PREGNANCY_CHANCE_PER_YEAR",
                                                            0.4) * self.theme_config.get("pregnancy_chance_factor", 1.0)

        # New attributes for enhanced simulation
        self.dynasty_wealth: int = int(
            globals().get("BASE_DYNASTY_WEALTH_START", 100) * self.theme_config.get("starting_wealth_modifier", 1.0))
        self.alliances: dict = {}  # Tracks alliances, e.g., { "SurnameA": {"SurnameB": year_allied} }
        self.active_event_effects: dict = {}  # Tracks ongoing effects from world events, e.g., {"event_id": {"end_year": YYYY, "mortality_impact_factor": X.X}}

    def add_person(self, person_obj: Person):
        """Adds a Person object to the family tree and logs their birth (if not a placeholder)."""
        if person_obj.id in self.members:
            if VERBOSE_LOGGING:
                print(
                    f"Warning (FamilyTree.add_person): Person ID {person_obj.id} ({person_obj.full_name}) already exists in tree.")
            return

        self.members[person_obj.id] = person_obj
        self.graph.add_node(person_obj.id, data=person_obj)  # Store the Person object with the node

        # Add directed edges from child to parents for lineage tracking in the graph
        if person_obj.father and person_obj.father.id in self.members:
            self.graph.add_edge(person_obj.id, person_obj.father.id, type="child_of_father")
        if person_obj.mother and person_obj.mother.id in self.members:
            self.graph.add_edge(person_obj.id, person_obj.mother.id, type="child_of_mother")

        # Log birth only for actual characters, not placeholder parents created for backstory
        is_placeholder_parent = any(
            "PlaceholderParent" in title for title in person_obj.titles) if person_obj.titles else False
        if not is_placeholder_parent:
            self.history.log_event(
                year=person_obj.birth_year,
                event_string=generate_narrative_flair(
                    category="birth",
                    theme_config=person_obj.theme_config,  # Person carries their theme for flair context
                    subject_name=person_obj.full_name,
                    year=person_obj.birth_year,
                    details={'noble': person_obj.is_noble, 'subject_person_obj': person_obj}
                    # Pass person for trait access
                ),
                person1_id=person_obj.id,
                event_type="birth"
            )

    def get_person(self, person_id: int) -> Person | None:
        """Retrieves a Person object by their ID."""
        return self.members.get(person_id)

    def marry_people(self, person1_id: int, person2_id: int, marriage_year: int,
                     is_arranged_external_marriage: bool = False) -> bool:
        """Performs a marriage between two people if they are eligible."""
        person1 = self.get_person(person1_id)
        person2 = self.get_person(person2_id)

        if not person1 or not person2:
            if VERBOSE_LOGGING: print(
                f"Marriage Failed (Year {marriage_year}): Person ID {person1_id if not person1 else ''}{person2_id if not person2 else ''} not found.")
            return False
        if person1.gender == person2.gender:
            # if VERBOSE_LOGGING: print(f"Marriage Failed (Year {marriage_year}): Same gender for {person1.full_name} and {person2.full_name}.")
            return False  # Simple rule, can be themed

        # Person.can_marry method handles all eligibility checks (age, status, already married)
        if person1.can_marry(marriage_year) and person2.can_marry(marriage_year):
            person1.spouse = person2
            person2.spouse = person1

            marriage_details_for_flair = {
                'noble_marriage': person1.is_noble and person2.is_noble,
                'subject_person_obj': person1,  # For accessing traits of person1 in flair
                'object_person_obj': person2  # For accessing traits of person2 in flair
            }
            if is_arranged_external_marriage and person1.is_noble and person2.is_noble and person1.surname != person2.surname:
                alliance_description = f"House {person1.surname} & House {person2.surname}"
                marriage_details_for_flair['alliance_formed'] = alliance_description
                marriage_details_for_flair['economic_exchange'] = True  # Hint for dowry/bride price themed flair

                # Track conceptual alliance
                if person1.surname not in self.alliances: self.alliances[person1.surname] = {}
                if person2.surname not in self.alliances: self.alliances[person2.surname] = {}
                self.alliances[person1.surname][person2.surname] = marriage_year
                self.alliances[person2.surname][person1.surname] = marriage_year
                if VERBOSE_LOGGING: print(
                    f"Alliance Tracked (Year {marriage_year}): {alliance_description}. (Current wealth: {self.dynasty_wealth})")

            self.history.log_event(
                year=marriage_year,
                event_string=generate_narrative_flair("marriage", self.theme_config,
                                                      person1.full_name, person2.full_name, marriage_year,
                                                      marriage_details_for_flair),
                person1_id=person1.id, person2_id=person2.id, event_type="marriage"
            )
            self.history.gen_marriage_pairs_names.append(
                f"{person1.name.split(' ')[0]}&{person2.name.split(' ')[0]}")  # For generation summary
            return True
        else:
            if VERBOSE_LOGGING:  # Log specific failure if trying to marry
                p1_can = person1.can_marry(marriage_year)
                p2_can = person2.can_marry(marriage_year)
                print(f"Marriage Failed (Yr {marriage_year}): Eligibility issue. "
                      f"{person1.full_name} can_marry: {p1_can}. {person2.full_name} can_marry: {p2_can}.")
            return False

    def attempt_conception(self, female_id: int, current_year: int) -> Person | None:
        """Attempts conception for a fertile married female."""
        female = self.get_person(female_id)
        # Female.can_have_children internally checks for living spouse, age, max children
        if not (female and female.gender == "FEMALE" and female.spouse and female.can_have_children(current_year)):
            return None  # Not eligible or no valid female found

        male_spouse = female.spouse  # Assumed from checks above

        # Use the pre-calculated themed pregnancy chance stored in FamilyTree
        if random.random() < self.themed_pregnancy_chance:
            child_gender = random.choice(["MALE", "FEMALE"])
            child_first_name = generate_name(child_gender, self.theme_config)  # Use FamilyTree's theme_config

            is_noble_child = female.is_noble or (male_spouse and male_spouse.is_noble)

            # Person __init__ handles surname logic based on its theme_config and parents
            child = Person(name=child_first_name, gender=child_gender, birth_year=current_year,
                           theme_config=self.theme_config,  # Child inherits FamilyTree's theme context
                           mother=female, father=male_spouse,
                           is_noble=is_noble_child)

            female.children.append(child)
            male_spouse.children.append(child)
            self.add_person(child)  # This will log the birth event via History

            # Child mortality check (using global BASE constant, could be themed)
            child_mortality_rate = globals().get("BASE_CHILD_MORTALITY_RATE_UNDER_5", 0.15)
            if random.random() < child_mortality_rate:
                child.die(current_year, self.history)  # Infant dies in the same year of birth
            return child
        return None  # Conception did not occur this year

    def process_yearly_events_for_person(self, person_id: int, current_year: int):
        """Processes all standard yearly life cycle events for a single person."""
        person = self.get_person(person_id)
        if not person or not person.is_alive(current_year):  # Check if person is valid and alive
            return

        # --- 1. Death Check ---
        person_age = person.get_age(current_year)

        # Calculate current mortality impact from any active world events
        effective_mortality_modifier = 1.0
        for event_id_key, effect_data_dict in list(
                self.active_event_effects.items()):  # Iterate over a copy if modifying dict
            if current_year < effect_data_dict.get("end_year", current_year):  # Check if effect is still active
                effective_mortality_modifier *= effect_data_dict.get("mortality_impact_factor", 1.0)
            else:  # Event effect has expired
                if VERBOSE_EVENT_LOGGING: print(f"Event effect '{event_id_key}' expired in {current_year}.")
                del self.active_event_effects[event_id_key]

        # Base mortality for this person's theme, modified by active events
        current_year_mortality_chance = self.themed_adult_mortality_base * effective_mortality_modifier

        # Add age-based modifiers (general theme mortality_factor applies to these age additions)
        theme_mortality_factor = self.theme_config.get("mortality_factor", 1.0)
        if person_age > 60: current_year_mortality_chance += 0.05 * theme_mortality_factor * effective_mortality_modifier
        if person_age > 75: current_year_mortality_chance += 0.15 * theme_mortality_factor * effective_mortality_modifier

        # Check against themed max age (if positive, it's an absolute cap)
        if self.themed_max_age > 0 and person_age > self.themed_max_age:
            current_year_mortality_chance = 1.0  # Guaranteed death if past max age

        person_died_this_year = False
        if random.random() < current_year_mortality_chance or \
                (self.themed_max_age > 0 and person_age > self.themed_max_age):
            if person.die(current_year, self.history):  # person.die() logs event & updates monarch status
                person_died_this_year = True

        # Also check for pre-set death year (e.g., from infant mortality at birth, if not handled immediately)
        if not person_died_this_year and person.death_year == current_year and person.is_alive(
                current_year):  # is_alive to prevent double processing
            if person.die(current_year, self.history):
                person_died_this_year = True

        if person_died_this_year:
            # If the deceased was the current monarch, trigger succession process
            if self.current_monarch and person.id == self.current_monarch.id:
                if VERBOSE_LOGGING: print(
                    f"LEADER DEATH (detected in yearly_events): {person.full_name} (ID: {person.id}). Processing succession.")
                self.process_succession(person.id)  # Pass ID of the monarch who just died
            return  # Person died, no further actions for them this year

        # --- 2. Marriage Seeking and Arrangement ---
        if person.is_noble and person.spouse is None and person.can_marry(
                current_year):  # Person.can_marry performs detailed checks
            base_marriage_seek_chance = 0.35  # Base chance to actively seek marriage if eligible

            is_important_person_for_marriage = person.is_monarch or \
                                               (self.current_monarch and (
                                                           person.father == self.current_monarch or person.mother == self.current_monarch))

            actual_marriage_seek_chance = 0.75 if is_important_person_for_marriage else base_marriage_seek_chance

            if random.random() < actual_marriage_seek_chance:
                if VERBOSE_LOGGING: print(
                    f"Marriage Seek (Yr {current_year}): {person.full_name} (Age {person_age}) actively seeking marriage. Important: {is_important_person_for_marriage}")
                self._arrange_marriage_for_person(person, current_year, is_important_person_for_marriage)

        # --- 3. Conception (for married fertile females) ---
        if person.gender == "FEMALE" and person.spouse and person.can_have_children(
                current_year):  # Person.can_have_children performs detailed checks
            # The attempt_conception method itself contains the RNG check against self.themed_pregnancy_chance
            self.attempt_conception(person.id, current_year)

    def _arrange_marriage_for_person(self, person_seeking_marriage: Person, current_year: int,
                                     is_important_person: bool):
        """Creates and attempts to marry an 'imported' spouse to person_seeking_marriage."""
        spouse_gender = "FEMALE" if person_seeking_marriage.gender == "MALE" else "MALE"
        spouse_given_name = generate_name(spouse_gender, self.theme_config)

        # Determine surname for the new spouse's family (importing from "another" noble house)
        surnames_for_spouse_pool = [s_name for s_name in
                                    self.theme_config.get("surnames_dynastic", ["ExternalNobleHouse"])
                                    if s_name != person_seeking_marriage.surname and s_name != self.dynasty_name]
        if not surnames_for_spouse_pool:  # Fallback if all theme surnames are already in use
            surnames_for_spouse_pool = [f"NewAlliedHouse{Person._next_id}"]  # Use Person's unique ID for uniqueness
        spouse_surname = random.choice(surnames_for_spouse_pool)

        # Determine spouse's age: try to use themed average, else relative to person seeking marriage
        psm_age = person_seeking_marriage.get_age(current_year)
        min_abs_spouse_marriage_age = person_seeking_marriage._get_themed_life_cycle_value(
            "min_marriage_age", "age_factor", "min_marriage_age_abs", globals().get("BASE_MIN_MARRIAGE_AGE", 16)
        )

        avg_marriage_age_key_for_spouse = "avg_marriage_age_male" if spouse_gender == "MALE" else "avg_marriage_age_female"
        target_spouse_age_from_theme = self.theme_config.get(avg_marriage_age_key_for_spouse)

        prospective_spouse_age: float
        if target_spouse_age_from_theme and isinstance(target_spouse_age_from_theme, (int, float)):
            age_variance_around_avg = random.randint(-4, 4)  # e.g. +/- 4 years around theme average
            prospective_spouse_age = max(min_abs_spouse_marriage_age,
                                         float(target_spouse_age_from_theme) + age_variance_around_avg)
        else:  # Fallback to age relative to person_seeking_marriage
            # Males often marry younger, females often marry older (traditional bias)
            age_difference_min = -7 if person_seeking_marriage.gender == "MALE" else -3
            age_difference_max = 3 if person_seeking_marriage.gender == "MALE" else 7
            prospective_spouse_age = max(min_abs_spouse_marriage_age,
                                         psm_age + random.randint(age_difference_min, age_difference_max))

        # Ensure spouse is within their own maximum marriageable age
        max_m_age_male_for_spouse = person_seeking_marriage._get_themed_life_cycle_value("max_marriage_age_male",
                                                                                         "age_factor",
                                                                                         "max_marriage_age_male_abs",
                                                                                         globals().get(
                                                                                             "BASE_MAX_MARRIAGE_AGE_MALE",
                                                                                             55))
        max_m_age_female_for_spouse = person_seeking_marriage._get_themed_life_cycle_value("max_marriage_age_female",
                                                                                           "age_factor",
                                                                                           "max_marriage_age_female_abs",
                                                                                           globals().get(
                                                                                               "BASE_MAX_MARRIAGE_AGE_FEMALE",
                                                                                               45))
        max_spouse_can_marry_at = max_m_age_male_for_spouse if spouse_gender == "MALE" else max_m_age_female_for_spouse

        final_spouse_age = min(prospective_spouse_age,
                               max_spouse_can_marry_at - 1)  # -1 to ensure they are not AT max age but can still marry
        final_spouse_age = max(final_spouse_age,
                               min_abs_spouse_marriage_age)  # Final check against min age for robustness
        spouse_birth_year = current_year - int(final_spouse_age)

        # Create the new Person object for the spouse
        new_spouse = Person(
            name=spouse_given_name, gender=spouse_gender, birth_year=spouse_birth_year,
            theme_config=self.theme_config,  # Spouse shares the main family's theme context for now
            explicit_surname=spouse_surname,
            is_noble=person_seeking_marriage.is_noble,  # Match nobility status
            is_founder=False  # Not a founder
        )

        # Optionally create placeholder parents for this imported spouse for a bit of backstory
        if random.random() < 0.6:  # 60% chance
            self._create_placeholder_parents_for_imported_spouse(new_spouse, current_year)

        self.add_person(new_spouse)  # Add to tree (logs birth if not placeholder)

        # Attempt to marry them
        if self.marry_people(person_seeking_marriage.id, new_spouse.id, current_year,
                             is_arranged_external_marriage=True):
            if VERBOSE_LOGGING:
                print(
                    f"Marriage Arranged (Yr {current_year}): {person_seeking_marriage.full_name} successfully married newly introduced noble "
                    f"{new_spouse.full_name} from House {new_spouse.surname} (Alliance Potentially Formed).")
        else:
            # This might happen if, despite calculations, one of them is no longer eligible by the time marry_people is called
            # (e.g., if can_marry had a dynamic element that changed, or age rounding issues)
            if VERBOSE_LOGGING:
                psm_can_marry_now = person_seeking_marriage.can_marry(current_year)
                new_spouse_can_marry_now = new_spouse.can_marry(current_year)
                print(
                    f"Marriage Arrangement FAILED (Yr {current_year}): {person_seeking_marriage.full_name} (can_marry:{psm_can_marry_now}) "
                    f"with newly created {new_spouse.full_name} (can_marry:{new_spouse_can_marry_now}). Check eligibility logic if this happens often.")

    def _create_placeholder_parents_for_imported_spouse(self, spouse_character: Person, current_simulation_year: int):
        """Creates deceased/obscure parents for an imported spouse for minimal backstory flavor."""
        parent_age_at_spouse_birth = random.randint(18, 40)  # Parent's age when spouse_character was born

        # Calculate birth years for parents
        father_birth_year = spouse_character.birth_year - parent_age_at_spouse_birth - random.randint(0,
                                                                                                      10)  # Father generally a bit older
        mother_birth_year = spouse_character.birth_year - parent_age_at_spouse_birth + random.randint(-5,
                                                                                                      5)  # Mother's age can vary more

        # Ensure parents are born before spouse_character could have been conceived by them
        min_parent_age_for_conception = globals().get("BASE_MIN_FERTILITY_AGE_FEMALE", 18) - 1  # Approx
        father_birth_year = min(father_birth_year, spouse_character.birth_year - min_parent_age_for_conception)
        mother_birth_year = min(mother_birth_year, spouse_character.birth_year - min_parent_age_for_conception)

        father_given_name = generate_name("MALE", self.theme_config)
        mother_given_name = generate_name("FEMALE", self.theme_config)

        # Mother gets a different "maiden" surname for variety
        maiden_surnames_pool = [s for s in self.theme_config.get("surnames_dynastic", ["AncientHouseName"]) if
                                s != spouse_character.surname]
        if not maiden_surnames_pool: maiden_surnames_pool = [f"OldFamily{Person._next_id}"]
        mother_maiden_surname = random.choice(maiden_surnames_pool)

        # Ensure placeholder parents are deceased well before current_simulation_year to not interfere
        father_death_year = min(current_simulation_year - random.randint(10, 30),  # At least 10 years ago
                                spouse_character.birth_year + random.randint(30,
                                                                             60))  # Lived some time after spouse's birth
        mother_death_year = min(current_simulation_year - random.randint(10, 30),
                                spouse_character.birth_year + random.randint(30, 65))
        # Ensure death year is after birth year
        father_death_year = max(father_death_year, father_birth_year + globals().get("BASE_MIN_MARRIAGE_AGE",
                                                                                     16) + 10)  # Min plausible lifespan
        mother_death_year = max(mother_death_year, mother_birth_year + globals().get("BASE_MIN_MARRIAGE_AGE", 16) + 10)

        # Create Person objects for placeholder parents
        father_placeholder = Person(name=father_given_name, gender="MALE", birth_year=father_birth_year,
                                    theme_config=self.theme_config, explicit_surname=spouse_character.surname,
                                    # Same surname as their child (the spouse)
                                    is_noble=spouse_character.is_noble)  # Match nobility
        father_placeholder.titles = ["PlaceholderParent", self.theme_config.get("default_noble_male", "Noble")]
        father_placeholder.death_year = father_death_year  # Mark as deceased

        mother_placeholder = Person(name=mother_given_name, gender="FEMALE", birth_year=mother_birth_year,
                                    theme_config=self.theme_config, explicit_surname=mother_maiden_surname,
                                    is_noble=spouse_character.is_noble)
        mother_placeholder.titles = ["PlaceholderParent", self.theme_config.get("default_noble_female", "Noblewoman")]
        mother_placeholder.death_year = mother_death_year  # Mark as deceased

        # Add them to the simulation (add_person will handle logging or skipping for placeholders)
        self.add_person(father_placeholder)
        self.add_person(mother_placeholder)

        # Link the imported spouse to these placeholder parents
        spouse_character.father = father_placeholder
        spouse_character.mother = mother_placeholder

        # Explicitly add graph edges if add_person's parent linking might miss due to timing
        if self.graph.has_node(spouse_character.id):
            if self.graph.has_node(father_placeholder.id) and not self.graph.has_edge(spouse_character.id,
                                                                                      father_placeholder.id):
                self.graph.add_edge(spouse_character.id, father_placeholder.id, type="child_of_father")
            if self.graph.has_node(mother_placeholder.id) and not self.graph.has_edge(spouse_character.id,
                                                                                      mother_placeholder.id):
                self.graph.add_edge(spouse_character.id, mother_placeholder.id, type="child_of_mother")

        if VERBOSE_LOGGING:
            print(f"Placeholder parents created for {spouse_character.full_name}: "
                  f"Father {father_placeholder.full_name} (B:{father_birth_year}-D:{father_death_year}), "
                  f"Mother {mother_placeholder.full_name} (B:{mother_birth_year}-D:{mother_death_year})")

    # --- Succession Logic ---
    # (Ensure _get_eligible_heirs_of_person, _find_heir_recursively, find_next_monarch,
    #  process_succession are complete and correct from previous versions.
    #  The versions from the response before this one were quite robust.)
    def _get_eligible_heirs_of_person(self, person: Person) -> list[Person]:
        if not person: return []
        eligible_children = [child for child in person.children if child.is_alive(self.current_year) and child.is_noble]
        if not eligible_children: return []

        rule = self.succession_rule
        if rule == "PRIMOGENITURE_MALE_PREFERENCE":
            eligible_children.sort(key=lambda c: (c.gender != "MALE", c.birth_year))
        elif rule == "PRIMOGENITURE_ABSOLUTE":
            eligible_children.sort(key=lambda c: c.birth_year)
        elif rule == "ELECTIVE_NOBLE_COUNCIL":
            # For elective, we might sort by a 'prestige' or 'influence' score, then age.
            # Placeholder: sort by age for now, actual election logic would be complex.
            if VERBOSE_LOGGING: print(
                f"Year {self.current_year}: Elective succession for heirs of {person.full_name} (using age as fallback sort).")
            eligible_children.sort(key=lambda p: (
                -sum(1 for tr in ["Valiant", "Learned", "Just", "Diplomatic", "Ambitious"] if tr in p.traits),
                # Higher positive traits first
                sum(1 for tr in ["Cruel", "Deceitful", "Greedy", "Reckless"] if tr in p.traits),
                # Lower negative traits first
                p.birth_year  # Older first among equals
            ))
        else:  # Default to male preference if rule is unrecognized
            eligible_children.sort(key=lambda c: (c.gender != "MALE", c.birth_year))
        return eligible_children

    def _find_heir_recursively(self, person_to_check_line_of: Person, visited_nodes: set) -> Person | None:
        if not person_to_check_line_of or person_to_check_line_of.id in visited_nodes:
            return None
        visited_nodes.add(person_to_check_line_of.id)

        # Get children of person_to_check_line_of, already sorted by primary succession preference
        # (e.g., for primogeniture, male children by age, then female children by age)
        # This order matters for checking whose *line* takes precedence.
        children_in_succession_order = []
        for child_obj in person_to_check_line_of.children:
            if not child_obj.is_noble: continue  # Non-noble children break the line

            # Determine sort key based on succession rule for this child's potential line
            sort_key_for_child_line = ()
            if self.succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                sort_key_for_child_line = (child_obj.gender != "MALE", child_obj.birth_year)
            elif self.succession_rule == "PRIMOGENITURE_ABSOLUTE" or self.succession_rule == "ELECTIVE_NOBLE_COUNCIL":  # Elective falls back
                sort_key_for_child_line = (child_obj.birth_year,)
            else:  # Default
                sort_key_for_child_line = (child_obj.gender != "MALE", child_obj.birth_year)
            children_in_succession_order.append((child_obj, sort_key_for_child_line))

        children_in_succession_order.sort(key=lambda x: x[1])  # Sort the children themselves

        for child_line_head, _ in children_in_succession_order:
            if child_line_head.id in visited_nodes:  # Already processed this line (e.g., through another branch)
                continue

            # If this child is alive and noble, they are the heir from this branch.
            if child_line_head.is_alive(self.current_year) and child_line_head.is_noble:
                return child_line_head

            # If child_line_head is dead (or not alive for current_year) but was noble,
            # their claim can pass to their descendants. Recurse on their line.
            if child_line_head.is_noble:  # Must have been noble to pass the claim
                heir_from_this_childs_line = self._find_heir_recursively(child_line_head, visited_nodes)
                if heir_from_this_childs_line:
                    return heir_from_this_childs_line  # Found heir deeper in this branch

        return None  # No heir found down this person_to_check_line_of's direct descendants

    def find_next_monarch(self, deceased_monarch: Person) -> Person | None:
        if not deceased_monarch: return None

        self.history.log_event(
            year=self.current_year,
            event_string=generate_narrative_flair("succession_start", self.theme_config,
                                                  subject_name=deceased_monarch.full_name, year=self.current_year,
                                                  details={'subject_person_obj': deceased_monarch}),
            person1_id=deceased_monarch.id, event_type="succession_start"
        )

        # Handle Elective Monarchy separately
        if self.succession_rule == "ELECTIVE_NOBLE_COUNCIL":
            if VERBOSE_LOGGING: print(
                f"Year {self.current_year}: Elective Council convenes for House {self.dynasty_name}.")
            # Identify candidates: living, adult nobles of the dynasty (or wider pool if defined by theme)
            candidates = [
                p for p in self.members.values()
                if p.is_alive(self.current_year) and p.is_noble and p.id != deceased_monarch.id and \
                   p.get_age(self.current_year) >= self.theme_config.get("min_leadership_age_abs", 18)
                # Min age for leadership
            ]
            if not candidates: return None  # No eligible candidates

            # Simple elective scoring: traits + age (older preferred among equals)
            # This could be much more complex (e.g., # of supporters, wealth, relationships)
            def elective_candidate_score(person_obj: Person):
                score = 0
                positive_traits = ["Valiant", "Learned", "Just", "Diplomatic", "Pious", "Generous",
                                   "Ambitious"]  # Ambitious can be good for a leader
                negative_traits = ["Cruel", "Deceitful", "Greedy", "Reckless", "Cowardly"]
                for trait in person_obj.traits:
                    if trait in positive_traits: score += 5
                    if trait in negative_traits: score -= 3
                # Add points for age (experience) up to a point, then maybe fewer for very old
                age = person_obj.get_age(self.current_year)
                if 30 <= age <= 55:
                    score += (age - 29) // 2  # Bonus for prime age
                elif age > 55:
                    score -= (age - 55) // 3  # Penalty for being very old
                return (score, -person_obj.birth_year)  # Higher score first, then older for tie-breaking

            candidates.sort(key=elective_candidate_score, reverse=True)  # Highest score first

            if VERBOSE_LOGGING and candidates:
                print(f"  Elective Candidates (Top 3 scores):")
                for cand in candidates[:3]: print(f"    - {cand.full_name}, Score: {elective_candidate_score(cand)}")
            return candidates[0] if candidates else None

        # For primogeniture-based succession:
        visited_for_this_succession_search = set()
        # 1. Direct descendants of the deceased monarch
        heir = self._find_heir_recursively(deceased_monarch, visited_for_this_succession_search)
        if heir: return heir

        # 2. Collateral lines (siblings, uncles/aunts, etc.)
        current_ancestor_in_line = deceased_monarch
        while current_ancestor_in_line:
            # Check lines from both father and mother if they exist
            parents_to_explore_collaterals_from = []
            if current_ancestor_in_line.father: parents_to_explore_collaterals_from.append(
                current_ancestor_in_line.father)
            if current_ancestor_in_line.mother: parents_to_explore_collaterals_from.append(
                current_ancestor_in_line.mother)  # For cognatic elements

            for parent_node in parents_to_explore_collaterals_from:
                if not parent_node or parent_node.id in visited_for_this_succession_search:
                    continue

                # Get parent_node's children (siblings of current_ancestor_in_line or their ancestor in this line)
                # Sort these potential collateral line heads by succession preference
                sibling_lines_to_check = []
                for child_of_parent_node in parent_node.children:
                    if not child_of_parent_node.is_noble: continue
                    # Don't re-check the line we just came up from (current_ancestor_in_line IS a child of parent_node)
                    if child_of_parent_node.id == current_ancestor_in_line.id: continue
                    if child_of_parent_node.id in visited_for_this_succession_search: continue  # Already explored this entire branch

                    # Determine sort key for this collateral branch head
                    key_collateral = ()
                    if self.succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
                        key_collateral = (child_of_parent_node.gender != "MALE", child_of_parent_node.birth_year)
                    elif self.succession_rule == "PRIMOGENITURE_ABSOLUTE":
                        key_collateral = (child_of_parent_node.birth_year,)
                    else:
                        key_collateral = (child_of_parent_node.gender != "MALE", child_of_parent_node.birth_year)
                    sibling_lines_to_check.append((child_of_parent_node, key_collateral))

                sibling_lines_to_check.sort(key=lambda x: x[1])  # Sort collateral branches

                for collateral_branch_head, _ in sibling_lines_to_check:
                    # First, is the head of this collateral branch (e.g. sibling/uncle) themselves the heir?
                    if collateral_branch_head.is_alive(self.current_year) and collateral_branch_head.is_noble and \
                            collateral_branch_head.id not in visited_for_this_succession_search:  # Check visited again just in case
                        return collateral_branch_head

                    # If not, search down their line using the recursive helper
                    heir_from_collateral_descendants = self._find_heir_recursively(collateral_branch_head,
                                                                                   visited_for_this_succession_search)
                    if heir_from_collateral_descendants:
                        return heir_from_collateral_descendants

                visited_for_this_succession_search.add(parent_node.id)  # Mark this ancestor's lines as checked

            # Move one generation up to continue searching collateral lines higher up
            # Prioritize father's line for upward traversal in many systems
            next_ancestor_up = None
            if current_ancestor_in_line.father and current_ancestor_in_line.father.id not in visited_for_this_succession_search:
                next_ancestor_up = current_ancestor_in_line.father
            elif current_ancestor_in_line.mother and current_ancestor_in_line.mother.id not in visited_for_this_succession_search:
                next_ancestor_up = current_ancestor_in_line.mother

            current_ancestor_in_line = next_ancestor_up  # This will eventually become None if top is reached
            # Break if we are trying to re-process an already visited ancestor (should prevent infinite loops on complex trees)
            if current_ancestor_in_line and current_ancestor_in_line.id in visited_for_this_succession_search:
                current_ancestor_in_line = None
        return None  # No heir found through any line

    def process_succession(self, deceased_monarch_id: int) -> bool:
        """Handles finding and crowning a new monarch."""
        old_monarch = self.get_person(deceased_monarch_id)
        if not old_monarch:
            if VERBOSE_LOGGING: print(
                f"Succession Error (Yr {self.current_year}): Deceased monarch ID {deceased_monarch_id} not found.")
            return False

        # The old monarch's is_monarch status and reign_end_year should have been set by Person.die()
        # if they were the current_monarch when they died.

        new_monarch_person = self.find_next_monarch(old_monarch)

        if new_monarch_person:
            self.current_monarch = new_monarch_person  # Update who is the current monarch

            # Determine the primary leader title from the theme
            male_titles = self.theme_config.get("titles_male", ["Leader"])
            female_titles = self.theme_config.get("titles_female", ["Leader"])
            new_leader_title = (male_titles[0] if male_titles and new_monarch_person.gender == "MALE"
                                else (female_titles[0] if female_titles else "Leader"))

            new_monarch_person.add_title(new_leader_title, self.history,
                                         self.current_year)  # This sets is_monarch and reign_start_year

            if new_monarch_person.id not in self.all_monarchs_ever_ids:
                self.all_monarchs_ever_ids.append(new_monarch_person.id)

            self.history.gen_new_monarch_name = new_monarch_person.full_name  # For generation summary
            self.history.log_event(
                year=self.current_year,
                event_string=generate_narrative_flair("succession_end", self.theme_config,
                                                      subject_name=new_monarch_person.full_name, year=self.current_year,
                                                      details={'subject_person_obj': new_monarch_person}),
                person1_id=new_monarch_person.id,
                event_type="succession_end"
            )
            return True  # Succession was successful
        else:  # No heir found
            self.current_monarch = None  # Throne is vacant
            self.history.log_event(
                year=self.current_year,
                event_string=generate_narrative_flair("no_heir", self.theme_config,
                                                      subject_name=self.dynasty_name, year=self.current_year,
                                                      details={
                                                          'context': f"after the passing of {old_monarch.full_name}"}),
                person1_id=old_monarch.id,  # Context of whose line failed
                event_type="succession_crisis"
            )
            return False  # Succession failed

    def _get_blood_relatives_graph(self, root_person_id: int) -> nx.Graph:
        """Creates an UNDIRECTED graph of blood relatives for distance calculation."""
        if root_person_id not in self.members:
            # if VERBOSE_LOGGING: print(f"Graph Gen Warning: Root person ID {root_person_id} not in members.")
            return nx.Graph()  # Return empty graph if root is not valid

        all_blood_related_ids = set()
        # 1. Find all ancestors of the root_person_id who are in self.members
        ancestor_search_queue = deque([root_person_id])
        visited_for_ancestor_search = {root_person_id}
        current_ancestors_found = {root_person_id}

        while ancestor_search_queue:
            current_id_from_queue = ancestor_search_queue.popleft()
            person_object = self.get_person(current_id_from_queue)
            if person_object:
                if person_object.father and person_object.father.id in self.members and \
                        person_object.father.id not in visited_for_ancestor_search:
                    current_ancestors_found.add(person_object.father.id)
                    ancestor_search_queue.append(person_object.father.id)
                    visited_for_ancestor_search.add(person_object.father.id)
                if person_object.mother and person_object.mother.id in self.members and \
                        person_object.mother.id not in visited_for_ancestor_search:
                    current_ancestors_found.add(person_object.mother.id)
                    ancestor_search_queue.append(person_object.mother.id)
                    visited_for_ancestor_search.add(person_object.mother.id)

        # 2. Find all descendants of these ancestors (forms the entire extended blood family in self.members)
        descendant_search_queue = deque(list(current_ancestors_found))  # Start with all found ancestors
        visited_for_descendant_search = set()
        while descendant_search_queue:
            current_id_from_queue = descendant_search_queue.popleft()
            if current_id_from_queue in visited_for_descendant_search: continue
            visited_for_descendant_search.add(current_id_from_queue)

            person_object = self.get_person(current_id_from_queue)
            if person_object:  # Should always be true if ID came from current_ancestors_found or children
                all_blood_related_ids.add(current_id_from_queue)  # Add this person to the set
                for child_character_object in person_object.children:
                    if child_character_object.id in self.members and \
                            child_character_object.id not in visited_for_descendant_search:  # Ensure child is in main member list
                        descendant_search_queue.append(child_character_object.id)

        # 3. Build the undirected subgraph using only these extended family members
        blood_relatives_subgraph = nx.Graph()
        for person_id_in_family in all_blood_related_ids:
            person_data = self.get_person(person_id_in_family)  # Known to exist
            blood_relatives_subgraph.add_node(person_id_in_family)  # Add node
            # Add edges to parents (if they are also in the extended_family_ids set)
            if person_data.father and person_data.father.id in all_blood_related_ids:
                blood_relatives_subgraph.add_edge(person_id_in_family, person_data.father.id)
            if person_data.mother and person_data.mother.id in all_blood_related_ids:
                blood_relatives_subgraph.add_edge(person_id_in_family, person_data.mother.id)
            # Children edges will be covered when children (as person_id_in_family) add edges to their parents.
        return blood_relatives_subgraph

    def prune_distant_relatives(self, max_distance: int) -> list[dict]:
        """Identifies and removes individuals too distantly related to the current monarch."""
        if not self.current_monarch or self.current_monarch.id not in self.members:
            if VERBOSE_LOGGING: print(f"Year {self.current_year}: Pruning skipped - no valid current monarch.")
            return []

        center_person_id = self.current_monarch.id
        # Get the graph of blood relatives around the monarch.
        # This graph only contains IDs that are currently in self.members.
        blood_relatives_graph = self._get_blood_relatives_graph(center_person_id)

        # It's possible the monarch is isolated or the graph is empty if something went wrong.
        if not blood_relatives_graph.has_node(center_person_id) and VERBOSE_LOGGING:
            print(
                f"Year {self.current_year}: Pruning Warning - Current monarch (ID {center_person_id}) not found in their own blood relatives graph. Pruning may be ineffective.")

        pruned_individuals_details_list = []
        ids_to_be_removed_from_tree = []

        # Determine important titles from theme (e.g., top 2-3 tiers)
        important_titles_from_theme = []
        for gender_title_key in ["titles_male", "titles_female"]:
            important_titles_from_theme.extend(self.theme_config.get(gender_title_key, [])[:3])  # Top 3

        for person_id_to_check in list(self.members.keys()):  # Iterate on a copy of keys
            if person_id_to_check == center_person_id: continue  # Don't prune the monarch

            person_object_to_check = self.get_person(person_id_to_check)
            if not person_object_to_check or not person_object_to_check.is_alive(self.current_year) or \
                    any("PlaceholderParent" in title for title in
                        person_object_to_check.titles):  # Don't prune placeholders
                continue

                # --- Importance Check ---
            is_person_important = False
            if person_object_to_check.is_monarch: is_person_important = True
            # Check direct family of current monarch
            if self.current_monarch:
                if person_object_to_check.father == self.current_monarch:
                    is_person_important = True
                elif person_object_to_check.mother == self.current_monarch:
                    is_person_important = True
                elif person_object_to_check in self.current_monarch.children:
                    is_person_important = True
                elif person_object_to_check == self.current_monarch.spouse:
                    is_person_important = True
            # Check if person holds a top-tier title
            if any(title in person_object_to_check.titles for title in important_titles_from_theme):
                is_person_important = True
            if is_person_important:
                continue  # Skip important individuals
            # --- End Importance Check ---

            reason_for_pruning = None
            try:
                # Only calculate distance if monarch is in the graph and person_to_check is in the graph
                if self.current_monarch and blood_relatives_graph.has_node(center_person_id) and \
                        blood_relatives_graph.has_node(person_id_to_check):

                    calculated_distance = nx.shortest_path_length(blood_relatives_graph, source=center_person_id,
                                                                  target=person_id_to_check)
                    if calculated_distance > max_distance:
                        reason_for_pruning = f"Exceeded max distance ({calculated_distance} > {max_distance}) from leader."

                elif self.current_monarch and not blood_relatives_graph.has_node(person_id_to_check):
                    # Person exists in self.members but not in the monarch's connected blood component
                    reason_for_pruning = "Not connected to current leader's main bloodline component."

                elif not self.current_monarch:  # No monarch to be distant from, prune based on other factors (e.g. just being non-important)
                    reason_for_pruning = "Considered peripheral (no active leader for reference)."

            except nx.NetworkXNoPath:  # Should be covered by not being in component, but as a safeguard
                if self.current_monarch:
                    reason_for_pruning = "No traceable blood path to current leader."
                else:
                    reason_for_pruning = "Peripheral (no leader and no path if graph was fragmented)."
            except Exception as e_graph:  # Catch other potential graph errors
                if VERBOSE_LOGGING: print(
                    f"Pruning graph distance calculation error for {person_object_to_check.full_name}: {e_graph}")
                reason_for_pruning = "Graph error during distance evaluation."

            if reason_for_pruning:
                ids_to_be_removed_from_tree.append(person_id_to_check)
                pruned_individuals_details_list.append({
                    "id": person_id_to_check,
                    "name": person_object_to_check.full_name,
                    "birth_year": person_object_to_check.birth_year,
                    "reason": reason_for_pruning,
                    "year": self.current_year
                })

        # Perform actual removal from simulation structures
        for id_to_remove in ids_to_be_removed_from_tree:
            if id_to_remove in self.members: del self.members[id_to_remove]
            if self.graph.has_node(id_to_remove): self.graph.remove_node(id_to_remove)  # Edges auto-removed by NetworkX

        # Log a summary of the pruning event
        if pruned_individuals_details_list:
            sample_pruned_names_for_log = [p_info['name'] for p_info in pruned_individuals_details_list[
                                                                        :min(3, len(pruned_individuals_details_list))]]
            summary_log_message = (
                f"Pruning Event: {len(pruned_individuals_details_list)} distant or peripheral individuals were removed from active records. "
                f"Examples: {', '.join(sample_pruned_names_for_log) if sample_pruned_names_for_log else 'N/A'}."
            )
            # Use a generic narrative flair for the summary log message
            self.history.log_event(
                year=self.current_year,
                event_string=generate_narrative_flair("pruning", self.theme_config,
                                                      subject_name=f"{len(pruned_individuals_details_list)} individuals",
                                                      details={'sample_names': sample_pruned_names_for_log}),
                event_type="pruning_event_main"  # A general event type for the main pruning action
            )
        return pruned_individuals_details_list


print("models.family_tree.FamilyTree class defined with yearly processing, marriage enhancements, events, and wealth.")