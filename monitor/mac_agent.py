#!/usr/bin/env python3
"""
Mac Studio Monitoring Agent
Collects WiFi and local network metrics from macOS and reports to Dell monitoring hub
"""

import subprocess
import json
import time
import requests
import logging
import yaml
import psutil
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MacNetworkAgent:
    """Mac-specific network monitoring agent"""
    
    def __init__(self, config_path: str = "../config/monitoring_config.yaml"):
        self.config = self._load_config(config_path)
        self.wifi_interface = self.config['local']['mac_agent']['wifi_interface']
        self.report_url = self.config['local']['mac_agent']['report_url']
        logger.info("Mac Network Agent initialized")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load monitoring configuration"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            # Return minimal config for standalone operation
            return {
                'local': {
                    'mac_agent': {
                        'wifi_interface': 'en0',
                        'report_url': 'http://192.168.4.255:8000/metrics'
                    }
                },
                'targets': {
                    'internal': {
                        'lan_gateway': '192.168.4.1'
                    }
                }
            }
    
    def get_wifi_info(self) -> Dict[str, Any]:
        """Get WiFi connection information using airport utility"""
        wifi_info = {}
        
        try:
            # Get basic WiFi info using networksetup
            cmd = ['networksetup', '-getairportnetwork', self.wifi_interface]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if "Current Wi-Fi Network:" in output:
                    ssid = output.split("Current Wi-Fi Network: ")[1]
                    wifi_info['ssid'] = ssid
                else:
                    wifi_info['ssid'] = 'Not Connected'
            
            # Get detailed WiFi info using airport command-line tool
            airport_path = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
            if Path(airport_path).exists():
                cmd = [airport_path, '-I']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if 'agrCtlRSSI:' in line:
                            rssi = int(line.split(':')[1].strip())
                            wifi_info['rssi'] = rssi
                        elif 'agrCtlNoise:' in line:
                            noise = int(line.split(':')[1].strip())
                            wifi_info['noise'] = noise
                        elif 'state:' in line:
                            state = line.split(':')[1].strip()
                            wifi_info['state'] = state
                        elif 'channel:' in line:
                            channel_info = line.split(':')[1].strip()
                            wifi_info['channel'] = channel_info
                        elif 'CC:' in line:
                            country_code = line.split(':')[1].strip()
                            wifi_info['country_code'] = country_code
                        elif 'maxRate:' in line:
                            max_rate = line.split(':')[1].strip()
                            wifi_info['max_rate'] = max_rate
                        elif 'lastTxRate:' in line:
                            tx_rate = line.split(':')[1].strip()
                            wifi_info['tx_rate'] = tx_rate
            
            # Calculate signal quality percentage
            if 'rssi' in wifi_info and 'noise' in wifi_info:
                snr = wifi_info['rssi'] - wifi_info['noise']
                wifi_info['snr'] = snr
                
                # Convert RSSI to quality percentage (rough approximation)
                if wifi_info['rssi'] >= -30:
                    quality = 100
                elif wifi_info['rssi'] >= -67:
                    quality = 100 - ((wifi_info['rssi'] + 30) * -1.5)
                elif wifi_info['rssi'] >= -70:
                    quality = 60 - ((wifi_info['rssi'] + 67) * -10)
                elif wifi_info['rssi'] >= -80:
                    quality = 35 - ((wifi_info['rssi'] + 70) * -2.5)
                elif wifi_info['rssi'] >= -90:
                    quality = 10 - ((wifi_info['rssi'] + 80) * -2.5)
                else:
                    quality = 0
                
                wifi_info['quality_percent'] = max(0, min(100, quality))
        
        except Exception as e:
            logger.debug(f"Failed to get WiFi info: {e}")
        
        return wifi_info
    
    def get_network_interfaces(self) -> Dict[str, Any]:
        """Get network interface statistics"""
        interface_stats = {}
        
        try:
            # Get interface statistics using psutil
            net_io = psutil.net_io_counters(pernic=True)
            
            for interface, stats in net_io.items():
                if interface.startswith(('en', 'wi')):  # Ethernet and WiFi interfaces
                    interface_stats[interface] = {
                        'bytes_sent': stats.bytes_sent,
                        'bytes_recv': stats.bytes_recv,
                        'packets_sent': stats.packets_sent,
                        'packets_recv': stats.packets_recv,
                        'errin': stats.errin,
                        'errout': stats.errout,
                        'dropin': stats.dropin,
                        'dropout': stats.dropout
                    }
            
            # Get interface addresses
            net_addrs = psutil.net_if_addrs()
            for interface, addrs in net_addrs.items():
                if interface in interface_stats:
                    for addr in addrs:
                        if addr.family.name == 'AF_INET':  # IPv4
                            interface_stats[interface]['ipv4'] = addr.address
                        elif addr.family.name == 'AF_INET6':  # IPv6
                            interface_stats[interface]['ipv6'] = addr.address
        
        except Exception as e:
            logger.debug(f"Failed to get interface stats: {e}")
        
        return interface_stats
    
    def ping_local_targets(self) -> Dict[str, Optional[float]]:
        """Ping local network targets with improved accuracy"""
        results = {}
        targets = self.config.get('targets', {}).get('internal', {})
        
        for name, target in targets.items():
            try:
                # Increase to 6 pings to get more reliable data
                cmd = ['ping', '-c', '6', '-W', '3000', target]  # 6 pings, 3 second timeout
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    # Parse individual ping times to handle them separately
                    output = result.stdout
                    
                    # Extract individual ping times from lines like "64 bytes from 192.168.4.1: icmp_seq=1 ttl=64 time=4.123 ms"
                    ping_times = []
                    for line in output.splitlines():
                        time_match = re.search(r'time=([\d.]+) ms', line)
                        if time_match:
                            ping_times.append(float(time_match.group(1)))
                    
                    if len(ping_times) >= 2:  # Need at least 2 pings to discard first one
                        # Discard the first ping to avoid ARP resolution penalty
                        ping_times = ping_times[1:]
                        
                        # Calculate average of remaining pings
                        avg_time = sum(ping_times) / len(ping_times)
                        results[name] = avg_time
                        logger.debug(f"Ping to {name} ({target}): first={ping_times[0]:.1f}ms, avg_without_first={avg_time:.1f}ms")
                    elif len(ping_times) == 1:
                        # Only got one ping result, use it but note in logs
                        results[name] = ping_times[0]
                        logger.debug(f"Ping to {name} ({target}): only one ping result: {ping_times[0]:.1f}ms")
                    else:
                        results[name] = None
                        logger.debug(f"Ping to {name} ({target}): no valid ping times extracted")
                else:
                    results[name] = None
                    logger.debug(f"Ping to {name} ({target}) failed with return code {result.returncode}")
            
            except Exception as e:
                logger.debug(f"Ping failed for {name} ({target}): {e}")
                results[name] = None
        
        return results
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get Mac system metrics"""
        metrics = {}
        
        try:
            # CPU and memory
            metrics['cpu_percent'] = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            metrics['memory_percent'] = memory.percent
            metrics['memory_available_gb'] = memory.available / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            metrics['disk_percent'] = disk.percent
            metrics['disk_free_gb'] = disk.free / (1024**3)
            
            # Network connections
            connections = psutil.net_connections()
            metrics['network_connections'] = len([c for c in connections if c.status == 'ESTABLISHED'])
            
            # Load average (macOS specific)
            load_avg = psutil.getloadavg()
            metrics['load_avg_1min'] = load_avg[0]
            metrics['load_avg_5min'] = load_avg[1]
            metrics['load_avg_15min'] = load_avg[2]
            
        except Exception as e:
            logger.debug(f"Failed to get system metrics: {e}")
        
        return metrics
    
    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all metrics from the Mac"""
        timestamp = datetime.now(timezone.utc)
        
        metrics = {
            'timestamp': timestamp.isoformat(),
            'hostname': psutil.boot_time(),  # Use boot time as unique identifier
            'wifi': self.get_wifi_info(),
            'network_interfaces': self.get_network_interfaces(),
            'ping_results': self.ping_local_targets(),
            'system': self.get_system_metrics()
        }
        
        return metrics
    
    def report_to_hub(self, metrics: Dict[str, Any]) -> bool:
        """Send metrics to the Dell monitoring hub"""
        try:
            # Convert to format expected by the hub
            response = requests.post(
                f"{self.report_url}/mac_metrics",
                json=metrics,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.debug("Metrics reported successfully")
                return True
            else:
                logger.warning(f"Failed to report metrics: HTTP {response.status_code}")
                return False
        
        except requests.exceptions.RequestException as e:
            logger.debug(f"Failed to report metrics: {e}")
            return False
    
    def run_monitoring_cycle(self):
        """Run one monitoring cycle"""
        try:
            logger.debug("Starting Mac monitoring cycle")
            
            # Collect metrics
            metrics = self.collect_all_metrics()
            
            # Report to hub
            self.report_to_hub(metrics)
            
            # Also log key metrics locally
            wifi = metrics.get('wifi', {})
            if wifi.get('ssid'):
                logger.info(f"WiFi: {wifi.get('ssid')} | "
                          f"RSSI: {wifi.get('rssi', 'N/A')} dBm | "
                          f"Quality: {wifi.get('quality_percent', 'N/A')}%")
            
            ping_results = metrics.get('ping_results', {})
            for target, latency in ping_results.items():
                if latency is not None:
                    logger.debug(f"Ping {target}: {latency:.1f}ms")
            
            logger.debug("Mac monitoring cycle completed")
            
        except Exception as e:
            logger.error(f"Mac monitoring cycle failed: {e}")

def main():
    """Main entry point for Mac agent"""
    logger.info("Starting Mac Network Agent")
    
    try:
        agent = MacNetworkAgent()
        
        # Get monitoring interval from config
        interval = 300  # Default 5 minutes
        try:
            interval = agent.config['intervals']['mac_agent_report']
        except (KeyError, TypeError):
            pass
        
        logger.info(f"Monitoring interval: {interval} seconds")
        
        while True:
            agent.run_monitoring_cycle()
            time.sleep(interval)
    
    except KeyboardInterrupt:
        logger.info("Mac agent stopped by user")
    except Exception as e:
        logger.error(f"Mac agent crashed: {e}")
        raise

if __name__ == "__main__":
    main()