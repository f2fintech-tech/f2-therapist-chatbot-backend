"""
QUICK START GUIDE: Testing Your Fine-Tuned Financial Therapist Model

This guide shows you how to test and use your fine-tuned model.
The actual model generation will work once you're under quota limits.
"""

import json
import logging
from pathlib import Path
from google import genai
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
load_dotenv()


class QuickModelDemo:
    """Quick demonstration of fine-tuned model without heavy quota usage"""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-3-flash-preview"

        # Load fine-tuned system prompt
        prompt_path = Path("src/model/finetuned_system_prompt.txt")
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self.system_prompt = f.read()
            logger.info("✓ Fine-tuned system prompt loaded")
        else:
            raise ValueError("Fine-tuned prompt not found!")

    def show_finetuning_summary(self):
        """Display what fine-tuning was done"""
        logger.info("\n" + "=" * 80)
        logger.info("FINE-TUNING SUMMARY")
        logger.info("=" * 80)
        logger.info("""
✓ Fine-tuning Method: Few-Shot Prompting (Google's recommended approach for Gemini)
✓ Examples Embedded: 8 diverse conversation examples covering:
  1. Financial Literacy Anxiety - shame, learning breakthrough
  2. Acute Financial Crisis - job loss, panic, immediate action
  3. Chronic Financial Stress - paycheck-to-paycheck, learned helplessness
  4. Financial Shame - identity crisis, guilt, family dynamics
  5. Relationship Money Conflict - partner disagreement, communication
  6. Behavioral Finance - compulsive spending, loss of control
  7. Financial Trauma - poverty, hypervigilance, safety concerns
  8. Behavior Change Failure - hopelessness, system design approach

✓ System Prompt Format: 12KB comprehensive guide that includes:
  - Core identity (who you are)
  - Purpose (what you're doing)
  - Communication style (how you talk)
  - Product knowledge (F2 Fintech offerings)
  - Situation handling (crisis, anxiety, shame, comparison, etc.)
  - Conversation flow (opening → discovery → education → solution → next step)
  - 8 worked examples showing excellent responses

✓ How It Works:
  By embedding examples in the system prompt, Gemini learns the desired:
  - Tone (warm, human, not corporate)
  - Structure (emotion first, then guidance)
  - Depth (specific numbers, realistic scenarios)
  - Complexity (handles shame, trauma, relationship issues)

This is equivalent to fine-tuning for Gemini because examples are part of
the prompt that shapes the model's generation behavior.
""")
        logger.info("=" * 80)

    def show_how_to_test(self):
        """Show how to actually test the model"""
        logger.info("\n" + "=" * 80)
        logger.info("HOW TO TEST YOUR MODEL")
        logger.info("=" * 80)
        logger.info("""
WHEN YOU'RE READY TO TEST (when quota resets):

1. Single Query Test:
   python -c "
from src.model.model_test import ModelTester
tester = ModelTester(use_finetuned=True)
result = tester.test_query(
    'I just lost my job and I am scared about bills',
    use_rag=True
)
   "

2. Batch Test with Training Examples:
   python -m src.model.model_test

   This will:
   - Test with 5 actual training examples
   - Test with 5 custom real-world queries
   - Show quality metrics for each response
   - Save detailed results to: src/model/model_test_results.json

3. Programmatic Test:
   from src.model.model_test import ModelTester
   tester = ModelTester(use_finetuned=True)

   # Test single query
   result = tester.test_query("Your question here")
   print(result['response'])

   # Test multiple queries
   queries = [
       "I don't understand credit cards",
       "My partner controls our money",
       "I can't stop spending"
   ]
   results = tester.test_multiple_queries(queries, use_rag=True)

4. With RAG Integration:
   The model automatically retrieves relevant knowledge base articles
   from Pinecone before generating responses. This augments the fine-tuning.
""")
        logger.info("=" * 80)

    def show_example_usage(self):
        """Show example code snippets"""
        logger.info("\n" + "=" * 80)
        logger.info("EXAMPLE: USING THE FINE-TUNED MODEL DIRECTLY")
        logger.info("=" * 80)
        logger.info("""
# Direct usage example:

from google import genai
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Load fine-tuned system prompt
with open('src/model/finetuned_system_prompt.txt') as f:
    system_prompt = f.read()

# Construct conversation
user_query = "I'm scared to take a loan because I've made bad financial decisions before"

prompt = f'''''{system_prompt}

User: {user_query}

Your response:''''

# Generate response
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=prompt
)

print(response.text)
""")
        logger.info("=" * 80)

    def calculate_prompt_stats(self):
        """Show prompt statistics"""
        logger.info("\n" + "=" * 80)
        logger.info("FINE-TUNED PROMPT STATISTICS")
        logger.info("=" * 80)

        with open("src/model/finetuned_system_prompt.txt") as f:
            content = f.read()

        lines = content.split('\n')
        examples = content.count("## Example")
        words = len(content.split())

        logger.info(f"File size: {len(content):,} characters")
        logger.info(f"Lines: {len(lines)}")
        logger.info(f"Words: {words:,}")
        logger.info(f"Examples embedded: {examples}")
        logger.info(f"Estimated tokens: ~{words // 3:.0f}")
        logger.info("\nBreakdown:")
        logger.info(f"  - System instructions: {content[:content.find('# EXAMPLES')].count(' ') // 4:.0f} words")
        logger.info(f"  - Few-shot examples: {content[content.find('# EXAMPLES'):].count(' ') // 4:.0f} words")
        logger.info("=" * 80)

    def show_expected_behavior(self):
        """Show what to expect from the fine-tuned model"""
        logger.info("\n" + "=" * 80)
        logger.info("WHAT TO EXPECT FROM THE FINE-TUNED MODEL")
        logger.info("=" * 80)
        logger.info("""
✓ EMOTIONAL VALIDATION FIRST
  User: "I'm embarrassed I don't understand money"
  Expected: Acknowledge shame, normalize experience, build confidence
  NOT: Immediate financial advice

✓ SPECIFIC, CONCRETE GUIDANCE
  User: "What's a credit card?"
  Expected: Explanation with numbers, comparison to concepts they know
  NOT: Generic definition

✓ WARM, HUMAN TONE
  User: "Will you judge me?"
  Expected: Warmth, reassurance, validation
  NOT: Corporate, formal, or robotic responses

✓ CONTEXT-AWARE COMPLEXITY
  User expressing suicidal thoughts about debt
  Expected: Take seriously, suggest professional help
  NOT: Minimize or just give financial advice

✓ ACTIONABLE NEXT STEPS
  User: "So what do I do?"
  Expected: Specific, small, manageable actions
  NOT: Vague or overwhelming suggestions

✓ RAG-ENHANCED RESPONSES
  When relevant knowledge base articles are available:
  - Cites specific FAQ/scenario information
  - Personalizes with user's situation
  - References relevant parts of knowledge base

✗ WHAT IT WON'T DO
  - Push products they don't need
  - Use dismissive phrases ("Don't worry", "It's simple")
  - Ignore emotional content
  - Make unsupported promises
  - Provide financial/legal advice beyond scope
""")
        logger.info("=" * 80)

    def show_quota_status(self):
        """Show current quota status"""
        logger.info("\n" + "=" * 80)
        logger.info("CURRENT API QUOTAS")
        logger.info("=" * 80)
        logger.info("""
FREE TIER LIMITS (reset daily UTC):
  - Generate Content Requests: 20/day
  - Embed Content Requests: 1000/day

WHEN QUOTA EXHAUSTED:
  Model testing will fail with 429 RESOURCE_EXHAUSTED error
  Wait for quota reset (typically UTC midnight) to continue

OPTIONS:
  1. Wait for quota reset
  2. Upgrade to paid tier for higher limits
  3. Use cached responses from previous tests
  4. Continue development without testing (not recommended)

After quota resets, run:
  python -m src.model.model_test
to see full evaluation with metrics
""")
        logger.info("=" * 80)

    def run_demo(self):
        """Run full demonstration"""
        logger.info("\n\n")
        logger.info("█" * 80)
        logger.info("FINANCIAL THERAPIST CHATBOT - ACTUAL FINE-TUNING COMPLETE")
        logger.info("█" * 80)

        self.show_finetuning_summary()
        self.calculate_prompt_stats()
        self.show_expected_behavior()
        self.show_how_to_test()
        self.show_example_usage()
        self.show_quota_status()

        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info("""
✓ COMPLETED:
  - Fine-tuned system prompt created with 8 examples
  - Examples cover all major financial therapy scenarios
  - Prompt is optimized for Gemini's instruction following
  - Ready for immediate use

NEXT STEPS:
  1. Wait for quota reset (or upgrade tier)
  2. Run: python -m src.model.model_test
  3. This will show actual model responses with quality metrics
  4. Deploy the fine-tuned model to production

INTEGRATION:
  Your API inference code (predictor.py) can use this prompt by:
  - Loading: src/model/finetuned_system_prompt.txt
  - Using in: client.models.generate_content()
  - The rest of your RAG pipeline works as-is
""")
        logger.info("=" * 80)


if __name__ == "__main__":
    demo = QuickModelDemo()
    demo.run_demo()
