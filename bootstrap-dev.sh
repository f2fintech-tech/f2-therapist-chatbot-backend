#!/bin/bash
# ============================================================================
# Bootstrap Development Environment
# ============================================================================
# This script automates the setup for new developers/collaborators.
# It clones repos, installs dependencies, and configures environments.
#
# Usage:
#   bash bootstrap-dev.sh
#
# What it does:
#   1. Clone both backend and frontend repos (if not already cloned)
#   2. Install backend Python dependencies (venv)
#   3. Install frontend Node.js dependencies (pnpm)
#   4. Set up .env files from templates
#   5. Create handy run scripts
# ============================================================================

set -e  # Exit on first error

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  F2 Therapist Chatbot - Dev Bootstrap${NC}"
echo -e "${BLUE}========================================${NC}"

# ============================================================================
# Step 1: Detect if we're in the workspace
# ============================================================================
if [ ! -d "/workspaces" ]; then
    echo -e "${YELLOW}Warning: Not in GitHub Codespace (no /workspaces detected)${NC}"
    WORKSPACE_DIR="$HOME/workspace"
    mkdir -p "$WORKSPACE_DIR"
else
    WORKSPACE_DIR="/workspaces"
fi

echo -e "${GREEN}✓ Workspace directory: $WORKSPACE_DIR${NC}"

# ============================================================================
# Step 2: Clone repositories if not already present
# ============================================================================
echo ""
echo -e "${BLUE}Step 1: Cloning repositories...${NC}"

BACKEND_DIR="$WORKSPACE_DIR/f2-therapist-chatbot-backend"
FRONTEND_DIR="$WORKSPACE_DIR/f2-therapist-chatbot-frontend"

if [ ! -d "$BACKEND_DIR" ]; then
    echo "Cloning backend repo..."
    git clone https://github.com/f2fintech-tech/f2-therapist-chatbot-backend.git "$BACKEND_DIR"
    echo -e "${GREEN}✓ Backend cloned${NC}"
else
    echo -e "${GREEN}✓ Backend already cloned${NC}"
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Cloning frontend repo..."
    git clone https://github.com/f2fintech-tech/f2-therapist-chatbot-frontend.git "$FRONTEND_DIR"
    echo -e "${GREEN}✓ Frontend cloned${NC}"
else
    echo -e "${GREEN}✓ Frontend already cloned${NC}"
fi

# ============================================================================
# Step 3: Backend setup (Python venv)
# ============================================================================
echo ""
echo -e "${BLUE}Step 2: Setting up backend (Python)...${NC}"

cd "$BACKEND_DIR"

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

echo "Activating venv and installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Backend dependencies installed${NC}"

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Note: No .env found in backend. Using defaults from environment or .env.example${NC}"
    if [ -f ".env.example" ]; then
        echo "To configure backend, copy .env.example to .env and fill in your values:"
        echo "  cp .env.example .env"
    fi
fi

# ============================================================================
# Step 4: Frontend setup (Node.js)
# ============================================================================
echo ""
echo -e "${BLUE}Step 3: Setting up frontend (Node.js)...${NC}"

cd "$FRONTEND_DIR"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Installing Node.js via nvm..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 22
    echo -e "${GREEN}✓ Node.js installed${NC}"
else
    echo -e "${GREEN}✓ Node.js already installed ($(node -v))${NC}"
fi

# Check if pnpm is installed
if ! command -v pnpm &> /dev/null; then
    echo "Installing pnpm..."
    npm install -g pnpm > /dev/null 2>&1
    echo -e "${GREEN}✓ pnpm installed${NC}"
else
    echo -e "${GREEN}✓ pnpm already installed ($(pnpm -v))${NC}"
fi

echo "Installing frontend dependencies..."
pnpm install > /dev/null 2>&1
echo -e "${GREEN}✓ Frontend dependencies installed${NC}"

# Create .env from template if not present
FRONTEND_APP_DIR="$FRONTEND_DIR/artifacts/f2-finheal"
if [ ! -f "$FRONTEND_APP_DIR/.env" ] && [ -f "$FRONTEND_APP_DIR/.env.example" ]; then
    echo "Creating frontend .env from template..."
    cp "$FRONTEND_APP_DIR/.env.example" "$FRONTEND_APP_DIR/.env"
    echo -e "${GREEN}✓ Frontend .env created (using defaults)${NC}"
fi

# ============================================================================
# Step 5: Create convenient run scripts
# ============================================================================
echo ""
echo -e "${BLUE}Step 4: Creating convenience scripts...${NC}"

# Backend run script
cat > "$BACKEND_DIR/run-backend.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
EOF
chmod +x "$BACKEND_DIR/run-backend.sh"
echo -e "${GREEN}✓ Created run-backend.sh${NC}"

# Frontend run script
cat > "$FRONTEND_DIR/run-frontend.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/artifacts/f2-finheal"
export PORT=5173
export BASE_PATH=/
pnpm dev
EOF
chmod +x "$FRONTEND_DIR/run-frontend.sh"
echo -e "${GREEN}✓ Created run-frontend.sh${NC}"

# ============================================================================
# Step 6: Summary and next steps
# ============================================================================
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Bootstrap Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Quick start in two terminals:"
echo ""
echo -e "${YELLOW}Terminal 1 (Backend):${NC}"
echo "  cd $BACKEND_DIR"
echo "  bash run-backend.sh"
echo ""
echo -e "${YELLOW}Terminal 2 (Frontend):${NC}"
echo "  cd $FRONTEND_DIR"
echo "  bash run-frontend.sh"
echo ""
echo "Then open: http://localhost:5173"
echo ""
echo -e "${YELLOW}Documentation:${NC}"
echo "  Backend:  $BACKEND_DIR/README.md"
echo "  Frontend: $FRONTEND_DIR/artifacts/f2-finheal/README.dev.md"
echo "  Collab:   $BACKEND_DIR/CONTRIBUTING.md"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
