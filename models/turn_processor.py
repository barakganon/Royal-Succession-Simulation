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
    db, DynastyDB, PersonDB, HistoryLogEntryDB, ClaimDB
)
from models.banking_system import BankingSystem
from models.project_system import ProjectSystem
from utils.theme_manager import get_all_theme_names, get_theme
from utils.llm_prompts import build_turn_story_prompt, generate_turn_story_fallback

logger = logging.getLogger('royal_succession.turn_processor')

INTERRUPT_REASONS = [
    'monarch_death',
    'civil_war',
    'heir_majority',
    'project_complete',
    'project_stalled',
    'war_declared',
    'attack_received',
    'major_world_event',
    'story_moment',
    'quiet_period',
]

# Pretender mechanics (Story 5-3): strength a living pretender gains per year.
PRETENDER_STRENGTH_PER_YEAR = 5

# Civil war (Story 5-4): a living pretender at/above this strength triggers a
# civil-war interrupt for human players (auto-resolved inline for AI dynasties).
CIVIL_WAR_THRESHOLD = 50

# Heir-majority (Story 5-4): age at which a person first reaches majority.
HEIR_MAJORITY_AGE = 16


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

    # Heir-majority backfill (Story 5-4): anyone already at/above majority age
    # when the turn begins has, by definition, already come of age — they must
    # not trip the heir_majority interrupt. Mark them seen up front so only
    # persons who CROSS the majority boundary during this turn (children raised
    # in play) trigger the interrupt.
    start_year = dynasty.current_simulation_year
    for person in living_persons:
        if (start_year - person.birth_year) >= HEIR_MAJORITY_AGE:
            person.has_seen_majority = True

    # Process each year — interrupt-driven loop (Sprint 1)
    interrupt = None
    years_advanced = 0
    stalled_project_ids: list = []  # populated if a project stalls this turn
    ps = ProjectSystem(db.session)

    while years_advanced < years_to_advance and interrupt is None:
        current_year = start_year + years_advanced

        # --- Project tick (Sprint 2 Story 2-3) ---
        # Runs BEFORE lifecycle so that a stalled project halts the turn at
        # the year of stalling — births/deaths in the same year are deferred
        # to the next turn so the player's report has a single clear cause.
        try:
            stall_interrupts = ps.tick_projects(dynasty_id, current_year)
        except Exception as tick_exc:
            logger.error(
                f"tick_projects failed for dynasty {dynasty_id} year {current_year}: {tick_exc}",
                exc_info=True,
            )
            stall_interrupts = []
        if stall_interrupts:
            # Don't advance years_advanced/current_simulation_year on stall —
            # the stalled year wasn't actually lived through (no lifecycle ran).
            # Matches the monarch_death pattern of halting mid-year.
            stalled_project_ids = [t[2] for t in stall_interrupts]
            interrupt = ('project_stalled', current_year)
            break

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
                        break  # exit person loop; prevents double-succession if heir also in living_persons
                    continue

                # Pretender strength accumulation (Story 5-3): living pretenders
                # gain influence each simulated year they remain uncrushed.
                if getattr(person, 'is_pretender', False):
                    person.pretender_strength = (person.pretender_strength or 0) + PRETENDER_STRENGTH_PER_YEAR

                # Process marriage for unmarried nobles
                if person.is_noble and person.spouse_sim_id is None:
                    process_marriage_check(dynasty, person, current_year, theme_config)

                # Process childbirth for married women
                if person.gender == "FEMALE" and person.spouse_sim_id is not None:
                    process_childbirth_check(dynasty, person, current_year, theme_config)

            # Update living persons list (remove those who died)
            living_persons = [p for p in living_persons if p.death_year is None]

            # --- Civil war + heir-majority detection (Story 5-4) ---
            # Runs AFTER the per-person loop (monarch_death + pretender
            # accumulation). monarch_death keeps precedence: if it fired above,
            # ``interrupt`` is already set and we skip detection. Order within
            # this block is civil_war first, then heir_majority; first match
            # sets the interrupt and breaks the turn loop.
            if interrupt is None:
                # Civil war: a living pretender at/above the threshold.
                for person in living_persons:
                    if getattr(person, 'is_pretender', False) and (person.pretender_strength or 0) >= CIVIL_WAR_THRESHOLD:
                        if not dynasty.is_ai_controlled:
                            # Human: halt the turn so the player must resolve it.
                            interrupt = ('civil_war', current_year)
                            break
                        else:
                            # AI: auto-resolve inline — the rebellion is put down.
                            person.is_pretender = False
                            person.pretender_strength = 0
                            db.session.add(HistoryLogEntryDB(
                                dynasty_id=dynasty.id,
                                year=current_year,
                                event_string=f"The rebellion of {person.name} {person.surname} was put down and the claim extinguished.",
                                person1_sim_id=person.id,
                                event_type="civil_war",
                            ))
                            # continue scanning other pretenders

                # Heir majority: a living person who first reaches majority age.
                if interrupt is None:
                    for person in living_persons:
                        if (current_year - person.birth_year) >= HEIR_MAJORITY_AGE and not getattr(person, 'has_seen_majority', False):
                            person.has_seen_majority = True  # always mark, human or AI
                            if not dynasty.is_ai_controlled:
                                interrupt = ('heir_majority', current_year)
                                break
                            # AI: flag only, no interrupt; keep scanning so all
                            # newly-major persons get marked this year.
        except Exception as year_exc:
            logger.error(f"Error processing year {current_year} for dynasty {dynasty_id}: {year_exc}", exc_info=True)
            # Continue to next year rather than aborting entire turn

        # --- Project completion check (Sprint 2 Story 2-3) ---
        # Runs AFTER lifecycle so a monarch_death halts the loop first; if
        # interrupt is set, skip completion (any due projects are picked up
        # on the next turn).
        if interrupt is None:
            try:
                due = [
                    p for p in ps.get_active_projects(dynasty_id)
                    if p.completion_year <= current_year
                ]
                for project in due:
                    ps.complete_project(project.id)
            except Exception as complete_exc:
                logger.error(
                    f"complete_project failed for dynasty {dynasty_id} year {current_year}: {complete_exc}",
                    exc_info=True,
                )

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
                        years_advanced=years_advanced,
                        interrupt_reason=interrupt[0],
                        monarch_traits=monarch_obj.get_traits() if monarch_obj else [],
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
                dynasty.name, start_year, dynasty.current_simulation_year - 1, event_texts, monarch_display,
                years_advanced=years_advanced,
                interrupt_reason=interrupt[0],
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
        'stalled_project_ids': stalled_project_ids,
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

    # Sickly trait halves expected lifespan and doubles mortality
    if "Sickly" in person.get_traits():
        max_age *= 0.5
        base_mortality *= 2

    if age > max_age:
        base_mortality = 1.0  # Guaranteed death if past max age

    # Roll for death
    if random.random() < base_mortality:
        person.death_year = current_year

        from utils.llm_narration import narrate_event
        from utils.llm_prompts import build_death_flavor_prompt, generate_death_flavor_fallback

        death_dynasty = DynastyDB.query.get(person.dynasty_id)
        death_house = death_dynasty.name if death_dynasty else "their house"
        person_full_name = f"{person.name} {person.surname}"

        # Log death
        death_log = HistoryLogEntryDB(
            dynasty_id=person.dynasty_id,
            year=current_year,
            event_string=narrate_event(
                build_death_flavor_prompt(
                    person_full_name, person.get_traits(), death_house, age, current_year, person.is_monarch
                ),
                generate_death_flavor_fallback(
                    person_full_name, death_house, age, current_year, person.is_monarch
                ),
                max_tokens=90,
            ),
            person1_sim_id=person.id,
            event_type="death"
        )
        db.session.add(death_log)
        return True

    return False


def _find_cross_dynasty_spouse(session, person: PersonDB, current_year: int, min_age: int, max_age: int):
    """Find an eligible noble from a different dynasty to marry ``person``.

    Searches for an unmarried, living noble of the opposite gender belonging to a
    different dynasty, whose age falls within [min_age, max_age]. Returns the first
    such candidate ordered by id, or None if no candidate exists (Story 7-1).
    """
    spouse_gender = "FEMALE" if person.gender == "MALE" else "MALE"

    candidate = (
        session.query(PersonDB)
        .filter(
            PersonDB.gender == spouse_gender,
            PersonDB.death_year.is_(None),
            PersonDB.is_noble.is_(True),
            PersonDB.spouse_sim_id.is_(None),
            PersonDB.dynasty_id != person.dynasty_id,
            (current_year - PersonDB.birth_year) >= min_age,
            (current_year - PersonDB.birth_year) <= max_age,
        )
        .order_by(PersonDB.id)
        .first()
    )
    return candidate


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
        # Story 7-1: prefer a cross-dynasty union before generating a stranger.
        partner = _find_cross_dynasty_spouse(
            db.session, person, current_year, min_marriage_age, max_marriage_age
        )
        if partner is not None:
            # Story 7-2: lazy imports keep this module importable even when Agent A's
            # new symbols are absent in this worktree.
            from models.ai_controller import AIController
            from models.diplomacy_system import DiplomacySystem
            from models.free_action_system import _llm_available
            from utils.llm_prompts import (
                build_wedding_chronicle_prompt,
                generate_wedding_fallback,
            )

            partner_dynasty = DynastyDB.query.get(partner.dynasty_id)
            person_house = dynasty.name
            partner_house = partner_dynasty.name if partner_dynasty else partner.surname

            # Story 7-2: if the partner's dynasty is AI-controlled, it must accept
            # the union before the link is forged. A rejection falls through to the
            # stranger-generation fallback below.
            accepted = True
            if partner_dynasty is not None and getattr(partner_dynasty, "is_ai_controlled", False):
                try:
                    relation_score = 0
                    relation = DiplomacySystem(db.session).get_diplomatic_relation(
                        person.dynasty_id, partner.dynasty_id
                    )
                    if relation is not None:
                        relation_score = relation.relation_score
                    ai = AIController(
                        db.session,
                        partner.dynasty_id,
                        partner_dynasty.ai_personality or "",
                    )
                    accepted = bool(ai.decide_marriage_response({
                        "proposer_dynasty_id": person.dynasty_id,
                        "relation_score": relation_score,
                        "proposer_prestige": (dynasty.prestige or 0),
                        "own_prestige": (partner_dynasty.prestige or 0),
                    }))
                except Exception as decide_exc:
                    logger.warning(
                        "Marriage acceptance check failed (proposer %s -> partner dynasty %s): %s",
                        person.dynasty_id, partner.dynasty_id, decide_exc,
                    )
                    accepted = False

            if accepted:
                # Link both ways; both spouses keep their own dynasty_id (no change in 7-1).
                person.spouse_sim_id = partner.id
                partner.spouse_sim_id = person.id

                # Story 7-2: a marriage alliance warms relations between the two houses.
                try:
                    alliance_relation = DiplomacySystem(db.session).get_diplomatic_relation(
                        person.dynasty_id, partner.dynasty_id
                    )
                    if alliance_relation is not None:
                        alliance_relation.update_relation("marriage_alliance", 30)
                except Exception as relation_exc:
                    logger.warning(
                        "Marriage alliance relation bump failed (%s <-> %s): %s",
                        person.dynasty_id, partner.dynasty_id, relation_exc,
                    )

                # Story 7-2: wedding chronicle line — LLM when available, else fallback.
                person_house_name = person.surname or person_house
                partner_house_name = partner.surname or partner_house
                wedding_text = None
                if _llm_available():
                    try:
                        import google.generativeai as genai
                        from flask import current_app
                        api_key = (
                            current_app.config.get("FLASK_APP_GOOGLE_API_KEY")
                            or os.environ.get("GOOGLE_API_KEY")
                        )
                        if api_key:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel("gemini-1.5-flash")
                            prompt = build_wedding_chronicle_prompt(
                                person.name,
                                person.get_traits(),
                                partner.name,
                                partner.get_traits(),
                                person_house_name,
                                partner_house_name,
                                current_year,
                            )
                            response = model.generate_content(
                                prompt,
                                generation_config={
                                    "max_output_tokens": 150,
                                    "temperature": 0.8,
                                },
                            )
                            text = response.text.strip() if response.text else ""
                            if text:
                                wedding_text = text
                    except Exception as llm_exc:
                        logger.warning(
                            "Wedding chronicle LLM failed (%s & %s): %s",
                            person.name, partner.name, llm_exc,
                        )
                if not wedding_text:
                    wedding_text = generate_wedding_fallback(
                        person.name,
                        partner.name,
                        person_house_name,
                        partner_house_name,
                        current_year,
                    )

                marriage_log = HistoryLogEntryDB(
                    dynasty_id=dynasty.id,
                    year=current_year,
                    event_string=wedding_text,
                    person1_sim_id=person.id,
                    person2_sim_id=partner.id,
                    event_type="marriage"
                )
                db.session.add(marriage_log)
                return True
            # Rejected by AI partner — fall through to stranger-generation fallback.

        # No cross-dynasty candidate found — fall back to generating a stranger spouse.
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

        # Set child traits: inherit from parents, then add one common trait.
        # Each parent trait is inherited with probability 0.30, deduplicated,
        # capped at 3 inherited traits total.
        parent_traits = list(woman.get_traits())
        father = PersonDB.query.get(woman.spouse_sim_id) if woman.spouse_sim_id else None
        if father:
            parent_traits.extend(father.get_traits())

        child_traits = []
        for trait in parent_traits:
            if len(child_traits) >= 3:
                break
            if trait in child_traits:
                continue
            if random.random() < 0.30:
                child_traits.append(trait)

        # Add one random common trait if available and not already present
        available_traits = theme_config.get("common_traits", [])
        if available_traits:
            new_trait = random.choice(available_traits)
            if new_trait not in child_traits:
                child_traits.append(new_trait)

        child.set_traits(child_traits)

        db.session.add(child)
        db.session.flush()  # Ensure child.id is assigned before portrait generation
        child.generate_portrait()

        # Log birth
        from utils.llm_narration import narrate_event
        from utils.llm_prompts import build_birth_flavor_prompt, generate_birth_flavor_fallback

        birth_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=narrate_event(
                build_birth_flavor_prompt(
                    child_name, child.get_traits(), woman.name, spouse.name, dynasty.name, current_year
                ),
                generate_birth_flavor_fallback(
                    child_name, woman.name, spouse.name, dynasty.name, current_year
                ),
                max_tokens=80,
            ),
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

        # Story 7-3: a child born to parents of two different dynasties takes the
        # mother's dynasty but gains a claim on the father's dynasty. Register it
        # only for surviving children. A claim failure must NEVER abort the birth.
        if child.death_year is None and spouse.dynasty_id != woman.dynasty_id:
            try:
                claim = ClaimDB(
                    claimant_sim_id=child.id,
                    target_dynasty_id=spouse.dynasty_id,
                    source_dynasty_id=woman.dynasty_id,
                    claim_type='cross_dynasty_birth',
                    created_year=current_year,
                )
                db.session.add(claim)
            except Exception as claim_exc:
                logger.warning(
                    "Cross-dynasty birth claim registration failed (child %s, "
                    "target dynasty %s): %s",
                    child.id, spouse.dynasty_id, claim_exc,
                )

        return True

    return False


def _sort_by_rule(people: list, succession_rule: str) -> None:
    """Sort a list of candidate PersonDB rows in place per the succession rule."""
    if succession_rule == "PRIMOGENITURE_MALE_PREFERENCE":
        # Sort by gender (males first) then by birth year (oldest first)
        people.sort(key=lambda p: (p.gender != "MALE", p.birth_year))
    elif succession_rule == "PRIMOGENITURE_ABSOLUTE":
        # Sort by birth year only (oldest first)
        people.sort(key=lambda p: p.birth_year)
    elif succession_rule == "ELECTIVE_NOBLE_COUNCIL":
        # For simplicity, just sort by traits count (desc) and age (oldest first)
        people.sort(key=lambda p: (-len(p.get_traits()), p.birth_year))


def get_succession_candidates(dynasty: DynastyDB, deceased_monarch: PersonDB, theme_config: dict) -> list:
    """Return the ordered list of eligible heirs for a deceased monarch.

    Pure helper: performs the children -> siblings -> any-noble selection and the
    per-rule sort. Does NOT crown anyone and never mutates the DB. May be empty.
    """
    succession_rule = theme_config.get("succession_rule_default", "PRIMOGENITURE_MALE_PREFERENCE")

    eligible_heirs: list = []

    # First, check for children of the deceased
    children = PersonDB.query.filter(
        (PersonDB.father_sim_id == deceased_monarch.id) |
        (PersonDB.mother_sim_id == deceased_monarch.id),
        PersonDB.death_year.is_(None),
        PersonDB.is_noble == True
    ).all()

    if children:
        _sort_by_rule(children, succession_rule)
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
            _sort_by_rule(siblings, succession_rule)
            eligible_heirs = siblings

    # If still no heirs, look for any living noble in the dynasty
    if not eligible_heirs:
        nobles = PersonDB.query.filter_by(
            dynasty_id=dynasty.id,
            death_year=None,
            is_noble=True
        ).all()

        if nobles:
            _sort_by_rule(nobles, succession_rule)
            eligible_heirs = nobles

    return eligible_heirs


def crown_heir(dynasty: DynastyDB, heir: PersonDB, current_year: int, theme_config: dict) -> None:
    """Crown ``heir`` as the new monarch of ``dynasty``.

    Clears the monarch flag from every currently-monarch person of the dynasty
    (including the deceased pending marker), sets the heir as monarch, records the
    reign start, grants the monarch title and appends a ``succession_end`` history
    log. Does NOT commit.
    """
    # Vacate the throne: clear is_monarch from every current monarch of the
    # dynasty — this includes the deceased monarch acting as the pending marker.
    current_monarchs = PersonDB.query.filter_by(
        dynasty_id=dynasty.id,
        is_monarch=True
    ).all()
    for m in current_monarchs:
        m.is_monarch = False

    heir.is_monarch = True
    heir.reign_start_year = current_year

    # Set monarch title
    title_key = "titles_male" if heir.gender == "MALE" else "titles_female"
    titles = theme_config.get(title_key, ["Leader"])
    monarch_title = titles[0] if titles else "Leader"
    current_titles = heir.get_titles()
    if monarch_title not in current_titles:
        current_titles.insert(0, monarch_title)
        heir.set_titles(current_titles)

    # Log succession
    succession_end_log = HistoryLogEntryDB(
        dynasty_id=dynasty.id,
        year=current_year,
        event_string=f"{heir.name} {heir.surname} has become the new {monarch_title} of House {dynasty.name}.",
        person1_sim_id=heir.id,
        event_type="succession_end"
    )
    db.session.add(succession_end_log)


def process_succession(dynasty: DynastyDB, deceased_monarch: PersonDB, current_year: int, theme_config: dict):
    """Process succession after a monarch's death.

    Always logs the ``succession_start`` crisis. For an AI-controlled dynasty (or
    when there is no candidate) this preserves the legacy auto-crown behaviour and
    returns a falsy value. For a human-controlled dynasty with at least one
    candidate it leaves the throne pending — the deceased monarch keeps
    ``is_monarch=True`` as the pending-succession marker so the player can choose
    an heir — and returns True.
    """
    # Log the succession crisis
    succession_log = HistoryLogEntryDB(
        dynasty_id=dynasty.id,
        year=current_year,
        event_string=f"With the death of {deceased_monarch.name} {deceased_monarch.surname}, the matter of succession weighs heavily on House {dynasty.name}.",
        person1_sim_id=deceased_monarch.id,
        event_type="succession_start"
    )
    db.session.add(succession_log)

    candidates = get_succession_candidates(dynasty, deceased_monarch, theme_config)

    # Human-controlled dynasty with a real choice: halt and let the player pick.
    # Leave the deceased monarch as the pending marker (still is_monarch=True with
    # a death_year set). Net: no living is_monarch, one dead is_monarch.
    if not dynasty.is_ai_controlled and candidates:
        return True

    # AI-controlled, or no candidate at all: preserve legacy behaviour.
    if candidates:
        crown_heir(dynasty, candidates[0], current_year, theme_config)
    else:
        # No heir found - dynasty in crisis
        crisis_log = HistoryLogEntryDB(
            dynasty_id=dynasty.id,
            year=current_year,
            event_string=f"House {dynasty.name} faces a succession crisis as no clear heir can be found.",
            event_type="succession_crisis"
        )
        db.session.add(crisis_log)

    return False


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
    """Generate the family tree visualization for the dynasty.

    Story 8-3: the legacy matplotlib PNG renderer has been retired.  This now
    populates DynastyDB.family_tree_svg via the Story 8-1/8-2 SVG renderer.
    A render failure must never abort the turn — it is logged and swallowed.
    """
    try:
        from visualization.family_tree_svg import generate_family_tree_svg
        from models.db_models import db
        dynasty.family_tree_svg = generate_family_tree_svg(dynasty.id, db.session)
        db.session.add(dynasty)
        return True
    except Exception as e:
        logger.error(f"Error generating family tree visualization: {str(e)}", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        return False
