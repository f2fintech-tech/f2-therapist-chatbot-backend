import pytest

from src.utils.emotion_analyzer import analyze_emotion


def test_analyze_emotion_high_stress():
    msg = "I'm panicking! I lost my job and have bills due now."
    result = analyze_emotion(msg, conversation_depth=0)
    assert result["stress_level"] in {"high", "moderate"}
    assert "stress_confidence" in result
    assert result["overall_confidence"] >= 0.0


def test_analyze_emotion_confused():
    msg = "I don't understand EMI, can you explain how it works?"
    result = analyze_emotion(msg, conversation_depth=1)
    assert result["indicators"]["emotional_state"] == "confused"
    assert result["conversation_phase"] in {"initial", "early", "mid", "deep"}


def test_analyze_emotion_willingness():
    msg = "Please explain, I want to learn how this works."
    result = analyze_emotion(msg, conversation_depth=2)
    assert result["indicators"]["willingness_to_learn"] in {"high", None}
