#!/bin/bash

# Home Network Monitor - Stop Monitoring Script
# Stops local Docker stack and Python monitoring agent

set -e

echo "================================================"
echo "Home Network Monitor - Stopping Services"
echo "================================================"

# Check if monitor.pid exists and kill the process
if [ -f "logs/monitor.pid" ]; then
    MONITOR_PID=$(cat logs/monitor.pid)
    echo -e "\n1. Stopping network monitoring agent (PID: $MONITOR_PID)..."
    if kill -0 $MONITOR_PID 2>/dev/null; then
        kill $MONITOR_PID
        echo "✓ Network monitoring agent stopped"
    else
        echo "! Network monitoring agent not running (PID: $MONITOR_PID)"
    fi
    # Remove the PID file
    rm logs/monitor.pid
else
    echo -e "\n1. No monitoring agent PID file found"
    echo "! Monitoring agent may not be running or was stopped manually"
fi

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ] && [ ! -f "local/docker-compose.yml" ]; then
    echo -e "\nERROR: docker-compose.yml not found."
    echo "Please run this script from the project root directory."
    exit 1
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "\nERROR: Docker is not installed or not in PATH."
    echo "Cannot stop Docker services."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "\nERROR: Docker daemon is not running."
    echo "Cannot stop Docker services."
    exit 1
fi

# Move to local directory if docker-compose.yml is there
if [ -f "local/docker-compose.yml" ]; then
    cd local
fi

echo -e "\n2. Stopping Docker monitoring services..."
docker-compose down
echo "✓ Docker services stopped"

# Move back to project root if needed
if [ -f "docker-compose.yml" ]; then
    cd ..
fi

echo -e "\n================================================"
echo "✅ All monitoring services have been stopped"
echo "================================================"

echo -e "\nTo restart monitoring services, run:"
echo "./scripts/start_monitoring.sh"