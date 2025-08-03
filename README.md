# Home Network Monitor

A hybrid local/cloud monitoring solution for home network quality monitoring.

## Project Structure

```
home-network-monitor/
├── README.md
├── .gitignore
├── requirements.txt
├── config/
│   ├── monitoring_config.yaml
│   └── aws_config.yaml
├── local/
│   ├── docker-compose.yml
│   ├── prometheus.yml
│   ├── blackbox.yml
│   └── grafana/
│       └── dashboards/
│           └── network-overview.json
├── monitor/
│   ├── network_monitor.py
│   ├── mac_agent.py
│   └── utils/
│       ├── __init__.py
│       ├── ping_utils.py
│       └── aws_utils.py
├── cloud/
│   ├── cloudwatch_setup.py
│   ├── lambda/
│   │   └── alert_processor.py
│   └── cloudformation/
│       └── monitoring_stack.yaml
├── scripts/
│   ├── install.sh
│   ├── start_monitoring.sh
│   └── setup_aws.sh
└── docs/
    ├── SETUP.md
    └── TROUBLESHOOTING.md
```

## Quick Start

1. **Initial Setup**
   ```bash
   git clone <your-repo>
   cd home-network-monitor
   chmod +x scripts/install.sh
   ./scripts/install.sh
   ```

2. **Configure AWS**
   ```bash
   aws configure  # Set up your AWS credentials
   ./scripts/setup_aws.sh
   ```

3. **Start Local Monitoring**
   ```bash
   ./scripts/start_monitoring.sh
   ```

4. **Access Dashboards**
   - Local Grafana: http://localhost:3000 (admin/admin)
   - AWS CloudWatch: https://console.aws.amazon.com/cloudwatch

## Features

- **Local Network Monitoring**: LAN latency, WiFi quality, internal bandwidth
- **Internet Quality Monitoring**: Multi-target latency, jitter, packet loss
- **Work-Proxy Monitoring**: Company endpoints, regional servers
- **Cloud Integration**: AWS CloudWatch metrics and dashboards
- **Alerting**: Email, SMS, Slack notifications
- **Cost Optimized**: Designed to stay under $5/month AWS usage

## Architecture

```
[Mac Studio] --WiFi--> [BASE] --Ethernet--> [Dell OptiPlex]
     |                                            |
     |-- Mac Agent (WiFi metrics)                 |-- Main Monitor
     |-- HTTP reports to Dell                     |-- Local Prometheus/Grafana
                                                 |-- CloudWatch Integration
                                                 |-- Alert Processing
```