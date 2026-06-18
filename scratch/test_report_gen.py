import sys
import logging
from datetime import datetime, timedelta
sys.path.insert(0, '.')

# Force stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.models import get_db, User, Conversation, ConversationMessage, UserSessionReport
from src.utils.report_worker import generate_report_for_user, aggregate_user_activity

db = next(get_db())
user_id = "e98b1e57-c74b-483e-b7d1-234dae7c7797"

try:
    print(f"--- Diagnostic Report Generation for User {user_id} ---")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        print(f"User not found in DB!")
        sys.exit(1)
        
    print(f"User: {user.name} ({user.email})")
    
    # Check messages
    now = datetime.utcnow()
    start_date = now - timedelta(days=1)
    
    print(f"Timeframe: {start_date} to {now}")
    
    messages = db.query(ConversationMessage).join(Conversation).filter(
        Conversation.user_id == user_id,
        ConversationMessage.created_at >= start_date,
        ConversationMessage.created_at <= now
    ).all()
    
    print(f"Messages count in last 24h: {len(messages)}")
    for m in messages:
        content_safe = m.content.encode('utf-8', errors='replace').decode('utf-8')
        print(f"  [{m.role}] {content_safe[:50]} (created_at: {m.created_at})")
        
    activity = aggregate_user_activity(db, user_id, start_date, now)
    print(f"Aggregated activity: {activity}")
    
    # Trigger report generation
    print("Triggering report generation...")
    report = generate_report_for_user(db, user_id, "daily")
    if report:
        print("Report successfully generated!")
        print(f"Report ID: {report.id}")
        print(f"Summary: {report.summary}")
        print(f"Takeaways: {report.key_takeaways}")
    else:
        print("Report generation returned None/Failed.")
finally:
    db.close()
