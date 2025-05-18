# tests/unit/test_simulation_engine.py
import pytest
from simulation_engine import SimulationEngine


@pytest.mark.unit
@pytest.mark.simulation
class TestSimulationEngine:
    """Unit tests for the SimulationEngine class."""

    def test_initialization(self):
        """Test that the SimulationEngine initializes correctly."""
        engine = SimulationEngine()
        assert engine is not None
        assert isinstance(engine, SimulationEngine)
        assert hasattr(engine, 'dynasties')
        assert hasattr(engine, 'persons')
        assert hasattr(engine, 'history')

    def test_configuration(self):
        """Test configuring the simulation engine."""
        engine = SimulationEngine()
        
        # Configure with custom settings
        engine.configure(
            verbose_log=True,
            viz_interval=25,
            max_years=200
        )
        
        # Check that the configuration was applied
        assert engine.verbose_log is True
        assert engine.viz_interval == 25
        assert engine.max_years == 200

    def test_create_dynasty(self):
        """Test creating a dynasty in the simulation."""
        engine = SimulationEngine()
        
        # Create a dynasty
        dynasty_id = engine.create_dynasty(
            name="Test Dynasty",
            culture="Western European",
            start_year=1400
        )
        
        # Check that the dynasty was created
        assert dynasty_id is not None
        assert dynasty_id in engine.dynasties
        assert engine.dynasties[dynasty_id].name == "Test Dynasty"
        assert engine.dynasties[dynasty_id].culture == "Western European"
        assert engine.dynasties[dynasty_id].start_year == 1400
        assert engine.dynasties[dynasty_id].current_year == 1400

    def test_create_person(self):
        """Test creating a person in the simulation."""
        engine = SimulationEngine()
        
        # Create a dynasty first
        dynasty_id = engine.create_dynasty(
            name="Test Dynasty",
            culture="Western European",
            start_year=1400
        )
        
        # Create a person
        person_id = engine.create_person(
            dynasty_id=dynasty_id,
            name="John",
            gender="male",
            birth_year=1380,
            is_noble=True
        )
        
        # Check that the person was created
        assert person_id is not None
        assert person_id in engine.persons
        assert engine.persons[person_id].name == "John"
        assert engine.persons[person_id].gender == "male"
        assert engine.persons[person_id].birth_year == 1380
        assert engine.persons[person_id].is_noble is True
        assert engine.persons[person_id].dynasty_id == dynasty_id

    def test_advance_simulation(self):
        """Test advancing the simulation by one year."""
        engine = SimulationEngine()
        
        # Create a dynasty
        dynasty_id = engine.create_dynasty(
            name="Test Dynasty",
            culture="Western European",
            start_year=1400
        )
        
        # Create a person
        person_id = engine.create_person(
            dynasty_id=dynasty_id,
            name="John",
            gender="male",
            birth_year=1380,
            is_noble=True
        )
        
        # Advance the simulation by one year
        engine.advance_year(dynasty_id)
        
        # Check that the year was advanced
        assert engine.dynasties[dynasty_id].current_year == 1401
        
        # Check that the person's age was updated
        assert engine.persons[person_id].age == 21  # 1401 - 1380 = 21

    def test_generate_events(self):
        """Test generating events in the simulation."""
        engine = SimulationEngine()
        
        # Create a dynasty
        dynasty_id = engine.create_dynasty(
            name="Test Dynasty",
            culture="Western European",
            start_year=1400
        )
        
        # Create a ruler
        ruler_id = engine.create_person(
            dynasty_id=dynasty_id,
            name="John",
            gender="male",
            birth_year=1380,
            is_noble=True,
            is_ruler=True
        )
        
        # Set the ruler for the dynasty
        engine.dynasties[dynasty_id].ruler_id = ruler_id
        
        # Generate events
        events = engine.generate_events(dynasty_id)
        
        # Check that events were generated
        assert events is not None
        assert isinstance(events, list)
        
        # Advance the simulation to trigger more events
        for _ in range(5):
            engine.advance_year(dynasty_id)
            new_events = engine.generate_events(dynasty_id)
            events.extend(new_events)
        
        # Check that we have some events
        assert len(events) > 0
        
        # Check the structure of an event
        if events:
            event = events[0]
            assert 'year' in event
            assert 'description' in event
            assert 'type' in event