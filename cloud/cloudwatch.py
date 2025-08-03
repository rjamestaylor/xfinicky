#!/usr/bin/env python3
"""
CloudWatch Setup Script
Creates dashboards, alarms, and SNS topics for home network monitoring
"""

import boto3
import json
import yaml
import logging
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CloudWatchSetup:
    """Setup CloudWatch resources for home network monitoring"""
    
    def __init__(self, config_path: str = "../config/monitoring_config.yaml"):
        self.config = self._load_config(config_path)
        self.region = self.config['aws']['region']
        self.namespace = self.config['aws']['namespace']
        
        # Initialize AWS clients
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        self.sns = boto3.client('sns', region_name=self.region)
        
        logger.info(f"CloudWatch setup initialized for region: {self.region}")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load monitoring configuration"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def create_sns_topic(self) -> str:
        """Create SNS topic for alerts"""
        topic_name = "home-network-alerts"
        
        try:
            response = self.sns.create_topic(Name=topic_name)
            topic_arn = response['TopicArn']
            logger.info(f"Created SNS topic: {topic_arn}")
            
            # Set topic attributes
            self.sns.set_topic_attributes(
                TopicArn=topic_arn,
                AttributeName='DisplayName',
                AttributeValue='Home Network Alerts'
            )
            
            return topic_arn
            
        except Exception as e:
            logger.error(f"Failed to create SNS topic: {e}")
            raise
    
    def create_dashboard(self) -> str:
        """Create CloudWatch dashboard"""
        dashboard_name = "HomeNetworkMonitoring"
        
        # Dashboard configuration
        dashboard_body = {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0, "y": 0, "width": 12, "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "network_latency_lan_gateway"],
                            [self.namespace, "network_latency_cloudflare_primary"],
                            [self.namespace, "network_latency_google_primary"]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.region,
                        "title": "Network Latency",
                        "period": 300,
                        "yAxis": {
                            "left": {
                                "min": 0,
                                "max": 200
                            }
                        }
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 0, "width": 12, "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "network_availability_lan_gateway"],
                            [self.namespace, "network_availability_cloudflare_primary"],
                            [self.namespace, "network_availability_google_primary"]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.region,
                        "title": "Network Availability",
                        "period": 300,
                        "yAxis": {
                            "left": {
                                "min": 0,
                                "max": 1
                            }
                        }
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 6, "width": 12, "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "dns_lookup_time", "domain", "google.com"],
                            [self.namespace, "dns_lookup_time", "domain", "cloudflare.com"],
                            [self.namespace, "dns_lookup_time", "domain", "amazon.com"]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.region,
                        "title": "DNS Lookup Times",
                        "period": 300
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 6, "width": 12, "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "system_cpu_percent"],
                            [self.namespace, "system_memory_percent"],
                            [self.namespace, "system_disk_percent"]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.region,
                        "title": "System Metrics",
                        "period": 300,
                        "yAxis": {
                            "left": {
                                "min": 0,
                                "max": 100
                            }
                        }
                    }
                }
            ]
        }
        
        try:
            self.cloudwatch.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            dashboard_url = f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard_name}"
            logger.info(f"Created dashboard: {dashboard_url}")
            return dashboard_url
            
        except Exception as e:
            logger.error(f"Failed to create dashboard: {e}")
            raise
    
    def create_alarms(self, topic_arn: str) -> List[str]:
        """Create CloudWatch alarms"""
        alarms = []
        
        # High latency alarms
        latency_alarms = [
            {
                'name': 'HomeNetwork-HighLatency-LAN',
                'metric': 'network_latency_lan_gateway',
                'threshold': self.config['thresholds']['latency']['lan_critical'],
                'description': 'High latency to LAN gateway'
            },
            {
                'name': 'HomeNetwork-HighLatency-Internet',
                'metric': 'network_latency_cloudflare_primary', 
                'threshold': self.config['thresholds']['latency']['internet_critical'],
                'description': 'High latency to internet'
            }
        ]
        
        for alarm_config in latency_alarms:
            try:
                self.cloudwatch.put_metric_alarm(
                    AlarmName=alarm_config['name'],
                    ComparisonOperator='GreaterThanThreshold',
                    EvaluationPeriods=2,
                    MetricName=alarm_config['metric'],
                    Namespace=self.namespace,
                    Period=300,
                    Statistic='Average',
                    Threshold=alarm_config['threshold'],
                    ActionsEnabled=True,
                    AlarmActions=[topic_arn],
                    AlarmDescription=alarm_config['description'],
                    Unit='Milliseconds'
                )
                alarms.append(alarm_config['name'])
                logger.info(f"Created alarm: {alarm_config['name']}")
                
            except Exception as e:
                logger.error(f"Failed to create alarm {alarm_config['name']}: {e}")
        
        return alarms
    
    def subscribe_to_alerts(self, topic_arn: str):
        """Subscribe to SNS alerts based on configuration"""
        alert_config = self.config.get('alerts', {})
        channels = alert_config.get('channels', {})
        
        # Email subscription
        if channels.get('email', {}).get('enabled'):
            email = channels['email']['address']
            try:
                self.sns.subscribe(
                    TopicArn=topic_arn,
                    Protocol='email',
                    Endpoint=email
                )
                logger.info(f"Subscribed email {email} to alerts")
                logger.info("Please check your email and confirm the subscription")
            except Exception as e:
                logger.error(f"Failed to subscribe email: {e}")
        
        # SMS subscription
        if channels.get('sms', {}).get('enabled'):
            phone = channels['sms']['phone_number']
            try:
                self.sns.subscribe(
                    TopicArn=topic_arn,
                    Protocol='sms',
                    Endpoint=phone
                )
                logger.info(f"Subscribed SMS {phone} to alerts")
            except Exception as e:
                logger.error(f"Failed to subscribe SMS: {e}")
    
    def create_cost_alarm(self, topic_arn: str):
        """Create billing alarm to monitor AWS costs"""
        try:
            # Note: Billing metrics are only available in us-east-1
            billing_client = boto3.client('cloudwatch', region_name='us-east-1')
            
            billing_client.put_metric_alarm(
                AlarmName='HomeNetwork-AWS-CostAlarm',
                ComparisonOperator='GreaterThanThreshold',
                EvaluationPeriods=1,
                MetricName='EstimatedCharges',
                Namespace='AWS/Billing',
                Period=86400,  # 24 hours
                Statistic='Maximum',
                Threshold=10.0,  # $10 threshold
                ActionsEnabled=True,
                AlarmActions=[topic_arn],
                AlarmDescription='AWS costs exceeded $10',
                Dimensions=[
                    {
                        'Name': 'Currency',
                        'Value': 'USD'
                    }
                ],
                Unit='None'
            )
            logger.info("Created AWS cost alarm ($10 threshold)")
            
        except Exception as e:
            logger.warning(f"Failed to create cost alarm: {e}")
            logger.warning("Note: Billing alarms require special permissions and us-east-1 region")
    
    def setup_all(self):
        """Setup all CloudWatch resources"""
        logger.info("Starting CloudWatch setup...")
        
        try:
            # Create SNS topic
            topic_arn = self.create_sns_topic()
            
            # Create dashboard
            dashboard_url = self.create_dashboard()
            
            # Create alarms
            alarms = self.create_alarms(topic_arn)
            
            # Subscribe to alerts
            self.subscribe_to_alerts(topic_arn)
            
            # Create cost monitoring alarm
            self.create_cost_alarm(topic_arn)
            
            # Summary
            logger.info("\n" + "="*60)
            logger.info("CloudWatch Setup Complete!")
            logger.info("="*60)
            logger.info(f"Dashboard URL: {dashboard_url}")
            logger.info(f"SNS Topic ARN: {topic_arn}")
            logger.info(f"Created {len(alarms)} alarms:")
            for alarm in alarms:
                logger.info(f"  - {alarm}")
            
            logger.info("\nNext steps:")
            logger.info("1. Confirm email subscription if you subscribed to email alerts")
            logger.info("2. Update your monitoring_config.yaml with the SNS topic ARN")
            logger.info("3. Start your network monitoring script")
            logger.info("4. Check the dashboard in about 10 minutes for initial data")
            
            return {
                'topic_arn': topic_arn,
                'dashboard_url': dashboard_url,
                'alarms': alarms
            }
            
        except Exception as e:
            logger.error(f"CloudWatch setup failed: {e}")
            raise
    
    def cleanup_all(self):
        """Remove all created CloudWatch resources (for testing/cleanup)"""
        logger.info("Cleaning up CloudWatch resources...")
        
        try:
            # Delete dashboard
            try:
                self.cloudwatch.delete_dashboards(DashboardNames=['HomeNetworkMonitoring'])
                logger.info("Deleted dashboard")
            except Exception as e:
                logger.warning(f"Failed to delete dashboard: {e}")
            
            # Delete alarms
            alarm_names = [
                'HomeNetwork-HighLatency-LAN',
                'HomeNetwork-HighLatency-Internet', 
                'HomeNetwork-Unavailable-LAN',
                'HomeNetwork-Unavailable-Internet',
                'HomeNetwork-AWS-CostAlarm'
            ]
            
            for alarm_name in alarm_names:
                try:
                    self.cloudwatch.delete_alarms(AlarmNames=[alarm_name])
                    logger.info(f"Deleted alarm: {alarm_name}")
                except Exception as e:
                    logger.warning(f"Failed to delete alarm {alarm_name}: {e}")
            
            # List and optionally delete SNS topics
            try:
                topics = self.sns.list_topics()
                for topic in topics['Topics']:
                    if 'home-network-alerts' in topic['TopicArn']:
                        logger.info(f"Found SNS topic: {topic['TopicArn']}")
                        logger.info("Note: SNS topic not auto-deleted. Delete manually if needed.")
            except Exception as e:
                logger.warning(f"Failed to list SNS topics: {e}")
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup CloudWatch for home network monitoring')
    parser.add_argument('--cleanup', action='store_true', help='Remove all CloudWatch resources')
    parser.add_argument('--config', default='../config/monitoring_config.yaml', help='Config file path')
    
    args = parser.parse_args()
    
    try:
        setup = CloudWatchSetup(args.config)
        
        if args.cleanup:
            setup.cleanup_all()
        else:
            setup.setup_all()
    
    except Exception as e:
        logger.error(f"Script failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()_config['name']}")
                
            except Exception as e:
                logger.error(f"Failed to create alarm {alarm_config['name']}: {e}")
        
        # Availability alarms
        availability_alarms = [
            {
                'name': 'HomeNetwork-Unavailable-LAN',
                'metric': 'network_availability_lan_gateway',
                'threshold': 0.5,
                'description': 'LAN gateway unavailable'
            },
            {
                'name': 'HomeNetwork-Unavailable-Internet',
                'metric': 'network_availability_cloudflare_primary',
                'threshold': 0.5, 
                'description': 'Internet connectivity lost'
            }
        ]
        
        for alarm_config in availability_alarms:
            try:
                self.cloudwatch.put_metric_alarm(
                    AlarmName=alarm_config['name'],
                    ComparisonOperator='LessThanThreshold',
                    EvaluationPeriods=1,
                    MetricName=alarm_config['metric'],
                    Namespace=self.namespace,
                    Period=300,
                    Statistic='Average',
                    Threshold=alarm_config['threshold'],
                    ActionsEnabled=True,
                    AlarmActions=[topic_arn],
                    AlarmDescription=alarm_config['description'],
                    Unit='Count'
                )
                alarms.append(alarm_config['name'])
                logger.info(f"Created alarm: {alarm