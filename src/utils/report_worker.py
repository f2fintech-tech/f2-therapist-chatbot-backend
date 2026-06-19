import os
import uuid
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from langchain_google_genai import ChatGoogleGenerativeAI
from src.models import (
    User, Conversation, ConversationMessage, MessageRole,
    UserCreditReport, UserLoanCalculatorActivity, TestResult,
    UserConsolidatedProfile, UserSessionReport
)

logger = logging.getLogger(__name__)

def get_report_llm():
    """Instantiate a local LLM client for generating summaries."""
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment")
        raise ValueError("GEMINI_API_KEY is not configured")
    
    logger.info(f"Initializing Report ChatGoogleGenerativeAI with model: {model_name}")
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.4,
        max_output_tokens=3072,
        google_api_key=api_key
    )

def _extract_text(content) -> str:
    """Helper to safely extract string text from potentially list-formatted LLM responses."""
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)
        return "".join(text_parts)
    return content if isinstance(content, str) else str(content)

def aggregate_user_activity(db: Session, user_id: str, start_date: datetime, end_date: datetime) -> dict:
    """Queries and compiles all user activities and telemetry within the timeframe."""
    
    # 1. Fetch chat message counts & average mood metadata
    messages = db.query(ConversationMessage).join(Conversation).filter(
        Conversation.user_id == user_id,
        ConversationMessage.created_at >= start_date,
        ConversationMessage.created_at <= end_date
    ).all()

    user_msg_count = sum(1 for m in messages if m.role == MessageRole.USER)
    
    mood_scores = {
        "stress": [],
        "urgency": [],
        "openness": [],
        "willingness": [],
        "emotion": []
    }

    for m in messages:
        if m.role == MessageRole.ASSISTANT and m.mood:
            mood_dict = m.mood
            dims = mood_dict.get("dimensions", {})
            if dims:
                for k in ["stress", "urgency", "openness", "willingness", "emotion"]:
                    if v := dims.get(k):
                        mood_scores[k].append(float(v))
                        
    avg_mood = {}
    for k, vals in mood_scores.items():
        avg_mood[k] = round(sum(vals) / len(vals), 1) if vals else 50.0

    # 2. Fetch CIBIL credit score checks
    cibil_checks = db.query(UserCreditReport).filter(
        UserCreditReport.user_id == user_id,
        UserCreditReport.fetched_at >= start_date,
        UserCreditReport.fetched_at <= end_date
    ).all()

    cibil_log = []
    for check in cibil_checks:
        cibil_log.append({
            "bureau": check.bureau,
            "score": check.score,
            "fetched_at": check.fetched_at.isoformat()
        })

    # 3. Fetch Loan Calculator runs
    calc_runs = db.query(UserLoanCalculatorActivity).filter(
        UserLoanCalculatorActivity.user_id == user_id,
        UserLoanCalculatorActivity.created_at >= start_date,
        UserLoanCalculatorActivity.created_at <= end_date
    ).all()

    calc_log = []
    for run in calc_runs:
        calc_log.append({
            "calculator_type": run.calculator_type,
            "loan_type": run.loan_type,
            "created_at": run.created_at.isoformat()
        })

    # 4. Fetch Completed wellness quizzes/tests
    tests = db.query(TestResult).filter(
        TestResult.user_id == user_id,
        TestResult.completed_at >= start_date,
        TestResult.completed_at <= end_date
    ).all()

    test_log = []
    for test in tests:
        test_log.append({
            "test_type": test.test_type,
            "raw_score": test.raw_score,
            "normalized_score": test.normalized_score,
            "completed_at": test.completed_at.isoformat()
        })

    # 5. Fetch watched educational videos & articles from profile metadata
    profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).first()
    videos_seen = []
    articles_seen = []
    if profile and profile.data:
        edu = profile.data.get("financial_education", {})
        videos_seen = edu.get("videos_seen", [])
        articles_seen = edu.get("articles_seen", [])

    return {
        "user_msg_count": user_msg_count,
        "avg_mood": avg_mood,
        "cibil_log": cibil_log,
        "calc_log": calc_log,
        "test_log": test_log,
        "videos_seen": videos_seen,
        "articles_seen": articles_seen
    }

def generate_report_for_user(db: Session, user_id: str, report_type: str) -> UserSessionReport | None:
    """Fetches telemetry for the window, runs LLM analysis, and saves to database."""
    now = datetime.utcnow()
    
    if report_type == "daily":
        start_date = now - timedelta(days=1)
        end_date = now
    elif report_type == "fortnightly":
        start_date = now - timedelta(days=15)
        end_date = now - timedelta(days=1)
    elif report_type == "monthly":
        start_date = now - timedelta(days=30)
        end_date = now - timedelta(days=1)
    else:
        logger.error(f"Invalid report type specified: {report_type}")
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"User {user_id} not found in database")
        return None

    # Step 1: Gather Activity Log
    activity = aggregate_user_activity(db, user_id, start_date, end_date)
    
    # Check if there is any activity in the timeframe
    has_activity = (
        activity["user_msg_count"] > 0 or
        len(activity["cibil_log"]) > 0 or
        len(activity["calc_log"]) > 0 or
        len(activity["test_log"]) > 0
    )
    
    if not has_activity:
        logger.info(f"Skipping report generation for user {user_id}. No activities in timeframe.")
        return None

    # Step 2: Call Gemini LLM to compile report
    try:
        llm = get_report_llm()
        
        prompt = f"""
        You are an expert, empathetic Financial Therapist and Counselor. 
        Analyze the user's financial wellness activity logs and chat history for the period {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} and compile a structured financial therapy report.

        Here is the User profile:
        - Name: {user.name or 'N/A'}
        - Wellness Score: {user.wellness_score}/100
        - Wellness Tier: {user.wellness_tier}

        Here is the User's activity log during this period:
        - Chat message count: {activity["user_msg_count"]} user messages sent.
        - CIBIL score checks performed: {json.dumps(activity["cibil_log"])}
        - Loan calculator runs performed: {json.dumps(activity["calc_log"])}
        - Financial wellness tests completed: {json.dumps(activity["test_log"])}
        - Educational videos consumed: {json.dumps(activity["videos_seen"])}
        - Educational articles consumed: {json.dumps(activity["articles_seen"])}

        Average mood/stress dimensions during this period (scaled 0-100, where higher stress means more anxiety, higher openness means ready for options):
        - Average Stress Level: {activity["avg_mood"].get('stress', 50.0)}/100
        - Average Financial Urgency: {activity["avg_mood"].get('urgency', 50.0)}/100
        - Average Openness to Solutions: {activity["avg_mood"].get('openness', 50.0)}/100
        - Average Learning Willingness: {activity["avg_mood"].get('willingness', 50.0)}/100
        - Average General Emotion Score: {activity["avg_mood"].get('emotion', 50.0)}/100

        Please structure your output exactly as a JSON object with the following keys:
        {{
            "summary": "A cohesive, compassionate 3-4 sentence paragraph summarizing the user's financial therapy progress, acknowledging their emotions and highlighting of the key topic they focused on.",
            "key_takeaways": [
                "Takeaway recommendation 1: a short, direct and actionable bullet point (max 15 words) starting with a relevant emoji.",
                "Takeaway recommendation 2: ...",
                "Takeaway recommendation 3: ..."
            ]
        }}
        Do not output any markdown code blocks or triple backticks, output raw JSON only.
        """
        
        response = llm.invoke(prompt)
        content = _extract_text(response.content).strip()
        
        # Clean markdown code blocks if Gemini returns them
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        parsed = json.loads(content)
        
        summary = parsed.get("summary", "No summary generated.")
        takeaways = parsed.get("key_takeaways", [])
        
        # Save Report to DB
        report_id = str(uuid.uuid4())
        
        # Clean existing reports of the same type within the last day to prevent duplicates
        db.query(UserSessionReport).filter(
            UserSessionReport.user_id == user_id,
            UserSessionReport.report_type == report_type,
            UserSessionReport.created_at >= now - timedelta(hours=12)
        ).delete()
        
        new_report = UserSessionReport(
            id=report_id,
            user_id=user_id,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            summary=summary,
            key_takeaways=takeaways,
            mood_trend=activity["avg_mood"],
            activity_summary={
                "msg_count": activity["user_msg_count"],
                "cibil_checks": len(activity["cibil_log"]),
                "calculator_runs": len(activity["calc_log"]),
                "tests_completed": len(activity["test_log"]),
                "videos_watched": len(activity["videos_seen"])
            },
            created_at=now
        )
        
        db.add(new_report)
        db.commit()
        db.refresh(new_report)
        
        logger.info(f"Successfully generated {report_type} report for user {user_id}")
        return new_report
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to generate {report_type} report for user {user_id}: {str(e)}", exc_info=True)
        return None

def run_scheduled_reports(db: Session):
    """Iterates over active users and generates necessary pending reports."""
    logger.info("Starting scheduled background reports generation worker")
    try:
        users = db.query(User).all()
        for user in users:
            # Generate reports based on last generation time
            for report_type in ["daily", "fortnightly", "monthly"]:
                generate_report_for_user(db, user.id, report_type)
        logger.info("Finished scheduled background reports generation")
    except Exception as e:
        logger.error(f"Scheduler worker execution failed: {str(e)}", exc_info=True)
