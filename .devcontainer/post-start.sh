#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "🚀 Starting Codespace Bootstrap..."
echo "========================================="

# Explicitly set AWS_REGION to a known default if not already set or empty.
# This prevents invalid STS endpoints like https://sts..amazonaws.com.
if [[ -z "${AWS_REGION:-}" ]]; then
  export AWS_REGION="ap-south-1"
  echo "AWS_REGION was not set; defaulting to ap-south-1"
fi
# AWS CLI uses AWS_DEFAULT_REGION; keep both variables in sync.
export AWS_DEFAULT_REGION="${AWS_REGION}"
echo "Using AWS_REGION: ${AWS_REGION}"

# Resolve all variables with defaults so the .env file holds real values.
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
export AWS_S3_BUCKET_NAME="${AWS_S3_BUCKET_NAME:-f2fintech-knowledge-base}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export PINECONE_API_KEY="${PINECONE_API_KEY:-}"
export PINECONE_INDEX_NAME="${PINECONE_INDEX_NAME:-f2-therapy-index}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
export LOG_LEVEL="${LOG_LEVEL:-info}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"

# Create .env file with fully resolved values (not shell-template strings).
# Using an unquoted heredoc (<<EOF) so variables are expanded at write-time, which means
# python-dotenv and other tools will read actual values instead of expressions.
echo "📝 Creating .env from GitHub Secrets..."
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

# Configure AWS CLI from secrets
if [[ -n "${AWS_ACCESS_KEY_ID}" && -n "${AWS_SECRET_ACCESS_KEY}" ]]; then
  echo "🔐 Configuring AWS CLI..."

  aws configure set aws_access_key_id "${AWS_ACCESS_KEY_ID}" --profile default
  aws configure set aws_secret_access_key "${AWS_SECRET_ACCESS_KEY}" --profile default
  aws configure set region "${AWS_REGION}" --profile default

  # Set secure permissions on AWS config
  chmod 600 ~/.aws/credentials 2>/dev/null || true
  chmod 600 ~/.aws/config 2>/dev/null || true

  echo "✓ AWS CLI configured successfully"
else
  echo "⚠️  AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not found"
  echo "   Please ensure these secrets are set in GitHub Codespaces Secrets"
fi

echo ""
echo "========================================="
echo "📊 Configuration Status:"
echo "========================================="
echo "AWS_ACCESS_KEY_ID:     $([ -n "${AWS_ACCESS_KEY_ID}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "AWS_SECRET_ACCESS_KEY: $([ -n "${AWS_SECRET_ACCESS_KEY}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "AWS_REGION:            ${AWS_REGION} ✓"
echo "AWS_S3_BUCKET_NAME:    ${AWS_S3_BUCKET_NAME} ✓"
echo "GEMINI_API_KEY:        $([ -n "${GEMINI_API_KEY}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "PINECONE_API_KEY:      $([ -n "${PINECONE_API_KEY}" ] && echo '✓ Set' || echo '✗ Missing')"
echo "PINECONE_INDEX_NAME:   ${PINECONE_INDEX_NAME} ✓"
echo ""

# AWS_REGION is guaranteed non-empty (set to ap-south-1 above if unset).
echo "🧪 Testing AWS credentials (region: ${AWS_REGION})..."
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
