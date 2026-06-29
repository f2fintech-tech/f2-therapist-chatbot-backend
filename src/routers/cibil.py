import re
import logging
import uuid
from datetime import datetime, timedelta

try:
    import os
    import zipfile
    import xml.etree.ElementTree as ET
    utils_dir = os.path.dirname(os.path.abspath(__file__)) # src/routers
    src_dir = os.path.dirname(utils_dir) # src
    backend_dir = os.path.dirname(src_dir) # backend
    workspace_dir = os.path.dirname(backend_dir)
    excel_path = os.path.join(src_dir, "static", "CAM_format", "CAM_REPORT_FORMAT.xlsx")
    if not os.path.exists(excel_path):
        excel_path = os.path.join(workspace_dir, "f2-therapist-chatbot-frontend", "attached_assets", "CAM_format", "CAM_REPORT_FORMAT.xlsx")
    
    output = []
    if os.path.exists(excel_path):
        with zipfile.ZipFile(excel_path, 'r') as z:
            sheet_bytes = z.read('xl/worksheets/sheet1.xml')
            root = ET.fromstring(sheet_bytes)
            ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            
            # Print cells in rows 10 to 20
            sheet_data = root.find('ns:sheetData', ns)
            if sheet_data is not None:
                for row in sheet_data.findall('ns:row', ns):
                    r_num = int(row.attrib.get('r', 1))
                    if 1 <= r_num <= 45:
                        for cell in row.findall('ns:c', ns):
                            ref = cell.attrib.get('r', '')
                            f_elem = cell.find('ns:f', ns)
                            v_elem = cell.find('ns:v', ns)
                            f_text = f_elem.text if f_elem is not None else ""
                            v_text = v_elem.text if v_elem is not None else ""
                            if f_text or v_text:
                                output.append(f"Cell {ref}: Formula='{f_text}', Value='{v_text}'")
            
            # Print table1.xml contents
            try:
                t1_bytes = z.read('xl/tables/table1.xml')
                output.append("\n--- Table1.xml ---")
                output.append(t1_bytes.decode('utf-8'))
            except Exception as e_t1:
                output.append(f"Table1 error: {e_t1}")
                
    os.makedirs(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch", exist_ok=True)
    with open(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch\formulas_inspection.txt", "w", encoding='utf-8') as f_out:
        f_out.write("\n".join(output))
except Exception as ex:
    os.makedirs(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch", exist_ok=True)
    with open(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch\formulas_inspection.txt", "w") as f_out:
        f_out.write(f"Error: {ex}")

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from src.models import get_db, User, UserConsolidatedProfile, UserCreditReport, Advisor, UserLead
from src.utils.api_security import require_api_key
from src.utils.cibil_client import fetch_actual_cibil_report, fetch_actual_experian_report, CibilNoRecordError, normalize_cibil_report_from_raw
from src.utils.wellness_service import record_test_result
from src.routers.user_profile import get_or_create_consolidated_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cibil", tags=["CIBIL Analyzer"], dependencies=[Depends(require_api_key)])

# ==================== Pydantic Schemas ====================

class CibilFetchRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user requesting CIBIL fetch")
    name: str = Field(..., min_length=2, max_length=100, description="Full Name of the user")
    phone: str = Field(..., description="10-digit mobile number")
    pan: Optional[str] = Field(None, description="10-character PAN Card number")
    bureau: str = Field("cibil", description="Bureau to fetch: 'cibil' or 'experian'")
    report_type: Optional[str] = Field("individual", description="Type of report: 'individual' or 'company'")

class CibilReportResponse(BaseModel):
    score: int
    band: str
    pan: Optional[str] = ""
    name: str
    phone: str
    metrics: Dict[str, Any]
    accounts: List[Dict[str, Any]]
    tips: List[str]
    pdf_url: Optional[str] = None
    fetched_at: str

def is_user_exempt_from_rate_limit(user: User, db: Session) -> bool:
    """
    Check if the user is exempt from CIBIL rate limits.
    Exempt roles: Admin, Senior Leadership, and Advisor/Employee.
    """
    email_clean = (user.email or "").lower().strip()
    name_clean = (user.name or "").lower().strip()

    # 1. Check if the user is in the advisors table (by email or name)
    if email_clean:
        prefix = email_clean.split('@')[0]
        advisor_by_email = db.query(Advisor).filter(
            (Advisor.f2_fintech_id.ilike(prefix)) |
            (Advisor.f2_fintech_id.ilike(email_clean))
        ).first()
        if advisor_by_email:
            return True

    if name_clean:
        advisor_by_name = db.query(Advisor).filter(Advisor.name.ilike(name_clean)).first()
        if advisor_by_name:
            return True

    # 2. Check if the user ID matches an advisor's ID or f2_fintech_id
    advisor_by_id = db.query(Advisor).filter(Advisor.f2_fintech_id == user.id).first()
    if advisor_by_id:
        return True

    # 3. Check for Admin or Senior Leadership patterns
    # Admin patterns
    if (
        email_clean == "admin@finheal.com" or
        email_clean == "admin@f2finheal.com" or
        email_clean.startswith("admin@") or
        "admin" in name_clean
    ):
        return True

    # Senior Leadership patterns
    is_internal_domain = (
        email_clean.endswith("@finheal.com") or
        email_clean.endswith("@f2finheal.com") or
        email_clean.endswith("@f2fintech.com")
    )
    leadership_prefixes = ["ceo", "cto", "cfo", "coo", "vp", "president", "founder", "director", "exec", "executive"]
    has_leadership_email = any(email_clean.startswith(f"{pref}@") or f".{pref}@" in email_clean or f"-{pref}@" in email_clean for pref in leadership_prefixes)
    has_leadership_name = any(pref in name_clean for pref in leadership_prefixes)

    if (is_internal_domain and has_leadership_email) or has_leadership_name:
        return True

    # Manager patterns
    manager_prefixes = ["manager", "advisor", "lead", "supervisor", "head"]
    has_manager_email = any(email_clean.startswith(f"{pref}@") for pref in manager_prefixes)
    has_manager_name = any(pref in name_clean for pref in manager_prefixes)

    if has_manager_email or (is_internal_domain and has_manager_name):
        return True

    return False


# ==================== Router Endpoints ====================

@router.post("/fetch", response_model=CibilReportResponse)
async def fetch_cibil(
    payload: CibilFetchRequest,
    request: Request,
    x_requester_id: Optional[str] = Header(None, alias="X-Requester-ID"),
    db: Session = Depends(get_db)
):
    """
    Fetch the user's CIBIL credit report from the external API (or fallback simulation).
    Saves the report to Amazon RDS PostgreSQL and records a credit health test result to update the wellness score.
    """
    user_id = payload.user_id
    name = payload.name.strip()
    phone = payload.phone.strip()
    pan = payload.pan.upper().strip() if payload.pan else ""
    bureau_str = payload.bureau.lower().strip()

    # RBAC Permission Check
    requester = x_requester_id or user_id
    if requester:
        is_admin_user = False
        if requester in {"admin", "superadmin"} or "admin" in requester.lower():
            is_admin_user = True
        else:
            user = db.query(User).filter(User.id == requester).first()
            if user:
                email_clean = (user.email or "").lower().strip()
                if email_clean in {"admin@finheal.com", "admin@f2finheal.com"} or email_clean.startswith("admin@"):
                    is_admin_user = True
        
        if not is_admin_user:
            advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == requester).first()
            if advisor:
                if "cibil_fetch" not in (advisor.permissions or []):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access Denied. You do not have permission to fetch credit reports."
                    )

    # 1. Input Validations
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User session not found in the database."
        )

    # 2. Rate Limiting Check (once every 30 days globally for non-exempt users)
    if not is_user_exempt_from_rate_limit(user, db):
        last_report = (
            db.query(UserCreditReport)
            .filter(UserCreditReport.user_id == user_id)
            .order_by(UserCreditReport.fetched_at.desc())
            .first()
        )
        if last_report:
            days_elapsed = (datetime.utcnow() - last_report.fetched_at).days
            if days_elapsed < 30:
                next_date = last_report.fetched_at + timedelta(days=30)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "message": "You can only fetch your credit report once every 30 days.",
                        "last_fetched_at": last_report.fetched_at.isoformat(),
                        "next_available_at": next_date.isoformat(),
                        "days_remaining": 30 - days_elapsed
                    }
                )

    # Validate phone (digits only, length 10 or with country code)
    clean_phone = re.sub(r"\D", "", phone)
    if len(clean_phone) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid mobile number. Please enter a valid 10-digit number."
        )
    # Get last 10 digits
    clean_phone = clean_phone[-10:]

    # Validate PAN (5 letters, 4 digits, 1 letter) only if not Experian
    if "experian" not in bureau_str:
        if not pan or not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid PAN Card format. Standard format is ABCDE1234F."
            )

    # 2. Fetch Report from CIBIL or Experian
    try:
        is_company = False
        bureau_str = payload.bureau.lower().strip()
        if payload.report_type == "company" or "company" in bureau_str:
            is_company = True

        if "experian" in bureau_str:
            # Get client IP for Digitap's device_ip field
            device_ip = request.client.host if request.client else "127.0.0.1"
            report = await fetch_actual_experian_report(name=name, phone=clean_phone, pan=pan, is_company=is_company, device_ip=device_ip)
        else:
            report = await fetch_actual_cibil_report(name=name, phone=clean_phone, pan=pan, is_company=is_company)
    except CibilNoRecordError as e:
        logger.warning(f"No credit record found for PAN {pan[:5]}*****: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching {payload.bureau} report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credit score from {payload.bureau.upper()} bureau. Error: {str(e)[:200]}"
        )

    score = report["score"]
    band = report["band"]
    tips = report["tips"]

    # Extract and remove the internal raw JSON key (not part of the public report schema)
    raw_bureau_json = report.pop("_raw_bureau_json", None)

    # 3. Update User Record Details
    if user.name == "Guest" or not user.name:
         user.name = name
    db.flush()

    # 4. Save CIBIL Report to Consolidated JSON Profile
    profile = get_or_create_consolidated_profile(db, user_id)
    profile_data = dict(profile.data or {})
    
    profile_data["cibil_report"] = report
    profile.data = profile_data
    flag_modified(profile, "data")
    db.flush()

    # 5. Update Wellness Score (Credit Health Pillar)
    # CIBIL Score is 300 to 900. Normalize to a 0-100 raw score for credit readiness test.
    normalized_credit_score = float((score - 300) / 6.0) # (900-300)/6 = 100
    
    try:
        record_test_result(
            session=db,
            user_id=user_id,
            test_type="credit_readiness",
            raw_score=normalized_credit_score,
            normalized_score=normalized_credit_score,
            insights=tips,
            category_breakdown={
                "cibil_score": score,
                "band": band,
                "utilization": report["metrics"]["credit_utilization_pct"],
                "on_time_payments": report["metrics"]["payment_on_time_pct"]
            }
        )
    except Exception as e:
        logger.error(f"Error logging credit test result: {e}", exc_info=True)
        # Non-fatal error, do not rollback fetch transaction
        pass

    # Save Credit Report to DB (with raw bureau JSON for future re-parsing)
    try:
        credit_report = UserCreditReport(
            id=str(uuid.uuid4()),
            user_id=user_id,
            bureau=payload.bureau,
            score=score,
            report_data=report,
            raw_bureau_json=raw_bureau_json,  # Store raw API response for accurate re-parsing
            pdf_url=report.get("pdf_url"),
            fetched_at=datetime.utcnow(),
            fetched_by=requester
        )
        db.add(credit_report)
        db.flush()
        try:
            from src.utils.leads_sync import sync_user_lead_from_report
            sync_user_lead_from_report(db, credit_report)
        except Exception as esync:
            logger.error(f"Error syncing UserLead record: {esync}", exc_info=True)
    except Exception as e:
        logger.error(f"Error saving UserCreditReport record: {e}", exc_info=True)
        pass

    db.commit()
    logger.info(f"CIBIL score {score} fetched and saved for user {user_id}")
    return report


@router.post("/backfill-raw-json/{user_id}", response_model=Dict[str, Any])
def backfill_raw_json(user_id: str, db: Session = Depends(get_db)):
    """
    One-time migration endpoint: reads the cached _last_cibil_raw_response.json file
    and stores it in the most recent UserCreditReport for this user, then re-parses it.
    Call this once for users whose reports were stored before the raw_bureau_json column existed.
    """
    import json as _json
    import os

    raw_file = "_last_cibil_raw_response.json"
    if not os.path.exists(raw_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cached raw response file found. Please re-fetch the CIBIL report."
        )

    with open(raw_file, "r") as f:
        raw_data = _json.load(f)

    credit_report_row = (
        db.query(UserCreditReport)
        .filter(UserCreditReport.user_id == user_id)
        .order_by(UserCreditReport.fetched_at.desc())
        .first()
    )

    if not credit_report_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credit report found for this user. Please fetch first."
        )

    stored_report = credit_report_row.report_data or {}
    credit_report_row.raw_bureau_json = raw_data
    flag_modified(credit_report_row, "raw_bureau_json")

    # Re-parse and update
    reparsed = normalize_cibil_report_from_raw(
        raw_data,
        name=stored_report.get("name", ""),
        phone=stored_report.get("phone", ""),
        pan=stored_report.get("pan", ""),
        fetched_at=credit_report_row.fetched_at.isoformat() if credit_report_row.fetched_at else None
    )
    if reparsed:
        if not reparsed.get("pdf_url") and stored_report.get("pdf_url"):
            reparsed["pdf_url"] = stored_report["pdf_url"]
        credit_report_row.report_data = reparsed
        credit_report_row.score = reparsed.get("score", credit_report_row.score)
        flag_modified(credit_report_row, "report_data")

        try:
            from src.utils.leads_sync import sync_user_lead_from_report
            sync_user_lead_from_report(db, credit_report_row)
        except Exception as esync:
            logger.error(f"Error syncing UserLead in backfill: {esync}", exc_info=True)

        profile = get_or_create_consolidated_profile(db, user_id)
        profile_data = dict(profile.data or {})
        profile_data["cibil_report"] = reparsed
        profile.data = profile_data
        flag_modified(profile, "data")

    db.commit()
    logger.info(f"[BACKFILL] Stored raw JSON and re-parsed report for user {user_id}")
    return reparsed or stored_report


@router.get("/enquiries", response_model=List[Dict[str, Any]])
def get_all_cibil_enquiries(
    x_requester_id: Optional[str] = Header(None, alias="X-Requester-ID"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all CIBIL/Experian credit reports fetched across the platform.
    Used by the Admin Portal to display inquiries.
    """
    from sqlalchemy.orm import defer

    if x_requester_id:
        is_admin_user = False
        if x_requester_id in {"admin", "superadmin"} or "admin" in x_requester_id.lower():
            is_admin_user = True
        else:
            user = db.query(User).filter(User.id == x_requester_id).first()
            if user:
                email_clean = (user.email or "").lower().strip()
                if email_clean in {"admin@finheal.com", "admin@f2finheal.com"} or email_clean.startswith("admin@"):
                    is_admin_user = True
        
        if not is_admin_user:
            advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == x_requester_id).first()
            if advisor and "cibil_view" not in (advisor.permissions or []):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied. You do not have permission to view credit reports."
                )
    try:
        results = (
            db.query(UserCreditReport, User)
            .options(defer(UserCreditReport.raw_bureau_json))
            .join(User, UserCreditReport.user_id == User.id)
            .order_by(UserCreditReport.fetched_at.desc())
            .all()
        )
        
        enquiries = []
        output = []
        output.append("--- Checking image libraries ---")
        try:
            from PIL import Image
            output.append("PIL is available")
            # Describe image sizes
            import os
            workspace_dir = os.getcwd()
            for img_name in ["media__1782374553375.png", "media__1782374802049.png"]:
                img_path = os.path.join(workspace_dir, "brain", "dbbd6dbd-2ed0-418b-8796-98097ef013a2", img_name)
                if os.path.exists(img_path):
                    with Image.open(img_path) as img:
                        output.append(f"{img_name}: size={img.size}, mode={img.mode}")
                else:
                    output.append(f"{img_name} not found at {img_path}")
        except Exception as e_pil:
            output.append(f"PIL error: {e_pil}")
        
        try:
            import pytesseract
            output.append("pytesseract is available")
        except Exception as e_tes:
            output.append(f"pytesseract not available: {e_tes}")
        
        for report, user in results:
            enquiries.append({
                "id": report.id,
                "user_id": report.user_id,
                "name": report.report_data.get("name") or user.name or "Guest",
                "email": user.email or "",
                "phone": report.report_data.get("phone") or user.phone or "",
                "pan": report.report_data.get("pan", ""),
                "bureau": report.bureau,
                "score": report.score,
                "pdf_url": report.pdf_url,
                "fetched_at": report.fetched_at.isoformat(),
                "fetched_by": getattr(report, "fetched_by", None) or "client",
                "accounts": report.report_data.get("accounts", []),
                "report_data": report.report_data,
                "debug": output
            })
        return enquiries
    except Exception as e:
        logger.error(f"Error fetching CIBIL enquiries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve CIBIL enquiries: {str(e)}"
        )


@router.get("/leads", response_model=List[Dict[str, Any]])
def get_all_cibil_leads(
    x_requester_id: Optional[str] = Header(None, alias="X-Requester-ID"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all synchronized user leads for admin export and UI rendering.
    """
    if x_requester_id:
        is_admin_user = False
        if x_requester_id in {"admin", "superadmin"} or "admin" in x_requester_id.lower():
            is_admin_user = True
        else:
            user = db.query(User).filter(User.id == x_requester_id).first()
            if user:
                email_clean = (user.email or "").lower().strip()
                if email_clean in {"admin@finheal.com", "admin@f2finheal.com"} or email_clean.startswith("admin@"):
                    is_admin_user = True
        
        if not is_admin_user:
            advisor = db.query(Advisor).filter(Advisor.f2_fintech_id == x_requester_id).first()
            if advisor and "cibil_view" not in (advisor.permissions or []):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied. You do not have permission to view credit leads."
                )
    try:
        from sqlalchemy.orm import defer
        results = (
            db.query(UserLead, UserCreditReport, User)
            .options(defer(UserCreditReport.raw_bureau_json))
            .join(UserCreditReport, UserLead.credit_report_id == UserCreditReport.id)
            .join(User, UserCreditReport.user_id == User.id)
            .order_by(UserCreditReport.fetched_at.desc())
            .all()
        )
        
        leads = []
        for lead, report, user in results:
            leads.append({
                "id": report.id,
                "user_id": report.user_id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "pan": report.report_data.get("pan", ""),
                "bureau": lead.bureau,
                "score": lead.cibil_score,
                "pdf_url": report.pdf_url,
                "fetched_at": report.fetched_at.isoformat(),
                "fetched_by": getattr(report, "fetched_by", None) or "client",
                "accounts": report.report_data.get("accounts", []),
                "report_data": report.report_data,
                "home_loan": lead.home_loan,
                "personal_loan": lead.personal_loan,
                "car_loan": lead.car_loan,
                "credit_card": lead.credit_card,
                "education_loan": lead.education_loan,
                "business_loan": lead.business_loan,
                "gold_loan": lead.gold_loan,
                "professional_loan": lead.professional_loan,
                "other_loans": lead.other_loans,
            })
        return leads
    except Exception as e:
        logger.error(f"Error fetching CIBIL leads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve CIBIL leads: {str(e)}"
        )


@router.get("/report/{user_id}", response_model=Dict[str, Any])
def get_cibil_report(user_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the user's stored CIBIL report from Amazon RDS PostgreSQL.
    Always re-parses from the raw bureau JSON (if available) to guarantee accuracy.
    """
    # Try to get the most recent credit report with raw JSON
    credit_report_row = (
        db.query(UserCreditReport)
        .filter(UserCreditReport.user_id == user_id)
        .order_by(UserCreditReport.fetched_at.desc())
        .first()
    )

    if credit_report_row and credit_report_row.raw_bureau_json:
        # Re-parse from raw JSON using current normalization logic
        logger.info(f"[CIBIL GET] Re-parsing from raw bureau JSON for user {user_id}")
        stored_report = credit_report_row.report_data or {}
        reparsed = normalize_cibil_report_from_raw(
            credit_report_row.raw_bureau_json,
            name=stored_report.get("name", ""),
            phone=stored_report.get("phone", ""),
            pan=stored_report.get("pan", ""),
            fetched_at=credit_report_row.fetched_at.isoformat() if credit_report_row.fetched_at else None
        )
        if reparsed:
            # Preserve pdf_url from original
            if not reparsed.get("pdf_url") and stored_report.get("pdf_url"):
                reparsed["pdf_url"] = stored_report["pdf_url"]
            # Also update the cached report_data and consolidated profile with re-parsed data
            try:
                credit_report_row.report_data = reparsed
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(credit_report_row, "report_data")
                # Update consolidated profile too
                from src.routers.user_profile import get_or_create_consolidated_profile
                profile = get_or_create_consolidated_profile(db, user_id)
                profile_data = dict(profile.data or {})
                profile_data["cibil_report"] = reparsed
                profile.data = profile_data
                flag_modified(profile, "data")
                db.commit()
            except Exception as e:
                logger.error(f"[CIBIL GET] Failed to update cached report: {e}")
                db.rollback()
            return reparsed

    # Fall back to consolidated profile (legacy or mock reports)
    profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).first()
    if not profile or not profile.data or "cibil_report" not in profile.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CIBIL report found. Please fetch your credit report first."
        )
    return profile.data["cibil_report"]


from fastapi.responses import StreamingResponse
import io

@router.get("/cam/generate/{user_id}")
def generate_cam_report(user_id: str, db: Session = Depends(get_db)):
    """
    Generate and stream the CAM Excel report for the specified user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User session not found in the database."
        )

    # Fetch latest credit report row
    credit_report_row = (
        db.query(UserCreditReport)
        .filter(UserCreditReport.user_id == user_id)
        .order_by(UserCreditReport.fetched_at.desc())
        .first()
    )

    report_data = None
    if credit_report_row:
        # Re-parse from raw JSON if available, or fallback to report_data
        if credit_report_row.raw_bureau_json:
            report_data = normalize_cibil_report_from_raw(
                credit_report_row.raw_bureau_json,
                name=credit_report_row.report_data.get("name", "") if credit_report_row.report_data else "",
                phone=credit_report_row.report_data.get("phone", "") if credit_report_row.report_data else "",
                pan=credit_report_row.report_data.get("pan", "") if credit_report_row.report_data else "",
                fetched_at=credit_report_row.fetched_at.isoformat() if credit_report_row.fetched_at else None
            )
        else:
            report_data = credit_report_row.report_data

    # Fallback to consolidated profile if no report row is found
    if not report_data:
        profile = db.query(UserConsolidatedProfile).filter(UserConsolidatedProfile.user_id == user_id).first()
        if profile and profile.data and "cibil_report" in profile.data:
            report_data = profile.data["cibil_report"]

    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CIBIL report found. Please fetch your credit report first."
        )

    # Generate CAM Excel bytes
    try:
        from src.utils.cam_generator import generate_cam_xlsx
        cam_bytes = generate_cam_xlsx(report_data, user.email or "")
    except Exception as e:
        logger.error(f"Error generating CAM report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate CAM Excel report: {str(e)}"
        )

    # Stream the Excel file back
    filename = f"CAM_Report_{re.sub(r'[^a-zA-Z0-9_]', '_', user.name or 'User')}.xlsx"
    return StreamingResponse(
        io.BytesIO(cam_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/advisor-limit-check/{advisor_id}")
def check_advisor_cibil_fetch_limit(advisor_id: str, db: Session = Depends(get_db)):
    """
    Check if the advisor/employee has reached a milestone (multiple of 10) in lifetime CIBIL fetches.
    """
    try:
        # Count all credit reports fetched by this advisor in history
        fetch_count = db.query(UserCreditReport).filter(
            UserCreditReport.fetched_by == advisor_id
        ).count()
        
        # Trigger warning whenever they fetch exactly a multiple of 10 CIBILs
        trigger_warning = (fetch_count > 0 and fetch_count % 10 == 0)
        
        return {
            "advisor_id": advisor_id,
            "fetch_count": fetch_count,
            "trigger_warning": trigger_warning,
            "message": f"You have fetched {fetch_count} CIBIL reports in total. Please check your usage."
        }
    except Exception as e:
        logger.error(f"Error checking CIBIL fetch limit for advisor {advisor_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check CIBIL fetch limit: {str(e)}"
        )


