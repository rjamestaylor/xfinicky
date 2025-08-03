#!/usr/bin/env python3
"""
Home Network Monitor - Main monitoring script
Monitors network performance and sends metrics to local Prometheus and AWS CloudWatch
"""

import time
import logging
import yaml
import boto3
import ping3
import json
import psutil
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/network_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class MetricData:
    """Container for metric data"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    dimensions: Optional[Dict[str, str]] = None

class NetworkMonitor:
    """Main network monitoring class"""
    
    def __init__(self, config_path: str = "config/monitoring_config.yaml"):
        self.config = self._load_config(config_path)
        self.aws_enabled = self._init_aws()
        self.metrics_cache = []
        self.last_alert_times = {}
        
        # Create logs directory if it doesn't exist
        Path("logs").mkdir(exist_ok=True)
        
        logger.info("Network Monitor initialized")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load monitoring configuration"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def _init_aws(self) -> bool:
        """Initialize AWS CloudWatch client"""
        try:
            self.cloudwatch = boto3.client(
                'cloudwatch',
                region_name=self.config['aws']['region']
            )
            # Test connection with a simple call
            self.cloudwatch.list_metrics(MaxRecords=1)
            logger.info("AWS CloudWatch client initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"AWS CloudWatch initialization failed: {e}")
            logger.warning("Continuing with local monitoring only")
            return False
    
    def ping_target(self, target: str, timeout: int = 5) -> Optional[float]:
        """Ping a target and return latency in milliseconds"""
        try:
            result = ping3.ping(target, timeout=timeout)
            if result is not None:
                return result * 1000  # Convert to milliseconds
            return None
        except Exception as e:
            logger.debug(f"Ping failed for {target}: {e}")
            return None
    
    def dns_lookup_time(self, hostname: str) -> Optional[float]:
        """Measure DNS lookup time"""
        import socket
        import time
        
        try:
            start_time = time.time()
            socket.gethostbyname(hostname)
            end_time = time.time()
            return (end_time - start_time) * 1000  # Convert to milliseconds
        except Exception as e:
            logger.debug(f"DNS lookup failed for {hostname}: {e}")
            return None
    
    def get_system_metrics(self) -> Dict[str, float]:
        """Get system performance metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'memory_available_mb': memory.available / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {}
    
    def collect_network_metrics(self) -> List[MetricData]:
        """Collect all network metrics"""
        metrics = []
        timestamp = datetime.now(timezone.utc)
        
        # Ping all targets
        all_targets = {
            **self.config['targets']['internal'],
            **self.config['targets']['internet'],
            **self.config['targets']['work_proxy']
        }
        
        for target_name, target_address in all_targets.items():
            latency = self.ping_target(target_address)
            if latency is not None:
                metrics.append(MetricData(
                    name=f"network_latency_{target_name}",
                    value=latency,
                    unit="Milliseconds",
                    timestamp=timestamp,
                    dimensions={"target": target_address, "target_name": target_name}
                ))
                
                # Also track availability (1 = available, 0 = unavailable)
                metrics.append(MetricData(
                    name=f"network_availability_{target_name}",
                    value=1.0,
                    unit="Count",
                    timestamp=timestamp,
                    dimensions={"target": target_address, "target_name": target_name}
                ))
            else:
                # Target is unavailable
                metrics.append(MetricData(
                    name=f"network_availability_{target_name}",
                    value=0.0,
                    unit="Count",
                    timestamp=timestamp,
                    dimensions={"target": target_address, "target_name": target_name}
                ))
        
        # DNS lookup times
        test_domains = ["google.com", "cloudflare.com", "amazon.com"]
        for domain in test_domains:
            dns_time = self.dns_lookup_time(domain)
            if dns_time is not None:
                metrics.append(MetricData(
                    name=f"dns_lookup_time",
                    value=dns_time,
                    unit="Milliseconds",
                    timestamp=timestamp,
                    dimensions={"domain": domain}
                ))
        
        # System metrics
        sys_metrics = self.get_system_metrics()
        for metric_name, value in sys_metrics.items():
            metrics.append(MetricData(
                name=f"system_{metric_name}",
                value=value,
                unit="Percent" if "percent" in metric_name else "Count",
                timestamp=timestamp
            ))
        
        logger.debug(f"Collected {len(metrics)} metrics")
        return metrics
    
    def send_to_cloudwatch(self, metrics: List[MetricData]) -> bool:
        """Send metrics to AWS CloudWatch"""
        if not self.aws_enabled:
            return False
        
        try:
            # CloudWatch accepts max 20 metrics per call
            chunk_size = 20
            for i in range(0, len(metrics), chunk_size):
                chunk = metrics[i:i + chunk_size]
                
                metric_data = []
                for metric in chunk:
                    data_point = {
                        'MetricName': metric.name,
                        'Value': metric.value,
                        'Unit': metric.unit,
                        'Timestamp': metric.timestamp
                    }
                    
                    if metric.dimensions:
                        data_point['Dimensions'] = [
                            {'Name': k, 'Value': v} 
                            for k, v in metric.dimensions.items()
                        ]
                    
                    metric_data.append(data_point)
                
                # Send to CloudWatch
                self.cloudwatch.put_metric_data(
                    Namespace=self.config['aws']['namespace'],
                    MetricData=metric_data
                )
            
            logger.debug(f"Sent {len(metrics)} metrics to CloudWatch")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send metrics to CloudWatch: {e}")
            return False
    
    def check_alerts(self, metrics: List[MetricData]):
        """Check metrics against thresholds and send alerts"""
        if not self.config['alerts']['enabled']:
            return
        
        current_time = datetime.now()
        cooldown_seconds = self.config['alerts']['cooldown_minutes'] * 60
        
        for metric in metrics:
            alert_sent = False
            
            # Check latency thresholds
            if metric.name.startswith('network_latency_'):
                target_type = self._get_target_type(metric.name)
                thresholds = self.config['thresholds']['latency']
                
                critical_threshold = thresholds.get(f'{target_type}_critical', 1000)
                warning_threshold = thresholds.get(f'{target_type}_warning', 500)
                
                if metric.value > critical_threshold:
                    alert_sent = self._send_alert(
                        f"CRITICAL: High latency to {metric.name}: {metric.value:.1f}ms",
                        "critical",
                        metric.name,
                        current_time,
                        cooldown_seconds
                    )
                elif metric.value > warning_threshold:
                    alert_sent = self._send_alert(
                        f"WARNING: Elevated latency to {metric.name}: {metric.value:.1f}ms",
                        "warning", 
                        metric.name,
                        current_time,
                        cooldown_seconds
                    )
            
            # Check availability
            elif metric.name.startswith('network_availability_') and metric.value == 0:
                alert_sent = self._send_alert(
                    f"CRITICAL: Target unreachable: {metric.name}",
                    "critical",
                    metric.name,
                    current_time,
                    cooldown_seconds
                )
    
    def _get_target_type(self, metric_name: str) -> str:
        """Determine target type from metric name"""
        if any(target in metric_name for target in self.config['targets']['internal'].keys()):
            return 'lan'
        elif any(target in metric_name for target in self.config['targets']['work_proxy'].keys()):
            return 'work'
        else:
            return 'internet'
    
    def _send_alert(self, message: str, severity: str, metric_key: str, 
                   current_time: datetime, cooldown_seconds: int) -> bool:
        """Send an alert if cooldown period has passed"""
        
        # Check cooldown
        last_alert = self.last_alert_times.get(metric_key)
        if last_alert and (current_time - last_alert).total_seconds() < cooldown_seconds:
            return False
        
        # Update last alert time
        self.last_alert_times[metric_key] = current_time
        
        # Send alert via configured channels
        alert_sent = False
        channels = self.config['alerts']['channels']
        
        try:
            # Email alerts
            if channels.get('email', {}).get('enabled'):
                self._send_email_alert(message, severity)
                alert_sent = True
            
            # SMS alerts  
            if channels.get('sms', {}).get('enabled'):
                self._send_sms_alert(message, severity)
                alert_sent = True
            
            # Slack alerts
            if channels.get('slack', {}).get('enabled'):
                self._send_slack_alert(message, severity)
                alert_sent = True
            
            # Webhook alerts
            if channels.get('webhook', {}).get('enabled'):
                self._send_webhook_alert(message, severity, metric_key)
                alert_sent = True
            
            if alert_sent:
                logger.info(f"Alert sent: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
        
        return alert_sent
    
    def _send_email_alert(self, message: str, severity: str):
        """Send email alert via AWS SES"""
        if not self.aws_enabled:
            return
        
        try:
            ses = boto3.client('ses', region_name=self.config['aws']['region'])
            email_config = self.config['alerts']['channels']['email']
            
            ses.send_email(
                Source='noreply@yourdomain.com',  # You'll need to verify this in SES
                Destination={'ToAddresses': [email_config['address']]},
                Message={
                    'Subject': {'Data': f'Network Alert - {severity.upper()}'},
                    'Body': {'Text': {'Data': message}}
                }
            )
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
    
    def _send_sms_alert(self, message: str, severity: str):
        """Send SMS alert via AWS SNS"""
        if not self.aws_enabled:
            return
        
        try:
            sns = boto3.client('sns', region_name=self.config['aws']['region'])
            sms_config = self.config['alerts']['channels']['sms']
            
            sns.publish(
                PhoneNumber=sms_config['phone_number'],
                Message=f"Network Alert [{severity.upper()}]: {message}"
            )
        except Exception as e:
            logger.error(f"SMS alert failed: {e}")
    
    def _send_slack_alert(self, message: str, severity: str):
        """Send Slack alert via webhook"""
        import requests
        
        try:
            slack_config = self.config['alerts']['channels']['slack']
            webhook_url = slack_config['webhook_url']
            
            color = "#ff0000" if severity == "critical" else "#ffaa00"
            
            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"Network Alert - {severity.upper()}",
                    "text": message,
                    "ts": int(datetime.now().timestamp())
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
    
    def _send_webhook_alert(self, message: str, severity: str, metric_key: str):
        """Send generic webhook alert"""
        import requests
        
        try:
            webhook_config = self.config['alerts']['channels']['webhook']
            webhook_url = webhook_config['url']
            
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": severity,
                "message": message,
                "metric": metric_key,
                "source": "home_network_monitor"
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
    
    def export_prometheus_metrics(self, metrics: List[MetricData]) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        for metric in metrics:
            # Convert metric name to Prometheus format
            prom_name = metric.name.replace('-', '_').lower()
            
            # Add dimensions as labels
            labels = ""
            if metric.dimensions:
                label_pairs = [f'{k}="{v}"' for k, v in metric.dimensions.items()]
                labels = "{" + ",".join(label_pairs) + "}"
            
            # Format: metric_name{labels} value timestamp
            timestamp_ms = int(metric.timestamp.timestamp() * 1000)
            lines.append(f"{prom_name}{labels} {metric.value} {timestamp_ms}")
        
        return "\n".join(lines)
    
    def run_monitoring_cycle(self):
        """Run one complete monitoring cycle"""
        try:
            logger.debug("Starting monitoring cycle")
            
            # Collect metrics
            metrics = self.collect_network_metrics()
            
            # Store in cache for Prometheus scraping
            self.metrics_cache = metrics
            
            # Send to CloudWatch
            if self.aws_enabled:
                self.send_to_cloudwatch(metrics)
            
            # Check for alerts
            self.check_alerts(metrics)
            
            logger.debug("Monitoring cycle completed successfully")
            
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")

class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus metrics endpoint"""
    
    def __init__(self, monitor_instance, *args, **kwargs):
        self.monitor = monitor_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests for metrics"""
        if self.path == '/metrics':
            try:
                # Export current metrics in Prometheus format
                metrics_text = self.monitor.export_prometheus_metrics(self.monitor.metrics_cache)
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(metrics_text.encode('utf-8'))
                
            except Exception as e:
                logger.error(f"Metrics endpoint error: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.debug(f"HTTP: {format % args}")

def run_metrics_server(monitor: NetworkMonitor, port: int = 8000):
    """Run the Prometheus metrics HTTP server"""
    def handler(*args, **kwargs):
        return MetricsHandler(monitor, *args, **kwargs)
    
    try:
        server = HTTPServer(('0.0.0.0', port), handler)
        logger.info(f"Metrics server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Metrics server failed: {e}")

def main():
    """Main entry point"""
    logger.info("Starting Home Network Monitor")
    
    try:
        # Initialize monitor
        monitor = NetworkMonitor()
        
        # Start metrics server in a separate thread
        metrics_thread = threading.Thread(
            target=run_metrics_server, 
            args=(monitor, 8000),
            daemon=True
        )
        metrics_thread.start()
        
        # Main monitoring loop
        while True:
            monitor.run_monitoring_cycle()
            
            # Wait for next cycle
            interval = monitor.config['intervals']['ping_check']
            time.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitor crashed: {e}")
        raise

if __name__ == "__main__":
    main()