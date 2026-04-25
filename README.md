# Financial Therapist Chatbot Backend

**AI-powered financial therapy chatbot API with RAG** | Built with FastAPI, Google Gemini 3.1, & Pinecone

---

## 🎯 Overview

The Financial Therapist Chatbot is an intelligent conversational AI service that provides **empathetic financial guidance** and emotional support. It combines state-of-the-art RAG (Retrieval-Augmented Generation) with financial domain knowledge to help users navigate their financial journeys.

**What makes it special:**
- 🧠 **RAG-Powered**: Retrieves relevant knowledge base documents for context-aware responses
- 💬 **Emotionally Intelligent**: Recognizes and validates financial anxiety
- 📚 **Knowledge-Rich**: Trained on FAQs, scenarios, and therapy conversations
- ⚡ **Fast**: Sub-second responses using Gemini 3.1 Flash
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
- **UUID-based tracking** - Unique identifiers for users and conversations
- **Risk scoring** - Identifies conversations requiring escalation

### 🚀 **Performance & Reliability**
- **Fast inference** - Sub-second RAG retrieval + generation
- **Horizontal scalability** - Stateless architecture
- **Docker containerization** - Easy deployment
- **Health checks** - Readiness and liveness probes
- **Comprehensive logging** - Debug and monitor everything

