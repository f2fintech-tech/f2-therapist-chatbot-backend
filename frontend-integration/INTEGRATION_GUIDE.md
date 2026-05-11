# React Frontend Integration Guide

This guide explains how to integrate the Financial Therapist Chatbot backend with your React frontend.

## 📋 Quick Start

### 1. Copy Files to Your React Project

Copy these files to your React project's `src/` directory:

```
src/
  ├── hooks/
  │   └── useChatbot.ts
  ├── services/
  │   └── chatbotApi.ts
  └── components/
      └── ChatInterface.tsx
```

### 2. Install Dependencies

Make sure you have `uuid` installed for generating unique user IDs:

```bash
npm install uuid
npm install --save-dev @types/uuid  # if using TypeScript
```

### 3. Set Environment Variables

Create a `.env` file in your React project root:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_API_KEY=dev-key
```

For production:
```env
VITE_API_BASE_URL=https://your-production-api.com/api/v1
VITE_API_KEY=your-production-api-key
```

### 4. Use in Your App

Import and use the `ChatInterface` component:

```tsx
import ChatInterface from './components/ChatInterface';

function App() {
  return (
    <div>
      <ChatInterface />
    </div>
  );
}

export default App;
```

Or use the hook directly for custom UI:

```tsx
import { useChatbot } from './hooks/useChatbot';
import { useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';

function MyChat() {
  const userId = uuidv4();
  const [state, actions] = useChatbot(userId);

  useEffect(() => {
    actions.checkHealth();
  }, []);

  return (
    <div>
      <button onClick={() => actions.createConversation('New Chat')}>
        Start Chat
      </button>
      <button onClick={(e) => actions.sendMessage('Hello!')}>
        Send Test Message
      </button>
    </div>
  );
}
```

## 🔌 API Endpoints

### Chat
- **POST** `/api/v1/chat`
  - Send a message and get a response
  - Body: `{ message, user_id, conversation_id? }`

### Conversations
- **GET** `/api/v1/conversations?user_id={userId}`
  - List all conversations for a user
- **POST** `/api/v1/conversations`
  - Create new conversation
- **GET** `/api/v1/conversations/{conversationId}`
  - Get conversation with messages
- **DELETE** `/api/v1/conversations/{conversationId}`
  - Delete a conversation

### Personalization
- **GET** `/api/v1/personalization/preferences?user_id={userId}`
  - Get user preferences and persona
- **POST** `/api/v1/personalization/preferences`
  - Update user preferences
- **GET** `/api/v1/personalization/personas`
  - List available personas

### Health
- **GET** `/health`
  - Backend health check

## 🛠️ Backend Configuration

The backend is configured to accept requests from:
- `http://localhost:3000` (React default port)
- `http://localhost:5173` (Vite default port)
- `http://localhost:8000` (backend dev server)

**To use the API, you need an API key.**

Check with the backend team for your API key, or set it in the environment variables.

## 🔒 Security

- All API calls require an `Authorization: Bearer {API_KEY}` header
- Messages are sanitized server-side
- Rate limiting: 200 requests/minute per IP
- CORS is configured for frontend origins

## 📊 Response Examples

### Chat Response
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": "That's a great question about your emergency fund...",
  "emotion_detected": "concerned",
  "mood_score": 0.65,
  "references": [
    {
      "source": "emergency_fund_guide.md",
      "content": "An emergency fund should cover 3-6 months of expenses..."
    }
  ]
}
```

### Conversation History
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:45:00Z",
  "title": "Emergency Fund Discussion",
  "preview": "User asked about emergency fund strategies...",
  "messages": [
    {
      "role": "user",
      "message": "How should I build an emergency fund?",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "role": "assistant",
      "message": "That's a great question...",
      "timestamp": "2024-01-15T10:30:05Z"
    }
  ]
}
```

## 🧪 Testing the Integration

### 1. Start Both Servers

**Backend:**
```bash
cd /workspaces/f2-therapist-chatbot-backend
./RUN_CHATBOT_TERMINAL.sh
# Or: python -m uvicorn src.main:app --reload
```

**Frontend (React):**
```bash
cd your-frontend-repo
npm run dev
```

### 2. Test Health Check

Open your browser console and run:
```javascript
const api = 'http://localhost:8000/api/v1';
const key = 'dev-key';

fetch(`${api.replace('/api/v1', '')}/health`)
  .then(r => r.json())
  .then(d => console.log('Health:', d))
  .catch(e => console.error('Error:', e));
```

### 3. Test Chat Endpoint

```javascript
const userId = '550e8400-e29b-41d4-a716-446655440001';

fetch('http://localhost:8000/api/v1/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer dev-key'
  },
  body: JSON.stringify({
    message: 'Hello, how can I improve my financial health?',
    user_id: userId
  })
})
  .then(r => r.json())
  .then(d => console.log('Response:', d))
  .catch(e => console.error('Error:', e));
```

## 🐛 Troubleshooting

### CORS Error
If you see: `Access to XMLHttpRequest from origin blocked by CORS policy`

**Solution:** Make sure your frontend URL is in `ALLOWED_ORIGINS` in the backend `.env`:
```env
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
```

Then restart the backend server.

### 401 Unauthorized
If you see: `401: Unauthorized`

**Solution:** Ensure you're sending the correct API key:
```javascript
headers: {
  'Authorization': 'Bearer your-api-key'
}
```

### Failed to Connect
If the API is unreachable:

1. Check backend is running: `http://localhost:8000/health`
2. Check ALLOWED_ORIGINS includes your frontend URL
3. Check firewall/network settings
4. Check API_BASE_URL is correct in `.env`

## 📚 Advanced Usage

### Custom Persona

```typescript
const [state, actions] = useChatbot(userId);

// Get available personas
const personas = await chatbotApi.getPersonas();

// Set user's preferred persona
await chatbotApi.updateUserPreferences(userId, {
  preferred_persona: 'financial_advisor'
});
```

### Conversation History

```typescript
// Get all conversations
const conversations = await chatbotApi.getConversations(userId);

// Load a previous conversation
await actions.loadConversation(conversationId);

// Delete a conversation
await actions.deleteConversation(conversationId);
```

### Error Handling

```typescript
const [state, actions] = useChatbot(userId);

try {
  await actions.sendMessage('Hello');
} catch (error) {
  console.error('Chat failed:', error);
  // Handle error in state.error
}

// Clear error
actions.clearError();
```

## 🚀 Deployment

### Frontend
1. Build: `npm run build`
2. Deploy to your hosting (Vercel, Netlify, etc.)
3. Update environment variables with production API URL

### Backend
The backend is already configured for production. Update:
```env
ENVIRONMENT=production
ALLOWED_ORIGINS=https://your-frontend-domain.com
ALLOWED_HOSTS=your-backend-domain.com
```

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the backend logs: `docker logs chatbot-backend`
3. Check the frontend console for errors
4. Contact the backend team with API key requests
