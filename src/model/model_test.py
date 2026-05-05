"""
Model Testing and Evaluation for Financial Therapist Chatbot
Tests the fine-tuned model against real queries and evaluates response quality
"""

import logging
import json
import os
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from google import genai
from dotenv import load_dotenv
import time
from src.utils.emotion_analyzer import analyze_emotion
from src.utils.results_store import append_test_result

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

try:
    from inference.predictor import TherapyChatbot
except ImportError:
    TherapyChatbot = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')
load_dotenv()


class ModelTester:
    """
    Comprehensive testing suite for the fine-tuned financial therapist model
    """

    def __init__(self, use_finetuned=True):
        """
        Initialize the model tester

        Args:
            use_finetuned: Whether to use the fine-tuned prompt (True) or base prompt (False)
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError("GEMINI_API_KEY not set")

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-3-flash-preview"
        self.use_finetuned = use_finetuned

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Initialize Pinecone for RAG
        try:
            if Pinecone is not None:
                pinecone_api_key = os.getenv("PINECONE_API_KEY")
                if pinecone_api_key:
                    self.pc = Pinecone(api_key=pinecone_api_key)
                    self.index = self.pc.Index("f2-therapy-index")
                    logger.info("✓ Connected to Pinecone index")
                else:
                    self.index = None
            else:
                self.index = None
        except Exception as e:
            logger.warning(f"Pinecone not available: {e}")
            self.index = None

        logger.info(f"✓ Initialized ModelTester (Using {'fine-tuned' if use_finetuned else 'base'} prompt)")

    def _load_system_prompt(self) -> str:
        """Load the appropriate system prompt"""
        if self.use_finetuned:
            prompt_path = Path("src/model/finetuned_system_prompt.txt")
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    logger.info(f"✓ Loaded fine-tuned system prompt ({prompt_path})")
                    return f.read()
            else:
                logger.warning("Fine-tuned prompt not found, falling back to base prompt")

        # Load base prompt
        prompt_path = Path("src/data/processed/system_prompt.md")
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()

        return "You are a compassionate financial therapist."

    def _get_rag_context(self, query: str, top_k: int = 3) -> str:
        """Retrieve relevant context from Pinecone"""
        if not self.index:
            return ""

        try:
            # Embed the query
            embed_result = self.client.models.embed_content(
                model="gemini-embedding-2",
                contents=query,
            )
            embeddings = getattr(embed_result, "embeddings", None)
            if not embeddings:
                return ""

            query_vector = embeddings[0].values

            # Search Pinecone
            search_results: Any = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )

            context = ""
            matches: Any = getattr(search_results, "matches", None)
            if matches is None and isinstance(search_results, dict):
                matches = search_results.get("matches")

            if matches:
                context = "\n# RELEVANT KNOWLEDGE BASE:\n"
                for match in cast(List[Any], matches):
                    metadata = getattr(match, "metadata", None)
                    if metadata is None and isinstance(match, dict):
                        metadata = match.get("metadata", {})

                    content = ""
                    if isinstance(metadata, dict):
                        content = metadata.get("content", "")[:200]
                    else:
                        content = getattr(metadata, "content", "")[:200]

                    if content:
                        context += f"- {content}\n"

            return context

        except Exception as e:
            logger.debug(f"RAG retrieval error: {e}")
            return ""

    def test_query(self, user_query: str, use_rag: bool = True) -> Dict:
        """
        Test a single user query and return the model's response

        Args:
            user_query: The user's question/concern
            use_rag: Whether to augment with RAG context

        Returns:
            Dict with query, response, metadata
        """
        logger.info(f"\n{'=' * 80}")
        logger.info(f"QUERY: {user_query}")
        logger.info(f"{'=' * 80}")

        result = {
            'query': user_query,
            'response': '',
            'rag_used': False,
            'response_length': 0,
            'generation_time': 0,
            'timestamp': time.time()
        }

        try:
            # Get RAG context if enabled
            rag_context = ""
            if use_rag:
                rag_context = self._get_rag_context(user_query)
                if rag_context:
                    result['rag_used'] = True

            # Build prompt
            prompt = f"""{self.system_prompt}

{rag_context}

User: {user_query}

Your response (remember to acknowledge emotion first, then provide guidance):"""

            # Generate response
            start_time = time.time()
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            generation_time = time.time() - start_time

            if response and response.text:
                result['response'] = response.text
                result['response_length'] = len(response.text)
                result['generation_time'] = generation_time

                logger.info(f"\nRESPONSE ({result['response_length']} chars, {generation_time:.2f}s):")
                logger.info("-" * 80)
                logger.info(response.text)
                logger.info("-" * 80)

                if result['rag_used']:
                    logger.info("✓ RAG context was used")
            else:
                logger.error("No response generated")
                result['response'] = "Error: No response generated"

        except Exception as e:
            logger.error(f"Error during generation: {e}")
            result['response'] = f"Error: {str(e)}"

        return result

    def test_multiple_queries(self, queries: List[str], use_rag: bool = True) -> List[Dict]:
        """Test multiple queries"""
        results = []

        logger.info("\n" + "=" * 80)
        logger.info("FINANCIAL THERAPIST MODEL - COMPREHENSIVE TEST SUITE")
        logger.info("=" * 80)
        logger.info(f"Testing {len(queries)} queries with {'RAG' if use_rag else 'base knowledge'}")

        for i, query in enumerate(queries, 1):
            logger.info(f"\n[Test {i}/{len(queries)}]")
            result = self.test_query(query, use_rag=use_rag)
            results.append(result)

            # Add delay between requests to avoid rate limiting
            if i < len(queries):
                time.sleep(1)

        return results

    def test_with_training_examples(self, num_examples: int = 5) -> List[Dict]:
        """
        Test the model using actual training examples.
        This shows how well the model learned from the fine-tuning examples.
        """
        # Load training data
        training_path = Path("src/data/processed/conversation_training_data.json")
        if not training_path.exists():
            logger.error("Training data not found")
            return []

        with open(training_path, 'r', encoding='utf-8') as f:
            examples = json.load(f)

        logger.info("\n" + "=" * 80)
        logger.info("TESTING WITH TRAINING EXAMPLES - EVALUATING LEARNED BEHAVIOR")
        logger.info("=" * 80)
        logger.info(f"Using {min(num_examples, len(examples))} examples from training set")

        results = []

        for i, example in enumerate(examples[:num_examples], 1):
            user_input = example.get('user_input', '')
            expected_response = example.get('expected_response', '')
            category = example.get('category', '')
            intent = example.get('user_intent', '')

            logger.info(f"\n[Example {i}/{min(num_examples, len(examples))}]")
            logger.info(f"Category: {category}")
            logger.info(f"Intent: {intent}")

            # Test the query
            result = self.test_query(user_input, use_rag=True)
            result['category'] = category
            result['intent'] = intent
            result['expected_response'] = expected_response

            # Evaluate response quality (simple heuristics)
            result['quality_metrics'] = self._evaluate_response(
                result['response'],
                expected_response,
                user_input
            )

            results.append(result)

            # Delay between requests
            if i < min(num_examples, len(examples)):
                time.sleep(1)

        # Summary
        self._print_evaluation_summary(results)

        return results

    def _evaluate_response(self, response: str, expected: str, query: str) -> Dict:
        """
        Evaluate response quality based on heuristics
        """
        metrics = {
            'emotional_acknowledgment': False,
            'specific_guidance': False,
            'clarity': False,
            'appropriate_length': False,
            'quality_score': 0.0
        }

        response_lower = response.lower()

        # Check for emotional acknowledgment
        emotional_words = ['feel', 'understand', 'know', 'appreciate', 'hear', 'sense', 'realize']
        metrics['emotional_acknowledgment'] = any(word in response_lower for word in emotional_words)

        # Check for specific guidance (not just empathy)
        guidance_words = ['you can', 'try', 'step', 'option', 'consider', 'would', 'could']
        metrics['specific_guidance'] = any(word in response_lower for word in guidance_words)

        # Check clarity (no "I don't know", "unclear", etc)
        unclear_phrases = ['i don\'t know', 'unclear', 'sorry', 'can\'t help']
        metrics['clarity'] = not any(phrase in response_lower for phrase in unclear_phrases)

        # Check length (therapist responses should be substantial: 100-500 chars)
        metrics['appropriate_length'] = 100 <= len(response) <= 500

        # Calculate overall score
        score = sum([
            metrics['emotional_acknowledgment'] * 0.25,
            metrics['specific_guidance'] * 0.35,
            metrics['clarity'] * 0.20,
            metrics['appropriate_length'] * 0.20
        ])

        metrics['quality_score'] = score

        return metrics

    def _print_evaluation_summary(self, results: List[Dict]):
        """Print summary of evaluation results"""
        logger.info("\n" + "=" * 80)
        logger.info("EVALUATION SUMMARY")
        logger.info("=" * 80)

        total_tests = len(results)

        # Count metrics
        emotional = sum(1 for r in results if r['quality_metrics']['emotional_acknowledgment'])
        guidance = sum(1 for r in results if r['quality_metrics']['specific_guidance'])
        clarity = sum(1 for r in results if r['quality_metrics']['clarity'])
        length = sum(1 for r in results if r['quality_metrics']['appropriate_length'])

        avg_score = sum(r['quality_metrics']['quality_score'] for r in results) / total_tests if results else 0

        logger.info(f"\nTests completed: {total_tests}")
        logger.info(f"\nMetric Breakdown:")
        logger.info(f"  ✓ Emotional Acknowledgment: {emotional}/{total_tests} ({100*emotional//total_tests}%)")
        logger.info(f"  ✓ Specific Guidance: {guidance}/{total_tests} ({100*guidance//total_tests}%)")
        logger.info(f"  ✓ Clarity: {clarity}/{total_tests} ({100*clarity//total_tests}%)")
        logger.info(f"  ✓ Appropriate Length: {length}/{total_tests} ({100*length//total_tests}%)")
        logger.info(f"\nOverall Quality Score: {avg_score:.2f}/1.00")

        if avg_score >= 0.75:
            logger.info("✓ MODEL PERFORMING WELL - Ready for deployment")
        elif avg_score >= 0.50:
            logger.info("⚠ MODEL ACCEPTABLE - May need refinement")
        else:
            logger.info("✗ MODEL NEEDS IMPROVEMENT - Consider tuning")

        logger.info("=" * 80)

    def _save_test_results(self, results_summary: Dict, output_path: Path) -> Path:
        """Save results without overwriting prior runs."""
        return append_test_result(results_summary, output_path)


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Test the financial therapist model")
    parser.add_argument(
        "--query",
        type=str,
        help="Run a single custom query instead of the default batch test",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable RAG context retrieval for the custom query",
    )
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip training example tests and only run custom queries",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start an interactive chatbot REPL instead of running evaluations",
    )
    parser.add_argument(
        "--chat-rag",
        action="store_true",
        help="Use RAG context in chat mode (adds an embedding API call per message)",
    )
    args = parser.parse_args()

    if args.chat:
        if TherapyChatbot is None:
            raise ImportError("TherapyChatbot could not be imported from src.inference.predictor")

        logger.info("\n" + "=" * 80)
        logger.info("FINANCIAL THERAPIST CHAT MODE")
        logger.info("Type 'exit', 'quit', or 'q' to stop.")
        if args.chat_rag:
            logger.info("RAG is enabled in chat mode, so each message uses 2 API calls.")
        else:
            logger.info("RAG is disabled in chat mode to keep each message to 1 API call.")
        logger.info("=" * 80)

        chatbot = TherapyChatbot()
        conversation_history = []
        chat_transcript = []
        chat_started_at = time.time()

        while True:
            try:
                user_message = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_message:
                continue

            if user_message.lower() in {"exit", "quit", "q"}:
                break

            conversation_history.append({"role": "user", "content": user_message})

            # Analyze user emotion/mood
            mood_analysis = analyze_emotion(user_message, conversation_depth=len(conversation_history) - 1)

            # Display mood analysis if detected
            stress_level = mood_analysis.get('stress_level', 'unknown')
            if stress_level != 'unknown':
                print(f"  📊 [Mood Detected] Stress Level: {stress_level.upper()}")
                emotional_state = mood_analysis.get('indicators', {}).get('emotional_state', [])
                if emotional_state:
                    print(f"     Emotional State: {', '.join(emotional_state)}")
                print()

            try:
                response = chatbot.chat(
                    user_message,
                    use_rag=args.chat_rag,
                    conversation_history=conversation_history,
                    verbose=False,
                )
            except Exception as exc:
                response = f"I'm sorry, I ran into an error: {exc}"

            print(f"Bot: {response}\n")
            conversation_history.append({"role": "assistant", "content": response})
            chat_transcript.append({
                "user": user_message,
                "assistant": response,
                "rag_used": args.chat_rag,
                "timestamp": time.time(),
                "mood_analysis": mood_analysis,
            })

        if chat_transcript:
            output_path = Path("src/model/model_test_results.json")
            results_summary = {
                "timestamp": chat_started_at,
                "mode": "interactive_chat",
                "model": getattr(chatbot, "model_name", "gemini-3-flash-preview"),
                "prompt_type": "fine-tuned",
                "chat_rag": args.chat_rag,
                "chat_session": chat_transcript,
                "turn_count": len(chat_transcript),
            }

            tester = ModelTester(use_finetuned=True)
            tester._save_test_results(results_summary, output_path)
            logger.info(f"✓ Chat session saved to {output_path}")

        logger.info("Chat session ended.")
        return

    tester = ModelTester(use_finetuned=True)

    if args.query:
        logger.info("\n" + "=" * 80)
        logger.info("CUSTOM QUERY TEST")
        logger.info("=" * 80)
        result = tester.test_query(args.query, use_rag=not args.no_rag)

        output_path = Path("src/model/model_test_results.json")
        results_summary = {
            "timestamp": time.time(),
            "model": tester.model_name,
            "prompt_type": "fine-tuned" if tester.use_finetuned else "base",
            "mode": "single_custom_query",
            "custom_query_test": result,
        }

        saved_path = tester._save_test_results(results_summary, output_path)

        logger.info(f"✓ Custom query result saved to {output_path}")
        logger.info("=" * 80)
        return

    training_results = []
    if not args.skip_training:
        # Test 1: With training examples
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: EVALUATING WITH TRAINING EXAMPLES")
        logger.info("=" * 80)
        training_results = tester.test_with_training_examples(num_examples=5)

    # Test 2: With custom queries (real-world scenarios)
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: CUSTOM REAL-WORLD QUERIES")
    logger.info("=" * 80)

    custom_queries = [
        "I just lost my job and I'm panicking about my bills",
        "I don't understand credit cards and I feel stupid about it",
        "Same financial problem every month - I don't think I can change",
        "My partner controls our money and I feel trapped",
        "I'm ashamed about my spending habits but I can't stop"
    ]

    custom_results = tester.test_multiple_queries(custom_queries, use_rag=True)

    # Save results
    logger.info("\n" + "=" * 80)
    logger.info("SAVING TEST RESULTS")
    logger.info("=" * 80)

    output_path = Path("src/model/model_test_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results_summary = {
        'timestamp': time.time(),
        'model': tester.model_name,
        'prompt_type': 'fine-tuned' if tester.use_finetuned else 'base',
        'training_examples_test': training_results,
        'custom_queries_test': custom_results,
        'summary': {
            'total_tests': len(training_results) + len(custom_results),
            'avg_response_length': sum(
                r['response_length'] for r in training_results + custom_results
            ) / (len(training_results) + len(custom_results))
        }
    }

    saved_path = tester._save_test_results(results_summary, output_path)

    logger.info(f"✓ Test results saved to {output_path}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
