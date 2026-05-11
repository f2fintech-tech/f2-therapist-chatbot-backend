# Frontend Integration - Quick Setup

This directory contains everything you need to connect your React frontend to the Financial Therapist Chatbot backend.

## 📂 Files Included

- **`chatbotApi.ts`** - API client for backend communication
- **`useChatbot.ts`** - React hook for managing chat state
- **`ChatInterface.tsx`** - Example chat UI component (ready to use!)
- **`integrationTest.ts`** - Test script to verify connection
- **`.env.example`** - Environment variables template
- **`INTEGRATION_GUIDE.md`** - Full documentation

## 🚀 Quick Start (5 minutes)

### Step 1: Copy Files to Your React Project
```bash
# From your React project root:
cp -r frontend-integration/chatbotApi.ts src/services/
cp -r frontend-integration/useChatbot.ts src/hooks/
cp -r frontend-integration/ChatInterface.tsx src/components/
```

### Step 2: Install Dependency
```bash
npm install uuid
npm install --save-dev @types/uuid  # if using TypeScript
```

### Step 3: Create `.env` File
Create `.env` in your React project root:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_API_KEY=dev-key
```

### Step 4: Use in Your App
```tsx
import ChatInterface from './components/ChatInterface';

export default function App() {
  return <ChatInterface />;
}
```

### Step 5: Test the Connection

Run your React app with `npm run dev`, then open the browser console and run:

```javascript
import { runIntegrationTest } from './integrationTest';
runIntegrationTest();
```

Or test via curl:
```bash
curl http://localhost:8000/health
```

## 📋 Backend Requirements

Make sure the backend is running:
```bash
./RUN_CHATBOT_TERMINAL.sh
# or: python -m uvicorn src.main:app --reload
```

Check that `.env` includes your frontend:
```env
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
```

## 🔑 Getting an API Key

Ask your backend team for an API key, or use the dev key for local testing:
```env
VITE_API_KEY=dev-key
```

## 🎯 What You Can Do

✅ Send messages to the chatbot  
✅ Get responses with emotion detection  
✅ Create and manage conversations  
✅ Retrieve conversation history  
✅ Set user preferences and personas  
✅ A/B test different chat responses  

## 📖 Available API Hooks

```typescript
// Use the useChatbot hook
const [state, actions] = useChatbot(userId);

// State properties
state.messages          // Array of chat messages
state.conversationId    // Current conversation ID
state.isLoading        // Loading indicator
state.error            // Error message if any
state.isHealthy        // Backend connection status

// Available actions
actions.sendMessage(message)              // Send a chat message
actions.createConversation(title?)        // Start a new conversation
actions.loadConversation(conversationId)  // Load previous conversation
actions.deleteConversation(conversationId) // Delete a conversation
actions.clearMessages()                    // Clear all messages
actions.clearError()                       // Clear error message
actions.checkHealth()                      // Check backend status
```

## 🔗 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send message & get response |
| GET | `/api/v1/conversations` | List conversations |
| POST | `/api/v1/conversations` | Create new conversation |
| GET | `/api/v1/conversations/{id}` | Get conversation details |
| DELETE | `/api/v1/conversations/{id}` | Delete conversation |
| GET | `/api/v1/personalization/preferences` | Get user preferences |
| POST | `/api/v1/personalization/preferences` | Update preferences |
| GET | `/api/v1/personalization/personas` | List available personas |
| GET | `/health` | Backend health check |

## 🛠️ Example: Custom Chat Component

```tsx
import { useChatbot } from './hooks/useChatbot';
import { v4 as uuidv4 } from 'uuid';

export default function MyChat() {
  const userId = uuidv4();
  const [state, actions] = useChatbot(userId);

  return (
    <div>
      <h1>Chat with Financial Therapist</h1>
      
      {/* Show status */}
      <p>Status: {state.isHealthy ? '✓ Connected' : '✗ Offline'}</p>
      
      {/* Show messages */}
      <div className="messages">
        {state.messages.map(msg => (
          <div key={msg.id} className={msg.role}>
            <p>{msg.content}</p>
            {msg.emotion && <small>Emotion: {msg.emotion}</small>}
          </div>
        ))}
      </div>

      {/* Show error if any */}
      {state.error && <p className="error">{state.error}</p>}

      {/* Input form */}
      <form onSubmit={(e) => {
        e.preventDefault();
        const input = e.currentTarget.elements[0] as HTMLInputElement;
        actions.sendMessage(input.value);
        input.value = '';
      }}>
        <input 
          type="text" 
          placeholder="Type your message..."
          disabled={state.isLoading || !state.isHealthy}
        />
        <button type="submit" disabled={state.isLoading}>Send</button>
      </form>
    </div>
  );
}
```

## 🧪 Testing Checklist

- [ ] Backend running on `http://localhost:8000`
- [ ] React running on `http://localhost:5173`
- [ ] CORS configured with `http://localhost:5173`
- [ ] `.env` file created with API keys
- [ ] Files copied to your React project
- [ ] `uuid` package installed
- [ ] ChatInterface component renders without errors
- [ ] Health check passes
- [ ] Can send a message and get a response

## ❓ Common Issues

### CORS Error
**Problem:** `Access to XMLHttpRequest ... blocked by CORS policy`

**Solution:** 
1. Check backend `.env`: `ALLOWED_ORIGINS=http://localhost:5173`
2. Restart backend server
3. Check frontend is actually on port 5173

### 401 Unauthorized
**Problem:** `Authorization required`

**Solution:**
1. Check `.env`: `VITE_API_KEY=dev-key`
2. Verify API key matches backend configuration

### Cannot Connect
**Problem:** `Failed to fetch` or timeout

**Solution:**
1. Is backend running? Check `http://localhost:8000`
2. Is frontend on correct port? Check browser tab URL
3. Check firewall settings
4. Try: `curl -i http://localhost:8000/health`

## 📚 More Info

See `INTEGRATION_GUIDE.md` for:
- Detailed API documentation
- All endpoint descriptions
- Advanced usage examples
- Deployment instructions
- Troubleshooting guide

## 🎓 Learning Path

1. **Get it working:** Follow Quick Start above
2. **Understand the hook:** Read useChatbot.ts
3. **Customize:** Copy ChatInterface.tsx and modify
4. **Advanced:** Read INTEGRATION_GUIDE.md for complex features

## 💬 Support

If you run into issues:
1. Check the troubleshooting section above
2. Read INTEGRATION_GUIDE.md
3. Review backend logs: Check if server is running and responding
4. Test in terminal: `curl http://localhost:8000/health`
5. Check browser console for error messages

---

**Happy integrating! 🎉**
