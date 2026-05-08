"""Tests for the conversation state machine helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.conversation_state import (
    build_conversation_state_guidance,
    infer_conversation_state,
)


def test_education_stage_for_concept_question():
    state = infer_conversation_state(
        "What is a SIP and how does it work?",
        prior_texts=["User: I want to start investing."]
    )

    assert state.stage == "education"
    assert state.current_topic == "investment"
    assert state.loop_detected is False


def test_solution_stage_for_decision_question():
    state = infer_conversation_state(
        "Should I pick a fixed deposit or mutual funds for my savings goal?",
        prior_texts=[
            "User: I'm thinking about investing.",
            "Assistant: I explained the basics of both options.",
        ],
    )

    assert state.stage == "solution"
    assert state.current_topic == "investment"
    assert state.loop_detected is False


def test_repeated_topic_triggers_follow_up_and_loop_detection():
    state = infer_conversation_state(
        "You already explained mutual funds, but I'm still confused about mutual funds versus fixed deposits.",
        prior_texts=[
            "User: I want mutual funds versus fixed deposits.",
            "Assistant: Here are the basics of both.",
            "User: Can you explain mutual funds versus fixed deposits again?",
            "Assistant: I already covered that comparison.",
        ],
    )

    guidance = build_conversation_state_guidance(state)

    assert state.stage == "follow_up"
    assert state.loop_detected is True
    assert "Do not repeat earlier advice" in guidance
    assert "follow-up question" in guidance
