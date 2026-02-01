#!/bin/bash

# SynonymSeeker Deployment Script
# This script deploys the complete SynonymSeeker infrastructure to AWS

set -e

# Configuration
STACK_NAME="synonymseeker"
ENVIRONMENT="dev"
REGION="us-east-1"
PROFILE="YOUR_AWS_PROFILE"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting SynonymSeeker deployment...${NC}"

# Check AWS CLI configuration
echo -e "${YELLOW}📋 Checking AWS configuration...${NC}"
if ! aws sts get-caller-identity --profile $PROFILE > /dev/null 2>&1; then
    echo -e "${RED}❌ AWS CLI not configured or profile '$PROFILE' not found${NC}"
    echo "Please run: aws configure --profile $PROFILE"
    exit 1
fi

echo -e "${GREEN}✅ AWS CLI configured${NC}"

# Step 1: Deploy secrets management
echo -e "${YELLOW}🔐 Deploying secrets management...${NC}"
aws cloudformation deploy \
    --template-file secrets-template.yaml \
    --stack-name "${STACK_NAME}-secrets" \
    --parameter-overrides Environment=$ENVIRONMENT \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION \
    --profile $PROFILE

echo -e "${GREEN}✅ Secrets management deployed${NC}"

# Step 2: Build and deploy Lambda functions
echo -e "${YELLOW}🔨 Building and deploying Lambda functions...${NC}"
sam build --profile $PROFILE
sam deploy \
    --stack-name $STACK_NAME \
    --parameter-overrides Environment=$ENVIRONMENT \
    --capabilities CAPABILITY_IAM \
    --region $REGION \
    --profile $PROFILE \
    --resolve-s3 \
    --no-confirm-changeset

# Get Lambda function URLs
GAME_BUILDER_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`GameBuilderFunctionUrl`].OutputValue' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

echo -e "${GREEN}✅ Lambda functions deployed${NC}"
echo -e "${GREEN}📍 Game Builder URL: $GAME_BUILDER_URL${NC}"

# Step 3: Deploy frontend infrastructure
echo -e "${YELLOW}🌐 Deploying frontend infrastructure...${NC}"
aws cloudformation deploy \
    --template-file frontend-template.yaml \
    --stack-name "${STACK_NAME}-frontend" \
    --parameter-overrides \
        Environment=$ENVIRONMENT \
        GameBuilderUrl=$GAME_BUILDER_URL \
    --capabilities CAPABILITY_IAM \
    --region $REGION \
    --profile $PROFILE

# Get CloudFront URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-frontend" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

echo -e "${GREEN}✅ Frontend infrastructure deployed${NC}"
echo -e "${GREEN}🌍 Website URL: $CLOUDFRONT_URL${NC}"

# Step 4: Build and deploy frontend application
echo -e "${YELLOW}📦 Building and deploying frontend application...${NC}"

# Get S3 bucket name
S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-frontend" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

# Get CloudFront distribution ID
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-frontend" \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

# Build frontend with correct environment variables
cd ../frontend
echo "VITE_GAME_BUILDER_URL=$GAME_BUILDER_URL" > .env.production
npm run build

# Deploy to S3
aws s3 sync dist/ s3://$S3_BUCKET/ \
    --delete \
    --region $REGION \
    --profile $PROFILE

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*" \
    --region $REGION \
    --profile $PROFILE

cd ../infrastructure

echo -e "${GREEN}✅ Frontend application deployed${NC}"

# Summary
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📍 Game Builder API: $GAME_BUILDER_URL${NC}"
echo -e "${GREEN}🌍 Website URL: $CLOUDFRONT_URL${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}📝 Next steps:${NC}"
echo "1. Update API keys in AWS Secrets Manager (see setup-secrets.sh)"
echo "2. Test the application at: $CLOUDFRONT_URL"
echo "3. Monitor logs in CloudWatch"