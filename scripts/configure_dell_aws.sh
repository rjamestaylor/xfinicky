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
