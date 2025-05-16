# simulation_engine.py
import random
import os
import json  # Not strictly needed here if theme_manager handles all JSON
from collections import defaultdict  # Used by History, but good for engine if needed
import logging
import traceback
import time
import signal
import sys

# --- Import from project structure ---
from models.person import Person
from models.family_tree import FamilyTree
from models.history import History

# theme_manager will handle loading themes from JSON file
from utils.theme_manager import get_theme, get_random_theme, generate_theme_from_story_llm, load_cultural_themes

# helpers will contain generate_name, generate_narrative_flair, etc.
from utils.helpers import generate_name, generate_narrative_flair, generate_story_from_chronicle, \
    set_llm_globals_for_helpers

# Import logging configuration
from utils.logging_config import setup_logger, log_performance

# plotter for visualizations
from visualization.plotter import visualize_family_tree_snapshot
import matplotlib.pyplot as plt

# Set up logger
logger = setup_logger('royal_succession.simulation_engine')

class SimulationEngine:
    """
    A class that encapsulates the simulation engine functionality.
    This class provides an interface for running royal succession simulations.
    """
    
    def __init__(self):
        """Initialize the SimulationEngine with default settings."""
        self.verbose_logging = True
        self.visualize_tree_interval_years = 50
        self.use_llm_flair = True
        self.verbose_event_logging = True
        self.verbose_trait_logging = True
        self.llm_model_instance = None
        self.google_api_key_is_set = False
        
    def configure(self, verbose_log=True, viz_interval=50, use_llm_flair=True,
                 event_log=True, trait_log=True, llm_model_obj=None, api_key_present_bool=False):
        """Configure the simulation engine settings."""
        self.verbose_logging = verbose_log
        self.visualize_tree_interval_years = viz_interval
        self.use_llm_flair = use_llm_flair
        self.verbose_event_logging = event_log
        self.verbose_trait_logging = trait_log
        self.llm_model_instance = llm_model_obj
        self.google_api_key_is_set = api_key_present_bool
        
        # Configure global settings for the simulation
        configure_simulation_globals(
            verbose_log=verbose_log,
            viz_interval=viz_interval,
            use_llm_flair=use_llm_flair,
            event_log=event_log,
            trait_log=trait_log,
            llm_model_obj=llm_model_obj,
            api_key_present_bool=api_key_present_bool
        )
        
    def run(self, theme_name_or_user_story=None, sim_years_override=None,
            start_year_override=None, succession_rule_override=None, is_user_story=False):
        """
        Run a royal succession simulation.
        
        Args:
            theme_name_or_user_story: The theme name or user story to use for the simulation
            sim_years_override: Override for the number of years to simulate
            start_year_override: Override for the starting year
            succession_rule_override: Override for the succession rule
            is_user_story: Whether the theme_name_or_user_story is a user story
            
        Returns:
            A tuple containing the family tree and history log
        """
        return run_simulation(
            theme_name_or_user_story=theme_name_or_user_story,
            sim_years_override=sim_years_override,
            start_year_override=start_year_override,
            succession_rule_override=succession_rule_override,
            is_user_story=is_user_story
        )

# --- Define BASE Constants (Master defaults for the simulation engine) ---
BASE_START_YEAR = 1000;
BASE_MAX_SIMULATION_YEARS = 200  # Default length of a run
BASE_MAX_AGE = 85;
BASE_MIN_MARRIAGE_AGE = 16
BASE_MAX_MARRIAGE_AGE_MALE = 55;
BASE_MAX_MARRIAGE_AGE_FEMALE = 45
BASE_MIN_FERTILITY_AGE_FEMALE = 18;
BASE_MAX_FERTILITY_AGE_FEMALE = 45
BASE_PREGNANCY_CHANCE_PER_YEAR = 0.40;
BASE_MAX_CHILDREN_PER_COUPLE = 8
BASE_CHILD_MORTALITY_RATE_UNDER_5 = 0.15;
BASE_ADULT_MORTALITY_BASE_PER_YEAR = 0.01
BASE_PRUNE_INTERVAL_YEARS = 40;
BASE_PRUNE_MAX_DISTANCE = 4
BASE_DYNASTY_WEALTH_START = 100

# --- Global Configs (Mutable by configure_simulation_globals) ---
VERBOSE_LOGGING = True;
VISUALIZE_TREE_INTERVAL_YEARS = 50
USE_LLM_FLAIR_IF_AVAILABLE = True;
VERBOSE_EVENT_LOGGING = True
VERBOSE_TRAIT_LOGGING = True

# LLM Model global (set by configure_simulation_globals)
LLM_MODEL_INSTANCE = None  # To be populated by main script
GOOGLE_API_KEY_IS_SET = False  # To be populated by main script


def configure_simulation_globals(verbose_log: bool, viz_interval: int, use_llm_flair: bool,
                                 event_log: bool, trait_log: bool,
                                 llm_model_obj, api_key_present_bool: bool):
    """Sets global configuration variables for the simulation run and dependent modules."""
    global VERBOSE_LOGGING, VISUALIZE_TREE_INTERVAL_YEARS, USE_LLM_FLAIR_IF_AVAILABLE
    global VERBOSE_EVENT_LOGGING, VERBOSE_TRAIT_LOGGING
    global LLM_MODEL_INSTANCE, GOOGLE_API_KEY_IS_SET

    VERBOSE_LOGGING = verbose_log
    VISUALIZE_TREE_INTERVAL_YEARS = viz_interval
    USE_LLM_FLAIR_IF_AVAILABLE = use_llm_flair
    VERBOSE_EVENT_LOGGING = event_log
    VERBOSE_TRAIT_LOGGING = trait_log

    LLM_MODEL_INSTANCE = llm_model_obj
    GOOGLE_API_KEY_IS_SET = api_key_present_bool

    # Pass LLM model and API key status to the helpers module where it's used
    set_llm_globals_for_helpers(LLM_MODEL_INSTANCE, GOOGLE_API_KEY_IS_SET)

    # Update Person class's static/class attributes for logging if they exist
    # This allows Person instances to check these flags without needing them passed everywhere.
    if hasattr(Person, 'VERBOSE_LOGGING'): Person.VERBOSE_LOGGING = verbose_log
    if hasattr(Person, 'VERBOSE_TRAIT_LOGGING'): Person.VERBOSE_TRAIT_LOGGING = trait_log

    if VERBOSE_LOGGING: print("Simulation globals configured.")



def run_simulation(theme_name_or_user_story: str = None,
                   sim_years_override: int = None,
                   start_year_override: int = None,
                   succession_rule_override: str = None,
                   is_user_story: bool = False) -> tuple[FamilyTree | None, History | None]:
    """
    Main function to orchestrate and run the dynasty simulation.
    """
    start_time = time.time()
    
    # Wrap the entire function in a try-except block to catch any unhandled exceptions
    # --- 1. Theme Loading and Configuration ---
    logger.info("Starting simulation with theme loading")
    theme_load_start = time.time()
    
    current_run_theme_config: dict | None = None
    dynasty_id_for_filenames: str = "DefaultDynasty"  # Fallback for naming output files

    if is_user_story and theme_name_or_user_story:
        logger.info("Attempting to generate custom theme from user story")
        # generate_theme_from_story_llm is imported from utils.theme_manager
        # It needs LLM_MODEL_INSTANCE and GOOGLE_API_KEY_IS_SET to be configured via configure_simulation_globals
        try:
            custom_theme_dict = generate_theme_from_story_llm(theme_name_or_user_story)
            if custom_theme_dict:
                current_run_theme_config = custom_theme_dict
                # Try to get a dynastic name from the generated theme for file naming
                surnames_list_custom = current_run_theme_config.get("surnames_dynastic")
                if surnames_list_custom and isinstance(surnames_list_custom, list) and surnames_list_custom:
                    dynasty_id_for_filenames = surnames_list_custom[0].replace(" ", "_")  # Use first for file ID
                else:
                    dynasty_id_for_filenames = "CustomStoryDynasty"  # Fallback
                logger.info(f"Successfully generated custom theme: {current_run_theme_config.get('description', 'N/A')}")
            else:  # LLM theme generation failed
                logger.warning("Failed to generate theme from user story. Falling back to a random predefined theme.")
                # get_random_theme is imported from utils.theme_manager
                theme_name_or_user_story, current_run_theme_config = get_random_theme()
                is_user_story = False  # Update flag as we are no longer using the user's story directly
                if current_run_theme_config and "description" not in current_run_theme_config:  # Error theme from get_random_theme
                    logger.error(f"CRITICAL FALLBACK ERROR: Could not load a random theme ('{theme_name_or_user_story}'). Aborting.")
                    return None, None
                logger.info(f"Using fallback predefined theme: {theme_name_or_user_story}")
        except Exception as theme_error:
            logger.error(f"Error generating theme from story: {str(theme_error)}")
            logger.error(traceback.format_exc())
            # Fallback to random theme
            theme_name_or_user_story, current_run_theme_config = get_random_theme()
            is_user_story = False
            logger.info(f"Using emergency fallback theme: {theme_name_or_user_story}")

    else:  # Handles predefined themes OR if custom story generation failed and fell back
            try:
                chosen_theme_key = theme_name_or_user_story
                if not chosen_theme_key:  # If None was passed and not a story
                    chosen_theme_key, current_run_theme_config = get_random_theme()
                    logger.info(f"No theme specified. Randomly selected: {chosen_theme_key}")
                else:
                    current_run_theme_config = get_theme(chosen_theme_key)  # From theme_manager
                    if not current_run_theme_config:  # If specific theme not found by key
                        logger.warning(f"Theme '{chosen_theme_key}' not found. Picking a random predefined theme.")
                        chosen_theme_key, current_run_theme_config = get_random_theme()
                        if current_run_theme_config and "description" not in current_run_theme_config:  # Error theme
                            logger.error(f"CRITICAL FALLBACK ERROR: Could not load random theme after specific fail ('{chosen_theme_key}'). Aborting.")
                            return None, None

                if current_run_theme_config and "description" not in current_run_theme_config:  # Final check after all attempts
                    logger.error(f"CRITICAL ERROR: Theme '{chosen_theme_key}' seems to be an error placeholder from theme_manager. Aborting.")
                    return None, None
                dynasty_id_for_filenames = chosen_theme_key.replace(" ", "_") if chosen_theme_key else dynasty_id_for_filenames
            except Exception as theme_error:
                logger.error(f"Error loading predefined theme: {str(theme_error)}")
                logger.error(traceback.format_exc())
                # Create a minimal emergency theme
                current_run_theme_config = {
                    "description": "Emergency Fallback Theme",
                    "start_year_suggestion": 1000,
                    "default_simulation_length": 100,
                    "succession_rule_default": "PRIMOGENITURE_MALE_PREFERENCE",
                    "surnames_dynastic": ["EmergencyHouse"],
                    "founder_title_male": "Lord",
                    "founder_title_female": "Lady"
                }
                dynasty_id_for_filenames = "EmergencyDynasty"
                logger.info("Created emergency fallback theme")

    if not current_run_theme_config:  # If still no theme after all logic
        logger.critical("FATAL: Could not load or generate any theme configuration. Aborting simulation.")
        return None, None
        
    theme_load_time = time.time() - theme_load_start
    log_performance("Theme loading", theme_load_time)
    # --- End Theme Loading ---


    # --- 2. Simulation Initialization ---
    init_start = time.time()
    try:
        logger.info("Initializing simulation")
        Person._next_id = 0  # Reset unique ID counter for Person class for this run
        history_log = History()
        History.start_buffering_initial_logs()  # Start buffering for founder/initial spouse events

        # Determine effective simulation parameters using overrides or theme defaults
        effective_start_year = start_year_override if start_year_override is not None \
            else int(current_run_theme_config.get("start_year_suggestion", BASE_START_YEAR))
        effective_sim_years = sim_years_override if sim_years_override is not None \
            else int(current_run_theme_config.get("default_simulation_length",
                                                BASE_MAX_SIMULATION_YEARS))  # Added default_simulation_length to theme possibility
        effective_succession_rule = succession_rule_override if succession_rule_override is not None \
            else current_run_theme_config.get("succession_rule_default", "PRIMOGENITURE_MALE_PREFERENCE")

        # Create the FamilyTree instance for this simulation run
        family = FamilyTree(history_logger_instance=history_log,
                            theme_config=current_run_theme_config,
                            succession_rule=effective_succession_rule)

        # Use the dynasty name chosen by FamilyTree (which picks from theme_config) for file ID consistency
        dynasty_id_for_filenames = family.dynasty_name.replace(" ", "_")

        family.current_year = effective_start_year  # Set the starting year for the family tree
        history_log.start_new_generation_summary(1)  # Initialize for the first generation's summary
    except Exception as init_error:
        logger.error(f"Error during simulation initialization: {str(init_error)}")
        logger.error(traceback.format_exc())
        return None, None
        
    init_time = time.time() - init_start
    log_performance("Simulation initialization", init_time)

    # --- 3. Founder & Spouse Creation ---
    founder_start = time.time()
    try:
        # (Logs from this section will be buffered by History class until flush)
        logger.info("Creating founder and spouse")
        _initialize_founder_and_spouse(family, effective_start_year, history_log)  # Use helper
        # --- End Founder Setup ---

        History.flush_initial_log_buffer()  # Print sorted initial logs; subsequent logs will be direct
    except Exception as founder_error:
        logger.error(f"Error creating founder and spouse: {str(founder_error)}")
        logger.error(traceback.format_exc())
        # Try to continue anyway
        
    founder_time = time.time() - founder_start
    log_performance("Founder creation", founder_time)

    # Initialize loop control variables
    last_prune_year = effective_start_year
    last_viz_year = effective_start_year
    generation_counter = 1  # generation_num in History starts at 0, summary starts with 1

    logger.info(f"Starting Simulation: House of {family.dynasty_name} ({current_run_theme_config.get('description')})")
    logger.info(f"Years: {effective_start_year} to {effective_start_year + effective_sim_years - 1}, Rule: {family.succession_rule}, Initial Wealth: {family.dynasty_wealth}")

    # Set up signal handler for graceful interruption
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    original_sigterm_handler = signal.getsignal(signal.SIGTERM)
    
    def simulation_signal_handler(sig, frame):
        """Handle interrupt signals during simulation"""
        logger.warning(f"Received signal {sig} during simulation. Performing early wrap-up.")
        
        # Perform early wrap-up
        try:
            _simulation_wrap_up(family, history_log, effective_start_year,
                               family.current_year - effective_start_year,
                               dynasty_id_for_filenames)
            logger.info("Early simulation wrap-up completed successfully")
        except Exception as wrap_error:
            logger.error(f"Error during early simulation wrap-up: {str(wrap_error)}")
        
        # Restore original handlers and re-raise signal
        signal.signal(signal.SIGINT, original_sigint_handler)
        signal.signal(signal.SIGTERM, original_sigterm_handler)
        os.kill(os.getpid(), sig)
    
    # Set custom signal handlers
    signal.signal(signal.SIGINT, simulation_signal_handler)
    signal.signal(signal.SIGTERM, simulation_signal_handler)

    # --- 4. Main Simulation Loop ---
    simulation_start = time.time()
    try:
        for year_idx_offset in range(effective_sim_years):
            year_start_time = time.time()
            
            current_simulation_year = effective_start_year + year_idx_offset
            family.current_year = current_simulation_year  # Critical: Update family's sense of time

            if VERBOSE_LOGGING and year_idx_offset > 0 and year_idx_offset % 25 == 0:  # Periodic major year marker
                current_pop_for_log = sum(1 for p_obj in family.members.values() if p_obj.is_alive(current_simulation_year))
                logger.info(f"Year: {current_simulation_year} | Dynasty: {family.dynasty_name} | Wealth: {family.dynasty_wealth} | Pop: {current_pop_for_log}")

            try:
                # --- A. Process World Events for the Year ---
                _process_world_events(family, current_simulation_year, history_log)

                # --- B. Yearly Processing for each Person ---
                for person_sim_id_to_process in list(family.members.keys()):  # Iterate over copy of IDs
                    try:
                        family.process_yearly_events_for_person(person_sim_id_to_process, current_simulation_year)
                    except Exception as person_error:
                        logger.error(f"Error processing events for person {person_sim_id_to_process} in year {current_simulation_year}: {str(person_error)}")
                        # Continue with other persons

                # --- C. Periodic Simulation-Level Tasks ---
                # Generation Summary & New Noble Introduction (approx every 35-55 years)
                if year_idx_offset > 0 and year_idx_offset % random.randint(35, 55) == 0:
                    generation_counter += 1
                    history_log.start_new_generation_summary(generation_counter)
                    if random.random() < 0.4:  # 40% chance each generation cycle
                        _introduce_new_nobles(family, current_simulation_year, history_log)

                # Population Recording for stats plotting
                current_year_end_population = sum(
                    1 for p_obj_pop in family.members.values() if p_obj_pop.is_alive(current_simulation_year))
                history_log.current_population_over_time.append((current_simulation_year, current_year_end_population))
                if VERBOSE_LOGGING and (year_idx_offset % 10 == 0 or year_idx_offset == effective_sim_years - 1):
                    logger.info(f"End of Year {current_simulation_year}: Living Population = {current_year_end_population}, Dynasty Wealth = {family.dynasty_wealth}")

                # Pruning
                prune_interval_from_theme = int(
                    BASE_PRUNE_INTERVAL_YEARS * current_run_theme_config.get("prune_interval_factor", 1.0))
                if prune_interval_from_theme > 0 and current_simulation_year >= last_prune_year + prune_interval_from_theme:
                    _perform_pruning(family, current_simulation_year, history_log)
                    last_prune_year = current_simulation_year

                # Visualization
                # VISUALIZE_TREE_INTERVAL_YEARS is a global, set by configure_simulation_globals from main script
                if VISUALIZE_TREE_INTERVAL_YEARS > 0 and current_simulation_year >= last_viz_year + VISUALIZE_TREE_INTERVAL_YEARS:
                    _perform_visualization(family, current_simulation_year, dynasty_id_for_filenames, generation_counter)
                    last_viz_year = current_simulation_year

                # Extinction Check
                if family.current_monarch is None and year_idx_offset > 7:  # Grace period of ~7 years after losing monarch
                    current_living_nobles_count = sum(1 for p_ext_check in family.members.values() if
                                                    p_ext_check.is_alive(current_simulation_year) and p_ext_check.is_noble)
                    if current_living_nobles_count == 0:
                        logger.info(f"SIMULATION END (Extinction of Nobles)")
                        logger.info(f"Year {current_simulation_year}: No living leader and no living nobles remaining. Dynasty {family.dynasty_name} has effectively ended.")
                        break  # Exit the main simulation loop
                        
                # Log year performance
                year_time = time.time() - year_start_time
                if year_idx_offset % 10 == 0:  # Log every 10 years to avoid excessive logging
                    log_performance(f"Year {current_simulation_year}", year_time,
                                   {"population": current_year_end_population, "wealth": family.dynasty_wealth})
                    
            except Exception as year_error:
                logger.error(f"Error processing year {current_simulation_year}: {str(year_error)}")
                logger.error(traceback.format_exc())
                # Continue with next year
    except Exception as sim_error:
        logger.error(f"Critical error in simulation loop: {str(sim_error)}")
        logger.error(traceback.format_exc())
    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, original_sigint_handler)
        signal.signal(signal.SIGTERM, original_sigterm_handler)
        
    simulation_time = time.time() - simulation_start
    log_performance("Main simulation loop", simulation_time,
                   {"years": effective_sim_years, "final_population": len(family.members)})

    # --- 5. End of Simulation Wrap-up ---
    wrap_start = time.time()
    try:
        _simulation_wrap_up(family, history_log, effective_start_year, effective_sim_years, dynasty_id_for_filenames)
    except Exception as wrap_error:
        logger.error(f"Error during simulation wrap-up: {str(wrap_error)}")
        logger.error(traceback.format_exc())
        
    wrap_time = time.time() - wrap_start
    log_performance("Simulation wrap-up", wrap_time)
    
    # Log total simulation time
    total_time = time.time() - start_time
    log_performance("Total simulation", total_time,
                   {"dynasty": family.dynasty_name, "years": effective_sim_years})
    
    logger.info(f"Simulation completed for House of {family.dynasty_name}")
    return family, history_log

# --- Helper Functions for run_simulation ---

def _initialize_founder_and_spouse(family_obj: FamilyTree, effective_start_year: int, history_log_obj: History):
    """Creates and sets up the founder and their initial spouse."""
    theme_config_local = family_obj.theme_config  # Use the family's theme config

    founder_gender = random.choice(["MALE", "FEMALE"])
    founder_given_name = generate_name(founder_gender, theme_config_local)
    founder_age_at_start = random.randint(25, 40)  # Founder is an adult
    founder_birth_actual_year = effective_start_year - founder_age_at_start

    founder = Person(name=founder_given_name, gender=founder_gender, birth_year=founder_birth_actual_year,
                     theme_config=theme_config_local,
                     explicit_surname=family_obj.dynasty_name,  # Use the surname FamilyTree already picked
                     is_noble=True, is_founder=True)
    family_obj.add_person(founder)  # Logs birth first (if not placeholder)

    spouse_for_founder = None
    if random.random() < 0.9:  # High chance of initial spouse
        spouse_gender = "FEMALE" if founder_gender == "MALE" else "MALE"
        spouse_given_name = generate_name(spouse_gender, theme_config_local)

        # Select a different surname for the spouse's family
        available_spouse_surnames = [s for s in theme_config_local.get("surnames_dynastic", ["OtherHouseDefault"]) if
                                     s != family_obj.dynasty_name]
        if not available_spouse_surnames: available_spouse_surnames = [f"NewHouse{Person._next_id}"]  # Unique fallback
        spouse_surname = random.choice(available_spouse_surnames)

        # Spouse age relative to founder, ensuring marriageable
        spouse_age_at_start = random.randint(
            max(globals().get("BASE_MIN_MARRIAGE_AGE", 16), founder_age_at_start - 7),  # Spouse not too much younger
            founder_age_at_start + 3  # Spouse not too much older
        )
        spouse_birth_actual_year = effective_start_year - spouse_age_at_start

        spouse_for_founder = Person(name=spouse_given_name, gender=spouse_gender, birth_year=spouse_birth_actual_year,
                                    theme_config=theme_config_local,
                                    explicit_surname=spouse_surname, is_noble=True)
        family_obj.add_person(spouse_for_founder)  # Add spouse (logs their birth)

        # Optionally create placeholder parents for this initial spouse
        if random.random() < 0.7:  # 70% chance
            family_obj._create_placeholder_parents_for_imported_spouse(spouse_for_founder, effective_start_year)

    # Grant title to founder AFTER spouse might have been added (for log order)
    founder_title_text = (theme_config_local.get("founder_title_male", "Leader") if founder_gender == "MALE"
                          else theme_config_local.get("founder_title_female", "Leader"))
    founder.add_title(founder_title_text, history_log_obj, effective_start_year)  # add_title logs event

    family_obj.current_monarch = founder
    if founder.id not in family_obj.all_monarchs_ever_ids:
        family_obj.all_monarchs_ever_ids.append(founder.id)

    # Attempt to marry founder and spouse
    if spouse_for_founder:
        marriage_attempt_year = effective_start_year + random.randint(0, 1)  # Try to marry in first year or two

        founder_can_marry_flag = founder.can_marry(marriage_attempt_year)
        spouse_can_marry_flag = spouse_for_founder.can_marry(marriage_attempt_year)

        if founder_can_marry_flag and spouse_can_marry_flag:
            family_obj.marry_people(founder.id, spouse_for_founder.id, marriage_attempt_year,
                                    is_arranged_external_marriage=True)
        elif founder.can_marry(effective_start_year) and spouse_for_founder.can_marry(
                effective_start_year):  # Fallback to sim start year
            family_obj.marry_people(founder.id, spouse_for_founder.id, effective_start_year,
                                    is_arranged_external_marriage=True)
        elif VERBOSE_LOGGING:
            print(
                f"Initial Marriage SKIPPED for founder {founder.full_name} & {spouse_for_founder.full_name} (eligibility fail). "
                f"Founder can_marry({marriage_attempt_year}): {founder_can_marry_flag}, "
                f"Spouse can_marry({marriage_attempt_year}): {spouse_can_marry_flag}")


def _introduce_new_nobles(family_obj: FamilyTree, current_year: int, history_log_obj: History):
    # ... (Full logic as defined in previous correct version)
    num_to_introduce = random.randint(1, 2)
    if VERBOSE_LOGGING: print(
        f"Year {current_year}: Introducing {num_to_introduce} new noble individuals to the world.")
    for _ in range(num_to_introduce):
        new_person_gender = random.choice(["MALE", "FEMALE"])
        new_person_name = generate_name(new_person_gender, family_obj.theme_config)
        available_surnames_pool = [s_name for s_name in
                                   family_obj.theme_config.get("surnames_dynastic", ["MinorNobleDefault"]) if
                                   s_name != family_obj.dynasty_name]
        if not available_surnames_pool: available_surnames_pool = [f"NewArrival{Person._next_id}"]
        new_person_surname = random.choice(available_surnames_pool)
        new_person_age = random.randint(globals().get("BASE_MIN_MARRIAGE_AGE", 16),
                                        globals().get("BASE_MAX_MARRIAGE_AGE_FEMALE", 45) - 2)
        new_person_birth_year = current_year - new_person_age
        newly_introduced_person = Person(name=new_person_name, gender=new_person_gender,
                                         birth_year=new_person_birth_year,
                                         theme_config=family_obj.theme_config, explicit_surname=new_person_surname,
                                         is_noble=True)
        family_obj.add_person(newly_introduced_person)
        history_log_obj.log_event(year=current_year,
                                  event_string=f"A new noble figure, {newly_introduced_person.full_name} of House {new_person_surname}, has gained prominence.",
                                  person1_id=newly_introduced_person.id, event_type="new_noble_arrival")


def _perform_pruning(family_obj: FamilyTree, current_year: int, history_log_obj: History):
    # ... (Full logic as defined in previous correct version)
    if VERBOSE_LOGGING: print(f"\nYear {current_year}: Evaluating family tree for pruning.")
    prune_dist_factor = family_obj.theme_config.get("prune_distance_factor", 1.0)
    max_prune_dist = int(globals().get("BASE_PRUNE_MAX_DISTANCE", 4) * prune_dist_factor)
    pruned_individuals_list = family_obj.prune_distant_relatives(max_distance=max(2, max_prune_dist))
    if pruned_individuals_list:
        history_log_obj.all_pruned_individuals_details.extend(pruned_individuals_list)
        history_log_obj.gen_pruned_count += len(pruned_individuals_list)
        for p_info_sample_dict in pruned_individuals_list[:min(2, len(pruned_individuals_list))]:
            reason_text = history_log_obj._simplify_prune_reason(p_info_sample_dict.get('reason', 'N/A'))
            history_log_obj.gen_pruned_sample_info.append({'name': p_info_sample_dict['name'], 'reason': reason_text})
        history_log_obj.gen_pruned_sample_info = history_log_obj.gen_pruned_sample_info[-5:]


def _perform_visualization(family_obj: FamilyTree, current_year: int, dynasty_id_for_filenames_str: str,
                           generation_counter_val: int):
    # ... (Full logic as defined in previous correct version)
    if VERBOSE_LOGGING: print(f"\nYear {current_year}: Generating family tree visualization.")
    visualize_family_tree_snapshot(family_tree_obj=family_obj, year=current_year,
                                   filename_suffix=f"_{dynasty_id_for_filenames_str}_gen{generation_counter_val}",
                                   display_mode="monarch_focus")


def _process_world_events(family_obj: FamilyTree, current_year: int, history_log_obj: History):
    """Processes world events for the current year."""
    theme_event_definitions_list = family_obj.theme_config.get("events", [])
    if not theme_event_definitions_list: return
    random.shuffle(theme_event_definitions_list)
    for event_definition_dict in theme_event_definitions_list:
        min_event_year = event_definition_dict.get("min_year", 0)
        max_event_year = event_definition_dict.get("max_year", 99999)
        event_chance = event_definition_dict.get("chance_per_year", 0.0)
        if current_year >= min_event_year and current_year <= max_event_year and random.random() < event_chance:
            event_name_str = event_definition_dict.get("name", "A Mysterious Happening")
            raw_event_narrative = event_definition_dict.get("narrative", "Its consequences were felt.")
            formatted_narrative = raw_event_narrative.replace("{dynasty_name}", family_obj.dynasty_name).replace(
                "{location_flavor}", family_obj.theme_config.get("location_flavor", "these lands"))
            if "{rival_clan_name}" in formatted_narrative:
                rival_surnames_pool = [s for s in family_obj.theme_config.get("surnames_dynastic", ["Rivals"]) if
                                       s != family_obj.dynasty_name]
                chosen_rival_name_str = random.choice(rival_surnames_pool) if rival_surnames_pool else "a Rival House"
                formatted_narrative = formatted_narrative.replace("{rival_clan_name}", chosen_rival_name_str)
            if VERBOSE_EVENT_LOGGING: print(f"EVENT TRIGGERED (Year {current_year}): {event_name_str}!")
            wealth_change_amount = event_definition_dict.get("wealth_change", 0)
            if wealth_change_amount != 0:
                prev_wealth = family_obj.dynasty_wealth;
                family_obj.dynasty_wealth = max(0, family_obj.dynasty_wealth + wealth_change_amount)
                if VERBOSE_EVENT_LOGGING: print(
                    f"  Wealth Change: {wealth_change_amount:+.0f}. Old: {prev_wealth}, New: {family_obj.dynasty_wealth}")
            mort_factor = event_definition_dict.get("mortality_impact_factor");
            duration = event_definition_dict.get("duration")
            if mort_factor is not None and duration is not None:
                event_id_str = event_definition_dict.get("id", event_name_str.lower().replace(" ", "_"))
                family_obj.active_event_effects[event_id_str] = {"end_year": current_year + duration,
                                                                 "mortality_impact_factor": float(mort_factor)}
                if VERBOSE_EVENT_LOGGING: print(
                    f"  Mortality impact x{float(mort_factor):.2f} for {duration} years due to '{event_name_str}'.")
            event_details_flair = {'event_name': event_name_str, 'event_narrative': formatted_narrative}
            history_log_obj.log_event(year=current_year,
                                      event_string=generate_narrative_flair("event_generic", family_obj.theme_config,
                                                                            subject_name=family_obj.dynasty_name,
                                                                            year=current_year,
                                                                            details=event_details_flair),
                                      event_type="generic_event",
                                      person1_id=family_obj.current_monarch.id if family_obj.current_monarch else None)
            trait_grant = event_definition_dict.get("trait_grant_on_leader")
            if trait_grant and family_obj.current_monarch and family_obj.current_monarch.add_trait(trait_grant,
                                                                                                   current_year,
                                                                                                   f"the {event_name_str}"):
                if VERBOSE_EVENT_LOGGING: print(
                    f"  Leader {family_obj.current_monarch.full_name} gained trait: '{trait_grant}'.")
            break  # Only one world event per year


def _simulation_wrap_up(family_obj: FamilyTree, history_log_obj: History, start_year: int, sim_years: int,
                        dynasty_id_for_files_str: str):
    # ... (Full wrap-up logic as defined in the previous correct response, including stats printing, plot calls, and LLM story generation call) ...
    final_year = start_year + sim_years - 1
    print(f"\n--- SIMULATION COMPLETED FOR HOUSE OF {family_obj.dynasty_name} ---")
    print(f"Duration: {start_year} to {final_year} ({sim_years} simulated years)")
    history_log_obj.log_generation_summary_to_console()
    if VISUALIZE_TREE_INTERVAL_YEARS >= 0:
        print(f"\nGenerating final family tree visualization for year {final_year}...")
        visualize_family_tree_snapshot(family_obj, final_year, f"_{dynasty_id_for_files_str}_final",
                                       display_mode="living_nobles")
    print("\n--- Overall Simulation Statistics ---")
    overall_stats = history_log_obj.get_overall_stats_summary(family_obj, family_obj.all_monarchs_ever_ids, final_year,
                                                              start_year)
    for stat_key, stat_value in overall_stats.items():
        stat_name_pretty = stat_key.replace('_', ' ').capitalize()
        if stat_key == "pruning_reasons_summary":
            print(f"  {stat_name_pretty}:"); [print(f"    - {r}: {c}") for r, c in stat_value.items()] if isinstance(
                stat_value, dict) and stat_value else print("    - None")
        elif stat_key == "sample_of_pruned_individuals_overall":
            print(f"  {stat_name_pretty}:"); [print(f"    - {item}") for item in stat_value] if isinstance(stat_value,
                                                                                                           list) and stat_value else print(
                f"    - {stat_value}")
        else:
            print(f"  {stat_name_pretty}: {stat_value:.2f}" if isinstance(stat_value,
                                                                          float) else f"  {stat_name_pretty}: {stat_value}")
    if history_log_obj.current_population_over_time:  # Population Plot
        print("\n--- Plotting Population Over Time ---")
        years_pop, pop_counts = zip(*history_log_obj.current_population_over_time)
        plt.figure(figsize=(10, 5));
        plt.plot(years_pop, pop_counts, marker='.', linestyle='-', markersize=3, linewidth=1, color='darkcyan')
        plt.title(f"Population: {family_obj.dynasty_name}", fontsize=12);
        plt.xlabel("Year", fontsize=10);
        plt.ylabel("Count", fontsize=10)
        plt.grid(True, ls=':', alpha=0.6);
        plt.xticks(fontsize=8);
        plt.yticks(fontsize=8);
        plt.tight_layout()
        viz_dir = "visualizations";
        os.makedirs(viz_dir, exist_ok=True)
        pop_fn = os.path.join(viz_dir, f"pop_plot_{dynasty_id_for_files_str}_{start_year}_to_{final_year}.png")
        plt.savefig(pop_fn, dpi=100, bbox_inches='tight');
        print(f"Population plot saved: {pop_fn}");
        plt.show();
        plt.close()
    birth_death_counts_by_year = defaultdict(lambda: {"births": 0, "deaths": 0})  # Birth/Death Plot
    for yr, _, _, _, ev_type in history_log_obj.log:
        if yr is not None:
            if ev_type == "birth":
                birth_death_counts_by_year[yr]["births"] += 1
            elif ev_type == "death":
                birth_death_counts_by_year[yr]["deaths"] += 1
    if birth_death_counts_by_year:
        print("\n--- Plotting Births and Deaths Per Year ---")
        sorted_years = sorted(birth_death_counts_by_year.keys())
        births_data = [birth_death_counts_by_year[yr]["births"] for yr in sorted_years]
        deaths_data = [birth_death_counts_by_year[yr]["deaths"] for yr in sorted_years]
        plt.figure(figsize=(10, 5));
        plt.plot(sorted_years, births_data, label='Births/Year', color='lightgreen', alpha=0.9, linewidth=1.5,
                 marker='o', markersize=2, linestyle='--')
        plt.plot(sorted_years, deaths_data, label='Deaths/Year', color='lightcoral', alpha=0.9, linewidth=1.5,
                 marker='x', markersize=3, linestyle=':')
        plt.title(f"Births & Deaths: {family_obj.dynasty_name}", fontsize=12);
        plt.xlabel("Year", fontsize=10);
        plt.ylabel("Count", fontsize=10)
        plt.legend(fontsize='small');
        plt.grid(True, ls=':', alpha=0.6);
        plt.xticks(fontsize=8);
        plt.yticks(fontsize=8);
        plt.tight_layout()
        bd_fn = os.path.join("visualizations",
                             f"births_deaths_plot_{dynasty_id_for_files_str}_{start_year}_to_{final_year}.png")
        plt.savefig(bd_fn, dpi=100, bbox_inches='tight');
        print(f"Birth/Death plot saved: {bd_fn}");
        plt.show();
        plt.close()
    full_chronicle = history_log_obj.get_chronicle()  # LLM Story
    if full_chronicle.strip() and LLM_MODEL_INSTANCE and GOOGLE_API_KEY_IS_SET:
        print("\n--- Generating LLM Narrative Summary ---")
        narrative_story = generate_story_from_chronicle(full_chronicle, family_obj.theme_config,
                                                        family_obj.dynasty_name, start_year, final_year)
        print("\n--- Generated Saga ---");
        print(narrative_story)
        story_fn = f"saga_{dynasty_id_for_files_str}_{start_year}_to_{final_year}.txt"
        with open(story_fn, "w", encoding="utf-8") as f:
            f.write(
                f"Saga of {family_obj.dynasty_name}\nYears:{start_year}-{final_year}\nTheme:{family_obj.theme_config.get('description')}\n{'=' * 30}\n\n{narrative_story}")
        print(f"\nSaga saved: {story_fn}")
    else:
        print("\nSkipping LLM narrative summary (check chronicle/LLM setup).")
    chronicle_fn = f"chronicle_{dynasty_id_for_files_str}_{start_year}_to_{final_year}.txt"  # Save Chronicle
    with open(chronicle_fn, "w", encoding="utf-8") as f:
        f.write(
            f"Chronicle of {family_obj.dynasty_name} ({family_obj.theme_config.get('description')})\nYears:{start_year}-{final_year}\n{'-' * 30}\n{full_chronicle}")
    print(f"\nFull chronicle saved: {chronicle_fn}")
    return family_obj, history_log_obj


print("simulation_engine.py defined with refactored run_simulation and helpers.")