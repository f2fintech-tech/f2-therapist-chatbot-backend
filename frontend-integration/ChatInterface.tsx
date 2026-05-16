/**
 * ChatInterface Component
 * Example React component showing how to use the useChatbot hook
 */

import { useState, useEffect, useRef } from 'react';
import { useChatbot } from './useChatbot';
import { v4 as uuidv4 } from 'uuid';
import QuizPopup from './components/QuizPopup/QuizPopup';

export default function ChatInterface() {
  const [userId] = useState(() => uuidv4());
  const [inputValue, setInputValue] = useState('');
  const [showQuizPopup, setShowQuizPopup] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [state, actions] = useChatbot(userId);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      if (!window.localStorage.getItem('finheal_quiz_completed')) {
        setShowQuizPopup(true);
      }
    }, 1200);

    return () => window.clearTimeout(timeout);
  }, []);

  const handleQuizComplete = (tierName: string, score: number) => {
    window.localStorage.setItem('finheal_quiz_completed', 'true');
    window.localStorage.setItem('finheal_user_tier', tierName);
    window.localStorage.setItem('finheal_quiz_score', String(score));
    setShowQuizPopup(false);
  };

  // Check backend health on mount
  useEffect(() => {
    actions.checkHealth();
  }, [actions]);

  // Auto scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [state.messages]);

  // Handle message submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    // Create conversation if needed
    if (!state.conversationId) {
      await actions.createConversation('Chat Session');
    }

    await actions.sendMessage(inputValue);
    setInputValue('');
  };

  return (
    <>
      <QuizPopup
        visible={showQuizPopup}
        onDismiss={() => setShowQuizPopup(false)}
        onComplete={handleQuizComplete}
      />
      <div style={styles.container}>
        <div style={styles.header}>
        <h1>Financial Therapist Chatbot</h1>
        <div style={styles.status}>
          <span style={styles.healthBadge(state.isHealthy)}>
            {state.isHealthy ? '✓ Backend Connected' : '✗ Backend Offline'}
          </span>
        </div>
      </div>

      <div style={styles.messagesContainer}>
        {state.messages.length === 0 && (
          <div style={styles.emptyState}>
            <p>Start a conversation about your financial wellbeing...</p>
          </div>
        )}

        {state.messages.map((msg) => (
          <div key={msg.id} style={styles.messageWrapper(msg.role)}>
            <div style={styles.message(msg.role)}>
              <p style={styles.messageContent}>{msg.content}</p>
              {msg.emotion && (
                <small style={styles.metadata}>
                  Detected emotion: {msg.emotion} {msg.moodScore && `(${(msg.moodScore * 100).toFixed(0)}%)`}
                </small>
              )}
              <small style={styles.timestamp}>
                {new Date(msg.timestamp).toLocaleTimeString()}
              </small>
            </div>
          </div>
        ))}

        {state.isLoading && <div style={styles.typingIndicator}>Thinking...</div>}

        {state.error && (
          <div style={styles.errorMessage}>
            <p>⚠️ {state.error}</p>
            <button onClick={actions.clearError} style={styles.button}>
              Dismiss
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} style={styles.inputForm}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type your message..."
          disabled={state.isLoading || !state.isHealthy}
          style={styles.input}
        />
        <button
          type="submit"
          disabled={state.isLoading || !inputValue.trim() || !state.isHealthy}
          style={styles.sendButton}
        >
          {state.isLoading ? 'Sending...' : 'Send'}
        </button>
        {state.conversationId && (
          <button
            type="button"
            onClick={() => actions.createConversation('New Chat')}
            style={styles.newChatButton}
          >
            New Chat
          </button>
        )}
      </form>
    </div>
  );
}

const styles: Record<string, any> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#f5f5f5',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },
  header: {
    padding: '20px',
    backgroundColor: '#fff',
    borderBottom: '1px solid #e0e0e0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  status: {
    display: 'flex',
    gap: '10px',
  },
  healthBadge: (isHealthy: boolean) => ({
    padding: '6px 12px',
    borderRadius: '20px',
    fontSize: '14px',
    fontWeight: 'bold',
    backgroundColor: isHealthy ? '#d4edda' : '#f8d7da',
    color: isHealthy ? '#155724' : '#721c24',
  }),
  messagesContainer: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  emptyState: {
    textAlign: 'center' as const,
    color: '#999',
    marginTop: '40px',
  },
  messageWrapper: (role: 'user' | 'assistant') => ({
    display: 'flex',
    justifyContent: role === 'user' ? 'flex-end' : 'flex-start',
  }),
  message: (role: 'user' | 'assistant') => ({
    maxWidth: '70%',
    padding: '12px 16px',
    borderRadius: '12px',
    backgroundColor: role === 'user' ? '#007bff' : '#fff',
    color: role === 'user' ? '#fff' : '#333',
    borderLeft: role === 'user' ? 'none' : '4px solid #007bff',
    boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
  }),
  messageContent: {
    margin: '0 0 8px 0',
    lineHeight: '1.4',
  },
  metadata: {
    opacity: 0.7,
    fontSize: '12px',
    display: 'block',
  },
  timestamp: {
    opacity: 0.6,
    fontSize: '11px',
    marginTop: '4px',
    display: 'block',
  },
  typingIndicator: {
    padding: '12px',
    color: '#999',
    fontStyle: 'italic' as const,
  },
  errorMessage: {
    padding: '12px 16px',
    backgroundColor: '#f8d7da',
    color: '#721c24',
    borderRadius: '8px',
    borderLeft: '4px solid #f5c6cb',
  },
  inputForm: {
    display: 'flex',
    gap: '10px',
    padding: '20px',
    backgroundColor: '#fff',
    borderTop: '1px solid #e0e0e0',
  },
  input: {
    flex: 1,
    padding: '12px',
    border: '1px solid #ddd',
    borderRadius: '6px',
    fontSize: '14px',
    '&:focus': {
      outline: 'none',
      borderColor: '#007bff',
    },
  },
  sendButton: {
    padding: '12px 24px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    fontWeight: 'bold',
    cursor: 'pointer',
    '&:disabled': {
      opacity: 0.6,
      cursor: 'not-allowed',
    },
  },
  newChatButton: {
    padding: '12px 16px',
    backgroundColor: '#6c757d',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    '&:disabled': {
      opacity: 0.6,
      cursor: 'not-allowed',
    },
  },
  button: {
    padding: '6px 12px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    marginTop: '8px',
  },
};
