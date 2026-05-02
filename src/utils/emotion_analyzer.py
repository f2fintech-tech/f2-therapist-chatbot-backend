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
        "overwhelmed", "drowning", "trapped", "urgent", "immediately",
        "humiliated", "can't sleep", "falling apart", "scared",
        "afraid", "rejected", "rejection", "failing",
        "losing everything", "burden", "pressure", "helpless",
        "stressed out", "default", "late payment",
        "multiple emis", "collection calls", "financial pressure",
        "medical emergency", "salary delayed", "business loss",
        "loan rejection", "fear of rejection", "emis due","emis are due","can't pay bills","can't pay emi",
        "no money", "bills due", "eviction", "foreclosure","overdue", "can't manage", "handling too many things",
        "can't survive this","everything is collapsing", "i feel stuck","i'm drowning in debt", "i ruined my finances",
        "constant tension","i feel trapped financially","can't manage anymore","i'm at my breaking point","i'm exhausted",
        "too much responsibility","my family depends on me","i can't fail","fear of losing job","fear of losing business",
        "can't breathe","this is too much","i'm mentally tired","financial nightmare","out of control","emotionally drained",
        "i feel cornered","pressure is killing me",
        "credit card debt", "credit card debts", "medical bills", "multiple debts", "multiple loans",
        "sales dropped", "sales down", "dropped sales", "business failing", "business collapsed",
        "don't know how to manage"
    ],

    "moderate": [
        "worried", "anxious", "stressed", "concerned", "nervous", "frustrated",
        "confused", "lost", "stuck", "struggling", "difficult", "hard", "tough",
        "uncertain", "hesitant", "overthinking", "challenging",
        "tight budget", "managing somehow", "uncomfortable",
        "complicated", "pressure from family", "financial stress",
        "unstable", "uneasy", "concerned about money","trying to manage",
        "not sure what to do","handling somehow","things are difficult","little stressed",
        "feels risky","too many expenses","money is tight","things feel unstable",
        "i'm worried about future","not financially secure","not confident","unsure about decision",
        "need guidance","feeling pressured",
        "credit score", "don't understand", "confused", "confusing",
        "need help understanding", "need explanation",
        "processing fees", "loan terms", "interest rate", "emi"
    ],

    "low": [
        "curious", "interested", "wondering", "exploring", "thinking",
        "learning", "wondering", "okay", "fine", "manageable",
        "planning", "researching", "comparing", "stable",
        "under control", "just checking", "evaluating",
        "reviewing", "future planning", "financial goals","doing research",
        "want better options", "looking for alternatives", "considering lenders",
        "exploring possibilities","financially stable",
        "checking rates","planning ahead","thinking strategically","looking for best deal",
        "just comparing","want more clarity",
        "transparency", "compare", "breakdown", "data", "numbers",
        "real cost", "total cost", "how does this compare", "show me",
        "what is the", "can you explain", "data driven", "analytical"
    ]
}


EMOTIONAL_STATE_KEYWORDS = {

    "anxious": [
        "panic", "nervous", "worried", "afraid", "scared", "anxious",
        "can't sleep", "stress", "pressure", "tight", "uneasy",
        "what if", "terrified", "rejected", "fear",
        "overthinking", "panic attack", "fear of failure",
        "financial anxiety", "loan anxiety","what if i fail",
        "what if they reject me","what if i can't pay",
        "i'm scared of debt","i'm terrified",
        "i don't want another mistake","i'm afraid things get worse",
        "constant worry","always stressed","i feel unsafe financially",
        "worried about parents","worried about family",
        "can't stop thinking","fear of making wrong choice"
    ],

    "confused": [
        "confused", "don't understand", "unclear", "lost", "bewildered",
        "struggling to", "what does", "how do", "explain", "don't know",
        "loan terms", "emi", "interest", "processing fee",
        "too complicated", "need clarification", "break it down",
        "simple language", "hard to understand","finance confuses me",
        "i don't understand loans","all these terms confuse me",
        "too many financial words","need simple explanation",
        "don't know where to start","this feels overwhelming",
        "please simplify","what does this mean","i don't know what to ask"
    ],

    "shameful": [
        "ashamed", "embarrassed", "stupid", "dumb", "feel bad", "regret",
        "shouldn't have", "failed", "mess", "irresponsible", "bad at",
        "my mistake", "feel guilty", "humiliated","judged", "bad decisions", "i messed up",
        "feel like failure", "not good enough","i ruined everything",
        "i made bad choices","i feel guilty","people will judge me","i feel embarrassed",
        "i should've known better","i feel irresponsible","i hate myself for this","i failed my family",
        "i feel weak financially"
    ],

    "hopeless": [
        "hopeless", "despair", "never", "impossible", "can't change",
        "always fail", "give up", "what's the point", "useless",
        "no way out", "never ending", "drowning","falling apart", "nothing works", "stuck forever",
        "can't recover", "life is ruined","things will never improve",
        "i'm stuck forever","there's no solution",
        "nothing helps","i've tried everything","i don't see a future",
        "i'm done","can't escape debt","everything feels pointless"
    ],

    "defensive": [
        "you don't understand", "not my fault", "everyone else", "but",
        "disagree", "right", "wrong", "criticism",
        "stop judging", "i already know", "actually","that's wrong", "everyone does this",
        "i had no choice","people don't understand my situation",
        "you don't know my life","i had to do it","there was no option","i'm trying my best",
        "it's easy to judge","not everything is simple"
    ],

    "reflective": [
        "i think", "i realize", "i understand", "makes sense", "learned",
        "pattern", "i see", "perspective", "stepping back", "actually",
        "looking back", "thinking carefully", "i see now",
        "understand better", "lesson learned","trying to improve","i need better planning",
        "i should be smarter financially","i'm learning from this",
        "i understand my mistakes","i want to improve",
        "trying to be responsible","i see the pattern now"
    ],

    "ready": [
        "ready", "want to", "let's", "how do i", "help me", "show me",
        "do this", "start", "begin", "try","guide me", "next step", "what should i do",
        "walk me through", "help me improve",
        "best option", "need a plan","i want a solution",
        "tell me what to do","i'm ready to fix this",
        "help me move forward","i want financial stability",
        "i need a strategy","show me the safest option"
    ],

    # NEW CATEGORY
    "overwhelmed": [
        "too much", "everything at once", "buried",
        "exhausted", "drained", "multiple emis",
        "no breathing room", "can't manage",
        "handling too many things","too many responsibilities",
        "family pressure","business pressure","i'm mentally exhausted","too many payments",
        "life feels heavy","i'm carrying everyone","financial burden is huge"
    ],

    # NEW CATEGORY
    "analytical": [
        "compare", "breakdown", "data", "numbers",
        "real cost", "hidden fees", "calculations",
        "rate comparison", "pros and cons","financial decision", "statistics",
        "best roi", "transparent","show me comparison",
        "give me actual numbers","i need transparency",
        "what's the total cost","show full breakdown",
        "i want detailed analysis","what's financially optimal",
        "need evidence","logical decision","data driven",
        "i researched already","need smarter option"
    ]
}


FINANCIAL_URGENCY_KEYWORDS = {

    "crisis": [
        "today", "now", "immediately", "emergency", "can't wait", "overdue",
        "payment due", "bill", "eviction", "foreclosure", "urgent",
        "default", "collection call", "need money now",
        "medical emergency", "rent due", "can't pay emi",
        "salary delayed", "business loss", "loan overdue",
        "late fees", "urgent payment","need help immediately",
        "business is collapsing","need money for surgery",
        "can't survive this month","emi due tomorrow","credit card maxed out",
        "bank keeps calling","cash flow crisis"
    ],

    "urgent": [
        "soon", "this week", "this month", "deadline", "coming up",
        "need to", "have to", "must", "important",
        "upcoming emi", "inventory purchase","school fees", "working capital",
        "festival season", "monthly dues","business expenses","need inventory soon",
        "upcoming family expense","need working capital","need to manage payments",
        "business season coming","need short term support"
    ],

    "routine": [
        "planning", "thinking about", "wondering", "considering",
        "eventually", "someday", "exploring", "research",
        "researching", "future goals", "financial planning",
        "comparing lenders", "investment planning","loan comparison","planning ahead",
        "checking best rates","looking for better options","future investment",
        "retirement planning","optimizing finances"
    ]
}


WILLINGNESS_TO_LEARN_KEYWORDS = {

    "high": [
        "explain", "how does", "understand", "teach", "learn", "educate",
        "what is", "interested", "curious", "show me", "breakdown",
        "guide me", "walk me through", "help me learn",
        "simple explanation", "step by step",
        "examples", "clarify", "teach me finance"
    ],

    "medium": [
        "okay", "sure", "might", "could", "maybe", "i guess",
        "depends", "depends on", "if you think",
        "possibly", "open to learning",
        "can try", "maybe helpful"
    ],

    "low": [
        "don't care", "doesn't matter", "just", "already know",
        "not interested", "whatever", "skip",
        "skip details", "too much information",
        "just tell me", "don't explain",
        "keep it short"
    ]
}


OPENNESS_TO_SOLUTIONS_KEYWORDS = {

    "ready": [
        "help me", "show me", "how do i", "what are options", "let's",
        "ready", "want to", "curious", "explore",
        "guide me", "best solution",
        "want to improve", "let's start",
        "need a plan", "what should i do"
    ],

    "exploratory": [
        "could", "might", "maybe", "possibly", "consider", "explore",
        "what if", "think about",
        "researching options", "comparing",
        "looking into", "open minded",
        "trying to understand"
    ],

    "cautious": [
        "not sure", "hesitant", "worried about", "concern", "risky",
        "be careful", "but what if", "downside",
        "hidden charges", "what's the catch",
        "sounds risky", "don't want problems",
        "need reassurance", "careful decision"
    ],

    "closed": [
        "don't want", "can't", "impossible", "no way", "refuse",
        "won't", "not interested", "no thanks",
        "leave it", "forget it", "won't work",
        "don't trust this", "not doing that",
        "stop suggesting"
    ]
}


def _extract_keywords(text: str, keyword_dict: Dict[str, List[str]]) -> Tuple[str, float]:
    """
    Extract the predominant category from text based on keyword matching.
    Uses word-boundary matching to handle phrases with intervening words.
    Returns tuple of (category, confidence_score).
    """
    text_lower = text.lower()
    matches = {}
    
    for category, keywords in keyword_dict.items():
        count = 0
        for keyword in keywords:
            # Use word-boundary regex for multi-word phrases (e.g., "emis due" matches "emis are due")
            # For single words, use precise word-boundary matching
            if " " in keyword:
                # For phrases: match words in order, allowing other words between them
                words = re.split(r'\s+', keyword)
                pattern = r'\s+'.join(re.escape(w) for w in words)
                if re.search(pattern, text_lower):
                    count += 1
            else:
                # For single words: use strict word boundaries
                if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    count += 1
        
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
