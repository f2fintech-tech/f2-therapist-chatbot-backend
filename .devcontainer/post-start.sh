#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "🚀 Starting Codespace Bootstrap..."
echo "========================================="

# Create .env file from environment variables
echo "📝 Creating .env from GitHub Secrets..."
cat > .env << 'EOF'
# AWS Configuration - from Repository Secrets
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
AWS_REGION=${AWS_REGION:-ap-south-1}
AWS_S3_BUCKET_NAME=${AWS_S3_BUCKET_NAME:-f2fintech-knowledge-base}

# Google Gemini API - from Repository Secrets
GEMINI_API_KEY=${GEMINI_API_KEY:-}

# Pinecone Vector DB - from Repository Secrets
PINECONE_API_KEY=${PINECONE_API_KEY:-}
PINECONE_INDEX_NAME=${PINECONE_INDEX_NAME:-f2-therapy-index}

# Environment
ENVIRONMENT=development
LOG_LEVEL=info
HOST=0.0.0.0
PORT=8000
EOF

chmod 600 .env
echo "✓ .env file created with secure permissions"

# Export variables from .env
set -a
source .env
set +a
echo "✓ Environment variables loaded"

# Create AWS credentials directory
mkdir -p ~/.aws

# Configure AWS CLI from secrets
if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  echo "🔐 Configuring AWS CLI..."
  
  aws configure set aws_access_key_id "${AWS_ACCESS_KEY_ID}" --profile default
  aws configure set aws_secret_access_key "${AWS_SECRET_ACCESS_KEY}" --profile default
  aws configure set region "${AWS_REGION:-ap-south-1}" --profile default
  
  # Set secure permissions on AWS config
  chmod 600 ~/.aws/credentials 2>/dev/null || true
  chmod 600 ~/.aws/config 2>/dev/null || true
  
  echo "✓ AWS CLI configured successfully"
else
  echo "⚠️  AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not found"
  echo "   Please ensure these secrets are set in GitHub Secrets"
fi

echo ""
echo "========================================="
echo "📊 Configuration Status:"
echo "========================================="
echo "AWS_ACCESS_KEY_ID: $([ -n "${AWS_ACCESS_KEY_ID:-}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "AWS_SECRET_ACCESS_KEY: $([ -n "${AWS_SECRET_ACCESS_KEY:-}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "AWS_REGION: ${AWS_REGION:-ap-south-1} ✓"
echo "AWS_S3_BUCKET_NAME: ${AWS_S3_BUCKET_NAME:-f2fintech-knowledge-base} ✓"
echo "GEMINI_API_KEY: $([ -n "${GEMINI_API_KEY:-}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "PINECONE_API_KEY: $([ -n "${PINECONE_API_KEY:-}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "PINECONE_INDEX_NAME: ${PINECONE_INDEX_NAME:-f2-therapy-index} ✓"
echo ""

# Test AWS credentials
echo "🧪 Testing AWS credentials..."
if aws sts get-caller-identity > /dev/null 2>&1; then
  echo "✓ AWS credentials are valid!"
  echo ""
  aws sts get-caller-identity
else
  echo "✗ AWS credentials test failed - check your secrets"
fi

echo ""
echo "========================================="
echo "✅ Bootstrap Complete!"
echo "========================================="