# XFinicky AWS Infrastructure Deployment Guide

This guide covers deploying the AWS infrastructure for XFinicky monitoring using Infrastructure as Code (IaC).

## Overview

The IaC deployment creates:
- **IAM User**: `xfinicky-monitor-dell` with least-privilege permissions
- **IAM Policy**: Limited to CloudWatch metrics and SNS publishing
- **SNS Topic**: For network alerts via email/SMS
- **CloudWatch Dashboard**: Network monitoring visualization
- **CloudWatch Alarms**: High latency and connectivity alerts
- **Cost Monitoring**: Billing alarm to prevent surprise charges

## Prerequisites

### Required
- **AWS CLI** installed and configured with admin permissions
- **AWS Account** with billing enabled
- **Either** CloudFormation (built-in) **OR** Terraform installed

### Recommended Setup
```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure with admin credentials (temporarily)
aws configure
```

## Deployment Options

### Option 1: CloudFormation (Recommended)

```bash
# Deploy with email alerts
./scripts/deploy_aws_infrastructure.sh \
    --method cloudformation \
    --email your-email@gmail.com \
    --phone +1234567890 \
    --cost-threshold 10

# Deploy minimal (no alerts)
./scripts/deploy_aws_infrastructure.sh \
    --method cloudformation
```

### Option 2: Terraform

```bash
# Install Terraform first
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Deploy with Terraform
./scripts/deploy_aws_infrastructure.sh \
    --method terraform \
    --region us-west-2 \
    --email alerts@yourcompany.com
```

## Configuration Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--method` | Yes | - | `cloudformation` or `terraform` |
| `--region` | No | `us-east-1` | AWS region for deployment |
| `--email` | No | - | Email for alert notifications |
| `--phone` | No | - | Phone number for SMS alerts (format: +1234567890) |
| `--cost-threshold` | No | `10` | Monthly cost alarm threshold in USD |

## Deployment Process

### 1. Pre-deployment Validation
```bash
# Verify AWS access
aws sts get-caller-identity

# Check region
aws configure get region

# Validate template (CloudFormation only)
aws cloudformation validate-template \
    --template-body file://cloud/cloudformation/xfinicky-iam.yaml
```

### 2. Run Deployment
```bash
# Example with full configuration
./scripts/deploy_aws_infrastructure.sh \
    --method cloudformation \
    --region us-east-1 \
    --email network-alerts@yourdomain.com \
    --phone +15551234567 \
    --cost-threshold 15
```

### 3. Save Outputs
**CRITICAL**: The Secret Access Key is only shown once. Save it immediately:

```bash
# CloudFormation - get secret key
aws cloudformation describe-stacks \
    --stack-name xfinicky-monitoring \
    --query 'Stacks[0].Outputs[?OutputKey==`SecretAccessKey`].OutputValue' \
    --output text

# Terraform - get secret key
cd cloud/terraform
terraform output -raw secret_access_key
```

## Dell Configuration

### 1. Transfer Configuration Script
```bash
# Copy to Dell (via USB, network, etc.)
scp scripts/configure_dell_aws.sh user@dell-ip:~/
```

### 2. Run on Dell
```bash
# On Dell Windows (Git Bash)
./configure_dell_aws.sh

# Enter credentials when prompted:
# Access Key ID: AKIA...
# Secret Access Key: [from deployment output]
```

### 3. Test Dell Configuration
```bash
# Test AWS connection
aws sts get-caller-identity --profile xfinicky

# Test CloudWatch access
aws cloudwatch list-metrics --namespace HomeNetwork --profile xfinicky
```

## Resource Details

### IAM Policy Permissions
```json
{
  "CloudWatchMetrics": "PutMetricData to HomeNetwork namespace only",
  "SNSPublish": "Publish to home-network-alerts topic only", 
  "CostMonitoring": "Read-only cost and usage data",
  "BasicAccess": "GetCallerIdentity for connectivity testing"
}
```

### Cost Breakdown
- **CloudWatch Metrics**: ~$0.30 per metric per month
- **CloudWatch Alarms**: ~$0.10 per alarm per month
- **SNS Notifications**: ~$0.50 per 1000 messages
- **Dashboard**: Free (up to 3 dashboards)
- **Total Estimated**: $2-5 per month

### Security Features
- ✅ **Least Privilege**: Only required permissions
- ✅ **Resource Restrictions**: Limited to specific namespace/topic
- ✅ **No Admin Access**: Cannot create/delete AWS resources
- ✅ **Auditable**: All actions logged in CloudTrail
- ✅ **Isolated**: Separate from personal AWS credentials

## Troubleshooting

### Common Issues

**Permission Denied**:
```bash
# Check IAM user exists
aws iam get-user --user-name xfinicky-monitor-dell

# Check policy attachment
aws iam list-attached-user-policies --user-name xfinicky-monitor-dell
```

**Cost Alarm Not Working**:
- Cost alarms only work in `us-east-1` region
- Billing must be enabled on AWS account
- Takes 24 hours for first data point

**SNS Subscription Not Confirmed**:
- Check email spam folder
- Resend confirmation:
```bash
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:123456789012:xfinicky-network-alerts \
    --protocol email \
    --notification-endpoint your-email@gmail.com
```

### Validation Commands

```bash
# Test full deployment
aws cloudformation describe-stacks --stack-name xfinicky-monitoring
aws sns list-topics | grep xfinicky
aws cloudwatch describe-alarms --alarm-names xfinicky-high-latency
aws iam get-user --user-name xfinicky-monitor-dell

# Test permissions
aws cloudwatch put-metric-data \
    --namespace HomeNetwork \
    --metric-data MetricName=test,Value=1 \
    --profile xfinicky
```

## Cleanup

### Remove All Resources
```bash
# CloudFormation
aws cloudformation delete-stack --stack-name xfinicky-monitoring

# Terraform
cd cloud/terraform
terraform destroy -var-file=terraform.tfvars
```

### Partial Cleanup (Keep User, Remove Alarms)
```bash
# Remove just the alarms
aws cloudwatch delete-alarms --alarm-names \
    xfinicky-high-latency \
    xfinicky-connectivity-loss \
    xfinicky-cost-alarm
```

## Multi-Account Deployment

To deploy across multiple AWS accounts:

### 1. Create Parameter File
```yaml
# environments/prod.yaml
project_name: xfinicky-prod
alert_email: ops@company.com
cost_threshold: 25

# environments/dev.yaml  
project_name: xfinicky-dev
alert_email: dev@company.com
cost_threshold: 5
```

### 2. Deploy to Each Account
```bash
# Production account
aws configure --profile prod-account
./scripts/deploy_aws_infrastructure.sh \
    --method cloudformation \
    --email ops@company.com

# Development account  
aws configure --profile dev-account
./scripts/deploy_aws_infrastructure.sh \
    --method cloudformation \
    --email dev@company.com \
    --cost-threshold 5
```

## Best Practices

### Security
- Use separate AWS accounts for production vs development
- Rotate access keys every 90 days
- Enable CloudTrail for audit logging
- Review IAM permissions quarterly

### Cost Management
- Set conservative cost thresholds initially
- Monitor actual usage vs estimates
- Use AWS Cost Explorer for detailed analysis
- Consider Reserved Instances for consistent usage

### Operational
- Tag all resources consistently
- Document any manual changes
- Test alert delivery monthly
- Keep IaC templates in version control

This IaC approach ensures your XFinicky monitoring infrastructure is:
- **Repeatable**: Deploy to multiple accounts identically
- **Auditable**: All changes tracked in version control
- **Secure**: Least-privilege access by design
- **Cost-Effective**: Built-in cost monitoring and limits