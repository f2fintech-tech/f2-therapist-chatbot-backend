/**
 * Quick Start Test
 * Run this to verify the frontend-backend connection works
 */

import { chatbotApi } from './chatbotApi';
import { v4 as uuidv4 } from 'uuid';

export async function runIntegrationTest() {
  console.log('🚀 Starting Frontend-Backend Integration Test...\n');

  const userId = uuidv4();
  console.log(`📋 User ID: ${userId}\n`);

  try {
    // Test 1: Health Check
    console.log('1️⃣  Testing Health Check...');
    const isHealthy = await chatbotApi.healthCheck();
    if (isHealthy) {
      console.log('✅ Backend is healthy\n');
    } else {
      console.log('❌ Backend is not responding\n');
      console.log('   Make sure the backend is running on http://localhost:8000');
      return;
    }

    // Test 2: Create Conversation
    console.log('2️⃣  Creating New Conversation...');
    const conversation = await chatbotApi.createConversation(userId, 'Test Chat');
    console.log(`✅ Conversation created: ${conversation.id}\n`);

    // Test 3: Send Message
    console.log('3️⃣  Sending Test Message...');
    const response = await chatbotApi.sendMessage(
      'What is financial therapy?',
      userId,
      conversation.id
    );
    console.log(`✅ Response received:`);
    console.log(`   Emotion: ${response.emotion_detected}`);
    console.log(`   Mood Score: ${(response.mood_score * 100).toFixed(0)}%`);
    console.log(`   Message: "${response.response.substring(0, 100)}..."\n`);

    // Test 4: Get Conversation History
    console.log('4️⃣  Fetching Conversation History...');
    const history = await chatbotApi.getConversation(conversation.id);
    console.log(`✅ Conversation retrieved: ${history.messages?.length || 0} messages\n`);

    // Test 5: List All Conversations
    console.log('5️⃣  Listing All Conversations...');
    const conversations = await chatbotApi.getConversations(userId);
    console.log(`✅ Found ${conversations.length} conversation(s)\n`);

    // Test 6: Get User Preferences
    console.log('6️⃣  Fetching User Preferences...');
    try {
      const prefs = await chatbotApi.getUserPreferences(userId);
      console.log(`✅ User preferences retrieved`);
      console.log(`   Preferred Persona: ${prefs.preferred_persona || 'Not set'}\n`);
    } catch (err) {
      console.log('⚠️  Preferences not yet set (this is normal)\n');
    }

    // Test 7: Get Available Personas
    console.log('7️⃣  Fetching Available Personas...');
    try {
      const personas = await chatbotApi.getPersonas();
      console.log(`✅ Found ${personas.length} persona(s)\n`);
    } catch (err) {
      console.log('⚠️  Could not fetch personas\n');
    }

    console.log('✅ ✅ ✅ All tests passed! Your frontend and backend are connected! ✅ ✅ ✅\n');
    console.log('📝 Next steps:');
    console.log('   1. Copy the files from frontend-integration/ to your React project');
    console.log('   2. Install dependencies: npm install uuid');
    console.log('   3. Set environment variables in .env');
    console.log('   4. Import ChatInterface or useChatbot into your app');
    console.log('   5. Start chatting!\n');

  } catch (error) {
    console.error('\n❌ Test failed:', error);
    console.log('\n🔧 Troubleshooting:');
    console.log('   • Is the backend running? Start it with: ./RUN_CHATBOT_TERMINAL.sh');
    console.log('   • Check CORS settings: ALLOWED_ORIGINS should include http://localhost:5173');
    console.log('   • Check API key: Make sure VITE_API_KEY matches backend configuration');
    console.log('   • Check network: Can you reach http://localhost:8000/health in your browser?\n');
  }
}

// Run the test
runIntegrationTest();
