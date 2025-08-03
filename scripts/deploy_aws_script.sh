#!/bin/bash

# XFinicky AWS Infrastructure Deployment Script
# Deploys IAM user, policies, SNS topics, and CloudWatch resources

set -e

echo "================================================"
echo "XFinicky AWS Infrastructure Deployment"
echo "================================================"

# Configuration
STACK_NAME="xfinicky-monitoring"
PROJECT_NAME="xfinicky"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
DEPLOYMENT_METHOD=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --method)
            DEPLOYMENT_METHOD="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --email)
            ALERT_EMAIL="$2"
            shift 2
            ;;
        --phone)
            ALERT_PHONE="$2"
            shift 2
            ;;
        --cost-threshold)
            COST_THRESHOLD="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --method cloudformation|terraform  Deployment method (required)"
            echo "  --region AWS_REGION                AWS region (default: us-east-1)"
            echo "  --email EMAIL                      Alert email address (optional)"
            echo "  --phone PHONE                      Alert phone number (optional)"
            echo "  --cost-threshold AMOUNT            Cost alarm threshold in USD (default: 10)"
            echo "  --help                             Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --method cloudformation --email alerts@example.com"
            echo "  $0 --method terraform --region us-west-2 --phone +1234567890"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$DEPLOYMENT_METHOD" ]]; then
    echo "ERROR: Deployment method is required. Use --method cloudformation or --method terraform"
    exit 1
fi

if [[ "$DEPLOYMENT_METHOD" != "cloudformation" && "$DEPLOYMENT_METHOD" != "terraform" ]]; then
    echo "ERROR: Invalid deployment method. Use 'cloudformation' or 'terraform'"
    exit 1
fi

# Set defaults
ALERT_EMAIL="${ALERT_EMAIL:-}"
ALERT_PHONE="${ALERT_PHONE:-}"
COST_THRESHOLD="${COST_THRESHOLD:-10}"

echo "Configuration:"
echo "  Deployment Method: $DEPLOYMENT_METHOD"
echo "  AWS Region: $REGION"
echo "  Stack Name: $STACK_NAME"
echo "  Project Name: $PROJECT_NAME"
echo "  Alert Email: ${ALERT_EMAIL:-'Not configured'}"
echo "  Alert Phone: ${ALERT_PHONE:-'Not configured'}"
echo "  Cost Threshold: \$${COST_THRESHOLD}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI is not installed"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "ERROR: AWS credentials not configured or invalid"
    echo "Run: aws configure"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_USER=$(aws sts get-caller-identity --query Arn --output text)

echo -e "\nAWS Identity:"
echo "  Account: $AWS_ACCOUNT"
echo "  User: $AWS_USER"
echo "  Region: $REGION"

# Confirm deployment
echo -e "\n⚠️  This will create AWS resources that may incur costs."
echo "Estimated monthly cost: \$2-5"
read -p "Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Deploy based on method
if [[ "$DEPLOYMENT_METHOD" == "cloudformation" ]]; then
    echo -e "\n🚀 Deploying with CloudFormation..."
    
    # Check if CloudFormation template exists
    if [[ ! -f "cloud/cloudformation_iam.yml" ]]; then
        echo "ERROR: CloudFormation template not found: cloud/cloudformation_iam.yml"
        exit 1
    fi
    
    # Build parameters
    PARAMETERS="ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME"
    PARAMETERS="$PARAMETERS ParameterKey=MonitoringNamespace,ParameterValue=HomeNetwork"
    PARAMETERS="$PARAMETERS ParameterKey=CostAlarmThreshold,ParameterValue=$COST_THRESHOLD"
    
    if [[ -n "$ALERT_EMAIL" ]]; then
        PARAMETERS="$PARAMETERS ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL"
    fi
    
    if [[ -n "$ALERT_PHONE" ]]; then
        PARAMETERS="$PARAMETERS ParameterKey=AlertPhoneNumber,ParameterValue=$ALERT_PHONE"
    fi
    
    # Deploy stack
    aws cloudformation deploy \
        --template-file cloud/cloudformation_iam.yml \
        --stack-name $STACK_NAME \
        --parameter-overrides $PARAMETERS \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION \
        --tags Project=$PROJECT_NAME Purpose=HomeNetworkMonitoring
    
    echo -e "\n📊 Retrieving outputs..."
    
    # Get outputs
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs' \
        --output table)
    
    echo "$OUTPUTS"
    
    # Extract key values for configuration
    ACCESS_KEY_ID=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`AccessKeyId`].OutputValue' \
        --output text)
    
    SNS_TOPIC_ARN=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`SNSTopicArn`].OutputValue' \
        --output text)
    
    DASHBOARD_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
        --output text)
    
    SECRET_KEY_PARAM=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`SecretAccessKey`].OutputValue' \
        --output text)
    
    echo -e "\n⚠️  IMPORTANT: Secret Access Key is stored in SSM Parameter Store"
    echo "To retrieve it, run:"
    echo "aws ssm get-parameter --name $SECRET_KEY_PARAM --with-decryption --query Parameter.Value --output text --region $REGION"

elif [[ "$DEPLOYMENT_METHOD" == "terraform" ]]; then
    echo -e "\n🚀 Deploying with Terraform..."
    
    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        echo "ERROR: Terraform is not installed"
        echo "Install from: https://terraform.io/downloads"
        exit 1
    fi
    
    # Check if Terraform files exist
    if [[ ! -f "cloud/terraform/xfinicky-iam.tf" ]]; then
        echo "ERROR: Terraform configuration not found: cloud/terraform/xfinicky-iam.tf"
        exit 1
    fi
    
    cd cloud/terraform
    
    # Initialize Terraform
    echo "Initializing Terraform..."
    terraform init
    
    # Create terraform.tfvars file
    cat > terraform.tfvars << EOF
project_name          = "$PROJECT_NAME"
monitoring_namespace  = "HomeNetwork"
cost_alarm_threshold  = $COST_THRESHOLD
alert_email          = "$ALERT_EMAIL"
alert_phone_number   = "$ALERT_PHONE"
environment          = "prod"
EOF
    
    # Plan deployment
    echo -e "\nPlanning Terraform deployment..."
    terraform plan -var-file=terraform.tfvars
    
    # Apply deployment
    echo -e "\nApplying Terraform configuration..."
    terraform apply -var-file=terraform.tfvars -auto-approve
    
    # Get outputs
    echo -e "\n📊 Retrieving outputs..."
    ACCESS_KEY_ID=$(terraform output -raw access_key_id)
    SNS_TOPIC_ARN=$(terraform output -raw sns_topic_arn)
    DASHBOARD_URL=$(terraform output -raw dashboard_url)
    
    # Display all outputs
    terraform output
    
    cd ../..
fi

# Create Dell configuration file
echo -e "\n📝 Creating Dell configuration..."

mkdir -p config/generated

cat > config/generated/dell_aws_config.yaml << EOF
# XFinicky Dell AWS Configuration
# Generated on: $(date)
# DO NOT COMMIT THIS FILE - Contains sensitive credentials

aws:
  region: "$REGION"
  account_id: "$AWS_ACCOUNT"
  
  # Credentials for Dell monitoring agent
  access_key_id: "$ACCESS_KEY_ID"
  # secret_access_key: Retrieved from SSM Parameter Store
  # Run: aws ssm get-parameter --name "$SECRET_KEY_PARAM" --with-decryption --query Parameter.Value --output text
  
  cloudwatch:
    namespace: "HomeNetwork"
    detailed_monitoring: false
    retention_days: 14
  
  sns:
    topic_arn: "$SNS_TOPIC_ARN"
  
alerts:
  enabled: true
  channels:
    email:
      enabled: $([ -n "$ALERT_EMAIL" ] && echo "true" || echo "false")
      address: "$ALERT_EMAIL"
    sms:
      enabled: $([ -n "$ALERT_PHONE" ] && echo "true" || echo "false")
      phone_number: "$ALERT_PHONE"

# Deployment metadata
deployment:
  method: "$DEPLOYMENT_METHOD"
  stack_name: "$STACK_NAME"
  deployed_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  deployed_by: "$AWS_USER"
EOF

# Create AWS credentials script for Dell
cat > scripts/configure_dell_aws.sh << 'EOF'
#!/bin/bash

# XFinicky Dell AWS Configuration Script
# Run this on the Dell to configure AWS credentials

echo "Configuring AWS credentials for XFinicky monitoring..."

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI not installed on Dell"
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Get credentials from user
echo "Enter the AWS credentials from the deployment output:"
read -p "Access Key ID: " ACCESS_KEY_ID
read -s -p "Secret Access Key: " SECRET_ACCESS_KEY
echo

# Configure AWS profile
aws configure set aws_access_key_id "$ACCESS_KEY_ID" --profile xfinicky
aws configure set aws_secret_access_key "$SECRET_ACCESS_KEY" --profile xfinicky
aws configure set region "us-east-1" --profile xfinicky
aws configure set output "json" --profile xfinicky

# Test connection
echo "Testing AWS connection..."
if aws sts get-caller-identity --profile xfinicky &> /dev/null; then
    echo "✅ AWS configuration successful!"
    
    # Test CloudWatch access
    if aws cloudwatch list-metrics --namespace HomeNetwork --profile xfinicky &> /dev/null; then
        echo "✅ CloudWatch access verified!"
    else
        echo "⚠️  CloudWatch access may be limited (normal if no metrics sent yet)"
    fi
    
else
    echo "❌ AWS configuration failed. Please check credentials."
    exit 1
fi

echo "Dell is ready for XFinicky monitoring!"
EOF

chmod +x scripts/configure_dell_aws.sh

# Final summary
echo -e "\n================================================"
echo "🎉 AWS Infrastructure Deployment Complete!"
echo "================================================"

echo -e "\nCreated Resources:"
echo "• IAM User: $PROJECT_NAME-monitor-dell"
echo "• IAM Policy: $PROJECT_NAME-monitoring-policy"
echo "• SNS Topic: $SNS_TOPIC_ARN"
echo "• CloudWatch Dashboard: $DASHBOARD_URL"
echo "• CloudWatch Alarms: High latency, connectivity loss"
if [[ "$REGION" == "us-east-1" ]]; then
    echo "• Cost Monitoring: \$COST_THRESHOLD threshold"
fi

echo -e "\nNext Steps:"
echo "1. ⚠️  IMPORTANT: Retrieve the Secret Access Key from SSM Parameter Store:"
echo "   aws ssm get-parameter --name $SECRET_KEY_PARAM --with-decryption --query Parameter.Value --output text --region $REGION"
echo "2. Copy scripts/configure_dell_aws.sh to your Dell"
echo "3. Run the configuration script on Dell with the credentials"
echo "4. Update your monitoring configuration with SNS topic ARN"
echo "5. Start monitoring: ./scripts/start_monitoring.sh"

echo -e "\nConfiguration Files:"
echo "• Dell config: config/generated/dell_aws_config.yaml"
echo "• AWS setup script: scripts/configure_dell_aws.sh"

echo -e "\nSecurity Notes:"
echo "• Secret Access Key is only shown once - save it securely"
echo "• Rotate credentials every 90 days"
echo "• Monitor costs via CloudWatch billing alarms"
echo "• Review IAM permissions periodically"

if [[ -n "$ALERT_EMAIL" ]]; then
    echo -e "\n📧 Email Alerts:"
    echo "• Check your email for SNS subscription confirmation"
    echo "• Click the confirmation link to activate alerts"
fi

if [[ -n "$ALERT_PHONE" ]]; then
    echo -e "\n📱 SMS Alerts:"
    echo "• SMS alerts are automatically activated"
    echo "• Reply STOP to opt out if needed"
fi

echo -e "\n💰 Cost Management:"
echo "• Estimated monthly cost: \$2-5"
echo "• Cost alarm set at: \$COST_THRESHOLD"
echo "• Check costs: aws ce get-cost-and-usage"

echo -e "\n🔗 Useful Links:"
echo "• Dashboard: $DASHBOARD_URL"
echo "• CloudWatch Console: https://$REGION.console.aws.amazon.com/cloudwatch/"
echo "• SNS Console: https://$REGION.console.aws.amazon.com/sns/"

echo -e "\nInfrastructure deployment complete! 🎯"