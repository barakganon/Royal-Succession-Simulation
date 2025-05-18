# tests/unit/test_db_models.py
import pytest
import datetime
from models.db_models import (
    User, DynastyDB, PersonDB, HistoryLogEntryDB, 
    Territory, Province, Region, TerrainType
)


@pytest.mark.unit
@pytest.mark.model
class TestUserModel:
    """Unit tests for the User model."""

    def test_user_creation(self, session):
        """Test creating a user."""
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        
        session.add(user)
        session.commit()
        
        saved_user = session.query(User).filter_by(username="testuser").first()
        
        assert saved_user is not None
        assert saved_user.username == "testuser"
        assert saved_user.email == "test@example.com"
        assert saved_user.check_password("password123") is True
        assert saved_user.check_password("wrongpassword") is False

    def test_user_representation(self, session):
        """Test the string representation of a user."""
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        
        session.add(user)
        session.commit()
        
        assert repr(user) == f"<User testuser (ID: {user.id})>"


@pytest.mark.unit
@pytest.mark.model
class TestDynastyModel:
    """Unit tests for the DynastyDB model."""

    def test_dynasty_creation(self, session):
        """Test creating a dynasty."""
        # Create a user first
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        # Create a dynasty
        dynasty = DynastyDB(
            user_id=user.id,
            name="Test Dynasty",
            theme_identifier_or_json="medieval_europe",
            start_year=1400,
            current_simulation_year=1400
        )
        
        session.add(dynasty)
        session.commit()
        
        saved_dynasty = session.query(DynastyDB).filter_by(name="Test Dynasty").first()
        
        assert saved_dynasty is not None
        assert saved_dynasty.name == "Test Dynasty"
        assert saved_dynasty.theme_identifier_or_json == "medieval_europe"
        assert saved_dynasty.start_year == 1400
        assert saved_dynasty.current_simulation_year == 1400
        assert saved_dynasty.user_id == user.id

    def test_dynasty_representation(self, session):
        """Test the string representation of a dynasty."""
        # Create a user first
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        # Create a dynasty
        dynasty = DynastyDB(
            user_id=user.id,
            name="Test Dynasty",
            theme_identifier_or_json="medieval_europe",
            start_year=1400,
            current_simulation_year=1400
        )
        
        session.add(dynasty)
        session.commit()
        
        assert repr(dynasty) == f"<DynastyDB 'Test Dynasty' (ID: {dynasty.id}, User: {user.id})>"


@pytest.mark.unit
@pytest.mark.model
class TestPersonModel:
    """Unit tests for the PersonDB model."""

    def test_person_creation(self, session):
        """Test creating a person."""
        # Create a user and dynasty first
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        dynasty = DynastyDB(
            user_id=user.id,
            name="Test Dynasty",
            theme_identifier_or_json="medieval_europe",
            start_year=1400,
            current_simulation_year=1400
        )
        
        session.add(dynasty)
        session.commit()
        
        # Create a person
        person = PersonDB(
            dynasty_id=dynasty.id,
            name="John",
            surname="Smith",
            gender="male",
            birth_year=1380,
            is_noble=True,
            is_monarch=True
        )
        
        # Set titles and traits
        person.set_titles(["Duke", "Count"])
        person.set_traits(["Brave", "Ambitious"])
        
        session.add(person)
        session.commit()
        
        saved_person = session.query(PersonDB).filter_by(name="John").first()
        
        assert saved_person is not None
        assert saved_person.name == "John"
        assert saved_person.surname == "Smith"
        assert saved_person.gender == "male"
        assert saved_person.birth_year == 1380
        assert saved_person.is_noble is True
        assert saved_person.is_monarch is True
        assert saved_person.get_titles() == ["Duke", "Count"]
        assert saved_person.get_traits() == ["Brave", "Ambitious"]
        assert saved_person.dynasty_id == dynasty.id

    def test_person_relationships(self, session):
        """Test person family relationships."""
        # Create a user and dynasty first
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        dynasty = DynastyDB(
            user_id=user.id,
            name="Test Dynasty",
            theme_identifier_or_json="medieval_europe",
            start_year=1400,
            current_simulation_year=1400
        )
        
        session.add(dynasty)
        session.commit()
        
        # Create family members
        father = PersonDB(
            dynasty_id=dynasty.id,
            name="Robert",
            surname="Smith",
            gender="male",
            birth_year=1350,
            is_noble=True
        )
        
        mother = PersonDB(
            dynasty_id=dynasty.id,
            name="Mary",
            surname="Johnson",
            gender="female",
            birth_year=1355,
            is_noble=True
        )
        
        session.add_all([father, mother])
        session.commit()
        
        # Create child with relationships
        child = PersonDB(
            dynasty_id=dynasty.id,
            name="John",
            surname="Smith",
            gender="male",
            birth_year=1380,
            is_noble=True,
            father_sim_id=father.id,
            mother_sim_id=mother.id
        )
        
        session.add(child)
        session.commit()
        
        # Test relationships
        assert child.father.id == father.id
        assert child.mother.id == mother.id
        assert child in father.children_as_father
        assert child in mother.children_as_mother

    def test_person_methods(self, session):
        """Test person methods."""
        # Create a user and dynasty first
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        dynasty = DynastyDB(
            user_id=user.id,
            name="Test Dynasty",
            theme_identifier_or_json="medieval_europe",
            start_year=1400,
            current_simulation_year=1400
        )
        
        session.add(dynasty)
        session.commit()
        
        # Create a skilled person
        skilled_person = PersonDB(
            dynasty_id=dynasty.id,
            name="William",
            surname="Marshal",
            gender="male",
            birth_year=1370,
            is_noble=True,
            military_skill=10
        )
        skilled_person.set_traits(["Brave", "Strategist"])
        
        # Create an unskilled person
        unskilled_person = PersonDB(
            dynasty_id=dynasty.id,
            name="Coward",
            surname="Smith",
            gender="male",
            birth_year=1375,
            is_noble=True,
            military_skill=2
        )
        unskilled_person.set_traits(["Craven"])
        
        session.add_all([skilled_person, unskilled_person])
        session.commit()
        
        # Test can_lead_army method
        assert skilled_person.can_lead_army() is True
        assert unskilled_person.can_lead_army() is False
        
        # Test calculate_command_bonus method
        assert skilled_person.calculate_command_bonus() == 1.15  # 10 * 0.1 + 0.05 (Brave) + 0.1 (Strategist)
        assert unskilled_person.calculate_command_bonus() == 0.2  # 2 * 0.1


@pytest.mark.unit
@pytest.mark.model
class TestTerritoryModel:
    """Unit tests for the Territory model."""

    def test_territory_creation(self, session):
        """Test creating a territory with its hierarchy."""
        # Create region
        region = Region(
            name="Western Europe",
            base_climate="temperate"
        )
        session.add(region)
        session.commit()
        
        # Create province
        province = Province(
            region_id=region.id,
            name="Normandy",
            primary_terrain=TerrainType.COASTAL
        )
        session.add(province)
        session.commit()
        
        # Create territory
        territory = Territory(
            province_id=province.id,
            name="Rouen",
            terrain_type=TerrainType.COASTAL,
            x_coordinate=48.5,
            y_coordinate=1.2,
            base_tax=3,
            base_manpower=500,
            development_level=3,
            population=5000
        )
        session.add(territory)
        session.commit()
        
        # Test the relationships
        assert territory.province_id == province.id
        assert territory.province.name == "Normandy"
        assert territory.province.region_id == region.id
        assert territory.province.region.name == "Western Europe"
        
        # Test territory attributes
        assert territory.name == "Rouen"
        assert territory.terrain_type == TerrainType.COASTAL
        assert territory.base_tax == 3
        assert territory.population == 5000

    def test_territory_with_dynasty(self, session):
        """Test territory controlled by a dynasty."""
        # Create user and dynasty
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        session.add(user)
        session.commit()
        
        dynasty = DynastyDB(
            user_id=user.id,
            name="Test Dynasty",
            theme_identifier_or_json="medieval_europe",
            start_year=1400,
            current_simulation_year=1400
        )
        session.add(dynasty)
        session.commit()
        
        # Create region and province
        region = Region(name="Western Europe", base_climate="temperate")
        session.add(region)
        session.commit()
        
        province = Province(
            region_id=region.id,
            name="Normandy",
            primary_terrain=TerrainType.COASTAL
        )
        session.add(province)
        session.commit()
        
        # Create territory controlled by dynasty
        territory = Territory(
            province_id=province.id,
            name="Rouen",
            terrain_type=TerrainType.COASTAL,
            x_coordinate=48.5,
            y_coordinate=1.2,
            controller_dynasty_id=dynasty.id,
            is_capital=True
        )
        session.add(territory)
        session.commit()
        
        # Update dynasty with capital
        dynasty.capital_territory_id = territory.id
        session.commit()
        
        # Test the relationships
        assert territory.controller_dynasty_id == dynasty.id
        assert territory in dynasty.controlled_territories
        assert dynasty.capital_territory_id == territory.id
        assert dynasty.capital.name == "Rouen"