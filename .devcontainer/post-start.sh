#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "🚀 Starting Codespace Bootstrap..."
echo "========================================="

# Set default values
export AWS_REGION="${AWS_REGION:-ap-south-1}"
export AWS_S3_BUCKET_NAME="${AWS_S3_BUCKET_NAME:-f2fintech-knowledge-base}"
export PINECONE_INDEX_NAME="${PINECONE_INDEX_NAME:-f2-therapy-index}"

echo "📝 Creating .env file..."
cat > .env << EOF
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
AWS_REGION=${AWS_REGION}
AWS_S3_BUCKET_NAME=${AWS_S3_BUCKET_NAME}
GEMINI_API_KEY=${GEMINI_API_KEY:-}
PINECONE_API_KEY=${PINECONE_API_KEY:-}
PINECONE_INDEX_NAME=${PINECONE_INDEX_NAME}
ENVIRONMENT=development
LOG_LEVEL=info
HOST=0.0.0.0
PORT=8000
EOF
chmod 600 .env
echo "✓ .env created"

# Install dependencies (only if not already installed)
if [[ ! -d "venv" ]]; then
  echo "📦 Creating virtual environment and installing Python dependencies..."
  python -m venv venv
  # shellcheck disable=SC1091
  source venv/bin/activate
  pip install --upgrade pip setuptools wheel
  pip install -q -r requirements.txt
  echo "✓ venv created and dependencies installed"
else
  echo "✓ venv already exists"
fi

# Configure AWS
if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  echo "🔐 Configuring AWS..."
  mkdir -p ~/.aws
  cat > ~/.aws/credentials << 'CREDS'
[default]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
CREDS
  cat > ~/.aws/config << CONFIG
[default]
region = ${AWS_REGION}
output = json
CONFIG
  chmod 600 ~/.aws/credentials ~/.aws/config
  echo "✓ AWS configured"

  # Quick test
  if aws sts get-caller-identity > /dev/null 2>&1; then
    echo "✓ AWS credentials valid"
  else
    echo "⚠️  AWS test failed"
  fi
else
  echo "⚠️  AWS secrets not set"
fi

echo ""
echo "========================================="
echo "✅ Bootstrap Complete!"
echo "========================================="
