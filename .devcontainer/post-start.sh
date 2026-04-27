#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "🚀 Starting Codespace Bootstrap..."
echo "========================================="

# Set default values for critical variables
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
export AWS_REGION="${AWS_REGION:-ap-south-1}"
export AWS_S3_BUCKET_NAME="${AWS_S3_BUCKET_NAME:-f2fintech-knowledge-base}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export PINECONE_API_KEY="${PINECONE_API_KEY:-}"
export PINECONE_INDEX_NAME="${PINECONE_INDEX_NAME:-f2-therapy-index}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
export LOG_LEVEL="${LOG_LEVEL:-info}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"

echo "📝 Creating .env file with environment variables..."
cat > .env << EOF
# AWS Configuration - from Repository Secrets
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
AWS_REGION=${AWS_REGION}
AWS_S3_BUCKET_NAME=${AWS_S3_BUCKET_NAME}

# Google Gemini API - from Repository Secrets
GEMINI_API_KEY=${GEMINI_API_KEY}

# Pinecone Vector DB - from Repository Secrets
PINECONE_API_KEY=${PINECONE_API_KEY}
PINECONE_INDEX_NAME=${PINECONE_INDEX_NAME}

# Environment Configuration
ENVIRONMENT=${ENVIRONMENT}
LOG_LEVEL=${LOG_LEVEL}
HOST=${HOST}
PORT=${PORT}
EOF

chmod 600 .env
echo "✓ .env file created with secure permissions"

# Create AWS credentials directory
mkdir -p ~/.aws

# Configure AWS CLI from environment variables
if [[ -n "${AWS_ACCESS_KEY_ID}" && -n "${AWS_SECRET_ACCESS_KEY}" ]]; then
  echo "🔐 Configuring AWS CLI..."
  
  # Configure AWS credentials file directly
  cat > ~/.aws/credentials << 'AWSCREDS'
[default]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
AWSCREDS
  
  # Configure AWS config file
  cat > ~/.aws/config << AWSCONFIG
[default]
region = ${AWS_REGION}
output = json
AWSCONFIG
  
  # Set secure permissions on AWS config
  chmod 600 ~/.aws/credentials
  chmod 600 ~/.aws/config
  
  echo "✓ AWS CLI configured successfully"
else
  echo "⚠️  AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not found"
  echo "   Please ensure these secrets are set in GitHub Secrets"
fi

echo ""
echo "========================================="
echo "📊 Configuration Status:"
echo "========================================="
echo "AWS_ACCESS_KEY_ID: $([ -n "${AWS_ACCESS_KEY_ID}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "AWS_SECRET_ACCESS_KEY: $([ -n "${AWS_SECRET_ACCESS_KEY}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "AWS_REGION: ${AWS_REGION} ✓"
echo "AWS_S3_BUCKET_NAME: ${AWS_S3_BUCKET_NAME} ✓"
echo "GEMINI_API_KEY: $([ -n "${GEMINI_API_KEY}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "PINECONE_API_KEY: $([ -n "${PINECONE_API_KEY}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "PINECONE_INDEX_NAME: ${PINECONE_INDEX_NAME} ✓"
echo ""

# Test AWS credentials
echo "🧪 Testing AWS credentials..."
if aws sts get-caller-identity --region "${AWS_REGION}"; then
  echo ""
  echo "✓ AWS credentials are valid!"
else
  echo "⚠️  AWS credentials test failed"
  echo "   AWS CLI output above shows the error"
fi

echo ""
echo "========================================="
echo "✅ Bootstrap Complete!"
echo "========================================="