#!/bin/bash

# SynonymSeeker Secrets Setup Script
# This script helps configure API keys and secrets after deployment

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
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔐 SynonymSeeker Secrets Setup${NC}"
echo -e "${BLUE}This script will help you configure API keys and secrets.${NC}"
echo ""

# Check if secrets stack exists
if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}-secrets" --region $REGION --profile $PROFILE > /dev/null 2>&1; then
    echo -e "${RED}❌ Secrets stack not found. Please deploy infrastructure first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Secrets stack found${NC}"

# Function to update a secret
update_secret() {
    local secret_name=$1
    local secret_description=$2
    local current_value=$3
    
    echo -e "${YELLOW}📝 Configuring $secret_description...${NC}"
    echo -e "${BLUE}Current value: $current_value${NC}"
    
    read -p "Enter new value (or press Enter to keep current): " new_value
    
    if [ ! -z "$new_value" ]; then
        aws secretsmanager update-secret \
            --secret-id "$secret_name" \
            --secret-string "{\"api_key\": \"$new_value\"}" \
            --region $REGION \
            --profile $PROFILE > /dev/null
        
        echo -e "${GREEN}✅ Updated $secret_description${NC}"
    else
        echo -e "${YELLOW}⏭️  Keeping current value for $secret_description${NC}"
    fi
    echo ""
}

# Get current secret values
echo -e "${YELLOW}📋 Retrieving current secret values...${NC}"

THESAURUS_SECRET_NAME="/${STACK_NAME}/${ENVIRONMENT}/thesaurus-api-key"
OPENAI_SECRET_NAME="/${STACK_NAME}/${ENVIRONMENT}/openai-api-key"
BEARER_SECRET_NAME="/${STACK_NAME}/${ENVIRONMENT}/bearer-token"

# Get Thesaurus API key
THESAURUS_CURRENT=$(aws secretsmanager get-secret-value \
    --secret-id "$THESAURUS_SECRET_NAME" \
    --query 'SecretString' \
    --output text \
    --region $REGION \
    --profile $PROFILE 2>/dev/null | jq -r '.api_key' 2>/dev/null || echo "your-thesaurus-api-key-here")

# Get OpenAI API key
OPENAI_CURRENT=$(aws secretsmanager get-secret-value \
    --secret-id "$OPENAI_SECRET_NAME" \
    --query 'SecretString' \
    --output text \
    --region $REGION \
    --profile $PROFILE 2>/dev/null | jq -r '.api_key' 2>/dev/null || echo "your-openai-api-key-here")

# Get Bearer token
BEARER_CURRENT=$(aws secretsmanager get-secret-value \
    --secret-id "$BEARER_SECRET_NAME" \
    --query 'SecretString' \
    --output text \
    --region $REGION \
    --profile $PROFILE 2>/dev/null | jq -r '.token' 2>/dev/null || echo "[auto-generated]")

echo -e "${GREEN}✅ Retrieved current values${NC}"
echo ""

# Update secrets
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Configure API Keys (optional - leave blank to use fallback word sets)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

update_secret "$THESAURUS_SECRET_NAME" "Thesaurus API Key" "$THESAURUS_CURRENT"
update_secret "$OPENAI_SECRET_NAME" "OpenAI API Key" "$OPENAI_CURRENT"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Bearer Token (for A2A communication security)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}📝 Bearer Token Configuration...${NC}"
echo -e "${BLUE}Current value: [hidden for security]${NC}"
echo -e "${BLUE}This token secures communication between agents.${NC}"

read -p "Generate new bearer token? (y/N): " generate_token

if [[ $generate_token =~ ^[Yy]$ ]]; then
    NEW_TOKEN=$(openssl rand -base64 48)
    aws secretsmanager update-secret \
        --secret-id "$BEARER_SECRET_NAME" \
        --secret-string "{\"token\": \"$NEW_TOKEN\"}" \
        --region $REGION \
        --profile $PROFILE > /dev/null
    
    echo -e "${GREEN}✅ Generated new bearer token${NC}"
else
    echo -e "${YELLOW}⏭️  Keeping current bearer token${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Secrets configuration completed!${NC}"
echo ""
echo -e "${YELLOW}📝 Important Notes:${NC}"
echo "• API keys are optional - the system uses curated word sets as fallback"
echo "• Thesaurus API key enables dynamic word generation"
echo "• OpenAI API key enables enhanced hint generation"
echo "• Bearer token secures A2A agent communication"
echo "• All secrets are encrypted at rest in AWS Secrets Manager"
echo ""
echo -e "${BLUE}🔍 To view secret values later:${NC}"
echo "aws secretsmanager get-secret-value --secret-id '$THESAURUS_SECRET_NAME' --region $REGION --profile $PROFILE"
echo "aws secretsmanager get-secret-value --secret-id '$OPENAI_SECRET_NAME' --region $REGION --profile $PROFILE"
echo ""
echo -e "${GREEN}✅ Setup complete! Your application is ready to use.${NC}"