#!/bin/bash
# Helper script to detect Codespaces environment and configure correct backend URL

set -e

echo "🔍 Detecting Codespaces Environment..."
echo ""

# Check if running in Codespaces
if [ -z "$CODESPACES" ]; then
    echo "❌ Not running in Codespaces. This script is for Codespaces environments only."
    exit 1
fi

echo "✓ Running in GitHub Codespaces"
echo ""

# Get the Codespaces name
if [ -z "$CODESPACE_NAME" ]; then
    echo "❌ Cannot determine Codespace name"
    exit 1
fi

CODESPACE_NAME="${CODESPACE_NAME}"
CODESPACES_DOMAIN_PREFIX="${CODESPACE_NAME}"

# Construct the Codespaces URLs
BACKEND_URL="https://${CODESPACES_DOMAIN_PREFIX}-8000.app.github.dev/api/v1"
FRONTEND_URL="https://${CODESPACES_DOMAIN_PREFIX}-5173.app.github.dev"

echo "📍 Codespace Name: $CODESPACE_NAME"
echo ""
echo "🔗 Backend URL: $BACKEND_URL"
echo "🔗 Frontend URL: $FRONTEND_URL"
echo ""

# Check if frontend directory exists
if [ ! -d "/workspaces/f2-therapist-chatbot-frontend" ]; then
    echo "⚠️  Frontend repository not found at /workspaces/f2-therapist-chatbot-frontend"
    echo "   You need to set the VITE_API_BASE_URL in your frontend's .env file manually"
    echo ""
    echo "Add this to your frontend/.env.local:"
    echo "VITE_API_BASE_URL=$BACKEND_URL"
    exit 0
fi

# Update or create .env.local in frontend
FRONTEND_ENV_FILE="/workspaces/f2-therapist-chatbot-frontend/.env.local"

echo "📝 Updating frontend configuration..."

# Backup existing file if it exists
if [ -f "$FRONTEND_ENV_FILE" ]; then
    cp "$FRONTEND_ENV_FILE" "$FRONTEND_ENV_FILE.backup"
    echo "   Backed up to: $FRONTEND_ENV_FILE.backup"
fi

# Create or update .env.local
{
    echo "# Auto-generated for Codespaces"
    echo "VITE_API_BASE_URL=$BACKEND_URL"
    echo "VITE_API_KEY=dev-key"
} > "$FRONTEND_ENV_FILE"

echo ""
echo "✅ Frontend .env.local updated!"
echo ""
echo "📋 Configuration applied:"
cat "$FRONTEND_ENV_FILE"
echo ""
echo "🚀 Next steps:"
echo "   1. Make sure backend is running: python -m uvicorn src.main:app --reload"
echo "   2. Stop and restart frontend: pnpm dev"
echo "   3. Visit: $FRONTEND_URL"
echo ""
