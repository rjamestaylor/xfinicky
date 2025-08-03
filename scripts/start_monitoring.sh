#!/bin/bash

# Home Network Monitor - Start Monitoring Script
# Starts local Docker stack and Python monitoring agent

set -e

echo "================================================"
echo "Home Network Monitor - Starting Services"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ] && [ ! -f "local/docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found."
    echo "Please run this script from the project root directory."
    exit 1
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    echo "Please install Docker Desktop and try again."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running."
    echo "Please start Docker Desktop and try again."
    exit 1
fi

# Move to local directory if docker-compose.yml is there
if [ -f "local/docker-compose.yml" ]; then
    cd local
fi

echo -e "\n1. Checking Docker Compose configuration..."
docker-compose config --quiet
echo "✓ Docker Compose configuration is valid"

echo -e "\n2. Pulling latest Docker images..."
docker-compose pull

echo -e "\n3. Starting monitoring services..."
docker-compose up -d

# Wait a moment for services to start
echo -e "\n4. Waiting for services to initialize..."
sleep 10

# Check service status
echo -e "\n5. Checking service status..."
docker-compose ps

# Function to check if a service is healthy
check_service() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    echo -n "Checking $service_name on port $port"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" | grep -q "200\|404\|302"; then
            echo " ✓"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    echo " ✗"
    return 1
}

# Check if services are responding
echo -e "\n6. Verifying service health..."

if check_service "Prometheus" 9090; then
    PROMETHEUS_OK=true
else
    echo "WARNING: Prometheus may not be responding correctly"
    PROMETHEUS_OK=false
fi

if check_service "Grafana" 3000; then
    GRAFANA_OK=true
else
    echo "WARNING: Grafana may not be responding correctly"
    GRAFANA_OK=false
fi

if check_service "Blackbox Exporter" 9115; then
    BLACKBOX_OK=true
else
    echo "WARNING: Blackbox Exporter may not be responding correctly" 
    BLACKBOX_OK=false
fi

# Move back to project root
if [ -f "docker-compose.yml" ]; then
    cd ..
fi

# Start Python monitoring agent
echo -e "\n7. Starting Python monitoring agent..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "ERROR: Python virtual environment not found."
    echo "Please run ./scripts/install.sh first."
    exit 1
fi

# Activate virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Check if required Python packages are installed
if ! python3 -c "import boto3, ping3, psutil, yaml" 2>/dev/null; then
    echo "WARNING: Some Python dependencies may be missing."
    echo "Running pip install to ensure all packages are available..."
    pip install -r requirements.txt
fi

# Start the monitoring agent in the background
echo "Starting network monitoring agent..."
nohup python3 monitor/network_monitor.py > logs/monitor.log 2>&1 &
MONITOR_PID=$!

# Save PID for later cleanup
echo $MONITOR_PID > logs/monitor.pid

# Wait a moment and check if it's still running
sleep 3
if kill -0 $MONITOR_PID 2>/dev/null; then
    echo "✓ Network monitoring agent started (PID: $MONITOR_PID)"
else
    echo "✗ Network monitoring agent failed to start"
    echo "Check logs/monitor.log for details"
fi

# Display status summary
echo -e "\n================================================"
echo "🚀 Home Network Monitor Status"
echo "================================================"

echo -e "\nDocker Services:"
if [ "$PROMETHEUS_OK" = true ]; then
    echo "✓ Prometheus:        http://localhost:9090"
else
    echo "✗ Prometheus:        Failed to start"
fi

if [ "$GRAFANA_OK" = true ]; then
    echo "✓ Grafana:           http://localhost:3000 (admin/admin)"
else
    echo "✗ Grafana:           Failed to start"
fi

if [ "$BLACKBOX_OK" = true ]; then
    echo "✓ Blackbox Exporter: http://localhost:9115"
else
    echo "✗ Blackbox Exporter: Failed to start"
fi

echo -e "\nMonitoring Agent:"
if kill -0 $MONITOR_PID 2>/dev/null; then
    echo "✓ Network Monitor:   Running (PID: $MONITOR_PID)"
    echo "✓ Metrics Endpoint:  http://localhost:8000/metrics"
else
    echo "✗ Network Monitor:   Failed to start"
fi

echo -e "\nLog Files:"
echo "• Docker logs:       docker-compose logs -f"
echo "• Monitor logs:      tail -f logs/monitor.log"
echo "• All logs:          tail -f logs/*.log"

echo -e "\nUseful Commands:"
echo "• Stop all services: ./scripts/stop_monitoring.sh"
echo "• View logs:         docker-compose logs -f"
echo "• Restart services:  docker-compose restart"

# Check configuration warnings
echo -e "\n⚠️  Configuration Reminders:"
echo "• Update config/monitoring_config.yaml with your actual IP addresses"
echo "• Replace placeholder work endpoints with real targets you can monitor"
echo "• Configure alert channels (email, SMS, Slack) if desired"
echo "• Set up AWS integration with ./scripts/setup_aws.sh"

# Mac Studio setup reminder
echo -e "\n📱 Mac Studio Setup:"
echo "• Copy monitor/mac_agent.py to your Mac Studio"
echo "• Update Dell IP address in config file"
echo "• Run: python3 mac_agent.py"

echo -e "\n🎯 Next Steps:"
echo "1. Open Grafana: http://localhost:3000"
echo "2. Log in with admin/admin"
echo "3. Import or create dashboards"
echo "4. Wait 5-10 minutes for initial data to appear"
echo "5. Configure AWS CloudWatch if desired"

echo -e "\n✅ Monitoring system is starting up!"
echo "Check the web interfaces in a few minutes for data."