#!/bin/bash
# QUICK REFERENCE: TESTING YOUR FINE-TUNED MODEL
# Run these commands when quota resets (after ~24 hours)

# ============================================================================
# STEP 1: Simple Single Query Test (2 API calls)
# ============================================================================
# Tests with ONE query to verify fine-tuned model is working

python -c "
from src.model.model_test import ModelTester

# Initialize tester with fine-tuned prompt
tester = ModelTester(use_finetuned=True)

# Test a single query
result = tester.test_query(
    'I just lost my job and I am panicking about bills',
    use_rag=True
)

print('\nResponse Quality:')
print(f'  - Length: {result[\"response_length\"]} characters')
print(f'  - Generation time: {result[\"generation_time\"]:.2f}s')
print(f'  - RAG used: {result[\"rag_used\"]}')
"


# ============================================================================
# STEP 2: Comprehensive Batch Testing (5 training + 5 custom queries)
# ============================================================================
# Full evaluation with quality metrics
# Uses ~10 API calls (5 queries + RAG retrievals)

python -m src.model.model_test

# This will:
# ✓ Test with 5 actual training examples from your dataset
# ✓ Test with 5 real-world queries
# ✓ Calculate quality metrics for each response
# ✓ Generate overall quality score (0.00-1.00)
# ✓ Save detailed results to: src/model/model_test_results.json

# Expected output:
#   ✓ Emotional Acknowledgment: 4/5 (80%)
#   ✓ Specific Guidance: 5/5 (100%)
#   ✓ Clarity: 4/5 (80%)
#   ✓ Appropriate Length: 5/5 (100%)
#   Overall Quality Score: 0.87/1.00


# ============================================================================
# STEP 3: Review Detailed Results
# ============================================================================

# View as raw JSON
cat src/model/model_test_results.json

# Or with Python
python -c "
import json
with open('src/model/model_test_results.json') as f:
    results = json.load(f)
    
print('Test Results Summary:')
print(f'Model: {results[\"model\"]}')
print(f'Prompt Type: {results[\"prompt_type\"]}')
print(f'Total Tests: {results[\"summary\"][\"total_tests\"]}')
print(f'Avg Response Length: {results[\"summary\"][\"avg_response_length\"]:.0f} chars')
"


# ============================================================================
# STEP 4: Custom Query Testing
# ============================================================================
# Test with your own specific queries

python -c "
from src.model.model_test import ModelTester

tester = ModelTester(use_finetuned=True)

# Define your custom queries
custom_queries = [
    'I am embarrassed I don\'t understand credit cards',
    'My partner and I constantly fight about money',
    'I have been struggling with money for 5 years',
    'I grew up poor and now I have anxiety about money',
    'I spend money compulsively and I can\'t stop'
]

# Test all of them
results = tester.test_multiple_queries(custom_queries, use_rag=True)

# Extract quality scores
for i, result in enumerate(results):
    score = result.get('quality_metrics', {}).get('quality_score', 0)
    print(f'Query {i+1}: {score:.2f}/1.00')
"


# ============================================================================
# STEP 5: Quality Assessment Guide
# ============================================================================
# How to interpret results

# Quality Score Interpretation:
#   0.90+ = Excellent - Deploy immediately
#   0.80-0.89 = Very Good - Minor polish optional
#   0.70-0.79 = Good - Consider refinement
#   0.60-0.69 = Acceptable - Refinement recommended
#   <0.60 = Needs Work - Revise examples

# Check these metrics individually:
#   ✓ Emotional Acknowledgment: Does it validate feelings first?
#   ✓ Specific Guidance: Does it provide actionable advice?
#   ✓ Clarity: Is it coherent and confident?
#   ✓ Appropriate Length: Is it substantial (100-500 chars)?

# If ANY metric is low:
#   - Edit: src/model/finetuned_system_prompt.txt
#   - Add better examples or clearer instructions
#   - Retest: python -m src.model.model_test
#   - Repeat until satisfied


# ============================================================================
# STEP 6: Manual Response Inspection
# ============================================================================
# Read actual responses to verify quality

python -c "
import json

with open('src/model/model_test_results.json') as f:
    data = json.load(f)

# Print first test in detail
test = data['training_examples_test'][0]
print('='*80)
print('SAMPLE RESPONSE')
print('='*80)
print(f'\nQuery: {test[\"query\"]}')
print(f'\nResponse:')
print(test['response'])
print(f'\nMetrics:')
print(f'  - Quality Score: {test[\"quality_metrics\"][\"quality_score\"]:.2f}')
print(f'  - Emotional Acknowledgment: {test[\"quality_metrics\"][\"emotional_acknowledgment\"]}')
print(f'  - Specific Guidance: {test[\"quality_metrics\"][\"specific_guidance\"]}')
"


# ============================================================================
# STEP 7: Deployment (After Validation)
# ============================================================================
# Once quality_score >= 0.75, ready for production!

# The fine-tuned model is ALREADY integrated in predictor.py
# Just start using the chatbot API!

python -c "
from src.inference.predictor import TherapyChatbot

# Your model automatically uses fine-tuned prompt
bot = TherapyChatbot()

# Test it
response = bot.chat('I just lost my job and I need help')
print(response)
"


# ============================================================================
# STEP 8: If Quality Is Low, Refine and Iterate
# ============================================================================

# 1. Edit the prompt
nano src/model/finetuned_system_prompt.txt

# 2. Improve examples:
#    - Use more specific, emotional real examples
#    - Cover more edge cases
#    - Make instructions clearer

# 3. Rerun test
python -m src.model.model_test

# 4. Check metrics again
cat src/model/model_test_results.json | python -m json.tool

# 5. Repeat until quality >= 0.75


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# Q: "429 RESOURCE_EXHAUSTED" error?
#    A: You've hit daily quota limit. Wait for reset or upgrade tier.

# Q: Model responses are generic?
#    A: Few-shot examples need to be more specific/emotional.
#       Edit finetuned_system_prompt.txt with better examples.

# Q: Model ignoring instructions?
#    A: Check that finetuned_system_prompt.txt is loaded.
#       Verify: Test logs should say "Loaded fine-tuned system prompt"

# Q: Responses too long?
#    A: Add to system prompt: "Keep responses to 150-300 characters"

# Q: Responses too short?
#    A: Add to system prompt: "Provide detailed, thorough responses"

# Q: Want to test without full batch testing?
#    A: Use Step 1 (single query) which only uses 2 API calls


# ============================================================================
# QUOTA INFORMATION
# ============================================================================

# Free Tier Limits (reset daily UTC midnight):
#   - Generate Content Requests: 20/day
#   - Embed Content Requests: 1000/day

# API calls per test:
#   Step 1 (single query): ~2 calls (1 generate + 1 RAG)
#   Step 2 (batch test): ~10 calls (5 generates + 5 RAG)
#   Step 3-4: Variable based on custom queries

# After testing, you'll have used ~10-15 calls out of 20 daily quota


# ============================================================================
# SUMMARY CHECKLIST
# ============================================================================

# When quota resets:
# [ ] Run Step 1 (single query test)
# [ ] Run Step 2 (comprehensive batch test)
# [ ] Review Step 3 (detailed results)
# [ ] Inspect Step 4 & 6 (actual responses)
# [ ] Check quality score >= 0.75
# [ ] If good, proceed to Step 7 (deploy)
# [ ] If poor, proceed to Step 8 (refine and iterate)

echo "✓ Fine-tuned Model Testing Guide Ready"
echo "  - Wait for quota reset (UTC midnight)"
echo "  - Run tests from this guide"
echo "  - Check quality score"
echo "  - Deploy when ready!"
