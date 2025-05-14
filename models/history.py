# models/history.py
from collections import defaultdict
import random  # For sampling pruned individuals in stats summary

# --- Configuration Placeholders ---
# VERBOSE_LOGGING would ideally be imported from a central config or set by the main script.
VERBOSE_LOGGING = True  # Example default, will be overridden by configure_simulation_globals

# --- Forward type hints for cleaner code if classes are in separate files ---
# This helps type checkers and linters without creating circular import dependencies at runtime.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .person import Person
    from .family_tree import FamilyTree  # Assuming FamilyTree will be in models.family_tree


class History:
    """
    Manages the historical log of events, generation summaries,
    and overall simulation statistics.
    """
    _buffering_initial_logs: bool = False  # Class attribute to control global buffering state for setup
    _initial_log_buffer: list = []  # Class attribute for the setup log buffer

    def __init__(self):
        """Initializes the History object."""
        self.log: list[tuple] = []
        # Log entry format: (year, event_string, person1_id, person2_id, event_type)

        self.generation_num: int = 0  # Current generation number being tracked for summary

        # Statistics for the current generation being summarized
        self._reset_generation_stats()

        # Data tracked over the entire simulation
        self.current_population_over_time: list[tuple[int, int]] = []  # [(year, population_count)]
        self.all_pruned_individuals_details: list[dict] = []  # Stores detailed dicts for each pruned person
        self.events_triggered_counts: defaultdict[str, int] = defaultdict(int)  # Counts of event_types

    def _reset_generation_stats(self):
        """Resets statistics for the current or upcoming generation's summary."""
        self.gen_births: int = 0
        self.gen_deaths: int = 0
        self.gen_marriages: int = 0
        self.gen_successions: int = 0
        self.gen_new_monarch_name: str | None = None
        self.gen_marriage_pairs_names: list[str] = []  # e.g., ["John&Mary", "Louis&Anne"]
        self.gen_pruned_count: int = 0
        self.gen_pruned_sample_info: list[dict] = []  # Stores a few {'name': str, 'reason': str} for gen summary

    def log_event(self, year: int | None, event_string: str, person1_id: int = None,
                  person2_id: int = None, event_type: str = None):
        """
        Logs a simulation event and updates relevant statistics.

        Args:
            year: The year the event occurred. Can be None for timeless system messages.
            event_string: The narrative description of the event.
            person1_id: ID of the primary person involved.
            person2_id: ID of a secondary person involved (e.g., in a marriage).
            event_type: A string categorizing the event (e.g., "birth", "death", "generic_event").
        """
        log_entry = (year, event_string, person1_id, person2_id, event_type)
        self.log.append(log_entry)

        # Handle initial log buffering (for founder setup)
        if History._buffering_initial_logs:
            History._initial_log_buffer.append(log_entry)
        elif VERBOSE_LOGGING:  # Direct print to console if not buffering
            print(f"Year {year if year is not None else '----'}: {event_string}")

        # Count all specific event types for overall statistics
        if event_type:
            self.events_triggered_counts[event_type] += 1

        # Update stats for the current generation's summary
        if event_type == "birth":
            self.gen_births += 1
        elif event_type == "death":
            self.gen_deaths += 1
        elif event_type == "marriage":
            self.gen_marriages += 1
        elif event_type == "succession_end":
            self.gen_successions += 1
        # Note: gen_pruned_count and gen_pruned_sample_info are updated by the
        # simulation_engine after calling FamilyTree.prune_distant_relatives.

    @classmethod
    def start_buffering_initial_logs(cls):
        """Activates buffering for initial setup phase logs."""
        cls._buffering_initial_logs = True
        cls._initial_log_buffer = []  # Ensure buffer is clear

    @classmethod
    def flush_initial_log_buffer(cls):
        """Prints sorted buffered initial logs to console and deactivates buffering."""
        if VERBOSE_LOGGING and cls._initial_log_buffer:
            print("\n--- Initial Setup Events (Chronological Order) ---")

            # Define a sort key for initial events to make console output more logical
            def sort_key_for_initial_log(log_item_tuple: tuple):
                year_val = log_item_tuple[0] if log_item_tuple[0] is not None else -float('inf')
                event_type_val = log_item_tuple[4]
                # Prioritize common setup events
                type_order_preference = {
                    "birth": 0,
                    "new_noble_arrival": 1,  # For placeholder parents if they use this type
                    "trait_assignment": 2,  # If traits were logged as events
                    "marriage": 3,
                    "title_grant": 4,
                    "generic_event": 5  # For any other initial setup events
                }
                return (year_val, type_order_preference.get(event_type_val, 99))  # Unknown types last

            for year_val, event_str_val, _, _, _ in sorted(cls._initial_log_buffer, key=sort_key_for_initial_log):
                print(f"Year {year_val if year_val is not None else '----'}: {event_str_val}")
            print("------------------------------------------------\n")

        cls._initial_log_buffer = []  # Clear the buffer
        cls._buffering_initial_logs = False  # Deactivate buffering

    def _console_print(self, message: str):  # Internal helper for printing summaries
        """Prints a message to the console (respecting VERBOSE_LOGGING if it were used here)."""
        # For summaries, we usually always want to print them if the method is called.
        print(message)

    def start_new_generation_summary(self, generation_number: int):
        """
        Finalizes the summary for the previous generation (if any) and
        resets counters for the new generation.
        """
        if self.generation_num > 0:  # Log summary for the *completed* generation
            self.log_generation_summary_to_console()

        self.generation_num = generation_number
        self._reset_generation_stats()  # Prepare for the new generation
        self._console_print(f"--- Starting Generation {self.generation_num} Chronicle ---")

    def log_generation_summary_to_console(self):
        """Prints the summary of the most recently completed generation to the console."""
        self._console_print(f"\n--- Summary for Generation {self.generation_num} ---")
        self._console_print(f"  Births: {self.gen_births}, Deaths: {self.gen_deaths}, Marriages: {self.gen_marriages}")

        leader_info_str = f"(New Leader: {self.gen_new_monarch_name})" if self.gen_new_monarch_name else ""
        self._console_print(f"  Successions: {self.gen_successions} {leader_info_str}")

        marriages_str = ', '.join(self.gen_marriage_pairs_names) if self.gen_marriage_pairs_names else 'None'
        self._console_print(f"  Marriage Pairs This Gen: {len(self.gen_marriage_pairs_names)} ({marriages_str})")

        self._console_print(f"  Pruned This Gen: {self.gen_pruned_count}")
        if self.gen_pruned_sample_info:
            self._console_print(f"    Sample Pruned Individuals:")
            for entry in self.gen_pruned_sample_info:
                name = entry.get('name', 'Unknown Person')
                reason = entry.get('reason', 'Unknown Reason')
                self._console_print(f"      - {name} (Reason: {reason})")
        self._console_print("---------------------------------------\n")

    def get_chronicle(self) -> str:
        """Returns the full narrative log as a single string, sorted chronologically."""

        def sort_key_for_full_chronicle(log_item_tuple: tuple):
            year_val = log_item_tuple[0] if log_item_tuple[0] is not None else -float('inf')
            event_type_val = log_item_tuple[4]
            # Define a comprehensive order for all event types in the final chronicle
            type_order_preference = {
                "birth": 0, "new_noble_arrival": 1, "trait_assignment": 2, "marriage": 3,
                "title_grant": 4, "generic_event": 5, "event_generic": 5,  # Alias
                "succession_start": 6, "succession_end": 7,
                "pruning_detail": 8, "pruning_event_main": 9,  # Pruning summary after details
                "death": 10, "succession_crisis": 11
            }
            return (year_val, type_order_preference.get(event_type_val, 50))  # Unknown types towards end

        sorted_log_entries = sorted(self.log, key=sort_key_for_full_chronicle)
        return "\n".join([f"Year {entry[0] if entry[0] is not None else '-----'}: {entry[1]}"
                          for entry in sorted_log_entries])

    def _simplify_prune_reason(self, reason_str: str) -> str:
        """Helper to get a more concise summary of a pruning reason string for display."""
        if "Exceeded max distance" in reason_str: return "Too Distant from Leader"
        if "Not connected" in reason_str: return "Unconnected to Leader's Lineage"
        if "No blood path" in reason_str: return "No Blood Path to Leader"
        if "No active leader" in reason_str: return "Peripheral (No Active Leader)"
        if "Graph error" in reason_str: return "Graph Calculation Error"
        # Return the first part of the reason if it's long, or the whole thing if no period
        return reason_str.split('.')[0] if '.' in reason_str else reason_str

    def get_overall_stats_summary(self, family_tree_obj: 'FamilyTree', all_monarch_ids: list[int],
                                  end_year: int, start_year_sim: int) -> dict:
        """Generates a dictionary of key summary statistics for the entire simulation."""
        stats = {}

        # Basic population and duration stats
        final_living_people = [p for p in family_tree_obj.members.values() if p.is_alive(end_year)]
        stats["final_living_pop_at_end"] = len(final_living_people)
        stats["total_people_ever_simulated"] = Person._next_id  # Access class variable
        stats["total_people_in_tree_at_sim_end"] = len(family_tree_obj.members)
        stats["sim_duration_years"] = end_year - start_year_sim
        stats["num_generations_logged"] = self.generation_num

        # Leadership stats
        stats["total_leaders_reigned"] = len(all_monarch_ids)
        reign_durations_list = []
        for monarch_id_val in all_monarch_ids:
            monarch_character = family_tree_obj.get_person(monarch_id_val)
            if monarch_character and monarch_character.reign_start_year is not None:
                reign_end_actual = monarch_character.reign_end_year if monarch_character.reign_end_year is not None else end_year
                if reign_end_actual >= monarch_character.reign_start_year:  # Ensure valid duration
                    reign_durations_list.append(reign_end_actual - monarch_character.reign_start_year)
        stats["avg_reign_duration_years"] = sum(reign_durations_list) / len(
            reign_durations_list) if reign_durations_list else 0

        # Counts based on logged event types from self.events_triggered_counts
        stats["total_births_logged"] = self.events_triggered_counts.get("birth", 0)
        stats["total_deaths_logged"] = self.events_triggered_counts.get("death", 0)
        stats["total_marriages_logged"] = self.events_triggered_counts.get("marriage", 0)
        stats["total_successions_logged"] = self.events_triggered_counts.get("succession_end", 0)
        stats["total_world_events_triggered"] = self.events_triggered_counts.get("generic_event", 0)
        stats["total_new_nobles_introduced"] = self.events_triggered_counts.get("new_noble_arrival", 0)
        stats["total_pruning_summary_events"] = self.events_triggered_counts.get("pruning_event_main", 0)

        # Population trend stats (from data collected yearly)
        if self.current_population_over_time:
            populations_list_data = [pop_count for year_val, pop_count in self.current_population_over_time]
            stats["final_recorded_population_value"] = populations_list_data[-1] if populations_list_data else stats[
                "final_living_pop_at_end"]
            stats["min_population_during_sim"] = min(populations_list_data) if populations_list_data else 0
            stats["max_population_during_sim"] = max(populations_list_data) if populations_list_data else 0
            stats["avg_population_during_sim"] = sum(populations_list_data) / len(
                populations_list_data) if populations_list_data else 0
        else:  # Fallbacks if no yearly population data was recorded
            stats["final_recorded_population_value"] = stats["final_living_pop_at_end"]
            stats["min_population_during_sim"] = 0
            stats["max_population_during_sim"] = 0
            stats["avg_population_during_sim"] = 0

        # Detailed Pruning Stats
        stats["total_individuals_pruned_ever"] = len(self.all_pruned_individuals_details)
        pruning_reasons_counts_dict = defaultdict(int)
        for p_detail_item in self.all_pruned_individuals_details:
            simplified_reason = self._simplify_prune_reason(p_detail_item.get("reason", "Unknown Reason"))
            pruning_reasons_counts_dict[simplified_reason] += 1
        stats["pruning_reasons_summary"] = dict(pruning_reasons_counts_dict)

        # Sample of pruned individuals for the overall summary report
        sample_size_for_pruned_report = min(5, len(self.all_pruned_individuals_details))
        list_to_sample_from = self.all_pruned_individuals_details
        if len(self.all_pruned_individuals_details) > sample_size_for_pruned_report:  # Only sample if list is larger
            list_to_sample_from = random.sample(self.all_pruned_individuals_details, sample_size_for_pruned_report)

        sample_pruned_strings_for_report = [
            f"{p_info['name']} (Born:{p_info['birth_year']}, Pruned Yr:{p_info['year']}: {self._simplify_prune_reason(p_info.get('reason', 'N/A'))})"
            for p_info in list_to_sample_from  # Use the (potentially sampled) list
        ]
        stats[
            "sample_of_pruned_individuals_overall"] = sample_pruned_strings_for_report if sample_pruned_strings_for_report else "None Pruned or No Details."

        return stats


print("models.history.History class defined with log buffering, population, pruning stats, and event counts.")