#!/bin/bash

echo "Stopping all running instances of main_flask_app.py..."
# Kill all processes matching the pattern
pkill -f "python3 main_flask_app.py"

# More aggressive kill with SIGKILL if needed
echo "Ensuring all processes are terminated..."
sleep 2
pkill -9 -f "python3 main_flask_app.py" 2>/dev/null || true

# Check if port 8091 is still in use
echo "Checking if port 8091 is in use..."
if command -v lsof >/dev/null 2>&1; then
    # If lsof is available
    PORT_PROCESS=$(lsof -i :8091 -t 2>/dev/null)
    if [ ! -z "$PORT_PROCESS" ]; then
        echo "Port 8091 is still in use by process $PORT_PROCESS, killing it..."
        kill -9 $PORT_PROCESS 2>/dev/null || true
    fi
fi

# Wait a bit longer to ensure port is released
echo "Waiting for port to be released..."
sleep 10

echo "Removing the database to force a clean migration..."
rm -f instance/dynastysim.db

echo "Starting the Flask application with the fixes..."
python3 main_flask_app.py