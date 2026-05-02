"""
Emotion and mood analysis for user messages.
Analyzes stress level, emotional state, financial urgency, willingness to learn, 
and openness to solutions to inform therapeutic response customization.
"""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Keyword patterns for mood detection
STRESS_KEYWORDS = {
    "high": [
        "panic", "panicking", "terrified", "desperate", "crisis", "emergency",
        "can't", "can't handle", "breaking down", "suicidal", "hopeless",
        "overwhelmed", "drowning", "trapped", "urgent", "immediately"
    ],
    "moderate": [
        "worried", "anxious", "stressed", "concerned", "nervous", "frustrated",
        "confused", "lost", "stuck", "struggling", "difficult", "hard", "tough"
    ],
    "low": [
        "curious", "interested", "wondering", "exploring", "thinking",
        "learning", "wondering", "okay", "fine", "manageable"
    ]
}

EMOTIONAL_STATE_KEYWORDS = {
    "anxious": [
        "panic", "nervous", "worried", "afraid", "scared", "anxious",
        "can't sleep", "stress", "pressure", "tight", "uneasy"
    ],
    "confused": [
        "confused", "don't understand", "unclear", "lost", "bewildered",
        "struggling to", "what does", "how do", "explain", "don't know"
    ],
    "shameful": [
        "ashamed", "embarrassed", "stupid", "dumb", "feel bad", "regret",
        "shouldn't have", "failed", "mess", "irresponsible", "bad at"
    ],
    "hopeless": [
        "hopeless", "despair", "never", "impossible", "can't change",
        "always fail", "give up", "what's the point", "useless"
    ],
    "defensive": [
        "you don't understand", "not my fault", "everyone else", "but",
        "disagree", "right", "wrong", "criticism"
    ],
    "reflective": [
        "i think", "i realize", "i understand", "makes sense", "learned",
        "pattern", "i see", "perspective", "stepping back", "actually"
    ],
    "ready": [
        "ready", "want to", "let's", "how do i", "help me", "show me",
        "do this", "start", "begin", "try"
    ]
}

FINANCIAL_URGENCY_KEYWORDS = {
    "crisis": [
        "today", "now", "immediately", "emergency", "can't wait", "overdue",
        "payment due", "bill", "eviction", "foreclosure", "urgent"
    ],
    "urgent": [
        "soon", "this week", "this month", "deadline", "coming up",
        "need to", "have to", "must", "important"
    ],
    "routine": [
        "planning", "thinking about", "wondering", "considering",
        "eventually", "someday", "exploring", "research"
    ]
}

WILLINGNESS_TO_LEARN_KEYWORDS = {
    "high": [
        "explain", "how does", "understand", "teach", "learn", "educate",
        "what is", "interested", "curious", "show me", "breakdown"
    ],
    "medium": [
        "okay", "sure", "might", "could", "maybe", "i guess",
        "depends", "depends on", "if you think"
    ],
    "low": [
        "don't care", "doesn't matter", "just", "already know",
        "not interested", "whatever", "skip"
    ]
}

OPENNESS_TO_SOLUTIONS_KEYWORDS = {
    "ready": [
        "help me", "show me", "how do i", "what are options", "let's",
        "ready", "want to", "curious", "explore"
    ],
    "exploratory": [
        "could", "might", "maybe", "possibly", "consider", "explore",
        "what if", "think about"
    ],
    "cautious": [
        "not sure", "hesitant", "worried about", "concern", "risky",
        "be careful", "but what if", "downside"
    ],
    "closed": [
        "don't want", "can't", "impossible", "no way", "refuse",
        "won't", "not interested", "no thanks"
    ]
}


def _extract_keywords(text: str, keyword_dict: Dict[str, List[str]]) -> Tuple[str, float]:
    """
    Extract the predominant category from text based on keyword matching.
    Returns tuple of (category, confidence_score).
    """
    text_lower = text.lower()
    matches = {}
    
    for category, keywords in keyword_dict.items():
        count = sum(1 for keyword in keywords if keyword in text_lower)
        if count > 0:
            matches[category] = count
    
    if not matches:
        return None, 0.0
    
    # Return category with highest match count
    top_category = max(matches, key=matches.get)
    max_matches = matches[top_category]
    total_matches = sum(matches.values())
    confidence = min(max_matches / 3.0, 1.0)  # Cap confidence at 1.0 (3 keywords = max confidence)
    
    return top_category, confidence


def _analyze_sentence_structure(text: str) -> Dict[str, float]:
    """Analyze linguistic patterns: sentence length, punctuation, repetition."""
    sentences = text.split(".")
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
    
    # Short choppy sentences indicate high emotion/panic
    short_sentence_ratio = sum(1 for s in sentences if len(s.split()) < 5) / len(sentences) if sentences else 0
    
    # Exclamation marks indicate high emotion/urgency
    exclamation_count = text.count("!")
    
    # Question marks indicate seeking help/confusion
    question_count = text.count("?")
    
    # Repetition indicates obsessive thinking (anxiety)
    words = text.lower().split()
    word_freq = {}
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1
    max_repetition = max(word_freq.values()) if word_freq else 0
    
    return {
        "avg_sentence_length": avg_sentence_length,
        "short_sentence_ratio": short_sentence_ratio,
        "exclamation_ratio": min(exclamation_count / len(sentences), 1.0) if sentences else 0,
        "question_ratio": min(question_count / len(sentences), 1.0) if sentences else 0,
        "repetition_intensity": min(max_repetition / 5.0, 1.0)  # 5+ repeats = high
    }


def _estimate_conversation_depth(message_count: int) -> str:
    """Estimate user engagement level based on conversation depth."""
    if message_count < 2:
        return "initial"
    elif message_count < 5:
        return "early"
    elif message_count < 10:
        return "mid"
    else:
        return "deep"


class EmotionAnalyzer:
    """Analyze user messages for emotional state and mood indicators."""
    
    def analyze(self, user_message: str, conversation_depth: int = 0) -> Dict:
        """
        Analyze a user message and return mood/emotion indicators.
        
        Args:
            user_message: The user's text message
            conversation_depth: Number of previous messages in conversation (0 for first message)
            
        Returns:
            Dictionary with stress_level, indicators, detected_keywords, and confidence scores
        """
        try:
            # Primary stress level detection
            stress_level, stress_confidence = self._detect_stress_level(user_message)
            
            # Secondary indicators
            emotional_state, emotion_confidence = _extract_keywords(
                user_message, EMOTIONAL_STATE_KEYWORDS
            )
            
            financial_urgency, urgency_confidence = _extract_keywords(
                user_message, FINANCIAL_URGENCY_KEYWORDS
            )
            
            willingness_to_learn, willingness_confidence = _extract_keywords(
                user_message, WILLINGNESS_TO_LEARN_KEYWORDS
            )
            
            openness_to_solutions, openness_confidence = _extract_keywords(
                user_message, OPENNESS_TO_SOLUTIONS_KEYWORDS
            )
            
            # Linguistic analysis
            linguistic_patterns = _analyze_sentence_structure(user_message)
            
            # Conversation depth
            conversation_phase = _estimate_conversation_depth(conversation_depth)
            
            # Ensemble confidence (combine multiple signals)
            overall_confidence = self._calculate_ensemble_confidence(
                stress_confidence,
                emotion_confidence,
                linguistic_patterns,
                conversation_depth
            )
            
            result = {
                "stress_level": stress_level,
                "stress_confidence": round(stress_confidence, 2),
                "indicators": {
                    "emotional_state": emotional_state,
                    "financial_urgency": financial_urgency,
                    "willingness_to_learn": willingness_to_learn,
                    "openness_to_solutions": openness_to_solutions,
                },
                "confidence_scores": {
                    "emotional_state": round(emotion_confidence, 2),
                    "financial_urgency": round(urgency_confidence, 2),
                    "willingness_to_learn": round(willingness_confidence, 2),
                    "openness_to_solutions": round(openness_confidence, 2),
                },
                "linguistic_patterns": {k: round(v, 2) for k, v in linguistic_patterns.items()},
                "conversation_phase": conversation_phase,
                "overall_confidence": round(overall_confidence, 2),
            }
            
            detected_keywords = self._extract_detected_keywords(user_message, stress_level)
            if detected_keywords:
                result["detected_keywords"] = detected_keywords
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing emotion: {str(e)}")
            return {
                "stress_level": "unknown",
                "error": str(e)
            }
    
    def _detect_stress_level(self, text: str) -> Tuple[str, float]:
        """Detect primary stress level: high, moderate, or low."""
        text_lower = text.lower()
        
        high_count = sum(1 for kw in STRESS_KEYWORDS["high"] if kw in text_lower)
        moderate_count = sum(1 for kw in STRESS_KEYWORDS["moderate"] if kw in text_lower)
        low_count = sum(1 for kw in STRESS_KEYWORDS["low"] if kw in text_lower)
        
        # Boost high stress if exclamation marks or all caps
        if "!" in text or text.isupper():
            high_count += 2
        
        counts = {
            "high": high_count,
            "moderate": moderate_count,
            "low": low_count
        }
        
        if all(v == 0 for v in counts.values()):
            return "unknown", 0.0
        
        top_level = max(counts, key=counts.get)
        max_count = counts[top_level]
        confidence = min(max_count / 3.0, 1.0)
        
        return top_level, confidence
    
    def _calculate_ensemble_confidence(
        self,
        stress_conf: float,
        emotion_conf: float,
        linguistic: Dict,
        depth: int
    ) -> float:
        """Combine multiple confidence signals."""
        # Higher confidence if multiple signals align
        linguistic_signal = max(
            linguistic["short_sentence_ratio"],
            linguistic["exclamation_ratio"],
            linguistic["question_ratio"]
        )
        
        # Weight by conversation depth (early messages are noisier)
        depth_factor = min(depth / 5.0, 1.0) * 0.5 + 0.5  # Range: 0.5 to 1.0
        
        combined = (stress_conf + emotion_conf + linguistic_signal) / 3.0
        return combined * depth_factor
    
    def _extract_detected_keywords(self, text: str, stress_level: str) -> List[str]:
        """Extract actual keywords found in the text for transparency."""
        text_lower = text.lower()
        relevant_keywords = STRESS_KEYWORDS.get(stress_level, [])
        detected = [kw for kw in relevant_keywords if kw in text_lower]
        return detected[:5]  # Return top 5 to avoid noise


# Singleton instance
_analyzer = EmotionAnalyzer()


def analyze_emotion(user_message: str, conversation_depth: int = 0) -> Dict:
    """
    Analyze user message emotion and mood.
    
    Args:
        user_message: The user's text
        conversation_depth: How many messages in the conversation so far
        
    Returns:
        Dictionary with mood indicators
    """
    return _analyzer.analyze(user_message, conversation_depth)
