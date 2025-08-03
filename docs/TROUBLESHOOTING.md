# Home Network Monitor - Troubleshooting Guide

This guide covers common issues and their solutions for the Home Network Monitor system.

## Quick Diagnostics

### System Status Check

```bash
# Check all services at once
./scripts/status_check.sh

# Or manually check each component:
docker-compose ps                    # Docker services
ps aux | grep network_monitor        # Python agent
curl -s http://localhost:9090        # Prometheus
curl -s http://localhost:3000        # Grafana
curl -s http://localhost:8000/metrics # Metrics endpoint
```

### Log Analysis

```bash
# View recent logs
tail -f logs/monitor.log              # Python monitoring agent
docker-compose logs -f prometheus    # Prometheus logs
docker-compose logs -f grafana       # Grafana logs
docker-compose logs -f blackbox-exporter # Network probing

# Check for errors in last hour
grep -i error logs/monitor.log | tail -20
```

## Installation Issues

### Docker Problems

**Issue**: Docker daemon not running
```
Error: Cannot connect to the Docker daemon
```

**Solutions**:
```bash
# Windows
# Start Docker Desktop from Start Menu

# macOS
open -a Docker

# Linux
sudo systemctl start docker
sudo systemctl enable docker  # Auto-start on boot
```

**Issue**: Permission denied on Docker commands
```
permission denied while trying to connect to the Docker daemon socket
```

**Solutions**:
```bash
# Linux - Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in, or:
newgrp docker

# Windows/macOS - Restart Docker Desktop
```

### Python Environment Issues

**Issue**: Virtual environment activation fails
```bash
# Windows Git Bash
source venv/Scripts/activate

# macOS/Linux
source venv/bin/activate

# If venv doesn't exist
python3 -m venv venv
```

**Issue**: Missing Python dependencies
```
ModuleNotFoundError: No module named 'boto3'
```

**Solutions**:
```bash
# Ensure virtual environment is activated
pip install --upgrade pip
pip install -r requirements.txt

# If specific package fails
pip install boto3 ping3 psutil pyyaml
```

**Issue**: Python version compatibility
```
ERROR: Python 3.7 is not supported
```

**Solutions**:
- Install Python 3.8 or newer
- Update virtual environment:
```bash
rm -rf venv
python3.9 -m venv venv  # Use newer Python version
```

## Network Configuration Issues

### IP Address Problems

**Issue**: Can't reach Mac Studio from Dell
```
ping: cannot resolve 192.168.1.100: Host unreachable
```

**Diagnostics**:
```bash
# Find correct IP addresses
# On Mac:
ifconfig en0 | grep "inet "

# On Windows:
ipconfig | findstr IPv4

# On router admin page:
# Usually 192.168.1.1 in browser
```

**Solutions**:
- Update `config/monitoring_config.yaml` with correct IPs
- Check devices are on same network segment
- Verify no firewall blocking ICMP/HTTP

### Firewall Issues

**Issue**: Monitoring ports blocked

**Windows Firewall**:
```powershell
# Allow monitoring ports
netsh advfirewall firewall add rule name="Home Monitor" dir=in action=allow protocol=TCP localport=3000,8000,9090,9115
```

**macOS Firewall**:
```bash
# System Preferences > Security & Privacy > Firewall
# Add exceptions for monitoring apps
```

**Router/Eero Issues**:
- Check if device isolation is enabled
- Ensure all devices on same network
- Verify port forwarding not blocking internal traffic

### DNS Resolution Problems

**Issue**: DNS lookup timeouts
```
dns_lookup_time metric showing high values or failures
```

**Diagnostics**:
```bash
# Test DNS resolution
nslookup google.com
nslookup google.com 8.8.8.8
nslookup google.com 1.1.1.1

# Check DNS settings
cat /etc/resolv.conf  # Linux/macOS
ipconfig /all         # Windows
```

**Solutions**:
- Update DNS servers in router config
- Use alternative DNS (1.1.1.1, 8.8.8.8) temporarily
- Check for DNS filtering/blocking

## Service-Specific Issues

### Prometheus Issues

**Issue**: Prometheus not scraping targets
```
Targets showing as "DOWN" in Prometheus UI
```

**Diagnostics**:
```bash
# Check Prometheus config
docker exec network-prometheus cat /etc/prometheus/prometheus.yml

# Test target connectivity
curl -s http://localhost:9115/probe?target=google.com&module=icmp
```

**Solutions**:
- Verify `prometheus.yml` syntax: `docker-compose config`
- Check target URLs are accessible
- Restart Prometheus: `docker-compose restart prometheus`

**Issue**: Prometheus storage full
```
Error: storage is full
```

**Solutions**:
```bash
# Check disk space
df -h

# Reduce retention time in docker-compose.yml:
# --storage.tsdb.retention.time=15d
# --storage.tsdb.retention.size=256MB

# Clean up old data
docker-compose down
docker volume rm network-prometheus_prometheus_data
docker-compose up -d
```

### Grafana Issues

**Issue**: Grafana login problems
```
Invalid username or password
```

**Solutions**:
- Default credentials: admin/admin
- Reset admin password:
```bash
docker exec -it network-grafana grafana-cli admin reset-admin-password newpassword
```

**Issue**: No data in Grafana dashboards

**Diagnostics**:
- Check Prometheus datasource: Configuration > Data Sources
- Test query in Prometheus: http://localhost:9090
- Verify time range in Grafana (last 1 hour, not last 24 hours)

**Solutions**:
- Add Prometheus datasource: http://prometheus:9090
- Wait 5-10 minutes for initial data collection
- Check metric names match between Prometheus and Grafana

### Blackbox Exporter Issues

**Issue**: All ping targets failing
```
probe_success{job="blackbox-ping"} = 0
```

**Diagnostics**:
```bash
# Test blackbox directly
curl "http://localhost:9115/probe?target=google.com&module=icmp"

# Check ICMP permissions
docker logs network-blackbox
```

**Solutions**:
- Run Docker as privileged for ICMP:
```yaml
# In docker-compose.yml under blackbox-exporter:
privileged: true
```
- Use HTTP probes instead of ICMP if permissions issue persists

## Python Agent Issues

### Monitoring Agent Crashes

**Issue**: Network monitor stops running
```
No process found for network_monitor.py
```

**Diagnostics**:
```bash
# Check recent logs
tail -50 logs/monitor.log

# Check if process is running
ps aux | grep network_monitor

# Check for Python errors
python3 monitor/network_monitor.py  # Run in foreground
```

**Common Errors & Solutions**:

**AWS Credentials Error**:
```
NoCredentialsError: Unable to locate credentials
```
```bash
# Configure AWS CLI
aws configure

# Or disable AWS in config:
# aws: enabled: false
```

**Ping Permission Error**:
```
Operation not permitted (ping requires root)
```
```bash
# On Linux, allow ping for user
sudo sysctl -w net.ipv4.ping_group_range="0 2000"

# Or use alternative ping library in code
```

### Mac Agent Issues

**Issue**: Mac agent can't connect to Dell
```
ConnectionError: Failed to connect to Dell monitoring hub
```

**Diagnostics**:
```bash
# Test connectivity from Mac
ping 192.168.1.XXX  # Dell IP
curl http://192.168.1.XXX:8000/metrics

# Check Dell firewall
netstat -an | grep 8000  # Should show listening port
```

**Solutions**:
- Update Dell IP in Mac agent config
- Verify Dell monitoring agent is running
- Check Windows firewall allows port 8000

**Issue**: WiFi info not available on Mac
```
Empty wifi_info in Mac agent output
```

**Solutions**:
```bash
# Check WiFi interface name
networksetup -listallhardwareports

# Update interface in config (usually en0 or en1)
# Try manual airport command
/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I
```

## AWS CloudWatch Issues

### Authentication Problems

**Issue**: AWS credentials not working
```
InvalidClientTokenId: The security token included in the request is invalid
```

**Solutions**:
```bash
# Verify credentials
aws sts get-caller-identity

# Reconfigure if needed
aws configure

# Check region setting
aws configure get region
```

**Issue**: Permission denied errors
```
AccessDenied: User is not authorized to perform: cloudwatch:PutMetricData
```

**Solutions**:
- Add required IAM permissions (see SETUP.md)
- Verify user has programmatic access enabled
- Check AWS account is active and in good standing

### Cost Issues

**Issue**: Unexpected AWS charges

**Diagnostics**:
```bash
# Check current costs
python3 scripts/check_aws_costs.py

# Review CloudWatch pricing
# aws ce get-cost-and-usage --time-period Start=2024-01-01,End=2024-01-31 --granularity MONTHLY --metrics BlendedCost
```

**Solutions**:
- Reduce metric frequency in config
- Lower CloudWatch retention (14 days vs 30)
- Disable detailed monitoring
- Delete unused alarms/dashboards

### Metric Delivery Issues

**Issue**: Metrics not appearing in CloudWatch
```
No data points in CloudWatch dashboard
```

**Diagnostics**:
```bash
# Check local Python agent logs
grep -i cloudwatch logs/monitor.log

# Test CloudWatch connectivity
python3 -c "
import boto3
cw = boto3.client('cloudwatch')
print(cw.list_metrics(Namespace='HomeNetwork'))
"
```

**Solutions**:
- Verify AWS region matches in all configs
- Check metric names for typos
- Ensure proper timestamp format (UTC)
- Wait up to 15 minutes for metric propagation

## Performance Issues

### High CPU Usage

**Issue**: Docker containers using too much CPU

**Diagnostics**:
```bash
# Check resource usage
docker stats

# Identify heavy containers
top -p $(docker inspect --format='{{.State.Pid}}' network-prometheus)
```

**Solutions**:
- Reduce scrape frequency in prometheus.yml
- Limit resource usage in docker-compose.yml:
```yaml
services:
  prometheus:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: 0.5
```

### Memory Issues

**Issue**: System running out of memory

**Solutions**:
- Reduce Prometheus retention time
- Limit Docker container memory
- Add swap space if needed:
```bash
# Linux - add 2GB swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Network Congestion

**Issue**: Monitoring causing network slowdown

**Solutions**:
- Increase ping intervals (60s → 120s)
- Reduce number of monitored targets
- Disable bandwidth testing if not needed
- Schedule heavy tests during off-peak hours

## Recovery Procedures

### Complete System Reset

```bash
# Stop all services
./scripts/stop_monitoring.sh

# Remove all Docker data
docker-compose down -v
docker system prune -a

# Recreate Python environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Restart services
./scripts/start_monitoring.sh
```

### Backup and Restore

**Backup Configuration**:
```bash
# Create backup
tar -czf monitor-backup-$(date +%Y%m%d).tar.gz config/ logs/ local/
```

**Restore Configuration**:
```bash
# Extract backup
tar -xzf monitor-backup-YYYYMMDD.tar.gz
```

### Emergency Monitoring

If the full system fails, basic monitoring:

```bash
# Simple ping monitoring
while true; do
  echo "$(date): LAN=$(ping -c1 192.168.1.1 | grep time= | cut -d= -f4) Internet=$(ping -c1 8.8.8.8 | grep time= | cut -d= -f4)"
  sleep 60
done
```

## Getting Help

### Log Collection for Support

```bash
# Create diagnostic bundle
mkdir -p debug/
cp config/*.yaml debug/
cp logs/*.log debug/
docker-compose logs > debug/docker-logs.txt
docker-compose ps > debug/docker-status.txt
python3 --version > debug/system-info.txt
docker --version >> debug/system-info.txt

# Create archive
tar -czf debug-$(date +%Y%m%d-%H%M).tar.gz debug/
```

### Common Questions

**Q: Why aren't work VPN metrics showing up?**
A: We can't monitor the VPN directly since it's on your work device. Instead, monitor company public endpoints and regional infrastructure.

**Q: Is it safe to leave running 24/7?**
A: Yes, the system is designed for continuous operation with automatic restarts and resource limits.

**Q: Can I monitor devices on different network segments?**
A: Yes, but you may need to configure routing or use SNMP for devices behind firewalls.

**Q: How do I add monitoring for new devices?**
A: Add IP addresses to `config/monitoring_config.yaml` and restart the monitoring agent.

### Performance Benchmarks

**Normal Resource Usage**:
- CPU: <5% average on Dell OptiPlex
- Memory: ~500MB for Docker stack
- Network: <1Mbps monitoring traffic
- Disk: ~100MB/day for logs and metrics

If usage exceeds these levels, check for configuration issues or system problems.