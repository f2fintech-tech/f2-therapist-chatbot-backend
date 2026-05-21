/**
 * useChatbot Hook
 * React hook for managing chatbot interactions
 */

import { useState, useCallback, useRef } from 'react';
import { chatbotApi, ChatResponse, ConversationHistory } from './chatbotApi';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  emotion?: string;
  moodScore?: number;
  wellnessScore?: number;
  wellnessTier?: string;
  momentumScore?: number;
}

export interface UseChatbotState {
  messages: ChatMessage[];
  conversationId: string | null;
  isLoading: boolean;
  error: string | null;
  isHealthy: boolean;
}

export interface UseChatbotActions {
  sendMessage: (message: string) => Promise<void>;
  createConversation: (title?: string) => Promise<void>;
  loadConversation: (conversationId: string) => Promise<void>;
  deleteConversation: (conversationId: string) => Promise<void>;
  clearMessages: () => void;
  clearError: () => void;
  checkHealth: () => Promise<void>;
}

export function useChatbot(userId: string): [UseChatbotState, UseChatbotActions] {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isHealthy, setIsHealthy] = useState(false);
  const messageIdRef = useRef(0);

  // Generate unique message ID
  const generateMessageId = useCallback(() => {
    return `msg-${userId}-${++messageIdRef.current}-${Date.now()}`;
  }, [userId]);

  // Send a message
  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim()) return;

      setIsLoading(true);
      setError(null);

      try {
        // Add user message to UI immediately
        const userMessage: ChatMessage = {
          id: generateMessageId(),
          role: 'user',
          content: message,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, userMessage]);

        // Send to API
        const response = await chatbotApi.sendMessage(
          message,
          userId,
          conversationId || undefined
        );

        // Update conversation ID if new
        if (response.conversation_id && !conversationId) {
          setConversationId(response.conversation_id);
        }

        // Add assistant response
        const assistantMessage: ChatMessage = {
          id: generateMessageId(),
          role: 'assistant',
          content: response.response,
          timestamp: new Date().toISOString(),
          emotion: response.emotion_detected,
          moodScore: response.mood_score,
          wellnessScore: response.wellness?.wellnessScore,
          wellnessTier: response.wellness?.wellnessTier,
          momentumScore: response.wellness?.momentumScore,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message');
        console.error('Chat error:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [userId, conversationId, generateMessageId]
  );

  // Create new conversation
  const createConversation = useCallback(
    async (title?: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const conversation = await chatbotApi.createConversation(userId, title);
        setConversationId(conversation.id);
        setMessages([]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create conversation');
        console.error('Error creating conversation:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [userId]
  );

  // Load existing conversation
  const loadConversation = useCallback(async (convId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const conversation = await chatbotApi.getConversation(convId);
      setConversationId(conversation.id);

      // Load messages
      if (conversation.messages) {
        const loadedMessages: ChatMessage[] = conversation.messages.map((msg, index) => ({
          id: `loaded-${index}-${msg.timestamp}`,
          role: msg.role || 'user',
          content: msg.message,
          timestamp: msg.timestamp || new Date().toISOString(),
        }));
        setMessages(loadedMessages);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversation');
      console.error('Error loading conversation:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Delete conversation
  const deleteConversation = useCallback(async (convId: string) => {
    setError(null);

    try {
      await chatbotApi.deleteConversation(convId);
      if (conversationId === convId) {
        setConversationId(null);
        setMessages([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete conversation');
      console.error('Error deleting conversation:', err);
    }
  }, [conversationId]);

  // Clear messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
  }, []);

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Check backend health
  const checkHealth = useCallback(async () => {
    try {
      const healthy = await chatbotApi.healthCheck();
      setIsHealthy(healthy);
    } catch (err) {
      setIsHealthy(false);
      console.error('Health check failed:', err);
    }
  }, []);

  const state: UseChatbotState = {
    messages,
    conversationId,
    isLoading,
    error,
    isHealthy,
  };

  const actions: UseChatbotActions = {
    sendMessage,
    createConversation,
    loadConversation,
    deleteConversation,
    clearMessages,
    clearError,
    checkHealth,
  };

  return [state, actions];
}
