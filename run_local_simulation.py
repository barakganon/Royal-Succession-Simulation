# run_local_simulation.py
import random
import os
import json  # For potentially loading a user story from a file in the future

# Import from our project structure
from utils.theme_manager import load_cultural_themes, get_theme, get_random_theme, generate_theme_from_story_llm
from utils.helpers import set_llm_globals_for_helpers  # To pass LLM model to helpers
from simulation_engine import configure_simulation_globals, run_simulation

# --- Centralized LLM Setup for this script ---
LLM_MODEL_INSTANCE_FOR_RUN = None
API_KEY_IS_CONFIGURED = False
try:
    import google.generativeai as genai

    # IMPORTANT: Set your GOOGLE_API_KEY in your environment variables
    # OR uncomment and set directly below for testing
    # LOCAL_API_KEY = "YOUR_ACTUAL_API_KEY_HERE"
    LOCAL_API_KEY = os.environ.get("GOOGLE_API_KEY")

    if LOCAL_API_KEY:
        genai.configure(api_key=LOCAL_API_KEY)
        # You can choose your model here
        llm_model_name_to_use = "gemini-1.5-flash-latest"
        LLM_MODEL_INSTANCE_FOR_RUN = genai.GenerativeModel(llm_model_name_to_use)
        API_KEY_IS_CONFIGURED = True
        print(f"LLM Initialized for local simulation run: Model '{llm_model_name_to_use}'")
    else:
        print("LLM API Key not found. LLM-dependent features will use fallbacks or be disabled for this run.")
except ImportError:
    print("google-generativeai package not found. LLM features disabled for this run.")
except Exception as e_llm_init:
    print(f"Error initializing LLM in run_local_simulation.py: {type(e_llm_init).__name__} - {e_llm_init}")
# --- End Centralized LLM Setup ---


if __name__ == "__main__":
    print("--- Dynasty Saga Simulation (Local Runner Script) ---")

    # 1. Load predefined themes from JSON file using theme_manager
    # This also populates theme_manager.CULTURAL_THEMES_DATA
    loaded_themes_data = load_cultural_themes()
    if not loaded_themes_data:
        print("CRITICAL: No predefined themes were loaded. Exiting if not using custom story with LLM.")
        # Allow to proceed if LLM is available for custom story, otherwise exit.
        if not (LLM_MODEL_INSTANCE_FOR_RUN and API_KEY_IS_CONFIGURED):
            exit()

    # 2. --- Configuration for this specific simulation run ---

    # Option A: Use a predefined theme
    use_story_mode_flag = False
    # Make sure loaded_themes_data is not empty before trying to pick a theme
    if loaded_themes_data:
        # input_identifier_for_sim = "MEDIEVAL_EUROPEAN"
        input_identifier_for_sim = random.choice(list(loaded_themes_data.keys()))
    else:  # Should only happen if file was missing AND we proceed for LLM custom story
        input_identifier_for_sim = "CUSTOM_ONLY_NO_FALLBACK"  # Special case
        if not use_story_mode_flag:  # If not in story mode and no themes, this is an issue
            print("Error: No predefined themes and not in custom story mode. Cannot proceed.")
            exit()

    # Option B: Use a custom story (Uncomment to use this)
    # use_story_mode_flag = True
    # user_story_text_input = """
    # The Sunken City of Aethel-Mare was once a proud coastal metropolis before the Great Tide of year 250.
    # Its survivors, the Wavekin, now live in precarious settlements built on stilts and salvaged ships, forever battling the encroaching sea and mutated sea creatures.
    # They are led by a Tide-Speaker, chosen by their ability to commune with the ocean spirits.
    # Their culture values resilience, knowledge of the old world, and mastery of sea-craft. Surnames often relate to sea features or lost city districts.
    # They hope one day to reclaim their city from the depths.
    # """
    # input_identifier_for_sim = user_story_text_input

    # --- Simulation Parameters (Overrides) ---
    sim_years_to_run = 100  # Number of years to simulate for this run
    start_year_for_run = None  # None to use theme/LLM suggestion, or e.g., 750 for a specific start
    succession_rule_for_run = None  # None for theme default, or e.g., "PRIMOGENITURE_ABSOLUTE"

    # --- Global Settings for this Run ---
    g_verbose_logging_run = True
    g_viz_interval_run = 25  # Visualize every N years; 0 for final plot only
    g_use_llm_flair_run = True  # Controls flair generation during simulation
    g_event_logging_run = True
    g_trait_logging_run = True

    # 3. Configure global settings for the simulation_engine and helper modules
    configure_simulation_globals(
        verbose_log=g_verbose_logging_run,
        viz_interval=g_viz_interval_run,
        use_llm_flair=g_use_llm_flair_run,
        event_log=g_event_logging_run,
        trait_log=g_trait_logging_run,
        llm_model_obj=LLM_MODEL_INSTANCE_FOR_RUN,  # Pass the initialized LLM model
        api_key_present_bool=API_KEY_IS_CONFIGURED  # Pass its status
    )
    # Note: set_llm_globals_for_helpers is now called *inside* configure_simulation_globals

    # 4. Start the simulation
    print(f"\nAttempting to start simulation...")
    if use_story_mode_flag:
        print(f"Mode: Custom Story ('{str(input_identifier_for_sim)[:70]}...')")
        if not (LLM_MODEL_INSTANCE_FOR_RUN and API_KEY_IS_CONFIGURED):
            print(
                "WARNING: LLM is required for custom story mode but is not available. Simulation may fail or use very basic defaults.")
    else:
        print(f"Mode: Predefined Theme ('{input_identifier_for_sim}')")

    # The run_simulation function from simulation_engine.py will handle
    # theme loading/generation internally now using the theme_manager.
    final_family_tree_result, final_history_log_result = run_simulation(
        theme_name_or_user_story=input_identifier_for_sim,
        sim_years_override=sim_years_to_run,
        start_year_override=start_year_for_run,
        succession_rule_override=succession_rule_for_run,
        is_user_story=use_story_mode_flag
    )

    # 5. Post-Simulation Output (if successful)
    if final_family_tree_result and final_history_log_result:
        print("\n\n--- Simulation Run Concluded Successfully (Local Runner) ---")

        # Access the theme used for this run from the family_tree object
        # The FamilyTree object now stores its specific theme_config
        final_run_theme_config_used = final_family_tree_result.theme_config

        print(f"Dynasty: {final_family_tree_result.dynasty_name}")
        if final_run_theme_config_used:
            print(f"Theme Description: {final_run_theme_config_used.get('description', 'N/A')}")
        else:  # Should not happen if run_simulation completed successfully
            print("Theme description was not available for the completed run.")

        print("\n--- Leaders of the Dynasty ---")
        if final_family_tree_result.all_monarchs_ever_ids:
            for i, monarch_id_val in enumerate(final_family_tree_result.all_monarchs_ever_ids):
                monarch_char_obj = final_family_tree_result.get_person(monarch_id_val)
                if monarch_char_obj:
                    reign_end_display_str = monarch_char_obj.reign_end_year if monarch_char_obj.reign_end_year else 'current'
                    main_title_display_str = monarch_char_obj.titles[0] if monarch_char_obj.titles else "Leader"

                    # Set context year for __repr__ to get current age if alive
                    # The family tree's current_year should reflect the final year of simulation
                    age_context_year = final_family_tree_result.current_year
                    if monarch_char_obj.is_alive(age_context_year):
                        setattr(monarch_char_obj, '_repr_context_year', age_context_year)

                    print(f"{i + 1}. {monarch_char_obj.full_name}, {main_title_display_str} "
                          f"(Reign: {monarch_char_obj.reign_start_year}-{reign_end_display_str}) "
                          f"Age: {monarch_char_obj.get_age(age_context_year if monarch_char_obj.is_alive(age_context_year) else monarch_char_obj.death_year if monarch_char_obj.death_year else age_context_year)}")  # Complex age display

                    if hasattr(monarch_char_obj, '_repr_context_year'):  # Clean up temp attribute
                        delattr(monarch_char_obj, '_repr_context_year')
        else:
            print("No leaders were recorded for this dynasty.")
    else:
        print("\n--- Simulation Did Not Complete Successfully or Returned No Results (Local Runner) ---")

    print("\nLocal simulation script finished.")