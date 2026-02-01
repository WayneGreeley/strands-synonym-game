# SynonymSeeker Deployment Guide

This guide provides step-by-step instructions for deploying SynonymSeeker to AWS, including all necessary AWS CLI commands and troubleshooting tips.

## Prerequisites

### Required Tools

- **AWS CLI v2+** configured with your AWS profile
- **SAM CLI v1.100+** for serverless deployment
- **Node.js 22+** for frontend build
- **Python 3.13+** for backend development
- **Git** for version control

### AWS Account Setup

1. **Verify AWS CLI Configuration**:
   ```bash
   aws sts get-caller-identity --profile YOUR_PROFILE
   ```

2. **Required AWS Permissions**:
   - CloudFormation: Create/Update/Delete stacks
   - Lambda: Create/Update functions
   - S3: Create buckets, upload objects
   - CloudFront: Create distributions
   - Secrets Manager: Create/Read secrets
   - IAM: Create roles and policies

## Deployment Architecture

```
┌─────────────────┐
│ Secrets Stack   │ ← Deploy first (one-time setup)
├─────────────────┤
│ Backend Stack   │ ← Lambda functions and APIs
├─────────────────┤
│ Frontend Stack  │ ← S3 bucket and CloudFront
└─────────────────┘
```

## Step-by-Step Deployment

### Step 1: Clone Repository

```bash
git clone https://github.com/WayneGreeley/strands-synonym-game.git
cd strands-synonym-game
```

### Step 2: Deploy Secrets Management (One-Time Setup)

```bash
cd infrastructure

# Deploy secrets template
sam deploy \
    --template-file secrets-template.yaml \
    --stack-name synonym-seeker-secrets \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --profile YOUR_PROFILE \
    --region us-east-1
```

**Optional**: Configure external API keys (system works without them):
```bash
./setup-secrets.sh
```

### Step 3: Deploy Backend (Lambda Functions)

```bash
# Build the SAM application
sam build --profile YOUR_PROFILE

# Deploy the backend stack
sam deploy \
    --stack-name synonym-seeker-backend \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --profile YOUR_PROFILE \
    --region us-east-1
```

**Get Lambda Function URLs** (needed for frontend):
```bash
aws cloudformation describe-stacks \
    --stack-name synonym-seeker-backend \
    --query 'Stacks[0].Outputs[?OutputKey==`GameBuilderFunctionUrl`].OutputValue' \
    --output text \
    --profile YOUR_PROFILE
```

### Step 4: Deploy Frontend Infrastructure

```bash
# Deploy S3 and CloudFront
sam deploy \
    --template-file frontend-template.yaml \
    --stack-name synonym-seeker-frontend \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --profile YOUR_PROFILE \
    --region us-east-1 \
    --parameter-overrides \
        Environment=prod \
        GameBuilderUrl=<LAMBDA_FUNCTION_URL_FROM_STEP_3>
```

### Step 5: Build and Deploy Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Build for production
npm run build

# Get S3 bucket name
BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name synonym-seeker-frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
    --output text \
    --profile YOUR_PROFILE)

# Deploy to S3
aws s3 sync dist/ s3://$BUCKET_NAME \
    --delete \
    --profile YOUR_PROFILE

# Invalidate CloudFront cache
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name synonym-seeker-frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
    --output text \
    --profile YOUR_PROFILE)

aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*" \
    --profile YOUR_PROFILE
```

### Step 6: Verify Deployment

```bash
# Get the CloudFront URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name synonym-seeker-frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
    --output text \
    --profile YOUR_PROFILE)

echo "Application deployed at: $CLOUDFRONT_URL"

# Test the backend directly
GAME_BUILDER_URL=$(aws cloudformation describe-stacks \
    --stack-name synonym-seeker-backend \
    --query 'Stacks[0].Outputs[?OutputKey==`GameBuilderFunctionUrl`].OutputValue' \
    --output text \
    --profile YOUR_PROFILE)

curl -X POST "$GAME_BUILDER_URL/start-game" \
    -H "Content-Type: application/json" \
    -d '{}'
```

## Automated Deployment Scripts

### Quick Deploy Script

Create `deploy.sh` (for reference - don't create actual script files per guidelines):

```bash
#!/bin/bash
set -e

echo "🚀 Deploying SynonymSeeker..."

# Deploy secrets (if not exists)
echo "📦 Deploying secrets..."
sam deploy --template-file secrets-template.yaml --stack-name synonym-seeker-secrets --capabilities CAPABILITY_IAM --no-confirm-changeset --profile YOUR_PROFILE

# Deploy backend
echo "🔧 Deploying backend..."
sam build --profile YOUR_PROFILE
sam deploy --no-confirm-changeset --profile YOUR_PROFILE

# Get Lambda URL
LAMBDA_URL=$(aws cloudformation describe-stacks --stack-name synonym-seeker-backend --query 'Stacks[0].Outputs[?OutputKey==`GameBuilderFunctionUrl`].OutputValue' --output text --profile YOUR_PROFILE)

# Deploy frontend infrastructure
echo "🌐 Deploying frontend infrastructure..."
sam deploy --template-file frontend-template.yaml --stack-name synonym-seeker-frontend --capabilities CAPABILITY_IAM --no-confirm-changeset --profile YOUR_PROFILE --parameter-overrides GameBuilderUrl=$LAMBDA_URL

# Build and deploy frontend
echo "🎨 Building and deploying frontend..."
cd frontend
npm install
npm run build

BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name synonym-seeker-frontend --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' --output text --profile YOUR_PROFILE)
aws s3 sync dist/ s3://$BUCKET_NAME --delete --profile YOUR_PROFILE

# Get final URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks --stack-name synonym-seeker-frontend --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' --output text --profile YOUR_PROFILE)

echo "✅ Deployment complete!"
echo "🌍 Application URL: $CLOUDFRONT_URL"
```

## Environment-Specific Deployments

### Development Environment

```bash
# Deploy with dev parameters
sam deploy \
    --parameter-overrides \
        Environment=dev \
        LogLevel=DEBUG \
    --profile YOUR_PROFILE
```

### Production Environment

```bash
# Deploy with production parameters
sam deploy \
    --parameter-overrides \
        Environment=prod \
        LogLevel=INFO \
        EnableXRay=true \
    --profile YOUR_PROFILE
```

## Configuration Management

### Environment Variables

The system uses these environment variables:

```bash
# Backend Lambda Functions
HINT_PROVIDER_A2A_URL=<auto-configured>
HINT_PROVIDER_HTTP_URL=<auto-configured>
BEARER_TOKEN=<from-secrets-manager>
LOG_LEVEL=INFO
ENVIRONMENT=prod

# Frontend (build-time)
VITE_GAME_BUILDER_URL=<lambda-function-url>
VITE_ENVIRONMENT=prod
```

### Secrets Configuration

```bash
# Configure Thesaurus API key (optional)
aws secretsmanager put-secret-value \
    --secret-id synonym-seeker/thesaurus-api-key \
    --secret-string "your-api-key-here" \
    --profile YOUR_PROFILE

# Configure OpenAI API key (optional)
aws secretsmanager put-secret-value \
    --secret-id synonym-seeker/openai-api-key \
    --secret-string "your-openai-key-here" \
    --profile YOUR_PROFILE
```

## Monitoring and Logging

### CloudWatch Logs

```bash
# View Game Builder logs
aws logs tail /aws/lambda/synonym-seeker-GameBuilderFunction \
    --follow \
    --profile YOUR_PROFILE

# View Hint Provider logs
aws logs tail /aws/lambda/synonym-seeker-HintProviderFunction \
    --follow \
    --profile YOUR_PROFILE
```

### CloudWatch Metrics

```bash
# Get Lambda metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=synonym-seeker-GameBuilderFunction \
    --start-time 2024-01-01T00:00:00Z \
    --end-time 2024-01-02T00:00:00Z \
    --period 3600 \
    --statistics Sum \
    --profile YOUR_PROFILE
```

## Troubleshooting

### Common Issues

#### 1. AWS Session Expired

**Error**: `Unable to locate credentials`

**Solution**:
```bash
aws login --profile YOUR_PROFILE
```

#### 2. Lambda Function Not Found

**Error**: `Function not found`

**Solution**:
```bash
# Redeploy backend
sam build --profile YOUR_PROFILE
sam deploy --no-confirm-changeset --profile YOUR_PROFILE
```

#### 3. Frontend Not Loading

**Error**: `This site can't be reached`

**Solution**:
```bash
# Check CloudFront distribution
aws cloudfront list-distributions --profile YOUR_PROFILE

# Rebuild and redeploy frontend
cd frontend
npm run build
aws s3 sync dist/ s3://<bucket-name> --delete --profile YOUR_PROFILE
```

#### 4. CORS Errors

**Error**: `Access to fetch at ... has been blocked by CORS policy`

**Solution**:
```bash
# Check Lambda Function URL CORS configuration
aws lambda get-function-url-config \
    --function-name synonym-seeker-GameBuilderFunction \
    --profile YOUR_PROFILE

# Update CORS if needed (via SAM template)
sam deploy --no-confirm-changeset --profile YOUR_PROFILE
```

#### 5. A2A Communication Failures

**Error**: `A2A communication failed`

**Solution**:
```bash
# Check both Lambda functions are deployed
aws lambda list-functions \
    --query 'Functions[?contains(FunctionName, `synonym-seeker`)].FunctionName' \
    --profile YOUR_PROFILE

# Check environment variables
aws lambda get-function-configuration \
    --function-name synonym-seeker-GameBuilderFunction \
    --query 'Environment.Variables' \
    --profile YOUR_PROFILE
```

### Debug Mode

Enable debug logging:

```bash
# Update Lambda environment variables
aws lambda update-function-configuration \
    --function-name synonym-seeker-GameBuilderFunction \
    --environment Variables='{LOG_LEVEL=DEBUG}' \
    --profile YOUR_PROFILE

aws lambda update-function-configuration \
    --function-name synonym-seeker-HintProviderFunction \
    --environment Variables='{LOG_LEVEL=DEBUG}' \
    --profile YOUR_PROFILE
```

### Health Checks

```bash
# Test Game Builder endpoint
curl -X POST "https://<lambda-url>/start-game" \
    -H "Content-Type: application/json" \
    -d '{}'

# Test Hint Provider endpoint
curl -X POST "https://<lambda-url>/analyze-hint" \
    -H "Content-Type: application/json" \
    -d '{"guess": "test", "target_word": "happy", "previous_guesses": []}'
```

## Cleanup

### Remove All Resources

```bash
# Delete frontend stack
aws cloudformation delete-stack \
    --stack-name synonym-seeker-frontend \
    --profile YOUR_PROFILE

# Delete backend stack
aws cloudformation delete-stack \
    --stack-name synonym-seeker-backend \
    --profile YOUR_PROFILE

# Delete secrets stack (optional)
aws cloudformation delete-stack \
    --stack-name synonym-seeker-secrets \
    --profile YOUR_PROFILE

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
    --stack-name synonym-seeker-frontend \
    --profile YOUR_PROFILE

aws cloudformation wait stack-delete-complete \
    --stack-name synonym-seeker-backend \
    --profile YOUR_PROFILE
```

### Cleanup S3 Buckets (if needed)

```bash
# Empty S3 bucket before deletion
aws s3 rm s3://<bucket-name> --recursive --profile YOUR_PROFILE
```

## Cost Optimization

### Free Tier Usage

The deployment is designed to stay within AWS free tier:

- **Lambda**: 1M requests/month, 400,000 GB-seconds
- **S3**: 5GB storage, 20,000 GET requests
- **CloudFront**: 1TB data transfer, 10M requests
- **Secrets Manager**: 30-day free trial, then $0.40/secret/month

### Cost Monitoring

```bash
# Set up billing alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "SynonymSeeker-BillingAlarm" \
    --alarm-description "Alert when estimated charges exceed $5" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 86400 \
    --threshold 5.0 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=Currency,Value=USD \
    --profile YOUR_PROFILE
```

## Security Considerations

### IAM Roles

The deployment creates minimal IAM roles:

```yaml
# Game Builder Lambda Role
- CloudWatch Logs: Write access
- Secrets Manager: Read access for API keys
- Lambda: Invoke Hint Provider function

# Hint Provider Lambda Role  
- CloudWatch Logs: Write access
- Secrets Manager: Read access for API keys
```

### Network Security

- All communications use HTTPS/TLS
- Lambda Function URLs have CORS restrictions
- No VPC configuration needed (public internet access)

### Data Security

- No persistent data storage
- Session data exists only in memory
- No user authentication required
- Input sanitization prevents injection attacks

## Performance Optimization

### Lambda Configuration

```bash
# Optimize Lambda memory/timeout
aws lambda update-function-configuration \
    --function-name synonym-seeker-GameBuilderFunction \
    --memory-size 512 \
    --timeout 30 \
    --profile YOUR_PROFILE
```

### CloudFront Caching

The frontend template configures optimal caching:
- Static assets: 1 year cache
- HTML files: No cache (for updates)
- API responses: No cache (dynamic content)

---

This deployment guide provides comprehensive instructions for deploying SynonymSeeker to AWS. Follow the steps in order, and refer to the troubleshooting section if you encounter any issues.