# tests/unit/test_simulation_engine.py
# Tests for the SimulationEngine class. Rewrote against the current API:
#   - SimulationEngine has __init__, configure, and run methods.
#   - It does NOT have dynasties/persons attributes; those belong to the older standalone engine.
#   - run() delegates to the module-level run_simulation() function.
import pytest
from simulation_engine import SimulationEngine


@pytest.mark.unit
@pytest.mark.simulation
class TestSimulationEngine:
    """Unit tests for the SimulationEngine class."""

    def test_initialization(self):
        """Test that the SimulationEngine instantiates with correct defaults."""
        engine = SimulationEngine()
        assert engine is not None
        assert isinstance(engine, SimulationEngine)

    def test_has_required_attributes(self):
        """Test that SimulationEngine exposes the expected configuration attributes."""
        engine = SimulationEngine()
        assert hasattr(engine, 'verbose_logging')
        assert hasattr(engine, 'visualize_tree_interval_years')
        assert hasattr(engine, 'use_llm_flair')
        assert hasattr(engine, 'verbose_event_logging')
        assert hasattr(engine, 'verbose_trait_logging')
        assert hasattr(engine, 'llm_model_instance')
        assert hasattr(engine, 'google_api_key_is_set')

    def test_default_attribute_values(self):
        """Test that default attribute values are sensible."""
        engine = SimulationEngine()
        assert engine.verbose_logging is True
        assert engine.use_llm_flair is True
        assert engine.llm_model_instance is None
        assert engine.google_api_key_is_set is False
        assert engine.visualize_tree_interval_years == 50

    def test_configuration(self):
        """Test that configure() updates the engine's attributes."""
        engine = SimulationEngine()
        engine.configure(
            verbose_log=False,
            viz_interval=25,
            use_llm_flair=False,
            event_log=False,
            trait_log=False,
        )
        assert engine.verbose_logging is False
        assert engine.visualize_tree_interval_years == 25
        assert engine.use_llm_flair is False
        assert engine.verbose_event_logging is False
        assert engine.verbose_trait_logging is False

    def test_configure_llm_model(self):
        """Test that configure() stores the llm_model_obj and api_key flag."""
        engine = SimulationEngine()
        # Simulate passing a mock LLM model object
        mock_model = object()
        engine.configure(llm_model_obj=mock_model, api_key_present_bool=True)
        assert engine.llm_model_instance is mock_model
        assert engine.google_api_key_is_set is True

    def test_run_method_exists(self):
        """Test that the run() method exists and is callable."""
        engine = SimulationEngine()
        assert callable(getattr(engine, 'run', None))
