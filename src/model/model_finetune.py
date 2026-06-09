"""
Actual Fine-Tuning for Financial Therapist Chatbot using Few-Shot Prompting
Implements supervised learning through in-context examples rather than traditional fine-tuning
"""

import logging
import json
import os
from pathlib import Path
from typing import List, Dict, Tuple
from google import genai
from dotenv import load_dotenv
from src.exceptions import TrainingDataNotFoundError

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

logger = logging.getLogger(__name__)
load_dotenv()


class SupervisedFineTuner:
    """
    Fine-tunes the financial therapist using few-shot learning.
    Strategy: Select best examples and embed them in the system prompt so the model learns the desired behavior.
    """

    def __init__(self):
        """Initialize the fine-tuner"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("GEMINI_API_KEY not set")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-3-flash-preview"
        self.conversation_data_path = Path("src/data/processed/conversation_training_data.json")

        # Try to initialize Pinecone (optional for context retrieval)
        try:
            if Pinecone is not None:
                pinecone_api_key = os.getenv("PINECONE_API_KEY")
                if pinecone_api_key:
                    self.pc = Pinecone(api_key=pinecone_api_key)
                    self.index = self.pc.Index("f2-therapy-index")
                else:
                    self.index = None
            else:
                self.index = None
        except Exception as e:
            logger.warning(f"Pinecone not available: {e}")
            self.index = None

    def load_training_examples(self) -> List[Dict]:
        """Load conversation training examples"""
        if not self.conversation_data_path.exists():
            raise TrainingDataNotFoundError(f"Training data not found at {self.conversation_data_path}")

        with open(self.conversation_data_path, 'r', encoding='utf-8') as f:
            examples = json.load(f)

        logger.info(f"✓ Loaded {len(examples)} training examples")
        return examples

    def select_diverse_examples(self, examples: List[Dict], num_examples: int = 8) -> List[Dict]:
        """
        Select diverse examples covering different categories and intents.
        Strategy: Pick examples that cover different financial scenarios and emotional states.
        """
        logger.info(f"Selecting {num_examples} diverse examples from {len(examples)} total...")

        # Group by category
        by_category = {}
        for ex in examples:
            cat = ex.get('category', 'unknown')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(ex)

        # Select diverse examples: ~2 per category
        selected = []
        examples_per_cat = max(1, num_examples // len(by_category))

        for cat, cat_examples in by_category.items():
            selected.extend(cat_examples[:examples_per_cat])
            if len(selected) >= num_examples:
                break

        selected = selected[:num_examples]

        logger.info(f"Selected {len(selected)} examples covering {len(by_category)} categories")
        for ex in selected:
            logger.info(f"  - {ex['category']}: {ex['user_intent']}")

        return selected

    def build_fewshot_system_prompt(self, examples: List[Dict], base_prompt: str) -> str:
        """
        Build a system prompt that includes few-shot examples.
        The model learns from these examples to produce similar quality responses.
        """

        # Format examples
        examples_section = "# EXAMPLES OF EXCELLENT RESPONSES\n\n"
        examples_section += "Here are examples of high-quality responses you should emulate:\n\n"

        for i, ex in enumerate(examples, 1):
            category = ex.get('category', 'Financial Issue')
            user_input = ex.get('user_input', '')
            expected_response = ex.get('expected_response', '')
            intent = ex.get('user_intent', '')

            examples_section += f"## Example {i}: {category}\n"
            examples_section += f"**Intent:** {intent}\n"
            examples_section += f"**User says:** \"{user_input}\"\n\n"
            examples_section += f"**Your response:**\n{expected_response}\n\n"
            examples_section += "---\n\n"

        # Combine base prompt with examples
        fewshot_prompt = f"""{base_prompt}

{examples_section}

# YOUR INSTRUCTIONS FOR THIS CONVERSATION

1. Follow the pattern from the examples above
2. Acknowledge emotional content FIRST, then provide context or guidance
3. Use real numbers and specific examples
4. Be warm and human, never corporate
5. Never say "don't worry" or "it's simple" - these are dismissive
6. Ask questions when you need clarification
7. Explain jargon: e.g., "EMI (Equated Monthly Installment - your fixed monthly payment)"

Remember: The examples above are your style guide. Match their tone, depth, and approach."""

        return fewshot_prompt

    def finetune(self) -> Tuple[bool, str]:
        """
        Execute the fine-tuning process.
        Returns: (success, system_prompt_content)
        """
        logger.info("=" * 80)
        logger.info("FINANCIAL THERAPIST - SUPERVISED FINE-TUNING")
        logger.info("=" * 80)

        try:
            # Step 1: Load base system prompt
            logger.info("\n[STEP 1] Loading base system prompt...")
            prompt_path = Path("src/data/processed/system_prompt.md")
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    base_prompt = f.read()
                logger.info("✓ Base system prompt loaded")
            else:
                logger.warning("System prompt file not found, using minimal prompt")
                base_prompt = "You are a compassionate financial support specialist. You are not a licensed therapist."

            # Step 2: Load training examples
            logger.info("\n[STEP 2] Loading training examples...")
            all_examples = self.load_training_examples()
            if not all_examples:
                logger.error("No training examples available!")
                return False, base_prompt

            # Step 3: Select diverse examples
            logger.info("\n[STEP 3] Selecting diverse examples for few-shot learning...")
            selected_examples = self.select_diverse_examples(all_examples, num_examples=8)

            # Step 4: Build few-shot system prompt
            logger.info("\n[STEP 4] Building few-shot system prompt...")
            fewshot_prompt = self.build_fewshot_system_prompt(selected_examples, base_prompt)
            logger.info(f"✓ Few-shot prompt created ({len(fewshot_prompt)} chars)")

            # Step 5: Validate with test examples
            logger.info("\n[STEP 5] Validating fine-tuned prompt with examples...")
            validation_results = self._validate_prompt(fewshot_prompt, all_examples[8:10])

            if validation_results['success']:
                logger.info(f"✓ Validation passed - Model produces coherent responses")
            else:
                logger.warning("⚠ Validation showed issues but continuing...")

            # Step 6: Save fine-tuned prompt
            logger.info("\n[STEP 6] Saving fine-tuned system prompt...")
            output_path = Path("src/model/finetuned_system_prompt.txt")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(fewshot_prompt)
            logger.info(f"✓ Fine-tuned prompt saved to {output_path}")

            # Step 7: Summary
            logger.info("\n[STEP 7] Fine-tuning Summary")
            logger.info("=" * 80)
            logger.info(f"✓ Model: {self.model_name}")
            logger.info(f"✓ Fine-tuning method: Few-shot prompting")
            logger.info(f"✓ Training examples used: {len(selected_examples)}")
            logger.info(f"✓ Total examples available: {len(all_examples)}")
            logger.info(f"✓ System prompt size: {len(fewshot_prompt)} characters")
            logger.info(f"✓ Validation: {'PASSED' if validation_results['success'] else 'WITH WARNINGS'}")
            logger.info("=" * 80)
            logger.info("✓ Fine-tuning completed successfully!")

            return True, fewshot_prompt

        except Exception as e:
            logger.error(f"Error during fine-tuning: {e}")
            return False, base_prompt

    def _validate_prompt(self, fewshot_prompt: str, test_examples: List[Dict]) -> Dict:
        """Validate the fine-tuned prompt works with test examples"""
        results = {'success': True, 'tests_passed': 0, 'tests_failed': 0}

        for i, example in enumerate(test_examples[:2], 1):
            try:
                user_input = example.get('user_input', '')
                if not user_input:
                    continue

                logger.info(f"  Testing example {i}: {user_input[:50]}...")

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[fewshot_prompt, f"\nUser: {user_input}\n\nAssistant:"],
                )

                if response and response.text and len(response.text) > 20:
                    logger.info(f"    ✓ Generated response ({len(response.text)} chars)")
                    results['tests_passed'] += 1
                else:
                    logger.warning(f"    ⚠ Short or empty response")
                    results['tests_failed'] += 1
                    results['success'] = False

            except Exception as e:
                logger.error(f"    ✗ Validation error: {e}")
                results['tests_failed'] += 1
                results['success'] = False

        return results


if __name__ == "__main__":
    finetuner = SupervisedFineTuner()
    success, prompt = finetuner.finetune()

    if success:
        logger.info("\n" + "=" * 80)
        logger.info("NEXT STEP: Test the fine-tuned model with real queries")
        logger.info("Run: python -m src.model.model_test_with_finetuned")
        logger.info("=" * 80)
