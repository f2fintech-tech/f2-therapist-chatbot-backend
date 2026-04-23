# Financial Therapist Chatbot Backend

**AI-powered financial therapy chatbot API** | Built with FastAPI & Google Gemini 3.1

---

## 🎯 Overview

The Financial Therapist Chatbot is an intelligent conversational AI service that provides **empathetic financial guidance** and emotional support. It combines state-of-the-art natural language processing with deep financial domain knowledge to help users navigate their financial journeys.

**Live API Base URL:** `https://api.f2fintech.com/api/v1` (Coming Soon)

---

## ✨ Key Features

### 💬 **Conversational Intelligence**
- **Multi-turn conversations** - Maintains context across multiple exchanges
- **Emotional awareness** - Recognizes and responds to financial stress and anxiety
- **Natural dialogue** - Conversational, human-like responses (not robotic)
- **Financial expertise** - Deep knowledge of loans, credit scores, EMI, and personal finance

### 🔒 **Enterprise-Grade Security**
- **Input validation & sanitization** - Protects against injection attacks
- **Rate limiting** - 100 requests per minute per IP to prevent abuse
- **Request logging** - Full audit trail of all API interactions
- **Security monitoring** - Real-time threat detection and alerting
- **CORS protection** - Configurable cross-origin policies

### 📊 **Conversation Management**
- **Persistent storage** - All conversations saved in PostgreSQL
- **Conversation history** - Retrieve past conversations with full message history
- **UUID-based tracking** - Unique identifiers for users and conversations
- **Timestamp tracking** - Know when conversations started and were updated

### 🚀 **Performance & Reliability**
- **Fast inference** - Sub-second response times with Gemini 3.1 Flash
- **Horizontal scalability** - Stateless architecture designed for scaling
- **Docker containerization** - Easy deployment to any platform
- **Health checks** - Built-in readiness and liveness probes

---

## 📚 API Documentation

### **Base URL**
