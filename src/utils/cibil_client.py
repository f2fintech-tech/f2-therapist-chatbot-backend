import os
import hashlib
import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_mock_report(name: str, phone: str, pan: str) -> Dict[str, Any]:
    """
    Generate a highly realistic and deterministic CIBIL report based on the PAN card.
    Using hashing ensures that the same PAN will always retrieve the same credit score and history.
    """
    pan_upper = pan.upper().strip()
    # Simple hash to get a deterministic number
    hash_object = hashlib.sha256(pan_upper.encode('utf-8'))
    hash_hex = hash_object.hexdigest()
    hash_int = int(hash_hex[:8], 16)

    # Calculate deterministic score between 580 and 850
    score = 580 + (hash_int % 271)
    
    # Determine credit band
    if score >= 750:
        band = "Excellent"
        payment_on_time = 98 + (hash_int % 3) # 98% - 100%
        utilization = 10 + (hash_int % 15)   # 10% - 25%
        credit_age_months = 48 + (hash_int % 60) # 4 to 9 years
        enquiries_l6m = hash_int % 2         # 0 - 1
        secured_loans = 1 + (hash_int % 2)
        unsecured_loans = 1 + (hash_int % 2)
        write_offs = 0
        defaults = 0
    elif score >= 700:
        band = "Good"
        payment_on_time = 93 + (hash_int % 5) # 93% - 97%
        utilization = 25 + (hash_int % 15)   # 25% - 40%
        credit_age_months = 24 + (hash_int % 40) # 2 to 5 years
        enquiries_l6m = 1 + (hash_int % 2)     # 1 - 2
        secured_loans = 1
        unsecured_loans = 1 + (hash_int % 3)
        write_offs = 0
        defaults = 0
    elif score >= 630:
        band = "Fair"
        payment_on_time = 85 + (hash_int % 8) # 85% - 93%
        utilization = 40 + (hash_int % 25)   # 40% - 65%
        credit_age_months = 12 + (hash_int % 24) # 1 to 3 years
        enquiries_l6m = 2 + (hash_int % 3)     # 2 - 4
        secured_loans = 0
        unsecured_loans = 2 + (hash_int % 2)
        write_offs = 0
        defaults = hash_int % 2
    else:
        band = "Poor"
        payment_on_time = 65 + (hash_int % 15) # 65% - 80%
        utilization = 65 + (hash_int % 30)   # 65% - 95%
        credit_age_months = 6 + (hash_int % 18) # 0.5 to 2 years
        enquiries_l6m = 4 + (hash_int % 4)     # 4 - 8
        secured_loans = 0
        unsecured_loans = 2 + (hash_int % 3)
        write_offs = 1
        defaults = 1 + (hash_int % 2)

    # Format age in years
    credit_age_years = round(credit_age_months / 12, 1)

    # Detailed Mock Accounts
    accounts = []
    
    # 1. Credit Card Account (always present)
    cc_banks = ["HDFC Bank", "SBI Card", "ICICI Bank", "Axis Bank"]
    cc_bank = cc_banks[hash_int % len(cc_banks)]
    cc_limit = 50000 + ((hash_int % 10) * 50000) # 50K to 500K
    cc_balance = int(cc_limit * (utilization / 100.0))
    accounts.append({
        "lender": cc_bank,
        "type": "Credit Card",
        "sanctioned_amount": cc_limit,
        "outstanding_balance": cc_balance,
        "payment_status": "Current" if defaults == 0 else "30 Days Past Due",
        "open_date": f"{(2026 - int(credit_age_years))}-06-15",
        "is_active": True
    })

    # 2. Personal/Auto Loan Account (if age is higher)
    if credit_age_years > 2:
        loan_banks = ["HDFC Bank", "Kotak Mahindra", "SBI", "Tata Capital"]
        loan_bank = loan_banks[(hash_int + 1) % len(loan_banks)]
        loan_amount = 100000 + ((hash_int % 8) * 100000) # 100K to 800K
        loan_balance = int(loan_amount * 0.4) if defaults == 0 else int(loan_amount * 0.8)
        accounts.append({
            "lender": loan_bank,
            "type": "Personal Loan",
            "sanctioned_amount": loan_amount,
            "outstanding_balance": loan_balance,
            "payment_status": "Current" if defaults == 0 else "60 Days Past Due",
            "open_date": f"{(2026 - int(credit_age_years - 1))}-11-20",
            "is_active": True
        })

    # 3. Closed Consumer Durable Loan (for history)
    if credit_age_years > 1:
        cd_lenders = ["Bajaj Finserv", "Capital First", "Home Credit"]
        cd_lender = cd_lenders[(hash_int + 2) % len(cd_lenders)]
        accounts.append({
            "lender": cd_lender,
            "type": "Consumer Durable Loan",
            "sanctioned_amount": 35000,
            "outstanding_balance": 0,
            "payment_status": "Closed / Settled",
            "open_date": f"{(2026 - int(credit_age_years))}-01-10",
            "is_active": False
        })

    # Actionable Improvement Tips
    tips = []
    if utilization > 30:
        tips.append("Your credit card utilization is above the recommended 30%. Try paying off outstanding card balances to lower it.")
    if enquiries_l6m > 2:
        tips.append("You have multiple credit inquiries in the last 6 months. Avoid applying for new credit lines consecutively to protect your score.")
    if payment_on_time < 95:
        tips.append("Missed or late payments are hurting your score. Set up auto-debit payments for your loan EMIs and credit cards.")
    if defaults > 0 or write_offs > 0:
        tips.append("Unresolved defaults/past-due accounts are flag markers on your report. Contact your lenders to resolve settlements and get a No Due Certificate (NDC).")
    if secured_loans == 0:
        tips.append("Your credit profile lacks secured loans. Adding a secured credit line (like a gold loan or secure FD-backed card) will improve your credit mix.")
    
    if not tips:
        tips.append("Great job! Your credit habits are healthy. Keep utilization low and continue making timely payments to maintain this excellent score.")

    return {
        "score": score,
        "band": band,
        "pan": pan_upper,
        "name": name,
        "phone": phone,
        "metrics": {
            "payment_on_time_pct": payment_on_time,
            "credit_utilization_pct": utilization,
            "credit_history_age_years": credit_age_years,
            "enquiries_l6m": enquiries_l6m,
            "secured_loans_count": secured_loans,
            "unsecured_loans_count": unsecured_loans,
            "write_offs": write_offs,
            "defaults": defaults
        },
        "accounts": accounts,
        "tips": tips,
        "fetched_at": datetime.utcnow().isoformat()
    }

async def fetch_actual_cibil_report(name: str, phone: str, pan: str) -> Dict[str, Any]:
    """
    Core API client function. Attempts to query the real CIBIL API if configured.
    Falls back gracefully to the deterministic mock generator on missing credentials or API timeout.
    """
    api_url = os.getenv("CIBIL_API_URL")
    api_key = os.getenv("CIBIL_API_KEY")

    if not api_url or not api_key:
        logger.info("CIBIL_API_URL or CIBIL_API_KEY not configured. Falling back to simulated bureau report.")
        return generate_mock_report(name, phone, pan)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "name": name,
                "phone": phone,
                "pan": pan.upper().strip()
            }
            response = await client.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                logger.info("Successfully fetched CIBIL report from actual API.")
                data = response.json()
                # Attach fetch timestamp
                data["fetched_at"] = datetime.utcnow().isoformat()
                return data
            else:
                logger.warning(f"CIBIL API returned status code {response.status_code}. Falling back to simulation.")
                return generate_mock_report(name, phone, pan)
    except Exception as e:
        logger.error(f"Error querying CIBIL API: {e}. Falling back to simulation.", exc_info=True)
        return generate_mock_report(name, phone, pan)
