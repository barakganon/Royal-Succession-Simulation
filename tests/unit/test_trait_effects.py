# tests/unit/test_trait_effects.py
# Story 6-1 (Trait effects on Combat / Tax / Diplomacy) — CONTRACT-FIRST unit
# tests written by Agent C in an isolated worktree.
#
# These tests pin the PURE-LOGIC contract for models/trait_effects.py:
#
#   combat_modifier(traits)    -> float   (multiplicative; identity 1.0)
#   tax_modifier(traits)       -> float   (multiplicative; identity 1.0)
#   diplomacy_modifier(traits) -> int     (additive;       identity 0)
#
# Contract:
#   - None / empty list -> combat 1.0, tax 1.0, diplomacy 0.
#   - Unknown traits are ignored (no effect).
#   - Per-trait deltas (additive on top of the identity baseline):
#       Brave    : combat +0.15
#       Craven   : combat -0.15
#       Wroth    : combat +0.10 , diplomacy -10
#       Patient  : combat +0.05 , diplomacy +10
#       Cunning  : diplomacy +15
#       Pious    : diplomacy +10
#       Greedy   : tax +0.20    , diplomacy -5
#       Sickly   : combat -0.05
#   - Multiple traits stack additively against the baseline:
#       combat_modifier  = 1.0 + sum(combat deltas)
#       tax_modifier     = 1.0 + sum(tax deltas)
#       diplomacy_mod    = 0   + sum(diplomacy deltas)
#
# These tests WILL FAIL in this isolated worktree because models/trait_effects.py
# does not yet exist (the other agents build it). That is EXPECTED and correct
# for a contract-first suite — do NOT weaken, stub, or skip them.

import pytest

# Tolerance for float comparisons (deltas are exact tenths/hundredths).
EPS = 1e-9


def _funcs():
    """Import the (contract) pure-logic functions at call time.

    Imported inside each test rather than at module scope so the file always
    COLLECTS cleanly; a missing models/trait_effects.py then surfaces as a hard
    (expected) ImportError when the test RUNS — not as a collection error.
    """
    from models.trait_effects import (
        combat_modifier,
        tax_modifier,
        diplomacy_modifier,
    )
    return combat_modifier, tax_modifier, diplomacy_modifier


@pytest.mark.unit
class TestTraitEffectsIdentity:
    """Empty / None inputs collapse to the multiplicative/additive identity."""

    def test_empty_list_is_identity(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        assert combat_modifier([]) == pytest.approx(1.0, abs=EPS)
        assert tax_modifier([]) == pytest.approx(1.0, abs=EPS)
        assert diplomacy_modifier([]) == 0

    def test_none_is_identity(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        assert combat_modifier(None) == pytest.approx(1.0, abs=EPS)
        assert tax_modifier(None) == pytest.approx(1.0, abs=EPS)
        assert diplomacy_modifier(None) == 0


@pytest.mark.unit
class TestTraitEffectsSingleTrait:
    """A single relevant trait applies exactly its documented delta."""

    def test_brave_boosts_combat(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        assert combat_modifier(["Brave"]) == pytest.approx(1.15, abs=EPS)
        # Brave touches only combat — tax/diplomacy stay at identity.
        assert tax_modifier(["Brave"]) == pytest.approx(1.0, abs=EPS)
        assert diplomacy_modifier(["Brave"]) == 0

    def test_craven_reduces_combat(self):
        combat_modifier, _, _ = _funcs()
        assert combat_modifier(["Craven"]) == pytest.approx(0.85, abs=EPS)

    def test_sickly_reduces_combat(self):
        combat_modifier, _, _ = _funcs()
        assert combat_modifier(["Sickly"]) == pytest.approx(0.95, abs=EPS)

    def test_greedy_boosts_tax(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        assert tax_modifier(["Greedy"]) == pytest.approx(1.20, abs=EPS)
        # Greedy also costs diplomacy.
        assert diplomacy_modifier(["Greedy"]) == -5
        # Greedy does not touch combat.
        assert combat_modifier(["Greedy"]) == pytest.approx(1.0, abs=EPS)

    def test_cunning_boosts_diplomacy(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        assert diplomacy_modifier(["Cunning"]) == 15
        assert combat_modifier(["Cunning"]) == pytest.approx(1.0, abs=EPS)
        assert tax_modifier(["Cunning"]) == pytest.approx(1.0, abs=EPS)

    def test_pious_boosts_diplomacy(self):
        _, _, diplomacy_modifier = _funcs()
        assert diplomacy_modifier(["Pious"]) == 10

    def test_wroth_boosts_combat_and_hurts_diplomacy(self):
        combat_modifier, _, diplomacy_modifier = _funcs()
        assert combat_modifier(["Wroth"]) == pytest.approx(1.10, abs=EPS)
        assert diplomacy_modifier(["Wroth"]) == -10

    def test_patient_boosts_combat_and_diplomacy(self):
        combat_modifier, _, diplomacy_modifier = _funcs()
        assert combat_modifier(["Patient"]) == pytest.approx(1.05, abs=EPS)
        assert diplomacy_modifier(["Patient"]) == 10


@pytest.mark.unit
class TestTraitEffectsMultipleTraits:
    """Multiple traits stack additively against the identity baseline."""

    def test_brave_plus_wroth_combat_is_additive(self):
        combat_modifier, _, _ = _funcs()
        # 1.0 + 0.15 (Brave) + 0.10 (Wroth) = 1.25
        assert combat_modifier(["Brave", "Wroth"]) == pytest.approx(1.25, abs=EPS)

    def test_wroth_plus_greedy_diplomacy_is_additive(self):
        _, _, diplomacy_modifier = _funcs()
        # 0 + (-10) (Wroth) + (-5) (Greedy) = -15
        assert diplomacy_modifier(["Wroth", "Greedy"]) == -15

    def test_opposed_combat_traits_cancel(self):
        combat_modifier, _, _ = _funcs()
        # Brave (+0.15) and Craven (-0.15) cancel back to the identity.
        assert combat_modifier(["Brave", "Craven"]) == pytest.approx(1.0, abs=EPS)

    def test_mixed_traits_affect_each_channel_independently(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        traits = ["Brave", "Greedy", "Cunning"]
        # combat: 1.0 + 0.15 (Brave) = 1.15  (Greedy/Cunning don't touch combat)
        assert combat_modifier(traits) == pytest.approx(1.15, abs=EPS)
        # tax: 1.0 + 0.20 (Greedy) = 1.20
        assert tax_modifier(traits) == pytest.approx(1.20, abs=EPS)
        # diplomacy: 0 + 15 (Cunning) - 5 (Greedy) = 10
        assert diplomacy_modifier(traits) == 10


@pytest.mark.unit
class TestTraitEffectsUnknownTraits:
    """Unknown / unrecognised traits are ignored entirely."""

    def test_unknown_trait_is_identity(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        assert combat_modifier(["Nonexistent"]) == pytest.approx(1.0, abs=EPS)
        assert tax_modifier(["Nonexistent"]) == pytest.approx(1.0, abs=EPS)
        assert diplomacy_modifier(["Nonexistent"]) == 0

    def test_unknown_traits_do_not_disturb_known_ones(self):
        combat_modifier, tax_modifier, diplomacy_modifier = _funcs()
        # A known trait mixed with garbage still yields exactly the known delta.
        assert combat_modifier(["Brave", "Nonexistent", "Foo"]) == pytest.approx(1.15, abs=EPS)
        assert diplomacy_modifier(["Cunning", "Bar"]) == 15
        assert tax_modifier(["Greedy", "Baz"]) == pytest.approx(1.20, abs=EPS)


@pytest.mark.unit
class TestTraitModifiersTable:
    """The TRAIT_MODIFIERS table is exported and self-consistent with the funcs."""

    def test_trait_modifiers_table_exists_and_covers_documented_traits(self):
        from models.trait_effects import TRAIT_MODIFIERS

        assert isinstance(TRAIT_MODIFIERS, dict)
        for trait in ("Brave", "Craven", "Wroth", "Patient",
                      "Cunning", "Pious", "Greedy", "Sickly"):
            assert trait in TRAIT_MODIFIERS, f"TRAIT_MODIFIERS missing '{trait}'"
