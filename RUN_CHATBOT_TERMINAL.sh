#!/usr/bin/env bash
set -euo pipefail

# Interactive chatbot launcher for collaborators.
# Usage:
#   bash RUN_CHATBOT_TERMINAL.sh
#
# What it does:
# 1. Moves to the repo root
# 2. Activates the local virtual environment if present
# 3. Starts the chatbot REPL
#
# Chat mode defaults to one generation call per message to keep API usage low.
# To enable RAG context in chat mode, pass:
#   python -m src.model.model_test --chat --chat-rag

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"s

echo "============================================================"
echo "F2 Therapist Chatbot - Terminal Launcher"
echo "============================================================"

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
  echo "✓ Virtual environment activated"
else
  echo "⚠ .venv not found. Using system Python."
fi

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "⚠ .env file not found. Make sure GEMINI_API_KEY and PINECONE_API_KEY are set."
fi

echo "Starting interactive chatbot..."
echo "Type 'exit' to quit."
echo ""

python -m src.model.model_test --chat
