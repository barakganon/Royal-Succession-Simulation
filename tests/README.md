# Royal Succession Simulation Testing Framework

This directory contains a comprehensive testing framework for the Royal Succession Simulation project. The framework is built using pytest and is organized into different test categories.

## Test Structure

The tests are organized into the following categories:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test interactions between components
- **Functional Tests**: Test complete workflows

## Directory Structure

```
tests/
├── __init__.py
├── conftest.py           # Common test fixtures and configuration
├── unit/                 # Unit tests for individual components
│   ├── __init__.py
│   ├── test_db_models.py # Database model tests
│   ├── test_game_manager.py # Game manager tests
│   └── test_simulation_engine.py # Simulation engine tests
├── integration/          # Integration tests for component interactions
│   ├── __init__.py
│   └── test_flask_app.py # Flask application tests
└── functional/           # Functional tests for complete workflows
    ├── __init__.py
    └── test_game_flow.py # Game flow tests
```

## Running Tests

The project includes a test runner script that can run different types of tests:

```bash
# Run all tests
./run_tests.sh

# Run specific test types
./run_tests.sh unit        # Run unit tests only
./run_tests.sh integration # Run integration tests only
./run_tests.sh functional  # Run functional tests only

# Run tests for specific components
./run_tests.sh model       # Run database model tests
./run_tests.sh game_manager # Run game manager tests
./run_tests.sh simulation  # Run simulation engine tests
./run_tests.sh web         # Run web interface tests

# Run tests with coverage report
./run_tests.sh coverage
```

## Test Fixtures

Common test fixtures are defined in `conftest.py`:

- `app`: Flask application for testing
- `db`: Database for testing
- `session`: Database session for testing
- `game_manager`: Game manager instance for testing

## Test Categories

Tests are categorized using pytest markers:

- `unit`: Unit tests
- `integration`: Integration tests
- `functional`: Functional tests
- `model`: Database model tests
- `game_manager`: Game manager tests
- `simulation`: Simulation engine tests
- `web`: Web interface tests
- `api`: API tests
- `slow`: Tests that take a long time to run
- `db`: Tests that require a database

## Writing New Tests

When adding new features, create corresponding tests using pytest:

```python
import pytest
from models.my_module import MyClass

@pytest.mark.unit  # Mark the test category
class TestMyClass:
    @pytest.fixture
    def my_instance(self):
        # Setup code
        instance = MyClass()
        yield instance
        # Cleanup code (if needed)
    
    def test_my_method(self, my_instance):
        # Test code
        result = my_instance.my_method(param1, param2)
        assert result == expected_result
```

## Test Dependencies

To install the required dependencies for testing:

```bash
pip install -r requirements-test.txt
```

## Coverage Reports

To generate a coverage report:

```bash
./run_tests.sh coverage
```

This will generate a coverage report in the `htmlcov/` directory.