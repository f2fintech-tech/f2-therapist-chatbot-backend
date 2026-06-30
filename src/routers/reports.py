from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from src.models import get_db, UserSessionReport
from src.utils.api_security import require_api_key
from src.utils.report_worker import generate_report_for_user, run_scheduled_reports, generate_on_demand_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/reports", tags=["Reports"], dependencies=[Depends(require_api_key)])

@router.get("/{user_id}")
def get_user_reports(user_id: str, db: Session = Depends(get_db)):
    """
    Fetch all financial therapy and activity reports for a specific user.
    Only returns "on_demand" reports.
    """
    try:
        now = datetime.utcnow()
        for report_type in ["daily", "fortnightly", "monthly"]:
            # Set realistic cache thresholds based on report type to conserve Gemini API quota
            if report_type == "daily":
                threshold = timedelta(hours=24)
            elif report_type == "fortnightly":
                threshold = timedelta(days=7)
            else:  # monthly
                threshold = timedelta(days=15)

            existing = db.query(UserSessionReport).filter(
                UserSessionReport.user_id == user_id,
                UserSessionReport.report_type == report_type,
                UserSessionReport.created_at >= now - threshold
            ).first()
            
            if not existing:
                try:
                    # Generate report if user has activity in the timeframe
                    generate_report_for_user(db, user_id, report_type)
                except Exception as ex:
                    logger.error(f"Failed to generate {report_type} report on-the-fly: {str(ex)}", exc_info=True)
        reports = db.query(UserSessionReport).filter(
            UserSessionReport.user_id == user_id,
            UserSessionReport.report_type == "on_demand"
        ).order_by(UserSessionReport.created_at.desc()).all()
        
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "report_type": r.report_type,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "summary": r.summary,
                "key_takeaways": r.key_takeaways or [],
                "strengths": r.strengths or [],
                "weaknesses": r.weaknesses or [],
                "mood_trend": r.mood_trend or {},
                "activity_summary": r.activity_summary or {},
                "created_at": r.created_at.isoformat()
            } for r in reports
        ]
    except Exception as e:
        logger.error(f"Error fetching reports for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reports: {str(e)}"
        )

@router.post("/{user_id}/trigger")
def trigger_report_generation(
    user_id: str, 
    report_type: str = Query(..., pattern="^(on_demand)$"), 
    db: Session = Depends(get_db)
):
    """
    Developer/Admin endpoint to manually trigger report generation for testing.
    """
    try:
        report = generate_report_for_user(db, user_id, report_type)
        if not report:
            return {"status": "skipped", "message": "No activity found or failed to generate report."}
        
        return {
            "status": "success",
            "report": {
                "id": report.id,
                "user_id": report.user_id,
                "report_type": report.report_type,
                "start_date": report.start_date.isoformat(),
                "end_date": report.end_date.isoformat(),
                "summary": report.summary,
                "key_takeaways": report.key_takeaways or [],
                "strengths": report.strengths or [],
                "weaknesses": report.weaknesses or [],
                "mood_trend": report.mood_trend or {},
                "activity_summary": report.activity_summary or {},
                "created_at": report.created_at.isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error triggering report generation for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger report generation: {str(e)}"
        )

@router.post("/trigger-all")
def trigger_all_reports(db: Session = Depends(get_db)):
    """
    Developer/Admin endpoint to manually run the scheduled worker for all users.
    """
    try:
        # Scheduled generation of periodic reports is fully disabled.
        return {"status": "skipped", "message": "Scheduled background report generation is fully disabled."}
    except Exception as e:
        logger.error(f"Error triggering all reports: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger all reports: {str(e)}"
        )


@router.post("/{user_id}/generate")
def generate_user_on_demand_report(user_id: str, db: Session = Depends(get_db)):
    """
    On-demand endpoint for users to manually trigger report generation.
    Enforces a 7-day cooldown window and checks if there is any new activity.
    """
    try:
        report = generate_on_demand_report(db, user_id)
        return {
            "status": "success",
            "report": {
                "id": report.id,
                "user_id": report.user_id,
                "report_type": report.report_type,
                "start_date": report.start_date.isoformat(),
                "end_date": report.end_date.isoformat(),
                "summary": report.summary,
                "key_takeaways": report.key_takeaways or [],
                "mood_trend": report.mood_trend or {},
                "activity_summary": report.activity_summary or {},
                "created_at": report.created_at.isoformat()
            }
        }
    except ValueError as val_err:
        err_msg = str(val_err)
        if err_msg.startswith("COOLDOWN_ACTIVE"):
            cooldown_date = err_msg.split("|")[1]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "COOLDOWN_ACTIVE",
                    "message": "You can only generate a report once every 7 days.",
                    "next_available": cooldown_date
                }
            )
        elif err_msg == "NO_ACTIVITY":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "NO_ACTIVITY",
                    "message": "No new activity found since your last report / registration date."
                }
            )
        elif err_msg == "USER_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=err_msg
            )
    except Exception as e:
        logger.error(f"Error generating on-demand report for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )

