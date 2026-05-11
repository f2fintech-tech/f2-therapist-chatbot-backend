#!/bin/bash

# Frontend-Backend Integration Setup Script
# This script helps you set up the chatbot integration with your React frontend

set -e

echo "🚀 Financial Therapist Chatbot - Frontend Integration Setup"
echo "=========================================================="
echo ""

# Check if we're in the right directory
if [ ! -f "src/main.py" ]; then
    echo "❌ Error: This script must be run from the backend root directory"
    echo "   which should contain src/main.py"
    exit 1
fi

echo "✅ Backend directory detected"
echo ""

# Check Python environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "✅ Virtual environment found/created"
echo ""

# Activate virtual environment
source .venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Check dependencies
if [ ! -f "requirements.txt" ]; then
    echo "⚠️  requirements.txt not found"
else
    echo "📦 Installing/updating dependencies..."
    pip install -r requirements.txt > /dev/null 2>&1
    echo "✅ Dependencies installed"
fi

echo ""
echo "=========================================================="
echo "✅ Backend Setup Complete!"
echo "=========================================================="
echo ""

echo "📝 Next Steps:"
echo ""
echo "1️⃣  COPY FILES TO YOUR REACT PROJECT:"
echo "   copy frontend-integration/chatbotApi.ts → your-frontend/src/services/"
echo "   copy frontend-integration/useChatbot.ts → your-frontend/src/hooks/"
echo "   copy frontend-integration/ChatInterface.tsx → your-frontend/src/components/"
echo ""

echo "2️⃣  INSTALL DEPENDENCIES IN YOUR REACT PROJECT:"
echo "   npm install uuid"
echo ""

echo "3️⃣  CREATE .env FILE IN YOUR REACT PROJECT:"
echo "   VITE_API_BASE_URL=http://localhost:8000/api/v1"
echo "   VITE_API_KEY=dev-key"
echo ""

echo "4️⃣  START THE BACKEND (in new terminal):"
echo "   cd /workspaces/f2-therapist-chatbot-backend"
echo "   source .venv/bin/activate"
echo "   python -m uvicorn src.main:app --reload"
echo ""

echo "5️⃣  START YOUR REACT FRONTEND (in another terminal):"
echo "   cd your-frontend-repo"
echo "   npm run dev"
echo ""

echo "6️⃣  TEST THE INTEGRATION:"
echo "   • Open http://localhost:5173"
echo "   • Use ChatInterface component"
echo "   • Check browser console for any errors"
echo ""

echo "=========================================================="
echo "📚 For detailed instructions, see:"
echo "   frontend-integration/README.md"
echo "   frontend-integration/INTEGRATION_GUIDE.md"
echo "=========================================================="
echo ""
echo "🎉 You're all set! Happy coding!"
