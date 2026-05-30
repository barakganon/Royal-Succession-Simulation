"""Unit tests for the Story 9-1 event-flavor prompt builders and fallbacks.

Pure unit tests — no Flask app context, no network, no genai. They exercise the
five new prompt builders and their five deterministic fallbacks added to
``utils.llm_prompts`` per the Story 9-1 frozen contract.

Contract signatures (verbatim):
    build_birth_flavor_prompt(child_name, child_traits, mother_name, father_name, house, year) -> str
    generate_birth_flavor_fallback(child_name, mother_name, father_name, house, year) -> str
    build_death_flavor_prompt(person_name, person_traits, house, age, year, was_monarch=False) -> str
    generate_death_flavor_fallback(person_name, house, age, year, was_monarch=False) -> str
    build_battle_flavor_prompt(attacker_name, defender_name, location, victor_name, casualties, year) -> str
    generate_battle_flavor_fallback(attacker_name, defender_name, victor_name, year) -> str
    build_world_news_prompt(actor_dynasty, action_desc, player_dynasty, year) -> str
    generate_world_news_fallback(actor_dynasty, action_desc, year) -> str
    build_construction_complete_prompt(building_name, territory_name, house, year) -> str
    generate_construction_complete_fallback(building_name, territory_name, house, year) -> str
"""

from utils.llm_prompts import (
    build_birth_flavor_prompt,
    generate_birth_flavor_fallback,
    build_death_flavor_prompt,
    generate_death_flavor_fallback,
    build_battle_flavor_prompt,
    generate_battle_flavor_fallback,
    build_world_news_prompt,
    generate_world_news_fallback,
    build_construction_complete_prompt,
    generate_construction_complete_fallback,
)


# --------------------------------------------------------------------------- #
# Birth flavor
# --------------------------------------------------------------------------- #
def test_build_birth_flavor_prompt_contains_child_name():
    prompt = build_birth_flavor_prompt(
        child_name="Aldric",
        child_traits=["brave", "ambitious"],
        mother_name="Elswyth",
        father_name="Roderic",
        house="Ravensworth",
        year=1247,
    )
    assert isinstance(prompt, str)
    assert prompt
    assert "Aldric" in prompt


def test_build_birth_flavor_prompt_handles_none_traits():
    # child_traits=None must not raise and must still name the child.
    prompt = build_birth_flavor_prompt(
        child_name="Aldric",
        child_traits=None,
        mother_name="Elswyth",
        father_name="Roderic",
        house="Ravensworth",
        year=1247,
    )
    assert isinstance(prompt, str)
    assert prompt
    assert "Aldric" in prompt


def test_generate_birth_flavor_fallback_deterministic_and_named():
    args = ("Aldric", "Elswyth", "Roderic", "Ravensworth", 1247)
    first = generate_birth_flavor_fallback(*args)
    second = generate_birth_flavor_fallback(*args)
    assert isinstance(first, str)
    assert first
    assert first == second  # deterministic
    assert "Aldric" in first
    assert str(1247) in first


# --------------------------------------------------------------------------- #
# Death flavor
# --------------------------------------------------------------------------- #
def test_build_death_flavor_prompt_contains_person_name():
    prompt = build_death_flavor_prompt(
        person_name="Roderic",
        person_traits=["just", "weary"],
        house="Ravensworth",
        age=63,
        year=1290,
    )
    assert isinstance(prompt, str)
    assert prompt
    assert "Roderic" in prompt


def test_build_death_flavor_prompt_handles_empty_traits():
    # person_traits=[] must not raise.
    prompt = build_death_flavor_prompt(
        person_name="Roderic",
        person_traits=[],
        house="Ravensworth",
        age=63,
        year=1290,
    )
    assert isinstance(prompt, str)
    assert prompt
    assert "Roderic" in prompt


def test_build_death_flavor_prompt_monarch_differs_from_commoner():
    common_args = dict(
        person_name="Roderic",
        person_traits=["just"],
        house="Ravensworth",
        age=63,
        year=1290,
    )
    as_monarch = build_death_flavor_prompt(was_monarch=True, **common_args)
    as_commoner = build_death_flavor_prompt(was_monarch=False, **common_args)
    assert as_monarch != as_commoner


def test_generate_death_flavor_fallback_deterministic_and_named():
    args = ("Roderic", "Ravensworth", 63, 1290)
    first = generate_death_flavor_fallback(*args)
    second = generate_death_flavor_fallback(*args)
    assert isinstance(first, str)
    assert first
    assert first == second
    assert "Roderic" in first
    assert str(1290) in first


# --------------------------------------------------------------------------- #
# Battle flavor
# --------------------------------------------------------------------------- #
def test_build_battle_flavor_prompt_contains_combatants():
    prompt = build_battle_flavor_prompt(
        attacker_name="House Ravensworth",
        defender_name="House Caldemar",
        location="the Ford of Greywater",
        victor_name="House Ravensworth",
        casualties=1200,
        year=1305,
    )
    assert isinstance(prompt, str)
    assert prompt
    # Must contain attacker + defender (or victor); assert both combatants here.
    assert "House Ravensworth" in prompt
    assert "House Caldemar" in prompt


def test_generate_battle_flavor_fallback_deterministic_and_named():
    args = ("House Ravensworth", "House Caldemar", "House Ravensworth", 1305)
    first = generate_battle_flavor_fallback(*args)
    second = generate_battle_flavor_fallback(*args)
    assert isinstance(first, str)
    assert first
    assert first == second
    assert "House Ravensworth" in first
    assert str(1305) in first


# --------------------------------------------------------------------------- #
# World news
# --------------------------------------------------------------------------- #
def test_build_world_news_prompt_contains_actor_dynasty():
    prompt = build_world_news_prompt(
        actor_dynasty="House Volkov",
        action_desc="conquered the free city of Thornhold",
        player_dynasty="House Ravensworth",
        year=1312,
    )
    assert isinstance(prompt, str)
    assert prompt
    assert "House Volkov" in prompt


def test_generate_world_news_fallback_deterministic_and_named():
    args = ("House Volkov", "conquered the free city of Thornhold", 1312)
    first = generate_world_news_fallback(*args)
    second = generate_world_news_fallback(*args)
    assert isinstance(first, str)
    assert first
    assert first == second
    assert "House Volkov" in first
    assert str(1312) in first


# --------------------------------------------------------------------------- #
# Construction complete
# --------------------------------------------------------------------------- #
def test_build_construction_complete_prompt_contains_building_name():
    prompt = build_construction_complete_prompt(
        building_name="Stone Keep",
        territory_name="Ravenshollow",
        house="Ravensworth",
        year=1320,
    )
    assert isinstance(prompt, str)
    assert prompt
    assert "Stone Keep" in prompt


def test_generate_construction_complete_fallback_deterministic_and_named():
    args = ("Stone Keep", "Ravenshollow", "Ravensworth", 1320)
    first = generate_construction_complete_fallback(*args)
    second = generate_construction_complete_fallback(*args)
    assert isinstance(first, str)
    assert first
    assert first == second
    assert "Stone Keep" in first
    assert str(1320) in first
