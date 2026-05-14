#!/bin/bash
# Test to verify the fix for Codespaces backend connectivity

echo "========================================"
echo "CODESPACES BACKEND CONNECTIVITY TEST"
echo "========================================"
echo ""

# Extract Codespaces info from current frontend URL
FRONTEND_DOMAIN=$(echo "redesigned-chainsaw-pj6x7w7vv99w29r4p-5173.app.github.dev" | sed 's/-5173.app.github.dev//g')
BACKEND_URL="https://${FRONTEND_DOMAIN}-8000.app.github.dev"

echo "Frontend Domain: redesigned-chainsaw-pj6x7w7vv99w29r4p"
echo "Expected Backend URL: $BACKEND_URL"
echo ""
echo "Step 1: Test if backend is accessible"
echo "Command: curl -s -o /dev/null -w '%{http_code}' $BACKEND_URL/"
echo ""
echo "Step 2: Check CORS headers"
echo "Command: curl -i -X OPTIONS -H 'Origin: https://redesigned-chainsaw-pj6x7w7vv99w29r4p-5173.app.github.dev' $BACKEND_URL/api/v1/chat"
echo ""
echo "Step 3: Test chat endpoint"
echo "Command: curl -X POST $BACKEND_URL/api/v1/chat \\
  -H 'Content-Type: application/json' \\
  -H 'Origin: https://redesigned-chainsaw-pj6x7w7vv99w29r4p-5173.app.github.dev' \\
  -d '{\"message\": \"test\", \"user_id\": \"550e8400-e29b-41d4-a716-446655440000\"}'"
echo ""
echo "========================================"
echo "INSTRUCTIONS:"
echo "========================================"
echo "1. Copy and run Step 1, 2, and 3 commands in your terminal"
echo "2. Share the results"
echo "3. Confirm backend is accessible via Codespaces URL"
