# SynonymSeeker AWS Infrastructure

This directory contains AWS SAM templates and deployment scripts for the SynonymSeeker multi-agent word puzzle game.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFront    │    │   Game Builder   │    │ Hint Provider   │
│   Distribution  │◄──►│   Lambda         │◄──►│ Lambda          │
│                 │    │   (Strands)      │    │ (Strands)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   S3 Bucket     │    │   CloudWatch     │    │ Secrets Manager │
│   (Frontend)    │    │   Logs           │    │ (API Keys)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Components

### 1. Lambda Functions (`template.yaml`)
- **Game Builder Agent**: Main game logic and session management
- **Hint Provider Agent**: AI-powered hint generation and analysis
- **Strands Layer**: Shared dependencies for AWS Strands SDK
- **Function URLs**: Direct HTTPS endpoints with CORS support

### 2. Frontend Infrastructure (`frontend-template.yaml`)
- **S3 Bucket**: Static website hosting with encryption
- **CloudFront**: Global CDN with Origin Access Control (OAC)
- **Custom Domain**: Optional Route 53 and SSL certificate support
- **Deployment Function**: Automated frontend configuration

### 3. Secrets Management (`secrets-template.yaml`)
- **API Keys**: Thesaurus and OpenAI API keys (optional)
- **Bearer Token**: Secure A2A agent communication
- **IAM Roles**: Least-privilege access to secrets
- **Parameter Store**: Non-sensitive configuration references

## Prerequisites

### Required Tools
- AWS CLI v2+ configured with appropriate permissions
- SAM CLI v1.100+
- Node.js 22+ (for frontend build)
- Python 3.11+ (for Lambda functions)
- jq (for JSON parsing in scripts)

### AWS Permissions
Your AWS profile needs the following permissions:
- CloudFormation: Full access
- Lambda: Full access
- S3: Full access
- CloudFront: Full access
- Secrets Manager: Full access
- IAM: Create/manage roles and policies
- CloudWatch: Create log groups

### AWS CLI Configuration
```bash
aws configure --profile YOUR_PROFILE
# Enter your AWS Access Key ID, Secret Access Key, and region (us-east-1)
```

## Quick Start

### 1. Deploy Everything
```bash
cd infrastructure
./deploy.sh
```

This script will:
1. Deploy secrets management
2. Build and deploy Lambda functions
3. Deploy frontend infrastructure
4. Build and deploy the Vue.js application
5. Output the website URL

### 2. Configure API Keys (Optional)
```bash
./setup-secrets.sh
```

The application works without API keys using curated word sets. API keys enable:
- **Thesaurus API**: Dynamic word generation
- **OpenAI API**: Enhanced hint generation

### 3. Access Your Application
The deployment script outputs the CloudFront URL where your application is available.

## Manual Deployment Steps

If you prefer manual control over the deployment process:

### Step 1: Deploy Secrets Management
```bash
aws cloudformation deploy \
    --template-file secrets-template.yaml \
    --stack-name synonymseeker-secrets \
    --parameter-overrides Environment=dev \
    --capabilities CAPABILITY_NAMED_IAM \
    --region us-east-1 \
    --profile YOUR_PROFILE
```

### Step 2: Build and Deploy Lambda Functions
```bash
sam build --profile YOUR_PROFILE
sam deploy \
    --stack-name synonymseeker \
    --parameter-overrides Environment=dev \
    --capabilities CAPABILITY_IAM \
    --region us-east-1 \
    --profile YOUR_PROFILE
```

### Step 3: Deploy Frontend Infrastructure
```bash
# Get the Game Builder URL from the Lambda stack
GAME_BUILDER_URL=$(aws cloudformation describe-stacks \
    --stack-name synonymseeker \
    --query 'Stacks[0].Outputs[?OutputKey==`GameBuilderFunctionUrl`].OutputValue' \
    --output text \
    --region us-east-1 \
    --profile YOUR_PROFILE)

aws cloudformation deploy \
    --template-file frontend-template.yaml \
    --stack-name synonymseeker-frontend \
    --parameter-overrides \
        Environment=dev \
        GameBuilderUrl=$GAME_BUILDER_URL \
    --capabilities CAPABILITY_IAM \
    --region us-east-1 \
    --profile YOUR_PROFILE
```

### Step 4: Build and Deploy Frontend Application
```bash
# Get S3 bucket name and CloudFront distribution ID
S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name synonymseeker-frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
    --output text \
    --region us-east-1 \
    --profile YOUR_PROFILE)

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name synonymseeker-frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text \
    --region us-east-1 \
    --profile YOUR_PROFILE)

# Build frontend
cd ../frontend
echo "VITE_GAME_BUILDER_URL=$GAME_BUILDER_URL" > .env.production
npm run build

# Deploy to S3
aws s3 sync dist/ s3://$S3_BUCKET/ \
    --delete \
    --region us-east-1 \
    --profile YOUR_PROFILE

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*" \
    --region us-east-1 \
    --profile YOUR_PROFILE
```

## Configuration

### Environment Variables
The Lambda functions use these environment variables:

**Game Builder Agent:**
- `THESAURUS_API_KEY`: External thesaurus API key (optional)
- `OPENAI_API_KEY`: OpenAI API key (optional)
- `HINT_PROVIDER_URL`: Hint Provider Lambda URL (auto-configured)
- `HINT_PROVIDER_A2A_URL`: A2A endpoint URL (auto-configured)

**Hint Provider Agent:**
- `GAME_BUILDER_URL`: Game Builder Lambda URL (auto-configured)

### Secrets Management
API keys are stored in AWS Secrets Manager:
- `/synonymseeker/dev/thesaurus-api-key`
- `/synonymseeker/dev/openai-api-key`
- `/synonymseeker/dev/bearer-token`

### Updating Secrets
```bash
# Update Thesaurus API key
aws secretsmanager update-secret \
    --secret-id /synonymseeker/dev/thesaurus-api-key \
    --secret-string '{"api_key": "your-new-api-key"}' \
    --region us-east-1 \
    --profile YOUR_PROFILE

# Update OpenAI API key
aws secretsmanager update-secret \
    --secret-id /synonymseeker/dev/openai-api-key \
    --secret-string '{"api_key": "your-new-api-key"}' \
    --region us-east-1 \
    --profile YOUR_PROFILE
```

## Monitoring and Troubleshooting

### CloudWatch Logs
- Game Builder logs: `/aws/lambda/synonymseeker-game-builder`
- Hint Provider logs: `/aws/lambda/synonymseeker-hint-provider`

### View Logs
```bash
# Game Builder logs
aws logs tail /aws/lambda/synonymseeker-game-builder \
    --follow \
    --region us-east-1 \
    --profile YOUR_PROFILE

# Hint Provider logs
aws logs tail /aws/lambda/synonymseeker-hint-provider \
    --follow \
    --region us-east-1 \
    --profile YOUR_PROFILE
```

### Common Issues

**1. Lambda Function Timeout**
- Increase timeout in `template.yaml` (currently 30 seconds)
- Check CloudWatch logs for performance bottlenecks

**2. CORS Issues**
- Verify Function URL CORS configuration
- Check browser developer tools for specific CORS errors

**3. A2A Communication Failures**
- Check bearer token configuration
- Verify both Lambda functions are deployed and accessible
- Review CloudWatch logs for connection errors

**4. Frontend Build Issues**
- Ensure Node.js 22+ is installed
- Verify `VITE_GAME_BUILDER_URL` is set correctly
- Check that S3 bucket policy allows CloudFront access

## Cost Optimization

### Free Tier Usage
- Lambda: 1M requests/month, 400,000 GB-seconds compute
- S3: 5GB storage, 20,000 GET requests, 2,000 PUT requests
- CloudFront: 1TB data transfer, 10M requests
- Secrets Manager: First 30 days free, then $0.40/secret/month

### Production Optimizations
- Enable Lambda provisioned concurrency for consistent performance
- Use CloudFront caching policies to reduce Lambda invocations
- Implement request/response compression
- Monitor costs with AWS Cost Explorer

## Security

### Best Practices Implemented
- **Least Privilege IAM**: Functions only access required resources
- **Secrets Encryption**: All secrets encrypted at rest and in transit
- **HTTPS Only**: All communication uses TLS 1.2+
- **Origin Access Control**: S3 bucket only accessible via CloudFront
- **Input Validation**: Comprehensive sanitization and validation
- **No Hardcoded Secrets**: All sensitive data in Secrets Manager

### Security Monitoring
- Enable CloudTrail for API call auditing
- Set up CloudWatch alarms for unusual activity
- Regularly rotate API keys and bearer tokens
- Monitor AWS Security Hub for security findings

## Cleanup

To remove all AWS resources:
```bash
./cleanup.sh
```

This will delete:
- All CloudFormation stacks
- S3 bucket contents
- Secrets Manager entries
- CloudWatch log groups
- SAM build artifacts

## Support

### Troubleshooting Steps
1. Check CloudWatch logs for error messages
2. Verify AWS CLI configuration and permissions
3. Ensure all prerequisites are installed
4. Review stack outputs for correct URLs
5. Test Lambda functions individually using AWS Console

### Getting Help
- Review CloudFormation events in AWS Console
- Check SAM CLI documentation: https://docs.aws.amazon.com/serverless-application-model/
- AWS Strands documentation: https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html

## Development

### Local Testing
```bash
# Start SAM local API
sam local start-api --profile YOUR_PROFILE

# Test individual functions
sam local invoke GameBuilderFunction --event events/test-event.json
```

### Hot Reloading
```bash
# Watch for changes and auto-deploy
sam sync --watch --profile YOUR_PROFILE
```

### Custom Domains
To use a custom domain, update `frontend-template.yaml`:
```yaml
Parameters:
  DomainName:
    Type: String
    Default: 'yourdomain.com'
```

Then deploy with:
```bash
aws cloudformation deploy \
    --template-file frontend-template.yaml \
    --stack-name synonymseeker-frontend \
    --parameter-overrides \
        Environment=dev \
        GameBuilderUrl=$GAME_BUILDER_URL \
        DomainName=yourdomain.com \
    --capabilities CAPABILITY_IAM
```