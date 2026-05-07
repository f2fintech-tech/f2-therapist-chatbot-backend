# Financial Therapist Chatbot Backend

**AI-powered financial therapy chatbot API with RAG** | Built with FastAPI, Google Gemini 3.1, & Pinecone

---

## 🎯 Overview

The Financial Therapist Chatbot is an intelligent conversational AI service that provides **empathetic financial guidance** and emotional support. It combines state-of-the-art RAG (Retrieval-Augmented Generation) with financial domain knowledge to help users navigate their financial journeys.

**What makes it special:**
- 🧠 **RAG-Powered**: Retrieves relevant knowledge base documents for context-aware responses
- 💬 **Emotionally Intelligent**: Recognizes and validates financial anxiety
- 📚 **Knowledge-Rich**: Trained on FAQs, scenarios, and therapy conversations
- ⚡ **Fast**: Sub-second responses using Gemini 3.1 Flash preview
- 🔒 **Secure**: Enterprise-grade security with full audit trails

---

## ✨ Key Features

### 💬 **Conversational Intelligence with RAG**
- **Multi-turn conversations** - Maintains context across multiple exchanges
- **Semantic search** - Retrieves relevant KB documents via Pinecone vector DB
- **Context augmentation** - Enriches responses with domain knowledge
- **Emotional awareness** - Recognizes and responds to financial stress
- **Natural dialogue** - Conversational, human-like responses

### 📚 **Knowledge Base Management**
- **S3 Storage** - Upload and download KB files from AWS S3
- **Vector Indexing** - Pinecone VectorDB with 768-dimensional embeddings
- **Smart Retrieval** - Top-3 semantic similarity search
- **Metadata Tracking** - Category, tags, and relevance scoring
- **Auto-Processing** - Raw data → processed → embedded → indexed

### 🔒 **Enterprise-Grade Security**
- **Input validation & sanitization** - Protects against injection attacks
- **Rate limiting** - 100 requests per minute per IP
- **Request logging** - Full audit trail of interactions
- **API key management** - Secure credential handling
- **CORS protection** - Configurable cross-origin policies

### 📊 **Conversation Management**
- **Persistent storage** - All conversations saved in PostgreSQL
- **Conversation history** - Retrieve past conversations with full context
- **Sidebar-ready chat list** - Fetch previous chats with title, preview, and latest activity metadata
- **Resume support** - Restore a conversation thread with its recent messages after refresh or switch
- **UUID-based tracking** - Unique identifiers for users and conversations
- **Risk scoring** - Identifies conversations requiring escalation

### 🚀 **Performance & Reliability**
- **Fast inference** - Sub-second RAG retrieval + generation
- **Horizontal scalability** - Stateless architecture
- **Docker containerization** - Easy deployment
- **Health checks** - Readiness and liveness probes
- **Comprehensive logging** - Debug and monitor everything

---

## 🔐 Environment Variables

This project expects the following environment variables to be set in local development and/or production:

### ==================== ENVIRONMENT ====================
- `ENVIRONMENT` - App environment such as `development` or `production`

### ==================== APPLICATION ====================
- `APP_ENV` - Runtime app environment label

### ==================== SERVER ====================
- `HOST` - Host interface used by the API server
- `PORT` - Port used by the API server
- `LOG_LEVEL` - Logging level such as `info` or `debug`

### ==================== CORS ====================
- `ALLOWED_ORIGINS` - Comma-separated list of allowed CORS origins
- `ALLOWED_HOSTS` - Comma-separated list of allowed hostnames for production
- `CORS_ORIGINS` - Additional CORS origin configuration used by workflow/environment setup

### ==================== MONITORING & ALERTS ====================
- `SLACK_WEBHOOK_URL` - Optional Slack incoming webhook for monitor workflow alerts

### ==================== GOOGLE GEMINI API ====================
- `GEMINI_API_KEY` - Google Gemini API key used for generation and embeddings

### ==================== PINECONE VECTOR DB ====================
- `PINECONE_API_KEY` - Pinecone API key used for vector search and index operations

### ==================== AWS S3 ====================
- `AWS_ACCESS_KEY_ID` - AWS access key used for S3 operations
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key used for S3 operations
- `AWS_REGION` - AWS region for S3 and other AWS services
- `AWS_S3_BUCKET_NAME` - S3 bucket used for knowledge base and model artifacts

### ==================== DATABASE ====================
- `DATABASE_URL` - PostgreSQL connection string
- `POSTGRES_USER` - PostgreSQL username
- `POSTGRES_DB` - PostgreSQL database name

### ==================== LOGGING ====================
- `SQL_ECHO` - Enables SQLAlchemy SQL logging when set appropriately

> Tip: In production, keep secret values in GitHub Secrets or your deployment platform's secret store, not in source control.

---

## 🤖 GitHub Actions Secrets and Variables

The GitHub workflows in `.github/workflows/` use both **Secrets** and **Repository Variables**.

### Add these as GitHub Secrets
- `GEMINI_API_KEY`
- `PINECONE_API_KEY`
- `DATABASE_URL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `SLACK_WEBHOOK_URL` (optional, only needed if Slack alerts are enabled)

### Add these as GitHub Variables
- `ENVIRONMENT`
- `APP_ENV`
- `HOST`
- `PORT`
- `LOG_LEVEL`
- `ALLOWED_ORIGINS`
- `ALLOWED_HOSTS`
- `CORS_ORIGINS`
- `POSTGRES_USER`
- `POSTGRES_DB`
- `AWS_REGION`
- `AWS_S3_BUCKET_NAME`
- `SQL_ECHO`

### Where they are used
- `GEMINI_API_KEY` and `PINECONE_API_KEY` are used by the chatbot, training, evaluation, and monitoring jobs.
- `DATABASE_URL` is used by the API and persistence layers.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `AWS_S3_BUCKET_NAME` are used for S3 upload/download steps.
- `ALLOWED_ORIGINS` and `ALLOWED_HOSTS` are used in `src/main.py` for security and browser access control.
- `SLACK_WEBHOOK_URL` is used by `.github/workflows/6-monitor-pipeline.yml` for optional alert notifications.

### How to add them in GitHub
1. Open your repository on GitHub.
2. Go to `Settings`.
3. Select `Secrets and variables`.
4. Add the values under either `Actions secrets` or `Actions variables`.
5. Save each value carefully and keep production values separate from development values.

---

## 🪝 Pre-commit Hooks

This repository includes a pre-commit configuration in [`.pre-commit-config.yaml`](.pre-commit-config.yaml) so contributors can catch common issues before committing.

### What it checks
- Trailing whitespace
- Missing final newline / end-of-file cleanup
- YAML syntax
- Oversized files
- Ruff lint checks for Python syntax and error-prone patterns

### How to enable it locally
1. Install the project dependencies.
2. Run `pre-commit install` once in the repository.
3. Commit as usual; the hooks will run automatically before each commit.

### Useful manual commands
- `pre-commit run --all-files` to check the entire repository
- `pre-commit run --files <path>` to test specific files

> Tip: Secrets are masked in GitHub Actions logs. Variables are visible in workflow configuration, so only store non-sensitive values there.
