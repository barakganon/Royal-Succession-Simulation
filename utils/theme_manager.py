# utils/theme_manager.py
import json
import os
import random
import re

# Import LLM model and API key status from helpers (or a central config)
# This creates a slight interdependency, ensure helpers.py defines these globals
# or they are passed explicitly.
from .helpers import LLM_MODEL_GLOBAL, GOOGLE_API_KEY_GLOBAL, VERBOSE_LOGGING

# Assuming google.generativeai is imported in helpers or main script if LLM is used
try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore

DEFAULT_THEMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'themes', 'cultural_themes.json')
CULTURAL_THEMES_DATA = {}  # Cache for loaded themes


def load_cultural_themes(filepath: str = DEFAULT_THEMES_FILE) -> dict:
    """Loads cultural themes from a JSON file into CULTURAL_THEMES_DATA."""
    global CULTURAL_THEMES_DATA
    # Avoid reloading if already loaded from the default path, unless a different path is specified
    if CULTURAL_THEMES_DATA and filepath == DEFAULT_THEMES_FILE and os.path.exists(filepath):
        return CULTURAL_THEMES_DATA
    try:
        if VERBOSE_LOGGING: print(f"Attempting to load themes from: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            CULTURAL_THEMES_DATA = json.load(f)
        if VERBOSE_LOGGING: print(
            f"Cultural themes loaded successfully from: {filepath}. Found {len(CULTURAL_THEMES_DATA)} themes.")
    except FileNotFoundError:
        print(f"ERROR (theme_manager): Themes file not found at {filepath}. No predefined themes will be available.")
        CULTURAL_THEMES_DATA = {}
    except json.JSONDecodeError as e:
        print(f"ERROR (theme_manager): Could not decode JSON from {filepath}: {e}. Themes might be corrupted.")
        CULTURAL_THEMES_DATA = {}
    return CULTURAL_THEMES_DATA


def get_theme(theme_name: str) -> dict | None:
    """Gets a specific theme configuration by name. Loads themes if not already loaded."""
    if not CULTURAL_THEMES_DATA:  # Attempt to load if cache is empty
        load_cultural_themes()
    return CULTURAL_THEMES_DATA.get(theme_name)


def get_all_theme_names() -> list[str]:
    """Returns a list of all loaded predefined theme names."""
    if not CULTURAL_THEMES_DATA:
        load_cultural_themes()
    return list(CULTURAL_THEMES_DATA.keys())


def get_random_theme() -> tuple[str | None, dict | None]:
    """Gets a random predefined theme name and its configuration."""
    if not CULTURAL_THEMES_DATA:
        load_cultural_themes()
    if not CULTURAL_THEMES_DATA:  # Still no themes after attempting load
        error_theme_name = "ERROR_NO_THEMES_LOADED"
        # Provide a minimal valid theme structure for error case to prevent crashes downstream
        error_theme_config = {
            "description": "Error: No cultural themes could be loaded. Using emergency default.",
            "start_year_suggestion": 1000, "names_male": ["DefaultMale"], "names_female": ["DefaultFemale"],
            "surnames_dynastic": ["DefaultDynasty"], "surname_convention": "INHERITED_PATRILINEAL",
            "titles_male": ["Leader"], "titles_female": ["Leader"], "default_noble_male": "Noble",
            "default_noble_female": "Noblewoman", "founder_title_male": "Founder", "founder_title_female": "Founder",
            "succession_rule_default": "PRIMOGENITURE_MALE_PREFERENCE", "llm_persona_prompt": "A basic chronicler.",
            "common_traits": ["BasicTrait"], "events": [],
            # Add all numeric factors with default 1.0
            "mortality_factor": 1.0, "fertility_factor": 1.0, "pregnancy_chance_factor": 1.0,
            "max_children_factor": 1.0, "max_age_factor": 1.0, "prune_interval_factor": 1.0,
            "prune_distance_factor": 1.0, "starting_wealth_modifier": 1.0,
            "avg_marriage_age_male": 20, "avg_marriage_age_female": 18, "expected_lifespan_avg": 50,
            "location_flavor": "Default Land", "primary_economy": ["Subsistence"], "social_structure": "Basic",
            "tech_level": "Simple", "common_resources": ["Food"], "currency_name": "Units"
        }
        return error_theme_name, error_theme_config

    theme_name = random.choice(list(CULTURAL_THEMES_DATA.keys()))
    return theme_name, CULTURAL_THEMES_DATA[theme_name]


def generate_theme_from_story_llm(story_text: str) -> dict | None:
    """
    Uses an LLM to generate a cultural theme configuration based on user's story text.
    """
    if not LLM_MODEL_GLOBAL or not GOOGLE_API_KEY_GLOBAL:
        if VERBOSE_LOGGING: print("LLM not available for theme generation from story (theme_manager).")
        return None  # Cannot generate theme without LLM

    # Using the detailed prompt from CELL 0 of the previous full code response
    prompt = f"""
You are an expert world-building assistant for a historical/fantasy family saga simulation.
Your task is to take a short origin story provided by the user and generate a complete theme configuration for the simulation.
The output MUST be a single, valid JSON object. Do NOT include any text or explanation outside this JSON object.

The JSON object MUST contain the following keys, with values appropriate to the user's story:
- "description": (string) A brief (1-2 sentences) summary of the theme derived from the story.
- "start_year_suggestion": (integer) An appropriate starting year.
- "avg_marriage_age_male": (integer) Typical male marriage age for this theme.
- "avg_marriage_age_female": (integer) Typical female marriage age for this theme.
- "expected_lifespan_avg": (integer) Average expected lifespan in this setting.
- "location_flavor": (string) A short phrase describing the geographical/cultural setting (e.g., "Volcanic Isles of the Fire Drakes", "Steampunk Victorian London").
- "primary_economy": (list of 1-3 strings) Main economic activities (e.g., ["Agrarian", "Trade", "Mining"]).
- "social_structure": (string) Dominant social organization (e.g., "Feudal Hierarchy", "Tribal Confederacy", "Merchant Republic").
- "tech_level": (string) General technological era (e.g., "Iron Age", "Medieval", "Early Industrial", "Interstellar").
- "common_resources": (list of 3-5 strings) Important resources in the setting (e.g., ["Grain", "Iron Ore", "Spice"]).
- "currency_name": (string) Name of the common currency (e.g., "Gold Sovereigns", "Energy Credits").
- "names_male": (list of 10-15 strings) Typical male first names fitting the theme.
- "names_female": (list of 10-15 strings) Typical female first names fitting the theme.
- "surnames_dynastic": (list of 5-10 strings) Suitable dynastic, clan, or family surnames.
- "surname_convention": (string) Choose one: "INHERITED_PATRILINEAL", "PATRONYMIC", "MATRONYMIC", "FAMILY_NAME_FIRST", "INHERITED_PATRILINEAL_PLUS_MATERNAL_OPTION".
- "patronymic_suffix_male": (string, conditionally required if surname_convention is "PATRONYMIC" or "MATRONYMIC") e.g., "sson", "ovitch", "ap ". Provide a sensible default like "son" or "kin" if not obvious from story.
- "patronymic_suffix_female": (string, conditionally required if surname_convention is "PATRONYMIC" or "MATRONYMIC") e.g., "dottir", "ovna", "verch ". Provide a sensible default like "daughter" or "kin" if not obvious from story.
- "titles_male": (list of 5-7 strings) Male titles, from highest (e.g., Emperor, High Chief) to lower noble/influential person.
- "titles_female": (list of 5-7 strings) Female titles, corresponding to male titles or distinct female roles of power/influence.
- "default_noble_male": (string) A common title for a male of the influential class without a specific high rank.
- "default_noble_female": (string) A common title for a female of the influential class without a specific high rank.
- "founder_title_male": (string) The title the male founder of the dynasty would likely hold.
- "founder_title_female": (string) The title the female founder of the dynasty would likely hold.
- "succession_rule_default": (string) Choose one: "PRIMOGENITURE_MALE_PREFERENCE", "PRIMOGENITURE_ABSOLUTE", "ELECTIVE_NOBLE_COUNCIL". (Default to "PRIMOGENITURE_MALE_PREFERENCE" if unsure).
- "llm_persona_prompt": (string) A short (1-2 sentences) instruction for another AI that will act as a chronicler for this theme. This persona should match the story's tone. (e.g., "You are a grizzled spaceport bartender recounting local legends with a cynical wit.").
- "mortality_factor": (float, ideally between 0.7 and 1.5) Adjusts base mortality. 1.0 is average. Higher for dangerous settings.
- "fertility_factor": (float, ideally between 0.7 and 1.5) Adjusts base fertility. 1.0 is average.
- "pregnancy_chance_factor": (float, ideally between 0.7 and 1.5) Adjusts base pregnancy chance.
- "max_children_factor": (float, ideally between 0.7 and 1.5) Adjusts max children per couple.
- "max_age_factor": (float, ideally between 0.7 and 1.5) Adjusts max age.
- "prune_interval_factor": (float, between 0.5 and 1.5). 1.0 uses base prune interval.
- "prune_distance_factor": (float, between 0.5 and 1.5). 1.0 uses base prune distance.
- "starting_wealth_modifier": (float, between 0.5 and 2.0, default 1.0) Modifier for base starting wealth.
- "common_traits": (list of 8-12 strings) Personality traits common in this theme (e.g., "Brave", "Scheming", "Pious").
- "events": (list of 2-4 event objects) Each event object should have: "id" (unique_snake_case), "name", "chance_per_year" (float), "narrative". Optional: "min_year", "max_year", "wealth_change" (int), "mortality_impact_factor" (float), "duration" (int), "trait_grant_on_leader" (string).

USER ORIGIN STORY:
---
{story_text}
---
Remember, provide ONLY the JSON object as your response. Be creative and consistent with the user's story.
If the story is very vague on certain numerical factors (like mortality_factor), use 1.0 as a reasonable default.
For lists like names or titles, provide a good variety (around the number specified).
For events, ensure the 'narrative' uses placeholders like {{dynasty_name}} and {{location_flavor}} where appropriate.
"""
    try:
        if VERBOSE_LOGGING: print(f"\nLLM Theme Gen (theme_manager): Sending prompt for story '{story_text[:70]}...'")

        # Ensure genai is available if we reach here with LLM_MODEL_GLOBAL set
        if not genai: raise ImportError("google.generativeai not available for LLM call.")

        generation_config = genai.types.GenerationConfig(
            temperature=0.6,  # Slightly less random for structured JSON
            # max_output_tokens=2048 # Ensure enough space for JSON
        )
        response = LLM_MODEL_GLOBAL.generate_content(prompt, generation_config=generation_config)

        raw_response_text = response.text.strip()

        # Attempt to extract JSON from the response (LLMs sometimes add surrounding text)
        json_match = re.search(r"\{.*\}", raw_response_text, re.DOTALL)
        if not json_match:
            print(
                f"Error (theme_manager): LLM did not return a recognizable JSON object structure in its response. Response text:\n{raw_response_text}")
            return None

        cleaned_json_str = json_match.group(0)

        if VERBOSE_LOGGING: print(
            f"LLM Theme Gen (theme_manager): Cleaned JSON Text (first 500 chars):\n{cleaned_json_str[:500]}...")

        custom_theme_dict = json.loads(cleaned_json_str)

        # --- Perform Validation and Defaulting for the generated theme ---
        # (Using the more robust defaulting from previous CELL 0 example)
        required_keys_with_defaults = {
            "description": ("A saga spun from a custom story.", str), "start_year_suggestion": (1000, int),
            "avg_marriage_age_male": (22, int), "avg_marriage_age_female": (18, int),
            "expected_lifespan_avg": (60, int),
            "location_flavor": ("A newly imagined land", str), "primary_economy": (["Various"], list),
            "social_structure": ("Unique", str), "tech_level": ("Varied", str),
            "common_resources": (["Essentials"], list), "currency_name": ("Credits", str),
            "names_male": (["John", "Rob", "Will"], list), "names_female": (["Jane", "Liz", "Sue"], list),
            "surnames_dynastic": (["Storyborn", "EpicWeavers"], list),
            "surname_convention": ("INHERITED_PATRILINEAL", str),
            "titles_male": (["Leader", "Elder", "Captain"], list),
            "titles_female": (["Leader", "Elder", "First Mate"], list),
            "default_noble_male": ("Valued Person", str), "default_noble_female": ("Valued Person", str),
            "founder_title_male": ("First Leader", str), "founder_title_female": ("First Leader", str),
            "succession_rule_default": ("PRIMOGENITURE_MALE_PREFERENCE", str),
            "llm_persona_prompt": ("You are the designated chronicler for this unique saga.", str),
            "common_traits": (["Determined", "Adaptable", "Resourceful"], list), "events": ([], "list_of_dict")
        }
        float_factor_keys = ["mortality_factor", "fertility_factor", "pregnancy_chance_factor", "max_children_factor",
                             "max_age_factor", "prune_interval_factor", "prune_distance_factor",
                             "starting_wealth_modifier"]

        for key, (default_val, expected_type_info) in required_keys_with_defaults.items():
            current_value = custom_theme_dict.get(key)
            valid_type = False
            if expected_type_info == list:
                valid_type = isinstance(current_value, list) and current_value  # Must be non-empty list
            elif expected_type_info == "list_of_dict":
                valid_type = isinstance(current_value, list) and all(isinstance(i, dict) for i in current_value)
            elif isinstance(current_value, expected_type_info):
                valid_type = True

            if not valid_type:
                if VERBOSE_LOGGING: print(
                    f"LLM Theme Validation: Key '{key}' invalid or missing (value: '{current_value}'). Using default: '{default_val}'")
                custom_theme_dict[key] = default_val

        for factor_key_name in float_factor_keys:
            if not isinstance(custom_theme_dict.get(factor_key_name), (int, float)):
                if VERBOSE_LOGGING: print(
                    f"LLM Theme Validation: Factor '{factor_key_name}' invalid. Using default: 1.0")
                custom_theme_dict[factor_key_name] = 1.0
            else:
                custom_theme_dict[factor_key_name] = float(custom_theme_dict[factor_key_name])  # Ensure it's float

        if not isinstance(custom_theme_dict.get("start_year_suggestion"), int):
            custom_theme_dict["start_year_suggestion"] = 1000  # Default if not int

        # Validate event structure
        if isinstance(custom_theme_dict.get("events"), list):
            valid_event_list = []
            for i, event_dict_item in enumerate(custom_theme_dict["events"]):
                if isinstance(event_dict_item, dict) and all(
                        k in event_dict_item for k in ["id", "name", "chance_per_year", "narrative"]):
                    # Ensure chance_per_year is float
                    event_dict_item["chance_per_year"] = float(event_dict_item.get("chance_per_year", 0.01))
                    valid_event_list.append(event_dict_item)
                elif VERBOSE_LOGGING:
                    print(
                        f"Warning (theme_manager): LLM generated event definition at index {i} is malformed: {event_dict_item}. It will be skipped.")
            custom_theme_dict["events"] = valid_event_list
        else:
            custom_theme_dict["events"] = []  # Ensure it's a list if not properly formed

        if VERBOSE_LOGGING: print("\nCustom theme generated and processed from user story via LLM (theme_manager).")
        return custom_theme_dict

    except json.JSONDecodeError as e_json:
        print(f"Error decoding JSON from LLM for theme generation (theme_manager): {e_json}")
        if 'raw_response_text' in locals() and VERBOSE_LOGGING: print(f"LLM Raw Response was:\n{raw_response_text}")
        return None
    except Exception as e_llm_theme:
        print(
            f"An unexpected error occurred during custom LLM theme generation (theme_manager): {type(e_llm_theme).__name__} - {e_llm_theme}")
        import traceback
        traceback.print_exc()
        return None


# Attempt to load themes when this module is imported
load_cultural_themes()
print("utils.theme_manager initialized and themes loaded (if file found).")