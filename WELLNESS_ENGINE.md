# Financial Wellness Score Engine

## Overview

The **Financial Wellness Score Engine** is a psychologically-safe, stable, and behavior-dominant real-time scoring system designed to measure and track financial wellness across six key life pillars. The engine combines test results, real-time mood sentiment, and trending analysis to produce a holistic 0–100 wellness score that reflects both financial health and emotional readiness.

### Core Philosophy

- **Supportive & Non-Punitive**: Scores reflect reality but are smoothed to prevent single poor decisions from cratering confidence.
- **Behavior-Driven**: Test completion and mood snapshots directly inform score changes, not static algorithms.
- **Event-Driven**: Real-time updates respond to user actions (test completion, mood check-ins, chat interactions).
- **Modular & Extensible**: New test types and pillars can be added without breaking existing calculations.

---

## Architecture

### High-Level Flow

```
User Action (test completion, mood check-in)
    ↓
Wellness Event Captured
    ↓
Score Calculation:
  1. Normalize test/mood input to 0–100 scale
  2. Update pillar scores
  3. Apply throttling (smooth abrupt changes)
  4. Recalculate composite wellness score
  5. Generate insights & tier
    ↓
Persistence & Live Response
    ↓
Frontend Dashboard Updates (via useGetWellnessScore hook)
```

---

## Wellness Pillars & Weights

The composite score is built from **six pillars**, each weighted by their importance to financial wellness:

| Pillar               | Weight |                What It Measures                 |                    Examples                    |
|--------              |--------|-------------------------------------------------|----------------------------------------------- |
| **Money IQ**         |  20%   | Financial literacy & knowledge                  | Financial literacy tests, learning engagement  |
| **Debt Health**      |  20%   | Debt burden, repayment behavior, sustainability | Debt balance reviews, EMI pressure analysis    |
| **Financial Safety** |  20%   | Emergency readiness & savings buffer            | Emergency fund adequacy assessments            |
| **Credit Health**    |  15%   | Credit readiness & creditworthiness             | Credit readiness reviews, credit score proxies |
| **Loan Comfort**     |  10%   | Confidence in loan products & affordability     | Loan fit analysis, affordability checks        |
| **Mood Health**      |  15%   | Emotional readiness & financial confidence      | Real-time mood snapshots, sentiment analysis   |

**Composite Score Formula:**
```
Overall Score = (
  Money_IQ × 0.20 +
  Debt_Health × 0.20 +
  Financial_Safety × 0.20 +
  Credit_Health × 0.15 +
  Loan_Comfort × 0.10 +
  Mood_Health × 0.15
)
```

### Why These Weights?

- **Money IQ, Debt Health, Financial Safety** are equally weighted (20% each) because they form the foundation of financial wellness.
- **Mood Health** receives significant weight (15%) because emotional state strongly correlates with financial decision-making.
- **Credit Health** and **Loan Comfort** are secondary (15% + 10%) since they depend on the foundational pillars.

---

## Test Type Mapping

The engine recognizes these test types and maps them to pillars:

| Test Type | Canonical Form | Maps To Pillar | Score Direction |
|-----------|----------------|----------------|-----------------|
| `financial_literacy` | `financial_literacy` | Money IQ | Higher = Better |
| `money_iq` | `money_iq` | Money IQ | Higher = Better |
| `debt_balance` | `debt_balance` | Debt Health | **Inverted** (Pressure) |
| `debt_pressure` | `debt_pressure` | Debt Health | **Inverted** (Pressure) |
| `emergency_fund` | `emergency_fund` | Financial Safety | Higher = Better |
| `credit_readiness` | `credit_readiness` | Credit Health | Higher = Better |
| `loan_fit` | `loan_fit` | Loan Comfort | Higher = Better |
| `mood` | `mood` | Mood Health | Higher = Better |

### Pressure Test Types (Inverted Scoring)

Certain tests measure **financial pressure or risk**, not wellness directly. These are automatically **inverted**:

```
Inverted Score = 100 - Raw Score
```

**Why?** If a user scores 80% on a "debt pressure" test (high pressure), their wellness is actually lower. The inversion ensures that high pressure → lower wellness contribution.

**Pressure tests:**
- `debt_balance`
- `debt_pressure`
- `debt_pressure_analysis`
- `stress_metrics`

---

## Score Normalization

### Input Scaling

Tests may return scores in different formats. The engine normalizes all inputs to 0–100:

```python
def scale_to_percent(value):
    if 0.0 ≤ value ≤ 1.0:
        return value × 100       # e.g., 0.75 → 75
    if 0.0 ≤ value ≤ 5.0:
        return value × 20        # e.g., 4 → 80
    return value                 # Already 0–100
```

### Examples

| Raw Input | Scaled Result |
|-----------|---------------|
| 0.65 | 65 |
| 4.2 | 84 |
| 73 | 73 |
| 110 | 100 (clamped) |
| -5 | 0 (clamped) |

### Clamping

All scores are always clamped to [0, 100]:

```python
def clamp_score(value, min=0, max=100):
    return round(max(min, min(max, value)))
```

---

## Throttling: Smooth Score Updates

### Purpose

Prevent abrupt, confidence-eroding score swings. A single bad test shouldn't crater the overall wellness score.

### Mechanism

**Max allowed change per event:**
- **Mood events** (real-time sentiment): ±2 points per update
- **Test results**: ±10 points per test completion
- **Sync operations**: ±100 points (unthrottled, used during initialization)

### Formula

```python
def throttle_score_change(previous_score, proposed_score, event_type):
    max_delta = {
        "mood": 2,
        "test": 10,
        "test_result": 10,
        "test_completion": 10,
        "sync": 100,
    }.get(event_type, 100)
    
    delta = proposed_score - previous_score
    delta = max(-max_delta, min(max_delta, delta))  # Clamp delta
    return clamp_score(previous_score + delta)
```

### Example

**Scenario:** Your Loan Fit test score drops from 90 to 40 (proposed delta: -50).

| Pillar | Change Before Throttle | Max Allowed | Final Delta |
|--------|------------------------|-------------|-------------|
| Loan Comfort | -50 | ±10 | -10 |

Your Loan Comfort pillar drops by 10 (not 50). Overall score impact: `10 × 0.10 = 1 point`.

---

## Mood Integration

### Live Mood Stream

As users chat, the system captures real-time mood sentiment across five dimensions:

| Dimension | Meaning | Range |
|-----------|---------|-------|
| **Stress** | Financial anxiety level | 0 (no stress) to 100 (very stressed) |
| **Urgency** | Feeling of time pressure | 0 (relaxed) to 100 (urgent) |
| **Openness** | Receptiveness to advice | 0 (closed) to 100 (very open) |
| **Willingness** | Motivation to act | 0 (unmotivated) to 100 (highly motivated) |
| **Emotion** | General emotional tone | 0 (negative) to 100 (positive) |

### EMA (Exponential Moving Average) Trending

The system tracks a **7-day exponential moving average** for each dimension to identify trends:

```
EMA = (Current Value × 0.3) + (Previous EMA × 0.7)
```

Weights: Most recent = 30%, historical = 70% (responsive but stable).

### Mood-to-Wellness Conversion

**Mood Health Pillar Score:**
```
Mood Health = (
  (100 - Stress) × 0.25 +        # Lower stress = higher wellness
  (100 - Urgency) × 0.25 +       # Lower urgency = higher wellness
  Openness × 0.20 +              # Higher openness = higher wellness
  Willingness × 0.20 +           # Higher willingness = higher wellness
  Emotion × 0.10                 # Higher emotion = higher wellness
)
```

**Example:**
- Stress: 40, Urgency: 30, Openness: 70, Willingness: 80, Emotion: 60
- Mood Health = (60 × 0.25) + (70 × 0.25) + (70 × 0.20) + (80 × 0.20) + (60 × 0.10)
- Mood Health = 15 + 17.5 + 14 + 16 + 6 = **68.5**

---

## Wellness Tiers & Insights

### Tier Classification

Wellness Score → Emotional Tier:

| Score Range | Tier | Meaning | Color |
|-------------|------|---------|-------|
| 0–20 | **Recovering** | Early-stage, rebuilding confidence | 🔴 Red |
| 21–40 | **Stabilizing** | Making progress, establishing habits | 🟠 Orange |
| 41–60 | **Building** | Solid foundation, growing momentum | 🟡 Yellow |
| 61–80 | **Progressing** | Strong financial health, advancing | 🟢 Green |
| 81–100 | **Thriving** | Excellent wellness, flourishing | 💚 Dark Green |

### Adaptive Insights

When pillar scores drop significantly, the system generates **supportive insights** that:

1. **Validate the user's feelings** without blame.
2. **Contextualize the issue** (e.g., "Your emergency fund is below 3 months of expenses").
3. **Suggest concrete next steps** (e.g., "Start with ₹10,000–₹20,000 to build momentum").

**Example Insights by Pillar:**

| Pillar | Low Score Insight |
|--------|-------------------|
| Money IQ | "Financial literacy is your foundation. Even 1 hour/week of learning builds confidence." |
| Debt Health | "High debt-to-income ratio. Focus on one EMI at a time." |
| Financial Safety | "Emergency fund is thin. A ₹20,000 buffer prevents crisis spiral." |
| Credit Health | "Credit readiness involves small, consistent payments. You're building it." |
| Loan Comfort | "Not all loans are right for you—and that's okay. Affordability first." |
| Mood Health | "Financial stress is real. Take a breath. You're making progress." |

---

## Momentum Scoring

### Purpose

Track positive or negative momentum over the last 7–14 days to reward progress and identify declining trends early.

### Calculation

**Momentum Score** is derived from:
1. **Test completion frequency** (number of tests in last 7–14 days)
2. **Score trajectory** (average pillar improvement)
3. **Mood trend** (is the user becoming more open, willing, less stressed?)

```
Momentum = 50 + (Trend Contribution × 25)

Trend Contribution ranges from -1 (declining) to +1 (improving)
```

**Example:**
- User completed 3 tests in 7 days (high engagement): +0.4
- Average pillar improvement: +5 points (positive): +0.4
- Mood is more open, less urgent (positive): +0.3
- Momentum = 50 + ((0.4 + 0.4 + 0.3) / 3 × 25) = **58**

---

## Score Change Calculation

### What Does "-27 pts this week" Mean?

The dashboard previously surfaced the raw difference between two recent test scores, which could be confusing because a large raw delta does not translate directly to an equally large change in your overall wellness. The system now reports a **normalized (weighted) change** that reflects the estimated impact on the composite wellness score.

How the new `change_pts` is computed:

1. Identify the pillar the latest test affects (e.g., `loan_fit` → `loan_comfort`).
2. Compute the raw delta: `latest_test_normalized - previous_test_normalized`.
3. Scale that delta by the pillar weight (for example `loan_comfort` weight = 0.10).

```
change_pts = round((latest_test - previous_test) * pillar_weight)
```

Example (your scenario):
- Latest loan fit: 73, Previous loan fit: 100 → raw delta = -27
- Loan Comfort weight = 0.10 → impact = -27 × 0.10 ≈ -2.7 → **-3 pts** shown

This value represents the *expected contribution* of the latest test change to your overall wellness score. The dashboard still shows your overall wellness (`47/100`) separately — that is the current composite score after applying all pillars and smoothing rules.

### Trend Labels (unchanged)

| Change Pts | Trend | Meaning |
|-----------|-------|---------|
| ≥ +5 | Improving | Positive momentum |
| -4 to +4 | Steady | Stable performance |
| ≤ -5 | Softening | Declining trend |

---

## API Endpoints

### 1. Submit Test Result

**Endpoint:** `POST /api/v1/wellness/test-results`

**Request:**
```json
{
  "user_id": "user123",
  "test_type": "loan_fit",
  "raw_score": 73,
  "normalized_score": 73,
  "completed_at": "2026-05-21T10:30:00Z",
  "insights": ["Affordability mismatch", "Risk awareness"],
  "category_breakdown": {
    "category": "Moderate Risk",
    "riskLevel": "moderate"
  }
}
```

**Response:**
```json
{
  "message": "Test result recorded",
  "updated_score": 47,
  "wellness_tier": "Building",
  "momentum": 58,
  "change_pts": -3
}
```

### 2. Update Live Mood

**Endpoint:** `POST /api/v1/wellness/mood`

**Request:**
```json
{
  "user_id": "user123",
  "stress": 35,
  "urgency": 40,
  "openness": 75,
  "willingness": 85,
  "emotion": 65,
  "context": "Chat with financial coach"
}
```

**Response:**
```json
{
  "mood_health": 68,
  "updated_score": 48,
  "trend": "Improving"
}
```

### 3. Get Wellness Snapshot

**Endpoint:** `GET /api/v1/wellness/{user_id}`

**Response:**
```json
{
  "userId": "user123",
  "wellnessScore": 47,
  "wellnessTier": "Building",
  "momentumScore": 58,
  "breakdown": {
    "moneyIQ": 65,
    "debtHealth": 42,
    "financialSafety": 55,
    "creditHealth": 60,
    "loanComfort": 45,
    "moodHealth": 68,
    "overallScore": 47,
    "momentumScore": 58,
    "wellnessTier": "Building"
  },
  "pillars": {
    "moneyIQ": 65,
    "debtHealth": 42,
    "financialSafety": 55,
    "creditHealth": 60,
    "loanComfort": 45,
    "moodHealth": 68
  },
  "insights": [
    "Your debt burden is the focus area. Consolidation may help.",
    "Mood is improving. Stay consistent with check-ins.",
    "Financial literacy is strong. Keep learning."
  ],
  "liveMoodState": {
    "stress": 35,
    "urgency": 40,
    "openness": 75,
    "willingness": 85,
    "emotion": 65,
    "updatedAt": "2026-05-21T10:30:00Z"
  },
  "trendState": {
    "stress_trend": 32,
    "urgency_trend": 38,
    "openness_trend": 73,
    "willingness_trend": 82,
    "emotion_trend": 63,
    "updatedAt": "2026-05-21T10:30:00Z"
  },
  "updatedAt": "2026-05-21T10:30:00Z"
}
```

### 4. Legacy Endpoint (Generated API Compatibility)

**Endpoint:** `GET /api/v1/user/{user_id}/wellness-score`

**Response:**
```json
{
  "score": 47,
  "label": "Building",
  "change_pts": -3,
  "trend": "Softening",
  "session_count": 5,
  "active_days": 3
}
```

---

## Persistence & Storage

### Database Schema

**WellnessBreakdown** (Main wellness record per user):
- `user_id`: User identifier
- `overall_score`: Composite wellness score (0–100)
- `money_iq`, `debt_health`, `financial_safety`, `credit_health`, `loan_comfort`, `mood_health`: Pillar scores
- `wellness_tier`: Emotional tier (Recovering, Stabilizing, etc.)
- `momentum_score`: 7-day momentum (0–100)
- `insights`: Array of supportive insights
- `updated_at`: Timestamp of last update

**TestResult** (Individual test records):
- `user_id`: User identifier
- `test_type`: Type of assessment (e.g., `loan_fit`)
- `raw_score`: Original score (before normalization)
- `normalized_score`: 0–100 score used for wellness calculation
- `completed_at`: Test completion timestamp
- `insights`: JSON array of test-specific insights
- `category_breakdown`: JSON with test metadata

**MoodLiveState** (Real-time mood):
- `user_id`: User identifier
- `stress`, `urgency`, `openness`, `willingness`, `emotion`: Current mood dimensions
- `updated_at`: Timestamp of last mood update

**MoodTrendState** (7-day EMA):
- `user_id`: User identifier
- `stress_trend`, `urgency_trend`, `openness_trend`, `willingness_trend`, `emotion_trend`: EMA values
- `updated_at`: Timestamp of last trend calculation

---

## Recalculation & Updates

### When Does the Score Recalculate?

1. **Test Completion**: User finishes an assessment → Pillar updates → Overall recalculates
2. **Mood Update**: Chat sentiment captured → Mood Health updates → Overall recalculates
3. **Daily Sync**: (Optional) Nightly recalculation to refresh trending
4. **Manual Sync**: Admin or testing trigger for batch recalculation

### Recalculation Algorithm

```python
def recalculate_wellness(user_id, event_type="test"):
    # 1. Fetch all test results for user
    test_results = query_test_results(user_id)
    
    # 2. Calculate pillar scores from recent tests
    pillars = calculate_pillar_scores(test_results)
    
    # 3. Fetch and process mood state
    mood = get_mood_state(user_id)
    mood_health = calculate_mood_health(mood)
    
    # 4. Compute composite score
    proposed_score = weighted_sum(pillars, mood_health, PILLAR_WEIGHTS)
    
    # 5. Apply throttling
    previous_score = get_previous_score(user_id)
    final_score = throttle_score_change(previous_score, proposed_score, event_type)
    
    # 6. Calculate momentum
    momentum = calculate_momentum(test_results, mood)
    
    # 7. Generate insights
    insights = generate_insights(pillars, mood)
    
    # 8. Persist to database
    persist_wellness_breakdown(user_id, final_score, pillars, mood_health, momentum, insights)
    
    return {
        "score": final_score,
        "tier": determine_wellness_tier(final_score),
        "momentum": momentum,
        "insights": insights
    }
```

---

## Key Design Decisions

### 1. Why Weighted Averaging?

Different pillars matter differently. Money IQ and Debt Health form the foundation (20% each), while Loan Comfort is situational (10%). This prevents a single weak area from defining wellness.

### 2. Why Throttling?

Real financial life has ups and downs. Without throttling, a single low test score could swing the wellness score by 20+ points, eroding user confidence. Throttling ensures feedback is realistic but not destabilizing.

### 3. Why Mood Health is 15%?

Emotional state strongly predicts financial decision-making. A stressed, unmotivated user with 70% financial knowledge is less likely to succeed than a calm, willing user with 50% knowledge. Mood health reflects readiness to act.

### 4. Why Invert Pressure Tests?

Debt pressure and stress metrics are inversely related to wellness. A user scoring 90% on "high debt pressure" is actually in poor wellness condition. Inversion keeps semantics consistent: higher score = better wellness.

### 5. Why 7-Day EMA for Mood Trends?

- **7 days** captures medium-term mood patterns without noise
- **EMA** (70% historical, 30% current) smooths volatile daily swings while responding to real changes
- Helps identify sustained trends (e.g., "user is getting more open to advice") vs. noise

---

## Testing & Validation

### Test Coverage

The wellness engine is validated with:

1. **Unit Tests** (`test_wellness_engine.py`):
   - Score normalization (0–1, 0–5, 0–100 ranges)
   - Tier determination (score → tier mapping)
   - Throttling behavior (±2 for mood, ±10 for tests)
   - Pressure test inversion (high pressure → low wellness)

2. **Integration Tests** (`test_api_integration.py`):
   - End-to-end test submission → score update
   - Mood capture → wellness recalculation
   - Multi-pillar interactions (one test doesn't dominate)

3. **Regression Tests**:
   - Chat integration doesn't break mood updates
   - Database persistence is consistent
   - Generated API client receives expected response shape

### Example Test Cases

**Test 1: Single Low Test, Doesn't Crater Overall Score**
```python
# User with balanced pillars (all ~60)
# Loan Fit test scores 40
# Expected: Loan Comfort drops ~40, but overall drops only ~4 (weighted by 10%)
assert overall_score_change ≈ -4
```

**Test 2: Throttling Prevents Abrupt Swings**
```python
# Proposed overall change: -50 from a test
# Expected: Actual change clamped to ±10
# Final: -10 instead of -50
assert abs(final_change) <= 10
```

**Test 3: Mood Updates Don't Overwhelm Test Results**
```python
# Test completion updates score by ±10
# Mood update follows, tries to change by ±2
# Expected: Both applied independently, combined effect is smooth
assert score_after_both > score_after_test_alone
```

---

## Future Extensions

### 1. Custom Test Types

Add new assessment types without breaking the engine:
```python
TEST_TO_PILLAR["my_custom_test"] = "money_iq"
# Submission works immediately, no code changes needed
```

### 2. Behavioral Insights

Track patterns like:
- Test-taking frequency ("User is engaging 3x/week")
- Mood stability ("User stress trending down consistently")
- Pillar correlations ("High debt stress → Lower openness to advice")

### 3. Goal-Aligned Scoring

Support personal goals:
```python
# User sets goal: "Reduce debt stress"
# System weights debt_health more heavily in their personalized score
# Same shared data, personalized weights
```

### 4. Notifications & Alerts

Trigger supportive messages:
- "Your mood is improving—keep going!"
- "Try a short financial literacy quiz to build confidence"
- "Emergency fund hit a milestone—celebrate!"

---

## Troubleshooting

### My score isn't updating after a test

**Checklist:**
1. ✓ Test submission reaches `/api/v1/wellness/test-results` with `normalized_score` (0–100)
2. ✓ User `user_id` is consistent across frontend and backend
3. ✓ Database transaction committed (check logs for errors)
4. ✓ No throttling limiting change (`test_type` should be "test" or "test_result" for ±10 allowance)

### Why did my score drop more than expected?

**Likely causes:**
1. **Multiple pillars affected**: If a test touched multiple pillars (e.g., debt + mood), changes combine
2. **Throttling delayed the change**: Previous update was throttled; current update adds to it
3. **Mood concurrently degraded**: Test result + mood update both applied in same recalculation

Check the `insights` field in the response—it explains which pillars changed.

### Mood trending seems stuck

**Solution:**
- EMA requires 3–5 mood updates to show clear trends
- Verify mood captures are reaching `/api/v1/wellness/mood` with valid dimensions (0–100)
- Check `MoodTrendState` table for recent timestamps

---

## Performance & Limits

- **Score calculation**: ~10–50ms (depends on test result history size)
- **Recalculation frequency**: Once per event (test, mood), not polling
- **Storage**: ~500 bytes per TestResult, ~200 bytes per MoodLiveState
- **Scalability**: Tested with 1000+ test results per user; indexed by `user_id` and `completed_at`

---

## References

- **Wellness Scoring Module**: `src/utils/wellness_scoring.py`
- **Service Layer**: `src/utils/wellness_service.py`
- **API Routes**: `src/routers/wellness.py`
- **Database Models**: `src/models.py` (WellnessBreakdown, TestResult, MoodLiveState, MoodTrendState)
- **Tests**: `tests/test_wellness_engine.py`, `tests/test_api_integration.py`

---

## Summary

The Financial Wellness Score Engine is a **thoughtfully-designed, psychologically-safe system** that:

✅ Measures wellness across six foundational pillars  
✅ Normalizes diverse test formats into a unified 0–100 scale  
✅ Smooths score updates to prevent confidence erosion  
✅ Integrates real-time mood to assess readiness  
✅ Generates supportive, actionable insights  
✅ Tracks momentum to reward engagement and identify trends  

It empowers users with transparent, stable feedback while maintaining the flexibility to grow and adapt with their financial wellness journey.
