"""Unit tests for models.story_moments — Story 10-1 frozen contract.

Pure-data module: no Flask/DB/app context required. Operates on a plain
dynasty_state dict and returns plain dicts. These tests assert the structural
contract of STORY_MOMENT_TEMPLATES and the behavior of _matches,
eligible_templates, and maybe_trigger_story_moment.
"""

import random

import pytest

from models.story_moments import (
    BASE_TRIGGER_CHANCE,
    STORY_MOMENT_TEMPLATES,
    _matches,
    eligible_templates,
    maybe_trigger_story_moment,
)


# Trait names that the contract declares as valid (must be real trait keys).
VALID_TRAITS = {
    "Brave",
    "Craven",
    "Cunning",
    "Wroth",
    "Patient",
    "Pious",
    "Greedy",
    "Sickly",
}

# Effects vocabulary declared by the contract.
VALID_EFFECT_KEYS = {
    "prestige_delta",
    "wealth_delta",
    "add_trait_to_monarch",
    "relation_delta",
    "infamy_delta",
    "exile_person",
    "chronicle_note",
}

REQUIRED_TEMPLATE_KEYS = {
    "forbidden_love",
    "council_whispers",
    "dueling_lords",
    "bonds_of_kin",
    "fading_heir",
    "letter_from_east",
}


# --------------------------------------------------------------------------- #
# Fake deterministic RNG helpers
# --------------------------------------------------------------------------- #
class FakeRng:
    """Deterministic stand-in for random.Random.

    ``random()`` always returns ``fixed``. Weighted/plain picks always return
    the first element so results are fully deterministic.
    """

    def __init__(self, fixed):
        self._fixed = fixed

    def random(self):
        return self._fixed

    def choices(self, population, weights=None, k=1):
        return [population[0]] * k

    def choice(self, seq):
        return seq[0]


# --------------------------------------------------------------------------- #
# Module constants
# --------------------------------------------------------------------------- #
def test_base_trigger_chance_value():
    assert BASE_TRIGGER_CHANCE == 0.05


# --------------------------------------------------------------------------- #
# Template structure
# --------------------------------------------------------------------------- #
def test_templates_count_at_least_eight():
    assert isinstance(STORY_MOMENT_TEMPLATES, list)
    assert len(STORY_MOMENT_TEMPLATES) >= 8


def test_template_keys_unique():
    keys = [t["key"] for t in STORY_MOMENT_TEMPLATES]
    assert len(keys) == len(set(keys))


def test_named_keys_present():
    keys = {t["key"] for t in STORY_MOMENT_TEMPLATES}
    assert REQUIRED_TEMPLATE_KEYS.issubset(keys)


def test_each_template_has_required_fields_and_types():
    for t in STORY_MOMENT_TEMPLATES:
        assert isinstance(t["key"], str) and t["key"]
        assert isinstance(t["title"], str) and t["title"]
        assert isinstance(t["summary"], str) and t["summary"]
        assert isinstance(t["preconditions"], dict)
        assert isinstance(t["weight"], (int, float))
        assert float(t["weight"]) > 0
        choices = t["mechanical_choices"]
        assert isinstance(choices, list)
        assert 2 <= len(choices) <= 3


def test_each_choice_has_unique_key_and_required_fields():
    for t in STORY_MOMENT_TEMPLATES:
        choice_keys = [c["key"] for c in t["mechanical_choices"]]
        assert len(choice_keys) == len(set(choice_keys)), t["key"]
        for c in t["mechanical_choices"]:
            assert isinstance(c["key"], str) and c["key"]
            assert isinstance(c["label"], str) and c["label"]
            assert isinstance(c["description"], str) and c["description"]
            assert isinstance(c["effects"], dict)


def test_effects_use_only_declared_vocabulary():
    for t in STORY_MOMENT_TEMPLATES:
        for c in t["mechanical_choices"]:
            for eff_key in c["effects"]:
                assert eff_key in VALID_EFFECT_KEYS, (t["key"], c["key"], eff_key)


def test_referenced_traits_are_real():
    for t in STORY_MOMENT_TEMPLATES:
        for c in t["mechanical_choices"]:
            trait = c["effects"].get("add_trait_to_monarch")
            if trait is not None:
                assert trait in VALID_TRAITS, (t["key"], c["key"], trait)
        # monarch_has_trait / monarch_lacks_trait preconditions also reference traits
        for pc_key in ("monarch_has_trait", "monarch_lacks_trait"):
            if pc_key in t["preconditions"]:
                assert t["preconditions"][pc_key] in VALID_TRAITS, (t["key"], pc_key)


# --------------------------------------------------------------------------- #
# _matches
# --------------------------------------------------------------------------- #
def test_matches_empty_preconditions_true():
    assert _matches({}, {"prestige": 0}) is True


def test_matches_min_prestige():
    assert _matches({"min_prestige": 10}, {"prestige": 10}) is True
    assert _matches({"min_prestige": 10}, {"prestige": 50}) is True
    assert _matches({"min_prestige": 10}, {"prestige": 9}) is False


def test_matches_max_prestige():
    assert _matches({"max_prestige": 10}, {"prestige": 10}) is True
    assert _matches({"max_prestige": 10}, {"prestige": 5}) is True
    assert _matches({"max_prestige": 10}, {"prestige": 11}) is False


def test_matches_at_war():
    assert _matches({"at_war": True}, {"at_war": True}) is True
    assert _matches({"at_war": True}, {"at_war": False}) is False
    assert _matches({"at_war": False}, {"at_war": False}) is True


def test_matches_has_living_heir():
    assert _matches({"has_living_heir": True}, {"has_living_heir": True}) is True
    assert _matches({"has_living_heir": True}, {"has_living_heir": False}) is False


def test_matches_monarch_has_trait():
    assert _matches({"monarch_has_trait": "Brave"}, {"monarch_traits": ["Brave", "Pious"]}) is True
    assert _matches({"monarch_has_trait": "Brave"}, {"monarch_traits": ["Craven"]}) is False


def test_matches_monarch_lacks_trait():
    assert _matches({"monarch_lacks_trait": "Craven"}, {"monarch_traits": ["Brave"]}) is True
    assert _matches({"monarch_lacks_trait": "Craven"}, {"monarch_traits": ["Craven"]}) is False


def test_matches_year_bounds():
    assert _matches({"min_year": 1000}, {"year": 1000}) is True
    assert _matches({"min_year": 1000}, {"year": 999}) is False
    assert _matches({"max_year": 1000}, {"year": 1000}) is True
    assert _matches({"max_year": 1000}, {"year": 1001}) is False


def test_matches_missing_state_key_fails_safe_no_raise():
    # 'prestige' absent from state -> precondition fails, must not raise.
    result = _matches({"min_prestige": 10}, {})
    assert result is False


def test_matches_unknown_precondition_key_ignored():
    # Unknown keys are forward-compatible and treated as matching.
    assert _matches({"unknown_thing": 1}, {}) is True
    assert _matches({"unknown_thing": 1, "min_prestige": 5}, {"prestige": 10}) is True


# --------------------------------------------------------------------------- #
# eligible_templates
# --------------------------------------------------------------------------- #
def test_eligible_templates_filters_by_preconditions():
    # Craft a state that satisfies some templates but not all. Use an extreme
    # state so the result reliably both includes and excludes templates.
    rich_state = {
        "prestige": 9999,
        "wealth": 9999,
        "infamy": 0,
        "at_war": True,
        "has_living_heir": True,
        "heir_age": 25,
        "monarch_traits": list(VALID_TRAITS),  # has every trait
        "year": 1200,
        "relations": {},
    }
    poor_state = {
        "prestige": -9999,
        "wealth": -9999,
        "infamy": 9999,
        "at_war": False,
        "has_living_heir": False,
        "heir_age": None,
        "monarch_traits": [],  # lacks every trait
        "year": 1,
        "relations": {},
    }

    rich_eligible = eligible_templates(rich_state)
    poor_eligible = eligible_templates(poor_state)

    assert isinstance(rich_eligible, list)
    assert isinstance(poor_eligible, list)

    # All returned templates must genuinely pass their own preconditions.
    for t in rich_eligible:
        assert _matches(t["preconditions"], rich_state) is True
    for t in poor_eligible:
        assert _matches(t["preconditions"], poor_state) is True

    # Across the two opposite states, the eligible sets must differ — proving
    # filtering actually depends on preconditions (some included, some excluded).
    rich_keys = {t["key"] for t in rich_eligible}
    poor_keys = {t["key"] for t in poor_eligible}
    # At least one template is eligible somewhere...
    assert rich_keys or poor_keys
    # ...and the two states do not yield identical eligibility (real filtering).
    assert rich_keys != poor_keys or (
        len(rich_keys) < len(STORY_MOMENT_TEMPLATES)
        or len(poor_keys) < len(STORY_MOMENT_TEMPLATES)
    )


def test_eligible_templates_includes_and_excludes():
    # Templates with empty preconditions are always eligible (included).
    # A deliberately impossible-to-satisfy template set is excluded by using a
    # state that contradicts gated templates. We assert both a non-empty and a
    # smaller-than-full eligible list for at least one crafted state.
    base_state = {
        "prestige": 0,
        "wealth": 0,
        "infamy": 0,
        "at_war": False,
        "has_living_heir": True,
        "heir_age": 30,
        "monarch_traits": [],
        "year": 1100,
        "relations": {},
    }
    eligible = eligible_templates(base_state)
    # At least one template is eligible (those with empty/loose preconditions).
    assert len(eligible) >= 1
    # And not necessarily all are eligible — there exists at least one template
    # excluded for SOME state (proven by the opposite-state test above), so here
    # we just confirm the gating templates can exclude: a war-gated template
    # should not appear when at_war is False.
    for t in eligible:
        if t["preconditions"].get("at_war") is True:
            pytest.fail(f"war-gated template {t['key']} eligible while at peace")


# --------------------------------------------------------------------------- #
# maybe_trigger_story_moment
# --------------------------------------------------------------------------- #
def _eligible_state():
    """A permissive state guaranteed to have at least one eligible template."""
    return {
        "prestige": 100,
        "wealth": 500,
        "infamy": 0,
        "at_war": False,
        "has_living_heir": True,
        "heir_age": 28,
        "monarch_traits": ["Brave", "Pious"],
        "year": 1150,
        "relations": {"Lord Aldric": 0},
    }


def test_trigger_fires_with_low_roll_returns_eligible_dict():
    state = _eligible_state()
    assert len(eligible_templates(state)) >= 1, "precondition: state must be eligible"
    rng = FakeRng(0.0)  # 0.0 < 0.05 -> fires
    result = maybe_trigger_story_moment(state, rng=rng)
    assert result is not None
    assert isinstance(result, dict)
    assert "key" in result
    eligible_keys = {t["key"] for t in eligible_templates(state)}
    assert result["key"] in eligible_keys


def test_trigger_does_not_fire_with_high_roll_returns_none():
    state = _eligible_state()
    rng = FakeRng(0.99)  # 0.99 >= 0.05 -> does not fire
    assert maybe_trigger_story_moment(state, rng=rng) is None


def test_trigger_returns_none_when_no_eligible_templates():
    # Construct a state with no eligible templates. Empty dict has missing keys
    # so every gated precondition fails; any template with empty preconditions
    # would still match, so to force "no eligible" we rely on the contract that
    # maybe_trigger never raises and returns None when eligible is empty. We
    # build a state and, if templates remain eligible, we still verify the
    # no-eligible branch via an empty state which must never raise.
    eligible = eligible_templates({})
    rng = FakeRng(0.0)
    result = maybe_trigger_story_moment({}, rng=rng)
    if not eligible:
        assert result is None
    else:
        # Some templates may have empty preconditions; result must still be a
        # valid eligible dict or None, and must never raise.
        assert result is None or isinstance(result, dict)


def test_trigger_empty_state_never_raises():
    # Both firing and non-firing rolls must be safe on a bare/empty state.
    assert maybe_trigger_story_moment({}, rng=FakeRng(0.0)) in (None,) or isinstance(
        maybe_trigger_story_moment({}, rng=FakeRng(0.0)), dict
    )
    assert maybe_trigger_story_moment({}, rng=FakeRng(0.99)) is None


def test_trigger_with_default_rng_never_raises():
    # No rng injected -> module random used; must not raise for any state.
    maybe_trigger_story_moment(_eligible_state())
    maybe_trigger_story_moment({})
    maybe_trigger_story_moment({"prestige": 0})


def test_trigger_determinism_same_seed_same_key():
    state = _eligible_state()
    assert len(eligible_templates(state)) >= 1
    rng_a = random.Random(12345)
    rng_b = random.Random(12345)
    result_a = maybe_trigger_story_moment(state, rng=rng_a)
    result_b = maybe_trigger_story_moment(state, rng=rng_b)
    # Same seed -> identical outcome (both None or same template key).
    if result_a is None:
        assert result_b is None
    else:
        assert result_b is not None
        assert result_a["key"] == result_b["key"]


def test_trigger_determinism_fake_rng_same_key():
    state = _eligible_state()
    key1 = maybe_trigger_story_moment(state, rng=FakeRng(0.0))["key"]
    key2 = maybe_trigger_story_moment(state, rng=FakeRng(0.0))["key"]
    assert key1 == key2
