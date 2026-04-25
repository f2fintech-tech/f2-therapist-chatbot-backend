#!/bin/bash

# RAG Pipeline Quick Start Script
# This script sets up and runs the complete RAG pipeline

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     F2 THERAPIST - RAG PIPELINE QUICK START               ║"
echo "╚════════════════════════════════════════════════════════════╝"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}⚠ Python 3 is required but not installed${NC}"
    exit 1
fi

echo -e "\n${BLUE}[1/6] Checking Python environment...${NC}"
python3 --version

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${BLUE}[2/6] Creating virtual environment...${NC}"
    python3 -m venv venv
else
    echo -e "${GREEN}✓${NC} Virtual environment exists"
fi

# Activate virtual environment
echo -e "${BLUE}[3/6] Activating virtual environment...${NC}"
source venv/bin/activate

# Install/upgrade dependencies
echo -e "${BLUE}[4/6] Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
pip install google-generativeai

# Check environment variables
echo -e "${BLUE}[5/6] Checking environment configuration...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env file not found${NC}"
    echo -e "Create .env file with the following variables:"
    echo ""
    echo "  GEMINI_API_KEY=your-api-key"
    echo "  PINECONE_API_KEY=your-api-key"
    echo "  AWS_ACCESS_KEY_ID=your-key"
    echo "  AWS_SECRET_ACCESS_KEY=your-secret"
    echo "  AWS_REGION=us-east-1"
    echo "  S3_BUCKET_NAME=f2-fintech-kb"
    echo ""
    read -p "Continue without .env? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} .env file found"
fi

# Check raw data files
echo -e "${BLUE}[6/6] Checking data files...${NC}"

DATA_FILES=(
    "src/data/raw/conversations.json"
    "src/data/raw/FAQs_raw.json"
    "src/data/raw/scenarios_raw.json"
    "src/data/raw/system_prompt_raw.md"
)

for file in "${DATA_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${YELLOW}⚠${NC} $file (not found)"
    fi
done

echo -e "\n${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   RAG Pipeline is ready to run!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

echo ""
echo "Quick start options:"
echo ""
echo "  1. Run full pipeline (with S3):"
echo "     python src/rag_pipeline.py"
echo ""
echo "  2. Run pipeline without S3 (local only):"
echo "     python src/rag_pipeline.py --skip-s3-upload --skip-s3-download"
echo ""
echo "  3. Test data processing:"
echo "     python -c \"from src.knowledge.data_processor import DataProcessor; DataProcessor().process_all()\""
echo ""
echo "  4. Test chatbot:"
echo "     python src/inference/predictor.py"
echo ""
echo "  5. View documentation:"
echo "     cat RAG_PIPELINE.md"
echo ""

# Ask if user wants to run the pipeline
read -p "Run RAG pipeline now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}Starting RAG Pipeline...${NC}"
    echo ""
    cd src
    python rag_pipeline.py --skip-s3-upload --skip-s3-download
    cd ..
fi
