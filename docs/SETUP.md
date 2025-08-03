# Home Network Monitor - Setup Guide

This guide will walk you through setting up a comprehensive home network monitoring system that tracks network quality, performance, and availability.

## Overview

**Architecture**: Hybrid local/cloud monitoring system
- **Local**: Docker stack (Prometheus, Grafana, Blackbox Exporter) + Python monitoring agent
- **Cloud**: AWS CloudWatch for metrics storage, dashboards, and alerting
- **Distributed**: Mac Studio agent for WiFi monitoring
- **Cost**: Under $5/month for AWS services

## Prerequisites

### Required
- **Python 3.8+** with pip
- **Docker Desktop** (for local monitoring stack)
- **Git** (for version control)

### Optional
- **AWS Account** (for cloud integration and remote alerts)
- **AWS CLI** (for automated setup)

### Supported Platforms
- **Windows 10/11** (via Git Bash, PowerShell, or WSL)
- **macOS** (for Mac Studio WiFi monitoring)
- **Linux** (Ubuntu, CentOS, etc.)

## Quick Start

### 1. Initial Setup

```bash
# Clone and setup the project
git clone <your-repo-url>
cd home-network-monitor

# Run installation script
chmod +x scripts/install.sh
./scripts/install.sh
```

The install script will:
- Create Python virtual environment
- Install all dependencies
- Set up project structure
- Create configuration templates
- Check for required tools

### 2. Configure Monitoring

Edit `config/monitoring_config.yaml`:

```yaml
# Update with your actual network details
targets:
  internal:
    lan_gateway: "192.168.1.1"          # Your router IP
    mac_studio: "192.168.1.XXX"         # Mac Studio IP
  
  work_proxy:
    # Replace with actual work endpoints you can monitor
    company_portal: "portal.yourcompany.com"
    company_mail: "mail.yourcompany.com"

# Configure alert settings
alerts:
  enabled: true
  channels:
    email:
      enabled: true
      address: "your-email@gmail.com"
```

### 3. Start Local Monitoring

```bash
./scripts/start_monitoring.sh
```

This starts:
- **Prometheus** (metrics storage): http://localhost:9090
- **Grafana** (dashboards): http://localhost:3000
- **Blackbox Exporter** (network probes): http://localhost:9115
- **Python Agent** (custom monitoring): http://localhost:8000

### 4. Setup AWS Integration (Optional)

```bash
# Configure AWS credentials
aws configure

# Setup CloudWatch resources
./scripts/setup_aws.sh
```

### 5. Setup Mac Studio Agent (Optional)

On your Mac Studio:

```bash
# Copy agent script
scp monitor/mac_agent.py user@mac-studio:~/

# Install dependencies
pip3 install requests pyyaml psutil

# Update config with Dell IP address
# Edit the config file to point to your Dell's IP

# Run agent
python3 mac_agent.py
```

## Detailed Configuration

### Network Targets

Update `config/monitoring_config.yaml` with your specific network setup:

```yaml
targets:
  internal:
    lan_gateway: "192.168.1.1"      # Your Eero base station
    eero_base: "192.168.1.1"        # Usually same as gateway
    mac_studio: "192.168.1.5"     # Check with: ifconfig en0
    dell_optiplex: "192.168.1.4"  # Check with: ipconfig
  
  internet:
    cloudflare_primary: "1.1.1.1"
    google_primary: "8.8.8.8"
    # Keep these standard - they're reliable test endpoints
  
  work_proxy:
    # Examples - replace with your actual work endpoints
    company_portal: "portal.acme.com"
    company_vpn: "vpn.acme.com"
    office_website: "www.acme.com"
```

**Finding your IP addresses:**
- **Mac**: `ifconfig en0 | grep inet`
- **Windows**: `ipconfig`
- **Router**: Usually 192.168.1.1 or check router admin page

### Alert Configuration

```yaml
alerts:
  enabled: true
  
  channels:
    email:
      enabled: true
      address: "alerts@yourdomain.com"
    
    sms:
      enabled: true
      phone_number: "+1234567890"
    
    slack:
      enabled: true
      webhook_url: "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
  
  # Timing settings
  cooldown_minutes: 15      # Prevent spam
  escalation_minutes: 60    # Time before escalating alerts

# Threshold settings
thresholds:
  latency:
    lan_warning: 10         # ms
    lan_critical: 25        # ms
    internet_warning: 100   # ms
    internet_critical: 250  # ms
    work_warning: 150       # ms
    work_critical: 400      # ms
  
  packet_loss:
    warning: 1              # %
    critical: 5             # %
```

### AWS Configuration

For cloud integration, you'll need:

1. **AWS Account** with programmatic access
2. **IAM User** with permissions for:
   - CloudWatch (metrics, dashboards, alarms)
   - SNS (notifications)
   - SES (email alerts, optional)

Required IAM permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData",
                "cloudwatch:PutDashboard",
                "cloudwatch:PutMetricAlarm",
                "cloudwatch:ListMetrics",
                "sns:CreateTopic",
                "sns:Subscribe",
                "sns:Publish"
            ],
            "Resource": "*"
        }
    ]
}
```

## Dashboard Setup

### Grafana (Local)

1. **Access**: http://localhost:3000
2. **Login**: admin/admin (change on first login)
3. **Add Prometheus datasource**: http://prometheus:9090
4. **Import dashboards** or create custom ones

**Key Metrics to Monitor:**
- `probe_duration_seconds` - Network latency
- `probe_success` - Target availability
- `probe_dns_lookup_time_seconds` - DNS performance

### CloudWatch (AWS)

After running `./scripts/setup_aws.sh`:

1. **Dashboard**: Auto-created "HomeNetworkMonitoring"
2. **Metrics**: Custom namespace "HomeNetwork"
3. **Alarms**: Latency and availability monitoring
4. **Access**: https://console.aws.amazon.com/cloudwatch/

## Monitoring Workflow

### Daily Operation

The system runs automatically and provides:

**Continuous Monitoring:**
- Ping tests every 60 seconds
- DNS lookup tests every 5 minutes
- System metrics every 60 seconds
- Mac Studio reports every 5 minutes

**Alerting:**
- Immediate alerts for critical issues
- Warning alerts for performance degradation
- Email/SMS notifications for outages
- Slack integration for team visibility

### Accessing Data

**Real-time:**
- Grafana dashboards: http://localhost:3000
- Prometheus queries: http://localhost:9090
- Raw metrics: http://localhost:8000/metrics

**Historical:**
- CloudWatch dashboards (AWS console)
- Prometheus local storage (30 days)
- Log files in `logs/` directory

### Maintenance Tasks

**Weekly:**
- Check log files for errors: `tail -f logs/*.log`
- Verify alert delivery: test with intentional outage
- Review CloudWatch costs: `python3 scripts/check_aws_costs.py`

**Monthly:**
- Update configuration for any network changes
- Review and tune alert thresholds
- Clean up old log files
- Update Docker images: `docker-compose pull && docker-compose up -d`

## Work VPN Considerations

Since you can't monitor the work VPN directly, we use proxy indicators:

**Indirect Monitoring:**
- **Company endpoints**: Public websites, mail servers
- **Regional servers**: Infrastructure near your office
- **Route analysis**: Path quality to work destinations
- **Internet baseline**: Foundation performance metrics

**Configuration Example:**
```yaml
work_proxy:
  company_portal: "portal.yourcompany.com"
  company_mail: "outlook.office365.com"     # If using Office 365
  office_region: "speedtest-dallas.net"     # Server near office
  work_dns: "8.8.8.8"                      # Stable reference point
```

**Interpreting Results:**
- **High latency to company endpoints** → Potential VPN issues
- **Packet loss to regional servers** → ISP routing problems
- **DNS resolution delays** → Network infrastructure issues
- **Baseline internet degradation** → Will affect VPN performance

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

## Cost Management

**Local Only**: $0/month (electricity costs only)

**With AWS Integration**: $2-5/month
- CloudWatch metrics: ~$2/month
- SNS notifications: ~$0.50/month
- CloudWatch alarms: ~$0.10/month
- Data transfer: ~$0.50/month

**Cost Optimization:**
- Use standard resolution metrics (60-second intervals)
- Set retention to 14 days instead of default
- Monitor spending with cost alarms
- Use detailed monitoring only when troubleshooting

## Security Considerations

**Network Security:**
- Monitor exposes metrics on local network only
- No sensitive credentials in configuration files
- Docker containers run with minimal privileges

**AWS Security:**
- Use IAM user with minimal required permissions
- Enable MFA on AWS account
- Rotate access keys regularly
- Monitor CloudTrail for API usage

**Data Privacy:**
- No personal data collected
- Only network performance metrics stored
- Logs contain IP addresses and timestamps only

## Next Steps

1. **Customize Dashboards**: Create views specific to your needs
2. **Add More Targets**: Monitor additional devices or services
3. **Integrate with Home Automation**: Send alerts to smart home systems
4. **Advanced Analytics**: Use CloudWatch Insights for deeper analysis
5. **Mobile Access**: Set up remote dashboard access

## Support

- **Configuration Issues**: Check config/monitoring_config.yaml
- **Docker Problems**: Run `docker-compose logs -f`
- **AWS Issues**: Verify credentials with `aws sts get-caller-identity`
- **Network Problems**: Test basic connectivity with `ping` and `nslookup`