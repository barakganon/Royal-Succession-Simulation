# models/person.py
import random
import datetime

# --- Configuration Placeholders ---
# These constants and global flags would ideally be imported from a central configuration file
# or set by the main simulation script. For this module to be somewhat testable or understandable
# in isolation, we define them here. In a full project, they should be managed centrally.

# BASE constants (defaults if not overridden by theme)
BASE_MIN_MARRIAGE_AGE = 16
BASE_MAX_MARRIAGE_AGE_MALE = 55
BASE_MAX_MARRIAGE_AGE_FEMALE = 45
BASE_MIN_FERTILITY_AGE_FEMALE = 18
BASE_MAX_FERTILITY_AGE_FEMALE = 45
BASE_MAX_CHILDREN_PER_COUPLE = 8

# Global flags (should be set by the main controlling script)
VERBOSE_LOGGING = True  # Example default
VERBOSE_TRAIT_LOGGING = True  # Example default

# Attempt to import helper for narrative flair.
# This relative import works if 'models' and 'utils' are sibling packages.
try:
    from ..utils.helpers import generate_narrative_flair
except ImportError:
    # Fallback if direct run or utils not in python path for this context
    print(
        "Warning (models/person.py): Could not import 'generate_narrative_flair' from utils.helpers. Using a placeholder.")


    def generate_narrative_flair(category, theme_config, subject_name="", object_name="", year=None, details=None):
        return f"Placeholder Flair: Event '{category}' for {subject_name} in year {year}."


class Person:
    """
    Represents an individual in the simulation with attributes like name, gender,
    family relationships, titles, traits, and life events.
    """
    _next_id: int = 0  # Class variable for generating unique IDs

    def __init__(self,
                 name: str,
                 gender: str,
                 birth_year: int,
                 theme_config: dict,
                 mother: 'Person' = None,
                 father: 'Person' = None,
                 explicit_surname: str = None,
                 is_noble: bool = True,
                 is_founder: bool = False,
                 initial_traits: list[str] = None):
        """
        Initializes a new Person.

        Args:
            name: Given name.
            gender: "MALE" or "FEMALE".
            birth_year: Year of birth.
            theme_config: Dictionary containing cultural theme settings.
            mother: Person object of the mother.
            father: Person object of the father.
            explicit_surname: If provided, overrides themed surname logic.
            is_noble: Nobility status.
            is_founder: If this person is a dynasty founder.
            initial_traits: List of traits to assign at birth. If None, random traits are assigned.
        """
        self.id: int = Person._next_id
        Person._next_id += 1

        self.theme_config: dict = theme_config
        self.name: str = name
        self.gender: str = gender.upper()  # Ensure MALE/FEMALE
        self.birth_year: int = birth_year
        self.death_year: int | None = None

        self.mother: Person | None = mother
        self.father: Person | None = father
        self.surname: str = self._determine_surname(explicit_surname, is_founder)

        self.spouse: Person | None = None
        self.children: list[Person] = []

        self.titles: list[str] = []
        self.is_noble: bool = is_noble
        self.is_monarch: bool = False  # Current leader of their primary group/dynasty
        self.reign_start_year: int | None = None
        self.reign_end_year: int | None = None

        self.traits: list[str] = self._initialize_traits(initial_traits)

        # Assign default noble title if applicable (and not a placeholder parent)
        is_placeholder = any("PlaceholderParent" in t for t in self.titles)  # Titles might be pre-set for placeholders
        if self.is_noble and not self.titles and not is_founder and not is_placeholder:
            default_title_key = "default_noble_male" if self.gender == "MALE" else "default_noble_female"
            default_title_fallback = "Noble" if self.gender == "MALE" else "Noblewoman"
            self.titles.append(self.theme_config.get(default_title_key, default_title_fallback))

    def _determine_surname(self, explicit_surname: str | None, is_founder: bool) -> str:
        """Helper method to determine the person's surname based on rules."""
        if explicit_surname:
            return explicit_surname

        surname_convention = self.theme_config.get("surname_convention", "INHERITED_PATRILINEAL")

        if surname_convention == "PATRONYMIC" and self.father:
            base_name = self.father.name
            suffix_key = "patronymic_suffix_male" if self.gender == "MALE" else "patronymic_suffix_female"
            default_suffix = "sson" if self.gender == "MALE" else "sdottir"
            suffix = self.theme_config.get(suffix_key, default_suffix)
            return f"{base_name}{suffix}"
        elif surname_convention == "MATRONYMIC" and self.mother:
            base_name = self.mother.name
            suffix_key = "matronymic_suffix_male" if self.gender == "MALE" else "matronymic_suffix_female"  # Could have distinct matronymic suffixes
            default_suffix = "sson" if self.gender == "MALE" else "sdottir"  # Defaulting to patronymic style suffixes
            suffix = self.theme_config.get(suffix_key, default_suffix)
            return f"{base_name}{suffix}"
        elif surname_convention == "INHERITED_PATRILINEAL" and self.father:
            return self.father.surname
        elif is_founder:
            surnames_list = self.theme_config.get("surnames_dynastic", ["FounderDynastyName"])
            return random.choice(surnames_list) if surnames_list else "FounderDynastyName"

        return "Unlineaged"  # Fallback if no other rule applies

    def _initialize_traits(self, initial_traits: list[str] | None) -> list[str]:
        """Helper method to initialize traits, either given or randomly from theme."""
        if initial_traits and isinstance(initial_traits, list):
            return list(initial_traits)  # Return a copy

        newly_assigned_traits = []
        available_traits = self.theme_config.get("common_traits", [])
        if available_traits:
            num_traits_to_assign = random.randint(1, min(2, len(available_traits)))  # Assign 1 or 2
            newly_assigned_traits = random.sample(available_traits, num_traits_to_assign)

        # Log trait assignment, but not for placeholder parents (identified by a title later)
        # This check might be better after titles are assigned if placeholders get titles immediately
        # For now, assumes titles are not yet set for placeholders during this specific init part.
        if VERBOSE_TRAIT_LOGGING and newly_assigned_traits:
            # full_name depends on surname which is set above.
            print(
                f"Birth Trait Assignment: {self.full_name} (born {self.birth_year}) is {', '.join(newly_assigned_traits)}.")
        return newly_assigned_traits

    @property
    def full_name(self) -> str:
        """Returns the person's full name, respecting surname conventions from the theme."""
        surname_convention = self.theme_config.get("surname_convention", "INHERITED_PATRILINEAL")
        if surname_convention == "FAMILY_NAME_FIRST":
            return f"{self.surname} {self.name}"
        return f"{self.name} {self.surname}"  # Default Western order

    def get_age(self, current_year: int) -> int:
        """Calculates the person's current age or age at death."""
        if self.birth_year > current_year:
            # This case might occur if current_year is for an event before person's birth
            # or due to an error in year tracking.
            if VERBOSE_LOGGING:
                print(f"Warning (Person.get_age): {self.full_name} - current_year ({current_year}) "
                      f"is before birth_year ({self.birth_year}). Age set to 0.")
            return 0

        effective_end_year = current_year
        if self.death_year is not None:  # Person has died
            # If querying age for a year after or at death, age is fixed.
            # If querying for a year before death, use that year.
            effective_end_year = min(self.death_year, current_year)

        # Ensure age is not negative if effective_end_year somehow became less than birth_year
        return max(0, effective_end_year - self.birth_year)

    def is_alive(self, current_year: int) -> bool:
        """Checks if the person is considered alive at the given current_year."""
        if self.death_year is None:  # Never recorded as dead
            return True
        # If recorded as dead, they are only alive if current_year is before their death_year
        return current_year < self.death_year

    def _get_themed_life_cycle_value(self,
                                     base_value_name: str,
                                     theme_factor_key: str,  # e.g., "age_factor", "fertility_factor"
                                     absolute_theme_key: str | None = None,  # e.g., "min_marriage_age_abs"
                                     default_base_val_override: float | None = None  # To pass BASE_XXX directly
                                     ) -> float:
        """
        Helper to get a life cycle numerical value, applying theme overrides and factors.
        Priority: Absolute Theme Value > Factored Base Value > Base Value.
        """
        # 1. Check for an absolute value in the theme_config
        if absolute_theme_key and absolute_theme_key in self.theme_config:
            theme_abs_val = self.theme_config[absolute_theme_key]
            if isinstance(theme_abs_val, (int, float)):
                return float(theme_abs_val)
            elif VERBOSE_LOGGING:
                print(f"Warning (Person._get_themed_val): Absolute theme key '{absolute_theme_key}' "
                      f"for {self.full_name} is not numeric ('{theme_abs_val}'). Using base/factor.")

        # 2. Use base value (either passed override or from globals()) and apply theme factor
        base_val_to_use: float
        if default_base_val_override is not None:
            base_val_to_use = float(default_base_val_override)
        else:
            base_constant_name = f"BASE_{base_value_name.upper()}"
            # This relies on BASE_ constants being in the global scope where Person is used
            base_val_to_use = float(globals().get(base_constant_name, 0.0))  # Default to 0.0 if not found

        # Get the specific factor, or a general fallback factor, or default to 1.0
        factor_to_apply = 1.0
        if theme_factor_key in self.theme_config and isinstance(self.theme_config[theme_factor_key], (int, float)):
            factor_to_apply = float(self.theme_config[theme_factor_key])
        # Example of more general fallback (can be expanded)
        elif "age" in theme_factor_key.lower() and "age_factor" in self.theme_config and \
                isinstance(self.theme_config["age_factor"], (int, float)):
            factor_to_apply = float(self.theme_config["age_factor"])

        return base_val_to_use * factor_to_apply

    def can_marry(self, current_year: int) -> bool:
        """Checks if the person is eligible to marry in the given year. More readable."""
        age = self.get_age(current_year)

        min_m_age = self._get_themed_life_cycle_value(
            base_value_name="min_marriage_age",
            theme_factor_key="generic_age_factor",  # Example: Use a general age factor from theme
            absolute_theme_key="min_marriage_age_abs",
            default_base_val_override=BASE_MIN_MARRIAGE_AGE
        )
        if self.gender == "MALE":
            max_m_age = self._get_themed_life_cycle_value(
                "max_marriage_age_male", "generic_age_factor", "max_marriage_age_male_abs", BASE_MAX_MARRIAGE_AGE_MALE
            )
        else:  # FEMALE
            max_m_age = self._get_themed_life_cycle_value(
                "max_marriage_age_female", "generic_age_factor", "max_marriage_age_female_abs",
                BASE_MAX_MARRIAGE_AGE_FEMALE
            )

        is_currently_alive: bool = self.is_alive(current_year)
        is_unmarried: bool = self.spouse is None
        is_within_marriageable_age_range: bool = (min_m_age <= age <= max_m_age)
        is_eligible_by_social_status: bool = self.is_noble  # Current rule for simplicity

        can_proceed_to_marry: bool = (
                is_currently_alive and
                is_unmarried and
                is_within_marriageable_age_range and
                is_eligible_by_social_status
        )

        if VERBOSE_LOGGING and is_eligible_by_social_status and is_currently_alive and is_unmarried:
            if not can_proceed_to_marry:  # Log only if they are a candidate but fail a specific check
                reasons_failed = []
                if not is_within_marriageable_age_range:
                    reasons_failed.append(f"Age {age:.0f} not in marriageable range [{min_m_age:.0f}-{max_m_age:.0f}]")
                # Add other specific checks here if they were separated
                if reasons_failed:
                    print(
                        f"DEBUG Person.can_marry for {self.full_name} (Age {age}, Yr {current_year}): FAIL. Reasons: {'; '.join(reasons_failed)}")
        return can_proceed_to_marry

    def can_have_children(self, current_year: int) -> bool:
        """Checks if the person is eligible to have children. More readable."""
        if not self.is_alive(current_year): return False
        if self.spouse is None or not self.spouse.is_alive(current_year): return False

        if self.gender == "MALE":
            # Male's ability to have children depends on their female spouse
            if hasattr(self.spouse, 'gender') and self.spouse.gender == "FEMALE":
                return self.spouse.can_have_children(current_year)  # Recursive call
            return False  # Spouse is not female or some other issue

        elif self.gender == "FEMALE":
            age = self.get_age(current_year)
            min_fert_age = self._get_themed_life_cycle_value(
                "min_fertility_age_female", "fertility_factor", "min_fertility_age_female_abs",
                BASE_MIN_FERTILITY_AGE_FEMALE
            )
            max_fert_age = self._get_themed_life_cycle_value(
                "max_fertility_age_female", "fertility_factor", "max_fertility_age_female_abs",
                BASE_MAX_FERTILITY_AGE_FEMALE
            )
            # max_children_factor applies to the BASE constant
            max_children = self._get_themed_life_cycle_value(
                "max_children_per_couple", "max_children_factor", default_base_val_override=BASE_MAX_CHILDREN_PER_COUPLE
            )

            is_within_fertile_age_range: bool = (min_fert_age <= age <= max_fert_age)
            has_not_exceeded_max_children: bool = (len(self.children) < max_children)

            can_proceed_to_conceive: bool = is_within_fertile_age_range and has_not_exceeded_max_children

            if VERBOSE_LOGGING and not can_proceed_to_conceive:  # Log only if they are otherwise okay (alive, married) but fail these
                reasons_failed = []
                if not is_within_fertile_age_range:
                    reasons_failed.append(
                        f"Age {age:.0f} not in fertility range [{min_fert_age:.0f}-{max_fert_age:.0f}]")
                if not has_not_exceeded_max_children:
                    reasons_failed.append(f"Max children ({int(max_children)}) reached ({len(self.children)})")
                if reasons_failed:
                    print(
                        f"DEBUG Person.can_have_children (F) for {self.full_name} (Age {age}, Yr {current_year}, Children {len(self.children)}): FAIL. Reasons: {'; '.join(reasons_failed)}")
            return can_proceed_to_conceive
        return False

    def add_trait(self, trait: str, year: int = None, reason: str = "an event"):
        """Adds a trait to the person if they don't already have it and logs it."""
        if trait not in self.traits:
            self.traits.append(trait)
            is_placeholder = any("PlaceholderParent" in t for t in self.titles) if self.titles else False
            if VERBOSE_TRAIT_LOGGING and year and not is_placeholder:
                print(f"Trait Added: {self.full_name} is now known for being {trait} (Year {year}, due to {reason}).")
            return True
        return False

    def add_title(self, title: str, history_logger_obj: 'History', year: int):  # Type hint History
        """Adds a title to the person and logs the event."""
        if title not in self.titles:
            self.titles.append(title)  # Add first

            # Determine if this title makes them a monarch based on theme
            themed_male_leader_titles = self.theme_config.get("titles_male", [])
            themed_female_leader_titles = self.theme_config.get("titles_female", [])

            primary_male_leader_title = themed_male_leader_titles[0] if themed_male_leader_titles else None
            primary_female_leader_title = themed_female_leader_titles[0] if themed_female_leader_titles else None

            is_newly_crowned_monarch = False
            if self.gender == "MALE" and title == primary_male_leader_title:
                is_newly_crowned_monarch = True
            elif self.gender == "FEMALE" and title == primary_female_leader_title:
                is_newly_crowned_monarch = True

            if is_newly_crowned_monarch and not self.is_monarch:  # Check if not already monarch
                self.is_monarch = True
                self.reign_start_year = year
                # Remove lesser "heir" titles (e.g., "Prince" if "King" is gained)
                # Assumes second title in list is the heir-apparent title
                if len(themed_male_leader_titles) > 1 and themed_male_leader_titles[1] in self.titles:
                    self.titles.remove(themed_male_leader_titles[1])
                if len(themed_female_leader_titles) > 1 and themed_female_leader_titles[1] in self.titles:
                    self.titles.remove(themed_female_leader_titles[1])

            if history_logger_obj and year:  # Check history_logger_obj is not None
                history_logger_obj.log_event(
                    year=year,
                    event_string=generate_narrative_flair(
                        category="title_grant",
                        theme_config=self.theme_config,
                        subject_name=self.full_name,
                        object_name=title,
                        year=year,
                        details={'subject_person_obj': self}  # Pass person object for trait access
                    ),
                    person1_id=self.id,
                    event_type="title_grant"
                )

    def remove_title(self, title: str, year: int = None):
        """Removes a title from the person. Updates monarch status if a primary leadership title is removed."""
        if title in self.titles:
            self.titles.remove(title)

            if self.is_monarch:  # Only check if they were a monarch
                themed_male_leader_titles = self.theme_config.get("titles_male", [])
                themed_female_leader_titles = self.theme_config.get("titles_female", [])
                primary_male_leader_title = themed_male_leader_titles[0] if themed_male_leader_titles else None
                primary_female_leader_title = themed_female_leader_titles[0] if themed_female_leader_titles else None

                if title == primary_male_leader_title or title == primary_female_leader_title:
                    # Check if they still hold ANY monarch-equivalent title
                    still_has_a_monarch_title = False
                    if primary_male_leader_title and primary_male_leader_title in self.titles:
                        still_has_a_monarch_title = True
                    if primary_female_leader_title and primary_female_leader_title in self.titles:
                        still_has_a_monarch_title = True

                    if not still_has_a_monarch_title:
                        self.is_monarch = False
                        self.reign_end_year = year if year is not None else self.death_year  # Default to death year if not specified

    def die(self, year: int, history_logger_obj: 'History') -> bool:  # Type hint History
        """Marks the person as deceased and logs the event. Returns True if newly died, False if already dead."""
        if not self.is_alive(year):  # Already dead or death year is set to this year or earlier
            # if VERBOSE_LOGGING: print(f"DEBUG Person.die: {self.full_name} already marked as dead for year {year} or earlier (death_year: {self.death_year}).")
            return False

        self.death_year = year
        age_at_death = self.get_age(year)  # Will use self.death_year
        was_monarch_when_died = self.is_monarch  # Capture status before it changes

        if self.is_monarch:
            self.is_monarch = False  # No longer the monarch
            self.reign_end_year = year  # Reign ends at death year

        if history_logger_obj:  # Check history_logger_obj is not None
            history_logger_obj.log_event(
                year=year,
                event_string=generate_narrative_flair(
                    category="death",
                    theme_config=self.theme_config,
                    subject_name=self.full_name,
                    year=year,
                    details={'age': age_at_death,
                             'is_monarch': was_monarch_when_died,
                             'subject_person_obj': self}  # Pass person for trait access
                ),
                person1_id=self.id,
                event_type="death"
            )
        return True

    def __repr__(self) -> str:
        """Returns a string representation of the Person, useful for debugging."""
        # Try to get a contextual year for 'Alive' status, otherwise default to current real year
        # This allows FamilyTree to pass its current_year when printing lists of people
        context_year = getattr(self, '_repr_context_year', datetime.datetime.now().year)

        status_age_str: str
        if self.death_year is not None:
            status_age_str = f"Deceased (Died: {self.death_year}, Age: {self.get_age(self.death_year)})"
        else:
            status_age_str = f"Alive (Age: {self.get_age(context_year)})"

        titles_display = f" Titles: {', '.join(self.titles)}" if self.titles else ""
        traits_display = f" Traits: {', '.join(self.traits)}" if self.traits else ""

        monarch_display_str = ""
        if self.is_monarch and self.reign_start_year is not None:
            reign_end_display = self.reign_end_year if self.reign_end_year is not None else "current"
            monarch_display_str = f" (LEADER, Reign: {self.reign_start_year}-{reign_end_display})"
        elif self.reign_start_year is not None and self.reign_end_year is not None:  # Was a monarch previously
            monarch_display_str = f" (Former Leader, Reign: {self.reign_start_year}-{self.reign_end_year})"

        return (f"P(ID:{self.id}, {self.full_name}, {self.gender}, "
                f"Born: {self.birth_year}, {status_age_str}{monarch_display_str}{titles_display}{traits_display})")


print("models.person.Person class defined with enhanced readability and debug logging.")