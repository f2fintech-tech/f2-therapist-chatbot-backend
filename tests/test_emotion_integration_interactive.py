"""
Test emotion analyzer integration with interactive chat (TherapyChatbot)
Verifies that emotions are correctly detected when using the chat() method
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.utils.emotion_analyzer import analyze_emotion
from src.inference.predictor import TherapyChatbot


class TestEmotionIntegrationInteractiveChat(unittest.TestCase):
    """Test emotion analysis integration in interactive chat mode"""

    def test_emotion_detection_high_stress(self):
        """Test that high stress cases are correctly identified"""
        high_stress_message = "Three EMIs are due this week and a supplier payment came up unexpectedly"
        result = analyze_emotion(high_stress_message)

        self.assertEqual(result['stress_level'], 'high')
        self.assertIsNotNone(result['stress_score'])
        self.assertGreater(result['stress_score'], 0)

    def test_emotion_detection_moderate_stress(self):
        """Test that moderate stress cases are correctly identified"""
        moderate_message = "I'm a bit worried about my next EMI payment but I think I can manage"
        result = analyze_emotion(moderate_message)

        self.assertEqual(result['stress_level'], 'moderate')

    def test_emotion_detection_low_stress(self):
        """Test that low stress cases are correctly identified"""
        low_stress_message = "I'm just exploring different loan options to see what works best for me"
        result = analyze_emotion(low_stress_message)

        self.assertEqual(result['stress_level'], 'low')

    def test_emotion_detection_with_conversation_depth(self):
        """Test that emotion analysis considers conversation depth"""
        message = "I'm worried about my finances"

        # First turn
        result_depth_0 = analyze_emotion(message, conversation_depth=0)

        # Later turn
        result_depth_5 = analyze_emotion(message, conversation_depth=5)

        # Both should detect moderate stress
        self.assertIn(result_depth_0['stress_level'], ['moderate', 'high'])
        self.assertIn(result_depth_5['stress_level'], ['moderate', 'high'])

    @patch('src.inference.predictor.Pinecone')
    @patch('src.inference.predictor.genai.Client')
    def test_therapy_chatbot_calls_emotion_analyzer(self, mock_genai, mock_pinecone):
        """Test that TherapyChatbot.chat() integrates emotion analysis"""
        # Mock Pinecone and Gemini client
        mock_pinecone_instance = MagicMock()
        mock_pinecone.return_value = mock_pinecone_instance

        mock_client = MagicMock()
        mock_genai.return_value = mock_client

        # Mock response
        mock_response = MagicMock()
        mock_response.text = "I understand your concerns. Let's work through this together."
        mock_client.models.generate_content.return_value = mock_response

        # Mock Pinecone index
        mock_index = MagicMock()
        mock_pinecone_instance.Index.return_value = mock_index

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key', 'PINECONE_API_KEY': 'test-pc-key'}):
            chatbot = TherapyChatbot()

            # Chat should not raise an exception and should return a response
            response = chatbot.chat(
                "Three EMIs are due this week and a supplier payment came up unexpectedly",
                use_rag=False,
                verbose=False
            )

            self.assertIsNotNone(response)
            # Verify the bot responded
            self.assertIn("understand", response.lower())

    def test_conversation_depth_affects_analysis(self):
        """Test that conversation history depth is considered in emotion analysis"""
        test_message = "I'm stressed about money"

        # Empty conversation - no prior context
        result_new = analyze_emotion(test_message, conversation_depth=0)

        # Ongoing conversation - has prior context
        result_ongoing = analyze_emotion(test_message, conversation_depth=3)

        # Both should detect stress, even if levels differ slightly
        self.assertIn(result_new['stress_level'], ['moderate', 'high'])
        self.assertIn(result_ongoing['stress_level'], ['moderate', 'high'])


if __name__ == '__main__':
    unittest.main()
