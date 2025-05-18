#!/bin/bash
# Script to run tests for the Royal Succession Simulation

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Royal Succession Simulation Test Runner ===${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed.${NC}"
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install -r requirements-test.txt
fi

# Function to run tests with specific markers
run_tests() {
    local marker=$1
    local description=$2
    
    echo -e "\n${BLUE}Running $description...${NC}"
    
    if [ -z "$marker" ]; then
        pytest -v
    else
        pytest -v -m "$marker"
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}$description passed!${NC}"
        return 0
    else
        echo -e "${RED}$description failed!${NC}"
        return 1
    fi
}

# Parse command line arguments
if [ $# -eq 0 ]; then
    # No arguments, run all tests
    echo -e "${YELLOW}Running all tests...${NC}"
    run_tests "" "All tests"
    exit $?
fi

# Process specific test types
case "$1" in
    "unit")
        run_tests "unit" "Unit tests"
        ;;
    "integration")
        run_tests "integration" "Integration tests"
        ;;
    "functional")
        run_tests "functional" "Functional tests"
        ;;
    "model")
        run_tests "model" "Database model tests"
        ;;
    "game_manager")
        run_tests "game_manager" "Game Manager tests"
        ;;
    "simulation")
        run_tests "simulation" "Simulation Engine tests"
        ;;
    "web")
        run_tests "web" "Web interface tests"
        ;;
    "coverage")
        echo -e "${YELLOW}Running tests with coverage report...${NC}"
        pytest --cov=. --cov-report=term --cov-report=html
        echo -e "${GREEN}Coverage report generated in htmlcov/ directory${NC}"
        ;;
    *)
        echo -e "${RED}Unknown test type: $1${NC}"
        echo -e "${YELLOW}Available options: unit, integration, functional, model, game_manager, simulation, web, coverage${NC}"
        exit 1
        ;;
esac

exit $?