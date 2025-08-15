#!/bin/bash

# Home Network Monitor Installation Script
# Supports Windows (Git Bash/WSL), macOS, and Linux

set -e  # Exit on any error

echo "================================================"
echo "Home Network Monitor - Installation Script"
echo "================================================"

# Detect operating system
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
    echo "Detected: Windows (Git Bash/MSYS)"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "Detected: macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "Detected: Linux"
else
    echo "Unsupported operating system: $OSTYPE"
    exit 1
fi

# Check for required tools
echo -e "\n1. Checking prerequisites..."

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not installed."
    echo "Please install Python 3.8+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python: $PYTHON_VERSION"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is required but not installed."
    exit 1
fi

# Check Docker (for Dell OptiPlex)
if command -v docker &> /dev/null; then
    echo "Found Docker: $(docker --version)"
    DOCKER_AVAILABLE=true
else
    echo "WARNING: Docker not found. Local monitoring stack will not be available."
    echo "Install Docker Desktop to use Prometheus/Grafana locally."
    DOCKER_AVAILABLE=false
fi

# Check AWS CLI (optional)
if command -v aws &> /dev/null; then
    echo "Found AWS CLI: $(aws --version)"
    AWS_AVAILABLE=true
else
    echo "INFO: AWS CLI not found. Install it later for cloud integration."
    AWS_AVAILABLE=false
fi

# Create project structure
echo -e "\n2. Creating project directories..."
mkdir -p logs
mkdir -p data
mkdir -p local/grafana/dashboards
mkdir -p local/grafana/datasources

# Set up Python virtual environment
echo -e "\n3. Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created virtual environment"
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment based on OS
if [[ "$OS" == "windows" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Upgrade pip and install requirements
echo -e "\n4. Installing Python dependencies..."
#pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

echo "Python dependencies installed successfully"

# Create Grafana datasource configuration
echo -e "\n5. Creating Grafana configuration..."
cat > local/grafana/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

# Create basic Grafana dashboard provisioning
cat > local/grafana/dashboards/dashboard.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'home-network'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

# Create nginx config for metrics receiver
echo -e "\n6. Creating nginx configuration..."
cat > local/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name localhost;
        
        location /metrics {
            return 200 "# Metrics endpoint ready\n";
            add_header Content-Type text/plain;
        }
        
        location /mac_metrics {
            return 200 "# Mac metrics received\n";
            add_header Content-Type application/json;
        }
        
        location / {
            return 200 "Home Network Monitor - Metrics Receiver\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF

# Create sample secrets template
echo -e "\n7. Creating configuration templates..."
cat > config/aws_config.yaml << 'EOF'
# AWS Configuration Template
# Copy this to aws_config_local.yaml and fill in your details

aws:
  region: "us-east-1"  # Change to your preferred region
  access_key_id: "YOUR_ACCESS_KEY_HERE"
  secret_access_key: "YOUR_SECRET_KEY_HERE"
  
  # SNS Topic ARN (will be created by setup script)
  sns_topic_arn: ""
  
  # Optional: SES configuration for email alerts
  ses:
    verified_email: "your-verified-email@domain.com"
    
  # Cost optimization
  cloudwatch:
    detailed_monitoring: false
    retention_days: 14
EOF

# Set executable permissions on scripts
echo -e "\n8. Setting script permissions..."
chmod +x scripts/*.sh

# OS-specific setup
echo -e "\n9. OS-specific configuration..."

if [[ "$OS" == "macos" ]]; then
    echo "macOS detected - checking for airport utility..."
    AIRPORT_PATH="/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
    if [ -f "$AIRPORT_PATH" ]; then
        echo "✓ Airport utility found for WiFi monitoring"
    else
        echo "⚠ Airport utility not found - WiFi details may be limited"
    fi
    
    # Check for Homebrew (optional but recommended)
    if command -v brew &> /dev/null; then
        echo "✓ Homebrew found"
    else
        echo "ℹ Consider installing Homebrew for easier package management"
    fi

elif [[ "$OS" == "windows" ]]; then
    echo "Windows detected - additional setup notes:"
    echo "• Make sure Windows Subsystem for Linux (WSL) is available if needed"
    echo "• Docker Desktop should be installed for local monitoring"
    echo "• Git Bash or PowerShell can be used to run scripts"

elif [[ "$OS" == "linux" ]]; then
    echo "Linux detected - checking package manager..."
    if command -v apt &> /dev/null; then
        echo "✓ APT package manager found (Debian/Ubuntu)"
    elif command -v yum &> /dev/null; then
        echo "✓ YUM package manager found (RedHat/CentOS)"
    elif command -v pacman &> /dev/null; then
        echo "✓ Pacman package manager found (Arch)"
    else
        echo "ℹ Package manager not detected - manual installation may be needed"
    fi
fi

# Final status and next steps
echo -e "\n================================================"
echo "✅ Installation completed successfully!"
echo "================================================"

echo -e "\nInstalled components:"
echo "• Python virtual environment with all dependencies"
echo "• Project directory structure"
echo "• Configuration templates"
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "• Docker configuration for local monitoring"
fi

echo -e "\nNext steps:"
echo "1. Configure your settings:"
echo "   • Edit config/monitoring_config.yaml"
echo "   • Update IP addresses and target endpoints"
echo "   • Configure alert settings"

if [ "$AWS_AVAILABLE" = true ]; then
    echo -e "\n2. Set up AWS integration (optional):"
    echo "   • Run: aws configure"
    echo "   • Run: ./scripts/setup_aws.sh"
else
    echo -e "\n2. To enable AWS integration:"
    echo "   • Install AWS CLI: https://aws.amazon.com/cli/"
    echo "   • Run: aws configure"
    echo "   • Run: ./scripts/setup_aws.sh"
fi

if [ "$DOCKER_AVAILABLE" = true ]; then
    echo -e "\n3. Start local monitoring:"
    echo "   • Run: ./scripts/start_monitoring.sh"
else
    echo -e "\n3. Install Docker Desktop, then:"
    echo "   • Run: ./scripts/start_monitoring.sh"
fi

echo -e "\n4. Access dashboards:"
echo "   • Local Grafana: http://localhost:3000 (admin/admin)"
echo "   • Prometheus: http://localhost:9090"

echo -e "\n5. For Mac Studio:"
echo "   • Copy monitor/mac_agent.py to your Mac"
echo "   • Install dependencies: pip3 install -r requirements.txt"
echo "   • Update config with Dell IP address"
echo "   • Run: python3 mac_agent.py"

echo -e "\nFor detailed setup instructions, see: docs/SETUP.md"
echo "For troubleshooting help, see: docs/TROUBLESHOOTING.md"

echo -e "\n🎉 Happy monitoring!"