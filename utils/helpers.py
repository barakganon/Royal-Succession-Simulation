# utils/helpers.py
import random
import os

# Import the LLM library; this assumes google.generativeai is installed
try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore # Make type checker happy if not installed
    print("Warning (utils/helpers.py): google-generativeai not installed. LLM features will be disabled.")

# --- Global Configs (These are intended to be set by the main script, e.g., simulation_engine.py or run_local_simulation.py) ---
VERBOSE_LOGGING = True  # Default, should be overridden by main script's configuration
USE_LLM_FLAIR_IF_AVAILABLE = True  # Default, should be overridden

# These will be populated by set_llm_globals_for_helpers() called from the main script
LLM_MODEL_GLOBAL = None
GOOGLE_API_KEY_GLOBAL = False  # Indicates if API key was successfully configured


def set_llm_globals_for_helpers(llm_model_instance, api_key_is_present: bool):
    """Sets the LLM model instance and API key status for use within this helpers module."""
    global LLM_MODEL_GLOBAL, GOOGLE_API_KEY_GLOBAL
    LLM_MODEL_GLOBAL = llm_model_instance
    GOOGLE_API_KEY_GLOBAL = api_key_is_present
    if VERBOSE_LOGGING:
        status_msg = f"Helpers Module: LLM Globals Set. Model Instance: {'Available' if LLM_MODEL_GLOBAL else 'None'}, API Key Configured: {GOOGLE_API_KEY_GLOBAL}"
        print(status_msg)


def generate_name(gender: str, theme_config: dict) -> str:
    """Generates a name based on the cultural theme."""
    name_key = "names_male" if gender.upper() == "MALE" else "names_female"
    default_placeholder = f"{gender.capitalize()}NamePlaceholder"
    name_list = theme_config.get(name_key, [default_placeholder])

    if not name_list:
        return default_placeholder
    return random.choice(name_list)


def generate_narrative_flair(category: str, theme_config: dict, subject_name: str = "",
                             object_name: str = "", year: int = None, details: dict = None) -> str:
    """
    Generates a flavorful sentence for historical events, using LLM if available.
    """
    details = details or {}
    # Prepare subject traits string for LLM prompt and fallback
    subject_traits_desc = "of unknown disposition"  # Default
    if 'subject_person_obj' in details and hasattr(details['subject_person_obj'], 'traits'):
        traits_list = details['subject_person_obj'].traits
        if traits_list:
            subject_traits_desc = f"the {', '.join(traits_list)}"

    # --- LLM Call for Flair ---
    if USE_LLM_FLAIR_IF_AVAILABLE and LLM_MODEL_GLOBAL and GOOGLE_API_KEY_GLOBAL:
        try:
            llm_persona = theme_config.get("llm_persona_prompt", "You are a skilled historian and storyteller.")

            prompt_context = f"Event Category: '{category}'. Approximate Year: {year}."
            if subject_name:
                prompt_context += f" Primary Figure: {subject_name} (known as {subject_traits_desc})."
            if object_name:
                prompt_context += f" Secondary Figure/Object: {object_name}."

            # Filter details to pass only simple, relevant types to LLM for flair
            simple_details_for_flair = {
                k: v for k, v in details.items()
                if isinstance(v, (str, int, float, bool)) and k not in ['subject_traits', 'age', 'is_monarch']
                # Age/monarch status handled by fallback string directly
            }
            if 'event_name' in details: simple_details_for_flair['event_name'] = details[
                'event_name']  # Ensure event name passes
            if 'event_narrative' in details: simple_details_for_flair['event_narrative_hint'] = str(
                details['event_narrative'])[:100]  # Pass hint of narrative

            if simple_details_for_flair:
                prompt_context += f" Additional Context: {str(simple_details_for_flair)}."

            prompt = (
                f"{llm_persona}\n"
                f"You are chronicling a family saga with a specific thematic tone: '{theme_config.get('description', 'a general historical saga')}'.\n"
                f"Based on the following event information, craft a single, concise, and evocative sentence for the historical record (under 200 characters if possible):\n"
                f"{prompt_context}\n"
                f"Your sentence MUST reflect your persona and the theme's atmosphere. Be engaging and avoid anachronisms. "
                f"Do not repeat the input details verbatim; interpret them into a narrative snippet.\n"
                f"Chronicler's Entry:"
            )

            if VERBOSE_LOGGING and category not in ["birth", "death"]:  # Reduce logging for very common events
                print(f"DEBUG LLM Flair Prompt for {category}: {prompt_context[:200]}...")

            response = LLM_MODEL_GLOBAL.generate_content(prompt)

            if hasattr(response, 'text') and response.text:
                llm_text_candidate = response.text.strip().replace("*", "").split('\n')[0]  # Get first line
                if 15 < len(llm_text_candidate) < 350:  # Check for reasonable length
                    return llm_text_candidate
                elif VERBOSE_LOGGING:
                    print(
                        f"LLM flair for '{category}' was out of length bounds ({len(llm_text_candidate)} chars): '{llm_text_candidate[:100]}...'. Using fallback.")
            elif VERBOSE_LOGGING:
                # Try to get more info if prompt was blocked
                block_reason = response.prompt_feedback.block_reason if hasattr(response,
                                                                                'prompt_feedback') else "Unknown reason"
                print(f"LLM flair for '{category}' produced no text (Block reason: {block_reason}). Using fallback.")

        except Exception as e_llm_flair:
            if VERBOSE_LOGGING:
                print(
                    f"LLM Flair Generation Error for '{category}': {type(e_llm_flair).__name__} - {e_llm_flair}. Using fallback.")
    # --- End LLM Call ---

    # Fallback to generic predefined phrases if LLM fails or is not used
    age_str = f" at age {details['age']}" if details.get("age") is not None else ""
    # Use subject_traits_desc prepared earlier

    generic_phrases = {
        "birth": [
            f"In {year}, {subject_name} was born into House {details.get('surname', subject_name.split(' ')[-1] if ' ' in subject_name else subject_name)}."],
        "death": [f"{subject_traits_desc.capitalize()} {subject_name} passed from this world in {year}{age_str}."],
        "marriage": [
            f"A union between {subject_name} and {object_name} was celebrated in {year}{', potentially forging an alliance between House ' + details.get('alliance_formed', 'their houses') if details.get('alliance_formed') else ''}{', marked by customary exchanges' if details.get('economic_exchange') else ''}."],
        "succession_start": [
            f"With the passing of {subject_name} ({subject_traits_desc}), the matter of succession weighed heavily in {year}."],
        "succession_end": [f"The mantle of leadership was taken up by {subject_traits_desc}{subject_name} in {year}."],
        "title_grant": [f"{subject_name} was honored with the title of {object_name} in {year}."],
        "pruning_detail": [
            f"The records of {subject_name} ({details.get('reason', 'due to diverging lineage')}) grew sparse and eventually ceased."],
        "no_heir": [
            f"House {subject_name} faced an uncertain future in {year}, as no clear heir could be found to continue the line."],
        "event_generic": [
            f"The year {year} saw House {subject_name} contend with {details.get('event_name', 'a significant turn of events')}: \"{details.get('event_narrative', 'The outcome was duly noted.')}\""],
        "new_noble_arrival": [
            f"In {year}, the noble {subject_name} of House {details.get('surname', 'Unknown')} emerged as a figure of note in {theme_config.get('location_flavor', 'the region')}."],
        "default_event": [
            f"An event of type '{category}' concerning {subject_name} was recorded in the annals of {year}."]
    }
    selected_phrases = generic_phrases.get(category, generic_phrases["default_event"])
    chosen_phrase = random.choice(selected_phrases)

    # Basic substitution for placeholders in the fallback phrase
    final_narrative = chosen_phrase.replace("{subject_name}", str(subject_name)) \
        .replace("{object_name}", str(object_name)) \
        .replace("{year}", str(year))
    # Substitute other simple details if present in chosen_phrase's template
    if details:
        for key, value in details.items():
            if isinstance(value, (str, int, float, bool)):  # Only sub simple types
                final_narrative = final_narrative.replace(f"{{{key}}}", str(value))
    return final_narrative


def generate_story_from_chronicle(chronicle_text: str, theme_config: dict, dynasty_name: str,
                                  start_year: int, end_year: int) -> str:
    """Generates a narrative story from the simulation chronicle using an LLM."""
    if not LLM_MODEL_GLOBAL or not GOOGLE_API_KEY_GLOBAL:
        if VERBOSE_LOGGING: print("LLM not available for story generation from chronicle.")
        return "LLM Error: LLM not available for story generation."
    if not chronicle_text.strip():
        if VERBOSE_LOGGING: print("Chronicle text is empty, cannot generate story.")
        return "Error: Chronicle is empty."

    llm_persona = theme_config.get("llm_persona_prompt",
                                   "You are a master storyteller and historian, weaving epic sagas.")
    location = theme_config.get("location_flavor", "a land of legend")

    chronicle_lines = chronicle_text.splitlines()
    # Max lines for prompt - Gemini 1.5 Flash has a large context window, but very large chronicles still benefit from sampling
    # For a ~500-word story, a sample of the chronicle is usually sufficient.
    max_chronicle_lines_for_prompt = 400
    if len(chronicle_lines) > max_chronicle_lines_for_prompt:
        # Sample by taking beginning, middle, and end parts
        part_len = max_chronicle_lines_for_prompt // 3
        sample_chronicle = "\n".join(chronicle_lines[:part_len]) + \
                           f"\n\n... [CHRONICLE SECTION OMITTED FOR BREVITY ({len(chronicle_lines) - 2 * part_len} lines)] ...\n\n" + \
                           "\n".join(chronicle_lines[-part_len:])
        summary_instruction = "The following is a condensed sample from a longer chronicle."
    else:
        sample_chronicle = chronicle_text
        summary_instruction = "The following is the full chronicle provided."

    prompt = f"""
{llm_persona}
Your task is to transform the provided historical chronicle data into a short, engaging narrative saga (approximately 300-600 words).
The saga should tell the story of House {dynasty_name}, who resided in {location}, covering the period from {start_year} to {end_year}.
The theme of this saga is: "{theme_config.get('description', 'a tale of a notable family')}."

From the chronicle, identify and weave into your narrative:
- The founding of the dynasty and its initial circumstances.
- Key leaders, their notable traits (if mentioned or inferable), and their impact on the dynasty's fortunes.
- Significant events such as major alliances (marriages to other important houses), succession struggles, periods of growth or decline, conflicts, and any unique thematic events that occurred.
- The overall trajectory or arc of the dynasty: Did they rise to prominence? Did they face hardship and endure? Did they fade into obscurity?
- Conclude with a reflection on their legacy or the state of the house at the end of the chronicled period.

Maintain a consistent tone and style that reflects your persona and the described theme. Make the story immersive and compelling, not just a dry list of events. Use evocative language.

{summary_instruction}
--- CHRONICLE DATA START ---
{sample_chronicle}
--- CHRONICLE DATA END ---

Now, narrate the epic saga of House {dynasty_name}:
"""

    try:
        if VERBOSE_LOGGING: print(f"\nGenerating narrative story for House {dynasty_name} using LLM...")

        generation_config_story = genai.types.GenerationConfig(
            temperature=0.75,  # More creative
            # max_output_tokens=1024 # Ensure enough tokens for a decent story
            # top_p=0.9, top_k=40 # Example of other sampling parameters
        ) if genai else None  # Check if genai was imported

        response = LLM_MODEL_GLOBAL.generate_content(prompt, generation_config=generation_config_story)

        if hasattr(response, 'text') and response.text:
            if VERBOSE_LOGGING: print("Narrative story generated successfully by LLM.")
            return response.text.strip()
        else:
            # Log more detailed feedback if available
            feedback_reason = "Unknown reason (no text in response)"
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                feedback_reason = f"Prompt Feedback: {response.prompt_feedback}"
            elif hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0],
                                                                                     'finish_reason'):
                feedback_reason = f"Candidate Finish Reason: {response.candidates[0].finish_reason}"

            if VERBOSE_LOGGING: print(
                f"LLM generated an empty or invalid response for the story. Reason: {feedback_reason}. Full response: {response}")
            return f"LLM Error: Empty or invalid response for story ({feedback_reason})."

    except Exception as e_llm_story:
        if VERBOSE_LOGGING:
            print(f"An error occurred during LLM story generation: {type(e_llm_story).__name__} - {e_llm_story}")
            import traceback
            traceback.print_exc()  # Print full traceback for debugging
        return f"LLM Story Generation Error: {type(e_llm_story).__name__}"


print("utils.helpers defined with LLM integration placeholders now more complete.")