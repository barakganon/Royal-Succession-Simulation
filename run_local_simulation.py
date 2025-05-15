# run_local_simulation.py
import random
import os
import json  # For potentially loading a user story from a file in the future
import signal
import sys
import logging
import traceback

# Import from our project structure
from utils.theme_manager import load_cultural_themes, get_theme, get_random_theme, generate_theme_from_story_llm
from utils.helpers import set_llm_globals_for_helpers  # To pass LLM model to helpers
from simulation_engine import configure_simulation_globals, run_simulation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simulation.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("royal_succession")

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
        logger.info(f"LLM Initialized for local simulation run: Model '{llm_model_name_to_use}'")
    else:
        logger.warning("LLM API Key not found. LLM-dependent features will use fallbacks or be disabled for this run.")
except ImportError:
    logger.warning("google-generativeai package not found. LLM features disabled for this run.")
except Exception as e_llm_init:
    logger.error(f"Error initializing LLM in run_local_simulation.py: {type(e_llm_init).__name__} - {e_llm_init}")
# --- End Centralized LLM Setup ---

# Global variables to track simulation state
simulation_running = False
family_tree_result = None
history_log_result = None

def signal_handler(sig, frame):
    """Handle interrupt signals gracefully"""
    global simulation_running
    
    if simulation_running:
        logger.info("\nReceived interrupt signal. Gracefully shutting down simulation...")
        simulation_running = False
        
        # Save any partial results if available
        if family_tree_result and history_log_result:
            logger.info("Saving partial simulation results before exit...")
            try:
                # Here you could implement saving partial results
                pass
            except Exception as e:
                logger.error(f"Error saving partial results: {e}")
        
        logger.info("Simulation terminated by user.")
    else:
        logger.info("\nReceived interrupt signal. Exiting immediately.")
    
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("--- Dynasty Saga Simulation (Local Runner Script) ---")

        # 1. Load predefined themes from JSON file using theme_manager
        # This also populates theme_manager.CULTURAL_THEMES_DATA
        loaded_themes_data = load_cultural_themes()
        if not loaded_themes_data:
            logger.critical("No predefined themes were loaded. Exiting if not using custom story with LLM.")
            # Allow to proceed if LLM is available for custom story, otherwise exit.
            if not (LLM_MODEL_INSTANCE_FOR_RUN and API_KEY_IS_CONFIGURED):
                sys.exit(1)

        # 2. --- Configuration for this specific simulation run ---

        # Option A: Use a predefined theme
        use_story_mode_flag = False
        # Make sure loaded_themes_data is not empty before trying to pick a theme
        if loaded_themes_data:
            # Randomly select a theme from available themes
            input_identifier_for_sim = random.choice(list(loaded_themes_data.keys()))
            logger.info(f"Selected theme: {input_identifier_for_sim}")
        else:  # Should only happen if file was missing AND we proceed for LLM custom story
            input_identifier_for_sim = "CUSTOM_ONLY_NO_FALLBACK"  # Special case
            if not use_story_mode_flag:  # If not in story mode and no themes, this is an issue
                logger.error("Error: No predefined themes and not in custom story mode. Cannot proceed.")
                sys.exit(1)

        # Option B: Use a custom story (uncomment to use)
        # use_story_mode_flag = True
        # user_story_text_input = """
        # Your custom dynasty story here.
        # Describe the setting, culture, and key historical events.
        # The more details you provide, the better the simulation will be.
        # """
        # input_identifier_for_sim = user_story_text_input

        # --- Simulation Parameters (Overrides) ---
        sim_years_to_run = 100  # Number of years to simulate for this run
        start_year_for_run = None  # None to use theme default, or specify a year
        succession_rule_for_run = None  # None to use theme default, or specify a rule

        # --- Global Settings for this Run ---
        g_verbose_logging_run = True
        g_viz_interval_run = 0  # Set to 0 for final plot only to avoid visualization errors
        g_use_llm_flair_run = False  # Disable LLM flair since we don't have an API key
        g_event_logging_run = True
        g_trait_logging_run = True
        
        # Ensure visualization directory exists
        os.makedirs('visualizations', exist_ok=True)

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
        logger.info(f"\nAttempting to start simulation...")
        if use_story_mode_flag:
            logger.info(f"Mode: Custom Story ('{str(input_identifier_for_sim)[:70]}...')")
            if not (LLM_MODEL_INSTANCE_FOR_RUN and API_KEY_IS_CONFIGURED):
                logger.warning(
                    "WARNING: LLM is required for custom story mode but is not available. Simulation may fail or use very basic defaults.")
        else:
            logger.info(f"Mode: Predefined Theme ('{input_identifier_for_sim}')")

        # Set simulation running flag
        simulation_running = True
        
        # The run_simulation function from simulation_engine.py will handle
        # theme loading/generation internally now using the theme_manager.
        family_tree_result, history_log_result = run_simulation(
            theme_name_or_user_story=input_identifier_for_sim,
            sim_years_override=sim_years_to_run,
            start_year_override=start_year_for_run,
            succession_rule_override=succession_rule_for_run,
            is_user_story=use_story_mode_flag
        )
        
        # Reset simulation running flag
        simulation_running = False

        # 5. Post-Simulation Output (if successful)
        if family_tree_result and history_log_result:
            logger.info("\n\n--- Simulation Run Concluded Successfully (Local Runner) ---")

            # Access the theme used for this run from the family_tree object
            # The FamilyTree object now stores its specific theme_config
            final_run_theme_config_used = family_tree_result.theme_config

            logger.info(f"Dynasty: {family_tree_result.dynasty_name}")
            if final_run_theme_config_used:
                logger.info(f"Theme Description: {final_run_theme_config_used.get('description', 'N/A')}")
            else:  # Should not happen if run_simulation completed successfully
                logger.warning("Theme description was not available for the completed run.")

            logger.info("\n--- Leaders of the Dynasty ---")
            if family_tree_result.all_monarchs_ever_ids:
                for i, monarch_id_val in enumerate(family_tree_result.all_monarchs_ever_ids):
                    monarch_char_obj = family_tree_result.get_person(monarch_id_val)
                    if monarch_char_obj:
                        reign_end_display_str = monarch_char_obj.reign_end_year if monarch_char_obj.reign_end_year else 'current'
                        main_title_display_str = monarch_char_obj.titles[0] if monarch_char_obj.titles else "Leader"

                        # Set context year for __repr__ to get current age if alive
                        # The family tree's current_year should reflect the final year of simulation
                        age_context_year = family_tree_result.current_year
                        if monarch_char_obj.is_alive(age_context_year):
                            setattr(monarch_char_obj, '_repr_context_year', age_context_year)

                        logger.info(f"{i + 1}. {monarch_char_obj.full_name}, {main_title_display_str} "
                              f"(Reign: {monarch_char_obj.reign_start_year}-{reign_end_display_str}) "
                              f"Age: {monarch_char_obj.get_age(age_context_year if monarch_char_obj.is_alive(age_context_year) else monarch_char_obj.death_year if monarch_char_obj.death_year else age_context_year)}")  # Complex age display

                        if hasattr(monarch_char_obj, '_repr_context_year'):  # Clean up temp attribute
                            delattr(monarch_char_obj, '_repr_context_year')
            else:
                logger.warning("No leaders were recorded for this dynasty.")
        else:
            logger.error("\n--- Simulation Did Not Complete Successfully or Returned No Results (Local Runner) ---")

        logger.info("\nLocal simulation script finished.")
    
    except Exception as e:
        logger.critical(f"Unhandled exception in simulation: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)