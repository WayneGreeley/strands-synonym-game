#!/bin/bash

# SynonymSeeker Cleanup Script
# This script removes all AWS resources created by the deployment

set -e

# Configuration
STACK_NAME="synonymseeker"
REGION="us-east-1"
PROFILE="YOUR_AWS_PROFILE"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}🗑️  SynonymSeeker Cleanup${NC}"
echo -e "${YELLOW}⚠️  This will DELETE ALL AWS resources for SynonymSeeker!${NC}"
echo ""

read -p "Are you sure you want to continue? (type 'DELETE' to confirm): " confirmation

if [ "$confirmation" != "DELETE" ]; then
    echo -e "${GREEN}✅ Cleanup cancelled${NC}"
    exit 0
fi

echo -e "${YELLOW}🧹 Starting cleanup...${NC}"

# Function to delete stack if it exists
delete_stack_if_exists() {
    local stack_name=$1
    local description=$2
    
    if aws cloudformation describe-stacks --stack-name "$stack_name" --region $REGION --profile $PROFILE > /dev/null 2>&1; then
        echo -e "${YELLOW}🗑️  Deleting $description...${NC}"
        
        # Empty S3 bucket if it's the frontend stack
        if [[ $stack_name == *"frontend"* ]]; then
            BUCKET_NAME=$(aws cloudformation describe-stacks \
                --stack-name "$stack_name" \
                --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
                --output text \
                --region $REGION \
                --profile $PROFILE 2>/dev/null || echo "")
            
            if [ ! -z "$BUCKET_NAME" ]; then
                echo -e "${YELLOW}📦 Emptying S3 bucket: $BUCKET_NAME${NC}"
                aws s3 rm s3://$BUCKET_NAME --recursive --region $REGION --profile $PROFILE 2>/dev/null || true
            fi
        fi
        
        aws cloudformation delete-stack \
            --stack-name "$stack_name" \
            --region $REGION \
            --profile $PROFILE
        
        echo -e "${YELLOW}⏳ Waiting for $description deletion to complete...${NC}"
        aws cloudformation wait stack-delete-complete \
            --stack-name "$stack_name" \
            --region $REGION \
            --profile $PROFILE
        
        echo -e "${GREEN}✅ $description deleted${NC}"
    else
        echo -e "${YELLOW}⏭️  $description not found, skipping${NC}"
    fi
}

# Delete stacks in reverse order of creation
delete_stack_if_exists "${STACK_NAME}-frontend" "Frontend infrastructure"
delete_stack_if_exists "$STACK_NAME" "Lambda functions"
delete_stack_if_exists "${STACK_NAME}-secrets" "Secrets management"

# Clean up SAM artifacts
echo -e "${YELLOW}🧹 Cleaning up SAM artifacts...${NC}"
if [ -d ".aws-sam" ]; then
    rm -rf .aws-sam
    echo -e "${GREEN}✅ SAM artifacts cleaned${NC}"
fi

# Clean up samconfig.toml if it exists
if [ -f "samconfig.toml" ]; then
    echo -e "${YELLOW}📝 Backing up samconfig.toml...${NC}"
    cp samconfig.toml samconfig.toml.backup
    echo -e "${GREEN}✅ Configuration backed up${NC}"
fi

echo -e "${GREEN}🎉 Cleanup completed successfully!${NC}"
echo ""
echo -e "${YELLOW}📝 What was deleted:${NC}"
echo "• All Lambda functions and layers"
echo "• S3 bucket and all website files"
echo "• CloudFront distribution"
echo "• All secrets in AWS Secrets Manager"
echo "• IAM roles and policies"
echo "• CloudWatch log groups"
echo ""
echo -e "${BLUE}💡 To redeploy, run: ./deploy.sh${NC}"