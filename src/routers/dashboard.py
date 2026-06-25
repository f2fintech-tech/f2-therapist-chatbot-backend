from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from src.models import (
    get_db, User, UserCreditReport, AdvisorAppointment,
    TestResult, UserConsolidatedProfile, MoodLiveState,
    Conversation, ConversationMessage, MessageRole
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Standard Test definitions matching the frontend
TEST_CATALOG = {
    "financial_literacy": "Financial Literacy Test",
    "emergency_fund": "Emergency Fund Test",
    "loan_fit": "Loan Fit / Borrowing Readiness",
    "credit_readiness": "Credit Readiness Test",
    "debt_balance": "Debt Balance Test"
}

# Standard Education content categories matching the frontend
EDUCATION_CATALOG = {
    "Loans": ["a1", "a2", "a4", "a5", "a6", "a8", "v1", "v2"],
    "Credit": ["a3", "v3"],
    "Business": ["a7", "v4"]
}

@router.get("/summary")
async def get_dashboard_summary(user_id: str, db: Session = Depends(get_db)):
    """
    Get consolidated dashboard metrics for the overview page, including CIBIL score,
    upcoming advisor appointments, mood trends, financial health tests analytics,
    and content consumption metrics with personalized recommendations.
    """
    # 1. Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User session not found."
        )

    # 2. Get latest credit report
    credit_score = None
    latest_report = (
        db.query(UserCreditReport)
        .filter(UserCreditReport.user_id == user_id)
        .order_by(UserCreditReport.fetched_at.desc())
        .first()
    )
    if latest_report:
        credit_score = {
            "score": latest_report.score,
            "bureau": latest_report.bureau,
            "fetched_at": latest_report.fetched_at.isoformat()
        }

    # 3. Get next upcoming appointment
    next_appointment = None
    upcoming_appt = (
        db.query(AdvisorAppointment)
        .filter(
            AdvisorAppointment.user_id == user_id,
            AdvisorAppointment.completed == False,
            AdvisorAppointment.cancelled == False
        )
        .order_by(AdvisorAppointment.date.asc(), AdvisorAppointment.time.asc())
        .first()
    )
    if upcoming_appt:
        next_appointment = {
            "id": upcoming_appt.id,
            "advisor_name": upcoming_appt.advisor_name,
            "advisor_id": upcoming_appt.advisor_id,
            "date": upcoming_appt.date,
            "time": upcoming_appt.time,
            "meet_url": upcoming_appt.meet_url
        }

    # 4. Fetch mood trends from recent conversation messages
    mood_trends = []
    try:
        convs = db.query(Conversation).filter(Conversation.user_id == user_id).all()
        if convs:
            conv_ids = [c.id for c in convs]
            messages = (
                db.query(ConversationMessage)
                .filter(
                    ConversationMessage.conversation_id.in_(conv_ids),
                    ConversationMessage.role == MessageRole.ASSISTANT,
                    ConversationMessage.mood.isnot(None)
                )
                .order_by(ConversationMessage.created_at.asc())
                .all()
            )
            # Take last 100 entries to make a beautiful trend line
            for msg in messages[-100:]:
                m = msg.mood
                if isinstance(m, dict):
                    dims = m.get("dimensions") or {}
                    mood_trends.append({
                        "date": msg.created_at.strftime("%Y-%m-%d"),
                        "displayDate": msg.created_at.strftime("%d %b"),
                        "stress": dims.get("stress", m.get("stress", 50)),
                        "openness": dims.get("openness", m.get("openness", 50)),
                        "urgency": dims.get("urgency", m.get("urgency", 50))
                    })
    except Exception as e:
        logger.error(f"Error fetching mood trends: {e}")

    # Fallback to Live State if no historical message moods exist
    if not mood_trends:
        live_mood = db.query(MoodLiveState).filter(MoodLiveState.user_id == user_id).first()
        fallback_date = datetime.now().strftime("%Y-%m-%d")
        if live_mood:
            mood_trends.append({
                "date": fallback_date,
                "displayDate": "Today",
                "stress": live_mood.stress,
                "openness": live_mood.openness,
                "urgency": live_mood.urgency
            })
        else:
            mood_trends.append({
                "date": fallback_date,
                "displayDate": "Today",
                "stress": 50,
                "openness": 50,
                "urgency": 50
            })

    # 5. Fetch and analyze financial health test results
    test_results = (
        db.query(TestResult)
        .filter(TestResult.user_id == user_id)
        .order_by(TestResult.completed_at.desc())
        .all()
    )
    
    total_attempted = len(test_results)
    test_scores = []
    attempted_ids = set()
    low_score_test = None

    for tr in test_results:
        # Avoid duplicate listings in current summary (take latest for each type)
        if tr.test_type not in attempted_ids:
            attempted_ids.add(tr.test_type)
            title = TEST_CATALOG.get(tr.test_type, tr.test_type.replace("-", " ").title())
            normalized_score = int(tr.normalized_score)
            test_scores.append({
                "test_id": tr.test_type,
                "title": title,
                "score": normalized_score,
                "date": tr.completed_at.strftime("%d %b %Y")
            })
            if normalized_score < 50 and not low_score_test:
                low_score_test = {"id": tr.test_type, "title": title, "score": normalized_score}

    # Generate Test Nudge / Recommendation (Creates urgency/fear or encourages more tests)
    test_nudge = "You haven't taken any financial health tests yet! Find out your Money IQ score now to avoid costly financial mistakes."
    recommended_test_id = "financial-literacy"

    if total_attempted > 0:
        if low_score_test:
            test_nudge = f"⚠️ Warning: Your score of {low_score_test['score']}% in the '{low_score_test['title']}' indicates high financial vulnerability. Take the recommended test immediately to build your safety net!"
            # Suggest a fallback test or the same test to improve
            recommended_test_id = low_score_test["id"]
        else:
            # Check for unattempted tests
            unattempted = [tid for tid in TEST_CATALOG.keys() if tid not in attempted_ids]
            if unattempted:
                recommended_test_id = unattempted[0]
                rec_title = TEST_CATALOG[recommended_test_id]
                test_nudge = f"🎯 Great job on your previous tests! To further secure your financial future, attempt the '{rec_title}' next."
            else:
                test_nudge = "🏆 Outstanding! You have completed all available financial literacy tests. Keep talking with FinHeal to maintain your high score!"
                recommended_test_id = None

    # 6. Fetch and analyze educational logs from Consolidated Profile
    articles_read_count = 0
    videos_watched_count = 0
    category_breakdown = {"Loans": 0, "Credit": 0, "Business": 0}
    seen_ids = set()

    profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).first()
    if profile and isinstance(profile.data, dict):
        edu = profile.data.get("financial_education", {})
        if isinstance(edu, dict):
            articles_seen = edu.get("articles_seen", [])
            videos_seen = edu.get("videos_seen", [])
            
            articles_read_count = len(articles_seen)
            videos_watched_count = len(videos_seen)
            
            for item in articles_seen:
                if isinstance(item, dict):
                    art_id = item.get("article_id")
                    if art_id:
                        seen_ids.add(art_id)
            
            for item in videos_seen:
                if isinstance(item, dict):
                    vid_id = item.get("video_id")
                    if vid_id:
                        seen_ids.add(vid_id)

    # Classify seen items into categories to calculate breakdown
    for cat, ids in EDUCATION_CATALOG.items():
        for item_id in ids:
            if item_id in seen_ids:
                category_breakdown[cat] += 1

    # Generate content recommendations (Nudge/behavior model)
    edu_nudge = "📊 You haven't explored our financial resources yet. Expand your money knowledge today by watching our introductory Loan Guide!"
    recommended_content_id = "v2" # Default video recommendation

    total_consumed = articles_read_count + videos_watched_count
    if total_consumed > 0:
        # Logic: Find the category with the least consumption and suggest items from it
        min_cat = min(category_breakdown, key=category_breakdown.get)
        # Find an item in min_cat that the user has NOT seen
        unseen_items = [item_id for item_id in EDUCATION_CATALOG[min_cat] if item_id not in seen_ids]
        
        if unseen_items:
            recommended_content_id = unseen_items[0]
            item_type = "video" if recommended_content_id.startswith("v") else "article"
            
            if min_cat == "Credit":
                edu_nudge = f"💡 Did you know? 3 out of 5 loan applications are rejected due to simple credit report errors. Read or watch our recommendation on Credit score tips immediately."
            elif min_cat == "Business":
                edu_nudge = f"📈 Interested in growth? Explore our Business category to learn about working capital loans, cash flow management, and funding strategies."
            else:
                edu_nudge = f"🏦 Balance your knowledge! You've read a lot of other articles, but we highly recommend exploring our Loans section to check current interest rates and offers."
        else:
            # Everything seen, recommend general review
            edu_nudge = "📚 Excellent work! You have consumed all our recommended financial guides. Keep checking back for newly added articles and videos!"
            recommended_content_id = None

    # 7. Fetch or generate platform usage history
    platform_usage = {}
    if profile and isinstance(profile.data, dict):
        platform_usage = profile.data.get("platform_usage", {})

    import datetime as dt
    usage_history = []
    total_minutes = 0
    today = dt.date.today()
    # Only include days that have real usage data
    for i in range(179, -1, -1):
        day_date = today - dt.timedelta(days=i)
        date_str = day_date.strftime("%Y-%m-%d")
        day_label = day_date.strftime("%a")
        date_display = day_date.strftime("%d %b")

        if date_str in platform_usage:
            mins = platform_usage[date_str]
            total_minutes += mins
            usage_history.append({
                "date": date_str,
                "displayDate": date_display,
                "day": day_label,
                "hours": round(mins / 60.0, 1),
                "minutes": mins,
            })
        
    total_hours = round(total_minutes / 60.0, 1)

    return {
        "credit_score": credit_score,
        "next_appointment": next_appointment,
        "mood_trends": mood_trends,
        "tests": {
            "total_attempted": total_attempted,
            "scores": test_scores,
            "nudge_message": test_nudge,
            "recommended_test_id": recommended_test_id
        },
        "education": {
            "articles_read_count": articles_read_count,
            "videos_watched_count": videos_watched_count,
            "category_breakdown": category_breakdown,
            "nudge_message": edu_nudge,
            "recommended_content_id": recommended_content_id
        },
        "platform_usage": {
            "total_hours": total_hours,
            "total_days": len(usage_history),
            "history": usage_history
        }
    }

