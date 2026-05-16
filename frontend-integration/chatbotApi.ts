/**
 * Chatbot API Client
 * Handles all communication with the Financial Therapist Chatbot backend
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const API_KEY = import.meta.env.VITE_API_KEY || 'dev-key';

export interface ChatMessage {
  id?: string;
  user_id: string;
  conversation_id?: string;
  message: string;
  role?: 'user' | 'assistant';
  timestamp?: string;
  user_tier?: string;
  user_tier_score?: number;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
  emotion_detected: string;
  mood_score: number;
  references?: {
    source: string;
    content: string;
  }[];
  variant?: string;
  experiment_assignment?: {
    experiment_name: string;
    variant: string;
  };
}

export interface ConversationHistory {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  title: string;
  preview: string;
  messages?: ChatMessage[];
}

export interface UserPreferences {
  user_id: string;
  preferred_persona: string;
  persona_details?: Record<string, any>;
  risk_tolerance?: string;
  financial_goals?: string[];
}

class ChatbotApiClient {
  private baseUrl: string;
  private apiKey: string;

  constructor() {
    this.baseUrl = API_BASE_URL;
    this.apiKey = API_KEY;
  }

  /**
   * Send a chat message and get a response
   */
  async sendMessage(
    message: string,
    userId: string,
    conversationId?: string
  ): Promise<ChatResponse> {
    try {
      const requestBody: Record<string, unknown> = {
        message,
        user_id: userId,
        conversation_id: conversationId,
      };

      if (typeof window !== 'undefined') {
        const tierName = window.localStorage.getItem('finheal_user_tier');
        const tierScore = window.localStorage.getItem('finheal_quiz_score');

        if (tierName) {
          requestBody.user_tier = tierName;
          if (tierScore !== null && tierScore !== '') {
            requestBody.user_tier_score = Number(tierScore);
          }
        }
      }

      const response = await fetch(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`Chat API error: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  }

  /**
   * Create a new conversation
   */
  async createConversation(userId: string, title?: string): Promise<ConversationHistory> {
    try {
      const response = await fetch(`${this.baseUrl}/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          user_id: userId,
          title: title || 'New Chat',
        }),
      });

      if (!response.ok) {
        throw new Error(`Create conversation error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to create conversation:', error);
      throw error;
    }
  }

  /**
   * Get all conversations for a user
   */
  async getConversations(userId: string): Promise<ConversationHistory[]> {
    try {
      const response = await fetch(`${this.baseUrl}/conversations?user_id=${userId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Get conversations error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
      throw error;
    }
  }

  /**
   * Get a specific conversation with its messages
   */
  async getConversation(conversationId: string): Promise<ConversationHistory> {
    try {
      const response = await fetch(`${this.baseUrl}/conversations/${conversationId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Get conversation error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to fetch conversation:', error);
      throw error;
    }
  }

  /**
   * Delete a conversation
   */
  async deleteConversation(conversationId: string): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/conversations/${conversationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Delete conversation error: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      throw error;
    }
  }

  /**
   * Get user preferences and persona
   */
  async getUserPreferences(userId: string): Promise<UserPreferences> {
    try {
      const response = await fetch(
        `${this.baseUrl}/personalization/preferences?user_id=${userId}`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Get preferences error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to fetch user preferences:', error);
      throw error;
    }
  }

  /**
   * Update user preferences and persona
   */
  async updateUserPreferences(
    userId: string,
    preferences: Partial<UserPreferences>
  ): Promise<UserPreferences> {
    try {
      const response = await fetch(`${this.baseUrl}/personalization/preferences`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          user_id: userId,
          ...preferences,
        }),
      });

      if (!response.ok) {
        throw new Error(`Update preferences error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to update preferences:', error);
      throw error;
    }
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl.replace('/api/v1', '')}/health`);
      return response.ok;
    } catch (error) {
      console.error('Health check failed:', error);
      return false;
    }
  }

  /**
   * Get available personas
   */
  async getPersonas(): Promise<any[]> {
    try {
      const response = await fetch(`${this.baseUrl}/personalization/personas`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Get personas error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to fetch personas:', error);
      throw error;
    }
  }
}

export const chatbotApi = new ChatbotApiClient();
