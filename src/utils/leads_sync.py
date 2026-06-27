import logging
from datetime import datetime
from sqlalchemy.orm import Session
from src.models import UserCreditReport, User, UserLead

logger = logging.getLogger(__name__)

def sync_user_lead_from_report(db: Session, report: UserCreditReport) -> UserLead:
    """
    Parses active accounts and CIBIL report details, then saves or updates the user_leads table.
    """
    try:
        user = db.query(User).filter(User.id == report.user_id).first()
        email = (user.email if user else None) or report.report_data.get("email") or "-"
        name = report.report_data.get("name") or (user.name if user else "Guest")
        phone = report.report_data.get("phone") or (user.phone if user else "-")
        
        # 1. Get active accounts list
        accounts = report.report_data.get("accounts", []) if report.report_data else []
        active_accounts = []
        for acc in accounts:
            is_active = acc.get("is_active")
            if is_active is None:
                is_active = acc.get("isActive")
            if is_active in [True, "true", "True", 1]:
                active_accounts.append(acc)
                
        # 2. Format overall active accounts string
        formatted_accounts_list = []
        for acc in active_accounts:
            bal = acc.get("outstanding_balance", 0)
            lender = acc.get("lender", "Unknown Lender")
            acc_type = acc.get("type", "Unknown Type")
            formatted_accounts_list.append(f"{lender} ({acc_type}) - Bal: Rs.{bal}")
            
        existing_open_accounts_str = "; ".join(formatted_accounts_list) if formatted_accounts_list else "No open accounts"
        
        # 3. Format Date Fetched
        # match exact frontend formatting, e.g. "27/6/2026, 11:10:16 am"
        fetched_at = report.fetched_at
        date_fetched_str = fetched_at.strftime("%d/%m/%Y, %I:%M:%S %p").lower()
        
        # 4. Classify loans into separate lists
        home_loan_list = []
        personal_loan_list = []
        car_loan_list = []
        credit_card_list = []
        education_loan_list = []
        business_loan_list = []
        gold_loan_list = []
        other_loans_list = []
        
        for acc in active_accounts:
            acc_type = (acc.get("type") or "").lower()
            lender = acc.get("lender", "Unknown Lender")
            bal = acc.get("outstanding_balance", 0)
            entry = f"{lender} - Bal: Rs.{bal}"
            
            if "home" in acc_type:
                home_loan_list.append(entry)
            elif "personal" in acc_type:
                personal_loan_list.append(entry)
            elif "car" in acc_type or "auto" in acc_type or "vehicle" in acc_type:
                car_loan_list.append(entry)
            elif "card" in acc_type:
                credit_card_list.append(entry)
            elif "education" in acc_type or "student" in acc_type:
                education_loan_list.append(entry)
            elif "business" in acc_type or "commercial" in acc_type:
                business_loan_list.append(entry)
            elif "gold" in acc_type:
                gold_loan_list.append(entry)
            else:
                other_loans_list.append(f"{lender} ({acc.get('type', 'Other')}) - Bal: Rs.{bal}")
                
        home_loan_val = "; ".join(home_loan_list) if home_loan_list else None
        personal_loan_val = "; ".join(personal_loan_list) if personal_loan_list else None
        car_loan_val = "; ".join(car_loan_list) if car_loan_list else None
        credit_card_val = "; ".join(credit_card_list) if credit_card_list else None
        education_loan_val = "; ".join(education_loan_list) if education_loan_list else None
        business_loan_val = "; ".join(business_loan_list) if business_loan_list else None
        gold_loan_val = "; ".join(gold_loan_list) if gold_loan_list else None
        other_loans_val = "; ".join(other_loans_list) if other_loans_list else None
        
        # 5. Save or Update in UserLead
        existing_lead = db.query(UserLead).filter(UserLead.credit_report_id == report.id).first()
        if existing_lead:
            existing_lead.name = name
            existing_lead.phone = phone
            existing_lead.email = email
            existing_lead.cibil_score = report.score
            existing_lead.bureau = report.bureau
            existing_lead.existing_open_accounts = existing_open_accounts_str
            existing_lead.date_fetched = date_fetched_str
            existing_lead.home_loan = home_loan_val
            existing_lead.personal_loan = personal_loan_val
            existing_lead.car_loan = car_loan_val
            existing_lead.credit_card = credit_card_val
            existing_lead.education_loan = education_loan_val
            existing_lead.business_loan = business_loan_val
            existing_lead.gold_loan = gold_loan_val
            existing_lead.other_loans = other_loans_val
            lead = existing_lead
            logger.info(f"Updated existing UserLead record for credit report {report.id}")
        else:
            new_lead = UserLead(
                credit_report_id=report.id,
                name=name,
                phone=phone,
                email=email,
                cibil_score=report.score,
                bureau=report.bureau,
                existing_open_accounts=existing_open_accounts_str,
                date_fetched=date_fetched_str,
                home_loan=home_loan_val,
                personal_loan=personal_loan_val,
                car_loan=car_loan_val,
                credit_card=credit_card_val,
                education_loan=education_loan_val,
                business_loan=business_loan_val,
                gold_loan=gold_loan_val,
                other_loans=other_loans_val
            )
            db.add(new_lead)
            lead = new_lead
            logger.info(f"Created new UserLead record for credit report {report.id}")
            
        return lead
    except Exception as e:
        logger.error(f"Error in sync_user_lead_from_report: {e}", exc_info=True)
        return None

def backfill_all_user_leads(db: Session):
    """
    Backfills all entries from user_credit_reports to user_leads.
    """
    try:
        reports = db.query(UserCreditReport).all()
        logger.info(f"Starting backfill of {len(reports)} UserCreditReports to user_leads")
        count = 0
        for report in reports:
            lead = sync_user_lead_from_report(db, report)
            if lead:
                count += 1
        db.commit()
        logger.info(f"Successfully backfilled {count} credit reports into user_leads")
    except Exception as e:
        logger.error(f"Error in backfill_all_user_leads: {e}", exc_info=True)
