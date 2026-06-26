import os
import hashlib
import httpx
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def generate_mock_report(name: str, phone: str, pan: Optional[str] = None, is_company: bool = False) -> Dict[str, Any]:
    """
    Generate a highly realistic and deterministic CIBIL report based on the PAN card.
    Using hashing ensures that the same PAN will always retrieve the same credit score and history.
    """
    pan_upper = pan.upper().strip() if pan else ""
    hash_source = pan_upper if pan_upper else f"MOCK_{phone}"
    # Simple hash to get a deterministic number
    hash_object = hashlib.sha256(hash_source.encode('utf-8'))
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
    tips = []

    if is_company:
        # Commercial / Corporate Credit Accounts
        # 1. Term Loan (Corporate)
        accounts.append({
            "lender": "State Bank of India",
            "type": "Term Loan (Corporate)",
            "sanctioned_amount": 15000000,
            "outstanding_balance": 9500000 if defaults == 0 else 14000000,
            "payment_status": "Current" if defaults == 0 else "30 Days Past Due",
            "open_date": f"{(2026 - int(credit_age_years))}-03-12",
            "is_active": True
        })
        # 2. Cash Credit / Overdraft Limit
        accounts.append({
            "lender": "HDFC Bank",
            "type": "Cash Credit / Overdraft",
            "sanctioned_amount": 5000000,
            "outstanding_balance": int(5000000 * (utilization / 100.0)),
            "payment_status": "Current",
            "open_date": f"{(2026 - int(credit_age_years))}-09-18",
            "is_active": True
        })
        if credit_age_years > 2:
            # 3. Bank Guarantee or Letter of Credit
            accounts.append({
                "lender": "ICICI Bank",
                "type": "Letter of Credit / Trade Credit",
                "sanctioned_amount": 2500000,
                "outstanding_balance": 0,
                "payment_status": "Current",
                "open_date": f"{(2026 - int(credit_age_years - 1))}-11-05",
                "is_active": True
            })

        if utilization > 40:
            tips.append("Your working capital / cash credit limit utilization is high. Try to service interest on time and clear outstanding balances regularly.")
        if enquiries_l6m > 2:
            tips.append("Frequent applications for commercial loans or bank guarantees can adversely impact your company's credit profile.")
        if payment_on_time < 95:
            tips.append("Late payments on term loans or overdrafts are impacting the company's CIBIL Rank. Set up auto-debit mechanisms.")
        if defaults > 0 or write_offs > 0:
            tips.append("Unresolved defaults in commercial accounts are major red flags. Settle any disputes or past due amounts with your commercial lenders.")
        if not tips:
            tips.append("Excellent commercial credit history! Maintain a healthy Debt Service Coverage Ratio (DSCR) to keep this rating.")
    else:
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

        # 3. Active Consumer Durable Loan
        if credit_age_years > 1:
            cd_lenders = ["Bajaj Finserv", "Capital First", "Home Credit"]
            cd_lender = cd_lenders[(hash_int + 2) % len(cd_lenders)]
            accounts.append({
                "lender": cd_lender,
                "type": "Consumer Durable Loan",
                "sanctioned_amount": 35000,
                "outstanding_balance": 12500,
                "payment_status": "Current",
                "open_date": f"{(2026 - int(credit_age_years))}-01-10",
                "is_active": True
            })

        # Actionable Improvement Tips
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
        "date_of_birth": "1999-12-28",
        "age": 26,
        "gender": "Male",
        "address": "123, Block C, Green Park, New Delhi, Delhi 110016",
        "email": "customer@example.com",
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
        "pdf_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf-test.pdf",
        "fetched_at": datetime.utcnow().isoformat()
    }

class CibilNoRecordError(Exception):
    """Raised when the bureau API returns a valid response indicating no credit record found for the PAN."""
    pass


async def fetch_actual_cibil_report(name: str, phone: str, pan: str, is_company: bool = False) -> Dict[str, Any]:
    """
    Core API client function. Attempts to query the real CIBIL API (Timble Glance) if configured.
    Raises CibilNoRecordError if the bureau explicitly says no records were found.
    Falls back to mock ONLY if credentials are not configured.
    """
    api_url = (os.getenv("CIBIL_API_URL") or "").strip()
    api_key = (os.getenv("CIBIL_API_KEY") or "").strip()

    if not api_url or not api_key:
        logger.info("CIBIL_API_URL or CIBIL_API_KEY not configured. Falling back to simulated bureau report.")
        return generate_mock_report(name, phone, pan, is_company=is_company)

    logger.info(f"[CIBIL] Attempting real API call to: {api_url}")
    logger.info(f"[CIBIL] API key (first 6 chars): {api_key[:6]}...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Timble Glance uses 'api-key' header (confirmed by IT admin curl command)
            headers = {
                "api-key": api_key,
                "Content-Type": "application/json"
            }
            # Timble Glance uses 'mobile' not 'phone' (confirmed by IT admin curl command)
            payload = {
                "name": name,
                "mobile": phone,
                "pan": pan.upper().strip()
            }
            logger.info(f"[CIBIL] Request headers: {headers}")
            logger.info(f"[CIBIL] Request payload: {payload}")

            response = await client.post(api_url, json=payload, headers=headers)
            
            logger.info(f"[CIBIL] Response status: {response.status_code}")
            logger.info(f"[CIBIL] Response body (first 2000 chars): {response.text[:2000]}")

            if response.status_code == 200:
                data = response.json()

                # --- Detect "no records found" responses ---
                # Timble Glance returns response_code=103 with empty result{} for no records
                response_code = data.get("response_code")
                status_val = str(data.get("status", data.get("response_code", ""))).lower()
                result_code = str(data.get("result_code", "")).lower()
                message = str(data.get("message", data.get("msg", data.get("error", data.get("response_message", ""))))).lower()

                no_record_indicators = ["no record", "not found", "no data", "no hit", "no match",
                                        "nhit", "no_record", "record_not_found", "no credit"]
                combined_text = f"{status_val} {result_code} {message}"
                is_no_record = any(indicator in combined_text for indicator in no_record_indicators)
                
                # Timble Glance: response_code 103 = no records, or result is empty dict
                if response_code == 103 or (isinstance(data.get("result"), dict) and not data.get("result") and not is_no_record):
                    is_no_record = True
                
                if is_no_record:
                    response_msg = data.get("response_message", message or status_val)
                    logger.warning(f"[CIBIL] Bureau returned NO RECORD for PAN {pan[:5]}*****: {response_msg}")
                    raise CibilNoRecordError(
                        f"No credit record found for this PAN in CIBIL bureau. "
                        f"This may mean the individual has no credit history. "
                        f"Bureau response: {response_msg}"
                    )

                # --- Check if response has expected score data ---
                actual_data = data
                for wrapper_key in ["data", "result", "report", "response", "cibil_data", "credit_report"]:
                    if wrapper_key in data and isinstance(data[wrapper_key], dict) and data[wrapper_key]:
                        actual_data = data[wrapper_key]
                        logger.info(f"[CIBIL] Found nested data under key '{wrapper_key}'")
                        break

                # Debug: log raw response structure
                logger.info(f"[CIBIL] Raw response top-level keys: {list(data.keys())}")
                logger.info(f"[CIBIL] Actual data keys (after unwrap): {list(actual_data.keys())}")
                import json as _json
                try:
                    with open("_last_cibil_raw_response.json", "w") as _f:
                        _f.write(_json.dumps(data, indent=2, default=str))
                    logger.info("[CIBIL] Raw response saved to _last_cibil_raw_response.json")
                except Exception:
                    pass

                # Normalize the response to our expected schema
                normalized = _normalize_bureau_response(actual_data, name, phone, pan, raw_data=data)
                
                # Attach the raw bureau JSON so the router can persist it separately
                normalized["_raw_bureau_json"] = data

                logger.info(f"[CIBIL] Successfully fetched real report. Score: {normalized.get('score')}, Band: {normalized.get('band')}")
                return normalized

            elif response.status_code == 401:
                error_body = response.text[:500]
                logger.error(f"[CIBIL] Authentication failed (401): {error_body}")
                raise Exception(f"CIBIL API authentication failed. Verify your api-key is correct and active. Response: {error_body}")
                
            else:
                logger.error(f"[CIBIL] API returned status {response.status_code}: {response.text[:1000]}")
                raise Exception(f"CIBIL API returned HTTP {response.status_code}: {response.text[:500]}")

    except CibilNoRecordError:
        raise  # Re-raise no-record errors without catching
    except Exception as e:
        logger.error(f"[CIBIL] Error querying CIBIL API: {e}", exc_info=True)
        raise  # Do NOT silently fall back to mock when API is configured


def normalize_cibil_report_from_raw(raw_bureau_json: Dict[str, Any], name: str = "", phone: str = "", pan: str = "", fetched_at: str = None) -> Dict[str, Any]:
    """
    Re-parse a raw bureau JSON response (as stored in DB) using the current normalization logic.
    Called by the GET /cibil/report endpoint so every retrieval always reflects the latest parser.
    Returns the normalized report dict WITHOUT the _raw_bureau_json key.
    """
    if not raw_bureau_json or not isinstance(raw_bureau_json, dict):
        return {}

    # Determine actual_data (same unwrapping logic as during fetch)
    actual_data = raw_bureau_json
    for wrapper_key in ["data", "result", "report", "response", "cibil_data", "credit_report"]:
        if wrapper_key in raw_bureau_json and isinstance(raw_bureau_json[wrapper_key], dict) and raw_bureau_json[wrapper_key]:
            actual_data = raw_bureau_json[wrapper_key]
            break

    normalized = _normalize_bureau_response(actual_data, name, phone, pan, raw_data=raw_bureau_json, fetched_at=fetched_at)
    # Ensure no internal keys leak out
    normalized.pop("_raw_bureau_json", None)
    logger.info(f"[CIBIL] Re-parsed stored raw JSON. Score: {normalized.get('score')}, Accounts: {len(normalized.get('accounts', []))}")
    return normalized


async def fetch_actual_experian_report(name: str, phone: str, pan: Optional[str] = None, is_company: bool = False, device_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Core API client function for Experian (Digitap). Attempts to query the real Experian API if configured.
    Raises CibilNoRecordError if the bureau explicitly says no records were found.
    Falls back to mock ONLY if credentials are not configured.
    """
    api_url = (os.getenv("EXPERIAN_API_URL") or "").strip()
    api_key = (os.getenv("EXPERIAN_API_KEY") or "").strip()
    client_id = (os.getenv("EXPERIAN_CLIENT_ID") or "").strip()

    if not api_url or not api_key:
        logger.info("EXPERIAN_API_URL or EXPERIAN_API_KEY not configured. Falling back to simulated bureau report.")
        return generate_mock_report(name, phone, pan, is_company=is_company)

    logger.info(f"[EXPERIAN] Attempting real API call to: {api_url}")
    logger.info(f"[EXPERIAN] API key (first 6 chars): {api_key[:6]}..., Client-ID: {client_id}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            import base64
            from datetime import datetime

            # ✅ CONFIRMED: Basic auth (client_id:api_key) is correct for Digitap
            auth_b64 = base64.b64encode(f"{client_id}:{api_key}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/json"
            }

            # ✅ ROOT CAUSE FIX: Exact payload format from working Postman request
            name_parts = name.strip().split()
            first_name = name_parts[0].upper() if name_parts else name.upper()
            last_name = " ".join(name_parts[1:]).upper() if len(name_parts) > 1 else ""

            # Timestamp format: DDMMYYYY-HH:MM:SS (as confirmed from Postman)
            timestamp = datetime.now().strftime("%d%m%Y-%H:%M:%S")

            # Make OTP configurable, default to the working test OTP
            experian_otp = os.getenv("EXPERIAN_OTP", "234567")
            
            import uuid
            unique_ref_num = str(uuid.uuid4())

            payload: dict = {
                "otp": experian_otp,
                "device_ip": device_ip,
                "mobile_no": phone,
                "timestamp": timestamp,
                "device_type": "web",
                "name_lookup": 0,
                "first_name": first_name,
                "last_name": last_name,
                "report_type": "3",
                "client_ref_num": unique_ref_num,
                "consent_message": "I hereby authorize Experian to pull my credit report for test purpose.",
                "consent_acceptance": "Yes"
            }
            if pan:
                payload["pan"] = pan.upper().strip()

            logger.info(f"[EXPERIAN] Request payload: {payload}")
            response = await client.post(api_url, json=payload, headers=headers)


            logger.info(f"[EXPERIAN] Response status: {response.status_code}")
            logger.info(f"[EXPERIAN] Response body (first 2000 chars): {response.text[:2000]}")

            # Save the full raw response to a file for the user to inspect
            try:
                import json
                with open("experian_raw_response.json", "w") as f:
                    json.dump(response.json(), f, indent=2)
                logger.info("[EXPERIAN] Full raw response saved to experian_raw_response.json")
            except Exception as e:
                logger.warning(f"[EXPERIAN] Could not save raw response to file: {e}")

            if response.status_code == 200:
                data = response.json()

                # --- Detect "no records found" responses ---
                status_val = str(data.get("status", "")).lower()
                result_code = str(data.get("result_code", "")).lower()
                message = str(data.get("message", data.get("msg", data.get("error", "")))).lower()

                no_record_indicators = ["no record", "not found", "no data", "no hit", "no match",
                                        "nhit", "no_record", "record_not_found", "no credit"]
                combined_text = f"{status_val} {result_code} {message}"
                if any(indicator in combined_text for indicator in no_record_indicators):
                    logger.warning(f"[EXPERIAN] Bureau returned NO RECORD for PAN {(pan[:5] if pan else '')}*****: {message}")
                    raise CibilNoRecordError(
                        f"No credit record found for this PAN in Experian bureau. "
                        f"This may mean the individual has no credit history. "
                        f"Bureau response: {message or status_val}"
                    )

                # --- Experian (Digitap) specific unwrapping ---
                # Response structure: data → result → result_json → INProfileResponse
                in_profile = None
                result_obj = data.get("result", {})
                if isinstance(result_obj, dict):
                    result_json = result_obj.get("result_json", {})
                    if isinstance(result_json, dict):
                        in_profile = result_json.get("INProfileResponse")
                        if in_profile:
                            logger.info("[EXPERIAN] Found INProfileResponse in result.result_json")

                if in_profile:
                    actual_data = in_profile
                else:
                    # Fallback: generic unwrap
                    actual_data = data
                    for wrapper_key in ["data", "result", "report", "response", "credit_report"]:
                        if wrapper_key in data and isinstance(data[wrapper_key], dict):
                            actual_data = data[wrapper_key]
                            logger.info(f"[EXPERIAN] Found nested data under key '{wrapper_key}'")
                            break

                normalized = _normalize_bureau_response(actual_data, name, phone, pan, raw_data=data)
                logger.info(f"[EXPERIAN] Successfully fetched real report. Score: {normalized.get('score')}, Band: {normalized.get('band')}")
                return normalized


            else:
                logger.error(f"[EXPERIAN] API returned status {response.status_code}: {response.text[:1000]}")
                raise Exception(f"Experian API returned HTTP {response.status_code}: {response.text[:500]}")

    except CibilNoRecordError:
        raise
    except Exception as e:
        logger.error(f"[EXPERIAN] Error querying Experian API: {e}", exc_info=True)
        raise  # Do NOT silently fall back to mock when API is configured


def _is_secured_inquiry(purpose_code: str) -> bool:
    code = str(purpose_code or "").strip().zfill(2)
    if code in {"01", "02", "03", "04", "07", "14", "16", "33", "34", "35"}:
        return True
    purpose_lower = code.lower()
    for kw in ["home", "housing", "auto", "car", "gold", "property", "vehicle", "lap", "two wheeler", "two-wheeler"]:
        if kw in purpose_lower:
            return True
    return False


def resolve_ownership_type(designator_node: dict, account_type_symbol: str = "", account_type_desc: str = "") -> str:
    if not isinstance(designator_node, dict):
        return "Individual"
        
    # 1. Try to resolve from description
    desc = (designator_node.get("description") or "").strip().lower()
    if desc:
        if "individual" in desc or "single" in desc:
            return "Individual"
        if "joint" in desc:
            return "Joint"
        if "guarantor" in desc:
            return "Guarantor"
        if "authorized" in desc or "supplementary" in desc:
            return "Authorized User"
        return designator_node.get("description").strip()
        
    # 2. Try to resolve from abbreviation
    abbr = (designator_node.get("abbreviation") or "").strip().upper()
    if abbr:
        if abbr in ["IND", "SG", "S"]:
            return "Individual"
        if abbr in ["JT", "J"]:
            return "Joint"
        if abbr in ["GT", "G", "GR"]:
            return "Guarantor"
        if abbr in ["SU", "A", "AU"]:
            return "Authorized User"
            
    # 3. Fallback to symbol mapping
    symbol = str(designator_node.get("symbol") or "").strip()
    if symbol == "1":
        return "Individual"
    elif symbol in ["2", "7"]:
        return "Joint"
    elif symbol == "3":
        if account_type_symbol == "08" or account_type_desc == "Education Loan":
            return "Joint"
        return "Authorized User"
    elif symbol == "4":
        if account_type_symbol == "08" or account_type_desc == "Education Loan":
            return "Joint"
        return "Guarantor"
        
    return "Individual"


def _normalize_bureau_response(data: Dict[str, Any], name: str, phone: str, pan: Optional[str] = None, raw_data: Dict[str, Any] = None, fetched_at: str = None) -> Dict[str, Any]:
    """
    Normalize a real bureau API response into our standard schema.
    Handles many possible key naming conventions from different providers.
    """
    if raw_data is None:
        raw_data = data

    # Standard Bureau Account Type Mapping
    ACCOUNT_TYPES = {
        "01": "Auto Loan",
        "02": "Housing Loan",
        "03": "Property Loan",
        "04": "Loan Against Shares/Securities",
        "05": "Personal Loan",
        "06": "Consumer Loan",
        "07": "Gold Loan",
        "08": "Education Loan",
        "09": "Professional Loan",
        "10": "Credit Card",
        "12": "Overdraft",
        "13": "Two-Wheeler Loan",
        "14": "Non-Funded Credit Facility",
        "15": "Loan Against Bank Deposits",
        "17": "Commercial Vehicle Loan",
        "18": "Professional Loan",
        "31": "Secured Credit Card",
        "32": "Used Car Loan",
        "33": "Construction Equipment Loan",
        "34": "Tractor Loan",
        "35": "Corporate Credit Card",
        "36": "Credit Card",
        "37": "Professional Loan",
        "38": "Professional Loan",
        "41": "Business Loan - General",
        "42": "Business Loan - Priority Sector (Agri)",
        "43": "Business Loan - Priority Sector (Small Bus)",
        "44": "Business Loan - Priority Sector (Prof)",
        "51": "Business Loan - Secured",
        "52": "Business Loan - Unsecured",
        "53": "Microfinance Business Loan",
        "54": "Microfinance Personal Loan",
        "57": "Microfinance Other",
        "61": "Business Loan",
        "99": "Other",
        # Sometimes returned without leading zero
        "1": "Auto Loan",
        "2": "Housing Loan",
        "3": "Property Loan",
        "4": "Loan Against Shares/Securities",
        "5": "Personal Loan",
        "6": "Consumer Loan",
        "7": "Gold Loan",
        "8": "Education Loan",
        "9": "Professional Loan",
    }

    # --- Timble Glance Specific Parser ---
    cibil_data = None
    if isinstance(data, dict):
        if "cibilData" in data:
            cibil_data = data["cibilData"]
        elif "cibil_report" in data and isinstance(data["cibil_report"], dict) and "raw" in data["cibil_report"]:
            cibil_data = data["cibil_report"]["raw"]
            
    if not cibil_data and isinstance(raw_data, dict):
        if "result" in raw_data and isinstance(raw_data["result"], dict):
            if "cibilData" in raw_data["result"]:
                cibil_data = raw_data["result"]["cibilData"]
            elif "cibil_report" in raw_data["result"] and isinstance(raw_data["result"]["cibil_report"], dict) and "raw" in raw_data["result"]["cibil_report"]:
                cibil_data = raw_data["result"]["cibil_report"]["raw"]

    if isinstance(cibil_data, dict):
        success_node = cibil_data.get("GetCustomerAssetsResponse", {}).get("GetCustomerAssetsSuccess", {})
        if success_node:
            logger.info("[NORMALIZE] Using Timble Glance CIBIL specific parser")
            asset = success_node.get("Asset", {})
            tl_report = asset.get("TrueLinkCreditReport", {})
            borrower = tl_report.get("Borrower", {})
            
            # Extract score
            score = 0
            credit_score_node = borrower.get("CreditScore", {})
            if isinstance(credit_score_node, dict):
                score_val = credit_score_node.get("riskScore")
                if score_val is not None:
                    try:
                        score = int(float(str(score_val)))
                    except (ValueError, TypeError):
                        pass

            # Determine band
            if score >= 750: band = "Excellent"
            elif score >= 700: band = "Good"
            elif score >= 630: band = "Fair"
            elif score > 0: band = "Poor"
            else: band = "Unknown"

            # Extract name
            name_node = borrower.get("BorrowerName", {}).get("Name", {})
            if name_node:
                forename = name_node.get("Forename", "")
                surname = name_node.get("Surname", "")
                report_name = f"{forename} {surname}".strip()
            else:
                report_name = name

            # Extract PAN
            report_pan = pan
            identifiers = borrower.get("IdentifierPartition", {}).get("Identifier", {})
            if isinstance(identifiers, dict):
                for k, ident_val in identifiers.items():
                    if isinstance(ident_val, dict):
                        id_node = ident_val.get("ID", {})
                        if id_node.get("IdentifierName") == "TaxId":
                            report_pan = id_node.get("Id", pan)
                            break

            # Extract accounts
            accounts = []
            trade_partition = tl_report.get("TradeLinePartition", {})
            if isinstance(trade_partition, dict):
                for k, part_val in trade_partition.items():
                    if not isinstance(part_val, dict):
                        continue
                    if "Tradeline" in part_val and isinstance(part_val["Tradeline"], dict):
                        tradeline = part_val["Tradeline"]
                    else:
                        tradeline = part_val
                    granted_trade = tradeline.get("GrantedTrade", {}) if isinstance(tradeline, dict) else {}
                    
                    lender = tradeline.get("creditorName") or "Unknown"
                    
                    symbol = part_val.get("accountTypeSymbol") or ""
                    acc_type = ACCOUNT_TYPES.get(symbol, part_val.get("accountTypeDescription") or "Other Loan")
                    
                    sanctioned = _safe_int(tradeline.get("highBalance") or granted_trade.get("CreditLimit"))
                    outstanding = _safe_int(tradeline.get("currentBalance"))
                    
                    is_active = True
                    if "dateClosed" in tradeline and tradeline["dateClosed"]:
                        is_active = False
                    
                    past_due_amt = _safe_int(granted_trade.get("amountPastDue"))
                    if past_due_amt > 0:
                        payment_status = f"Past Due (₹{past_due_amt})"
                    else:
                        payment_status = "Current"
                        
                    open_date_raw = tradeline.get("dateOpened") or ""
                    open_date = open_date_raw.split("+")[0].strip()
                    
                    # Ownership indicator mapping
                    designator_node = tradeline.get("AccountDesignator", {})
                    ownership = resolve_ownership_type(designator_node, symbol, acc_type)

                    # Tenure in months
                    tenure_months = None
                    term_months_val = granted_trade.get("termMonths") if isinstance(granted_trade, dict) else None
                    if term_months_val is not None:
                        try:
                            tenure_months = int(float(str(term_months_val)))
                        except (ValueError, TypeError):
                            pass

                    # Ending Date (Closed Date or Expected End Date)
                    date_closed_raw = tradeline.get("dateClosed") or ""
                    if date_closed_raw:
                        end_date = date_closed_raw.split("+")[0].strip()
                    else:
                        end_date = "-"
                        if open_date and open_date != "-" and tenure_months:
                            try:
                                base_dt = datetime.strptime(open_date, "%Y-%m-%d")
                                end_dt = _add_months(base_dt, tenure_months)
                                end_date = end_dt.strftime("%Y-%m-%d")
                            except Exception:
                                pass

                    accounts.append({
                        "lender": lender,
                        "type": acc_type,
                        "sanctioned_amount": sanctioned,
                        "outstanding_balance": outstanding,
                        "payment_status": payment_status,
                        "open_date": open_date,
                        "is_active": is_active,
                        "ownership": ownership,
                        "tenure_months": tenure_months,
                        "end_date": end_date
                    })

            # Extract metrics
            summary_data = success_node.get("CreditSummaryData", {})
            if isinstance(summary_data, dict) and summary_data:
                utilization = _safe_int(summary_data.get("CreditCardUtilization"))
                enquiries = _safe_int(summary_data.get("Inquires"))
                history_months = _safe_int(summary_data.get("OldestCreditAccountPeriod"))
                history_years = round(history_months / 12.0, 1)
                on_time_pct = _safe_int(summary_data.get("OnTimePaymentHistory", 100))
            else:
                utilization = 0
                enquiries = 0
                history_years = 3.0
                on_time_pct = 100
                
            # Filter enquiries to show only the last 6 months count and last 3 months counts
            inquiries_l6m_count = 0
            inquiries_l3m_count = 0
            inquiries_l3m_secured = 0
            inquiries_l3m_unsecured = 0
            inquiry_partition = tl_report.get("InquiryPartition", {})
            if isinstance(inquiry_partition, dict) and inquiry_partition:
                ref_dt = datetime.utcnow()
                creation_date_str = asset.get("CreationDate") or ""
                if creation_date_str:
                    parsed_ref = _parse_date(creation_date_str.split("T")[0])
                    if parsed_ref:
                        ref_dt = parsed_ref
                
                for key, val in inquiry_partition.items():
                    if isinstance(val, dict):
                        if "Inquiry" in val and isinstance(val["Inquiry"], dict):
                            inq = val["Inquiry"]
                        else:
                            inq = val
                        if isinstance(inq, dict):
                            inq_date_str = inq.get("inquiryDate") or ""
                            if inq_date_str:
                                inq_dt = _parse_date(inq_date_str)
                                if inq_dt:
                                    days_diff = (ref_dt - inq_dt).days
                                    if 0 <= days_diff <= 180:
                                        inquiries_l6m_count += 1
                                    if 0 <= days_diff <= 90:
                                        inquiries_l3m_count += 1
                                        purpose = str(inq.get("inquiryPurpose") or "").strip()
                                        if _is_secured_inquiry(purpose):
                                            inquiries_l3m_secured += 1
                                        else:
                                            inquiries_l3m_unsecured += 1
                enquiries = inquiries_l6m_count

            secured_count = len([a for a in accounts if any(x in a["type"].lower() for x in ["housing", "home", "auto", "gold", "lap", "property", "vehicle", "two wheeler", "two-wheeler"])])
            unsecured_count = len([a for a in accounts if any(x in a["type"].lower() for x in ["personal", "card", "consumer", "unsecured", "professional", "business", "overdraft", "other"])])
            
            defaults_count = len([a for a in accounts if "past due" in a["payment_status"].lower()])
            write_offs_count = 0
            for part_val in trade_partition.values():
                if not isinstance(part_val, dict):
                    continue
                if "Tradeline" in part_val and isinstance(part_val["Tradeline"], dict):
                    tradeline = part_val["Tradeline"]
                else:
                    tradeline = part_val
                if isinstance(tradeline, dict):
                    if _safe_int(tradeline.get("writtenOffAmtTotal")) > 0 or _safe_int(tradeline.get("writtenOffPrincipal")) > 0:
                        write_offs_count += 1
            
            # Extract gender, address, email, DOB, and age
            gender = borrower.get("Gender") or "-"
            
            address = "-"
            addr_node = borrower.get("BorrowerAddress", {})
            if isinstance(addr_node, dict):
                # Numbered nested keys check (CIBIL format: {"1": {...}, "2": {...}})
                best_addr = None
                latest_date = ""
                for k, v in addr_node.items():
                    if isinstance(v, dict):
                        caddr = v.get("CreditAddress", {})
                        if isinstance(caddr, dict) and caddr.get("StreetAddress"):
                            dt = v.get("dateReported") or ""
                            if not best_addr or (dt and dt > latest_date):
                                best_addr = caddr.get("StreetAddress")
                                latest_date = dt
                if best_addr:
                    address = best_addr
                else:
                    # Flat dictionary fallback
                    credit_addr = addr_node.get("CreditAddress", {})
                    if isinstance(credit_addr, dict):
                        address = credit_addr.get("StreetAddress") or "-"

            dob = "-"
            age = "-"
            birth_node = borrower.get("Birth", {})
            if isinstance(birth_node, dict):
                dob_raw = birth_node.get("date") or ""
                if dob_raw:
                    dob = dob_raw.split("+")[0].strip()
                else:
                    birth_date_node = birth_node.get("BirthDate", {})
                    if birth_date_node:
                        day = birth_date_node.get("day")
                        month = birth_date_node.get("month")
                        year = birth_date_node.get("year")
                        if day and month and year:
                            try:
                                dob = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                            except (ValueError, TypeError):
                                pass
                
                if dob != "-":
                    try:
                        birth_date = datetime.strptime(dob, "%Y-%m-%d")
                        ref_dt = datetime.utcnow()
                        age = ref_dt.year - birth_date.year - ((ref_dt.month, ref_dt.day) < (birth_date.month, birth_date.day))
                    except Exception:
                        pass

            email = "-"
            email_node = borrower.get("EmailAddress", {})
            if isinstance(email_node, dict):
                # Try getting the email from "1" first, or loop
                if "1" in email_node and isinstance(email_node["1"], dict):
                    email = email_node["1"].get("Email") or "-"
                if email == "-":
                    for k, v in email_node.items():
                        if isinstance(v, dict) and v.get("Email"):
                            email = v.get("Email")
                            break
            
            if email == "-":
                b_email_node = borrower.get("BorrowerEmail", {})
                if isinstance(b_email_node, dict):
                    email = b_email_node.get("EmailAddress") or "-"
                elif isinstance(b_email_node, list) and b_email_node:
                    email = b_email_node[0].get("EmailAddress") or "-"
            
            if email == "-":
                email_val = borrower.get("email") or borrower.get("Email")
                if isinstance(email_val, list) and email_val:
                    email = email_val[0].get("emailAddress") or email_val[0].get("EmailAddress") or "-"
                elif isinstance(email_val, str):
                    email = email_val

            # Extract employment type
            employer_node = borrower.get("Employer", {})
            employment_type = "-"
            if isinstance(employer_node, dict):
                employment_type = employer_node.get("OccupationCode", {}).get("description") or "-"
            elif isinstance(employer_node, list) and employer_node:
                first_emp = employer_node[0]
                if isinstance(first_emp, dict):
                    employment_type = first_emp.get("OccupationCode", {}).get("description") or "-"

            if employment_type and isinstance(employment_type, str):
                et_lower = employment_type.lower()
                if "self" in et_lower:
                    employment_type = "Self Employed"
                elif "salaried" in et_lower or "salary" in et_lower:
                    employment_type = "Salaried"

            metrics = {
                "payment_on_time_pct": on_time_pct,
                "credit_utilization_pct": utilization,
                "credit_history_age_years": history_years,
                "enquiries_l6m": enquiries,
                "enquiries_l3m": inquiries_l3m_count,
                "enquiries_l3m_secured": inquiries_l3m_secured,
                "enquiries_l3m_unsecured": inquiries_l3m_unsecured,
                "secured_loans_count": secured_count,
                "unsecured_loans_count": unsecured_count,
                "write_offs": write_offs_count,
                "defaults": defaults_count
            }

            tips = _generate_tips_from_metrics(metrics, score)

            pdf_url = None
            for d_source in [data, raw_data, raw_data.get("result", {}) if isinstance(raw_data, dict) else {}]:
                if isinstance(d_source, dict):
                    html_url = d_source.get("htmlUrl")
                    if html_url and isinstance(html_url, str) and html_url.startswith("http"):
                        pdf_url = html_url
                        break

            return {
                "score": score,
                "band": band,
                "pan": report_pan,
                "name": report_name,
                "phone": phone,
                "date_of_birth": dob,
                "age": age,
                "gender": gender,
                "address": address,
                "email": email,
                "employment_type": employment_type,
                "metrics": metrics,
                "accounts": accounts,
                "tips": tips,
                "pdf_url": pdf_url,
                "fetched_at": fetched_at or datetime.utcnow().isoformat()
            }

    # Extract score — try many possible key names
    score = None
    for key in ["score", "cibil_score", "credit_score", "bureau_score", "creditScore",
                 "CibilScore", "Score", "SCORE", "cibilScore"]:
        val = data.get(key)
        if val is not None:
            if isinstance(val, dict):
                # Handle nested SCORE objects (e.g. Experian INProfileResponse)
                inner_val = val.get("BureauScore", val.get("riskScore", val.get("score")))
                if inner_val is not None:
                    val = inner_val
            try:
                score = int(float(str(val)))
                break
            except (ValueError, TypeError):
                continue
    
    if score is None:
        logger.warning(f"[NORMALIZE] Could not find score in response keys: {list(data.keys())}")
        # If there's a raw_data wrapper, try there too
        if raw_data is not data:
            for key in ["score", "cibil_score", "credit_score", "bureau_score"]:
                val = raw_data.get(key)
                if val is not None:
                    try:
                        score = int(float(str(val)))
                        break
                    except (ValueError, TypeError):
                        continue
    
    if score is None:
        score = 0  # Unknown score

    # Determine band
    band = data.get("band", data.get("score_band", data.get("creditBand", "")))
    if not band:
        if score >= 750: band = "Excellent"
        elif score >= 700: band = "Good"
        elif score >= 630: band = "Fair"
        elif score > 0: band = "Poor"
        else: band = "Unknown"

    # Extract PAN
    report_pan = data.get("pan", data.get("PAN", data.get("panNumber", pan or "")))

    # Extract name
    report_name = data.get("name", data.get("full_name", data.get("consumerName", name)))

    # Extract accounts
    accounts_raw = data.get("accounts", data.get("account_details", data.get("credit_accounts",
                   data.get("tradeLines", data.get("AccountDetails", [])))))
    
    if not accounts_raw and "CAIS_Account" in data and isinstance(data["CAIS_Account"], dict):
        accounts_raw = data["CAIS_Account"].get("CAIS_Account_DETAILS", [])

    accounts = []
    if isinstance(accounts_raw, list):
        for acc in accounts_raw:
            if isinstance(acc, dict):
                # Map Experian CAIS account fields if present
                is_active = acc.get("is_active", acc.get("isActive"))
                if is_active is None:
                    # Experian: Date_Closed being null means active. Other bureaus use accountStatus.
                    date_closed = acc.get("Date_Closed")
                    acc_status = acc.get("accountStatus", "").lower()
                    is_active = not bool(date_closed) and acc_status not in ["closed", "written-off"]

                payment_status = acc.get("payment_status", acc.get("paymentStatus", acc.get("PaymentStatus")))
                if payment_status is None:
                    amt_past_due = _safe_int(acc.get("Amount_Past_Due"))
                    payment_status = "Current" if amt_past_due == 0 else f"Past Due (₹{amt_past_due})"

                raw_type = acc.get("type", acc.get("account_type", acc.get("Account_Type", acc.get("AccountType", "Unknown"))))
                mapped_type = ACCOUNT_TYPES.get(str(raw_type), raw_type) if raw_type else "Unknown"
                
                open_date = acc.get("open_date", acc.get("Open_Date", acc.get("openDate", acc.get("DateOpened", acc.get("dateOpened", "")))))

                # Try getting ownership from acc
                ownership = acc.get("ownership") or acc.get("Ownership")
                if not ownership:
                    designator_node = acc.get("AccountDesignator", {})
                    if isinstance(designator_node, dict) and designator_node:
                        ownership = resolve_ownership_type(designator_node, str(raw_type), mapped_type)
                    else:
                        # Fallback for Experian
                        ownership_val = acc.get("Ownership_Indicator") or acc.get("ownership_indicator")
                        if ownership_val:
                            ownership = str(ownership_val)
                        else:
                            ownership = "Individual"

                # Tenure
                tenure_months = acc.get("tenure_months") or acc.get("termMonths") or acc.get("Duration_of_Agreement")
                if tenure_months is not None:
                    try:
                        tenure_months = int(float(str(tenure_months)))
                    except (ValueError, TypeError):
                        tenure_months = None

                # Ending date
                end_date = acc.get("end_date") or acc.get("Date_Closed") or acc.get("dateClosed") or ""
                if end_date:
                    if isinstance(end_date, str):
                        end_date = end_date.split("+")[0].strip()
                else:
                    end_date = "-"
                    if open_date and open_date != "-" and tenure_months:
                        try:
                            base_dt = datetime.strptime(str(open_date).split("+")[0].strip()[:10], "%Y-%m-%d")
                            end_dt = _add_months(base_dt, tenure_months)
                            end_date = end_dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass

                accounts.append({
                    "lender": acc.get("lender", acc.get("lender_name", acc.get("institution", acc.get("Subscriber_Name", acc.get("MemberShortName", "Unknown"))))),
                    "type": mapped_type,
                    "sanctioned_amount": _safe_int(acc.get("sanctioned_amount", acc.get("Highest_Credit_or_Original_Loan_Amount", acc.get("highCredit", acc.get("SanctionAmount", acc.get("credit_limit", 0)))))),
                    "outstanding_balance": _safe_int(acc.get("outstanding_balance", acc.get("Current_Balance", acc.get("currentBalance", acc.get("CurrentBalance", acc.get("balance", 0)))))),
                    "payment_status": payment_status,
                    "open_date": open_date,
                    "is_active": is_active,
                    "ownership": ownership,
                    "tenure_months": tenure_months,
                    "end_date": end_date
                })

    # Extract metrics
    metrics_raw = data.get("metrics", data.get("score_factors", {}))
    if isinstance(metrics_raw, dict) and metrics_raw:
        metrics = {
            "payment_on_time_pct": _safe_int(metrics_raw.get("payment_on_time_pct", metrics_raw.get("onTimePaymentPct", 0))),
            "credit_utilization_pct": _safe_int(metrics_raw.get("credit_utilization_pct", metrics_raw.get("utilizationPct", 0))),
            "credit_history_age_years": round(float(metrics_raw.get("credit_history_age_years", metrics_raw.get("historyAgeYears", 0))), 1),
            "enquiries_l6m": _safe_int(metrics_raw.get("enquiries_l6m", metrics_raw.get("recentEnquiries", 0))),
            "enquiries_l3m": _safe_int(metrics_raw.get("enquiries_l3m", 0)),
            "enquiries_l3m_secured": _safe_int(metrics_raw.get("enquiries_l3m_secured", 0)),
            "enquiries_l3m_unsecured": _safe_int(metrics_raw.get("enquiries_l3m_unsecured", 0)),
            "secured_loans_count": _safe_int(metrics_raw.get("secured_loans_count", 0)),
            "unsecured_loans_count": _safe_int(metrics_raw.get("unsecured_loans_count", 0)),
            "write_offs": _safe_int(metrics_raw.get("write_offs", 0)),
            "defaults": _safe_int(metrics_raw.get("defaults", 0)),
        }
    else:
        # Derive metrics from accounts if not provided directly
        total_limit = sum(a.get("sanctioned_amount", 0) for a in accounts)
        total_balance = sum(a.get("outstanding_balance", 0) for a in accounts)
        utilization = int((total_balance / total_limit * 100)) if total_limit > 0 else 0
        active_count = len([a for a in accounts if a.get("is_active")])
        metrics = {
            "payment_on_time_pct": 95 if score >= 700 else (85 if score >= 630 else 70),
            "credit_utilization_pct": utilization,
            "credit_history_age_years": 3.0,
            "enquiries_l6m": _safe_int(data.get("enquiries_l6m", data.get("recentEnquiries", 0))),
            "enquiries_l3m": _safe_int(data.get("enquiries_l3m", 0)),
            "enquiries_l3m_secured": _safe_int(data.get("enquiries_l3m_secured", 0)),
            "enquiries_l3m_unsecured": _safe_int(data.get("enquiries_l3m_unsecured", 0)),
            "secured_loans_count": len([a for a in accounts if a.get("type", "").lower() in ["home loan", "car loan", "auto loan", "gold loan", "secured loan", "loan against property"]]),
            "unsecured_loans_count": len([a for a in accounts if a.get("type", "").lower() in ["personal loan", "credit card", "consumer durable", "consumer durable loan", "education loan"]]),
            "write_offs": 0,
            "defaults": 0,
        }

    # Calculate enquiries in the last 6 months from the actual list of inquiries if available
    inquiries_list = []
    
    # 1. Check root-level inquiry array
    if raw_data and isinstance(raw_data.get("inquiry"), list):
        inquiries_list = raw_data["inquiry"]
    elif isinstance(data.get("inquiry"), list):
        inquiries_list = data["inquiry"]
    elif isinstance(data.get("inquiries"), list):
        inquiries_list = data["inquiries"]
    elif isinstance(data.get("enquiries"), list):
        inquiries_list = data["enquiries"]
    
    # 2. Check InquiryPartition (dict of dicts) if present
    inquiry_partition = None
    if isinstance(raw_data, dict) and "result" in raw_data and isinstance(raw_data["result"], dict):
        cibil_data_node = raw_data["result"].get("cibilData")
        if isinstance(cibil_data_node, dict):
            success_node = cibil_data_node.get("GetCustomerAssetsResponse", {}).get("GetCustomerAssetsSuccess", {})
            if success_node:
                asset_node = success_node.get("Asset", {})
                tl_report_node = asset_node.get("TrueLinkCreditReport", {})
                inquiry_partition = tl_report_node.get("InquiryPartition")

    # If we have inquiries, compute counts
    if inquiries_list or inquiry_partition:
        # Determine reference date
        ref_dt = datetime.utcnow()
        creation_date_str = ""
        if isinstance(raw_data, dict) and "result" in raw_data and isinstance(raw_data["result"], dict):
            cibil_data_node = raw_data["result"].get("cibilData")
            if isinstance(cibil_data_node, dict):
                success_node = cibil_data_node.get("GetCustomerAssetsResponse", {}).get("GetCustomerAssetsSuccess", {})
                if success_node:
                    creation_date_str = success_node.get("Asset", {}).get("CreationDate") or ""
        
        if creation_date_str:
            parsed_ref = _parse_date(creation_date_str.split("T")[0])
            if parsed_ref:
                ref_dt = parsed_ref
        
        l6m_count = 0
        l3m_count = 0
        l3m_secured = 0
        l3m_unsecured = 0
        if inquiry_partition and isinstance(inquiry_partition, dict):
            for key, val in inquiry_partition.items():
                if isinstance(val, dict):
                    if "Inquiry" in val and isinstance(val["Inquiry"], dict):
                        inq = val["Inquiry"]
                    else:
                        inq = val
                    if isinstance(inq, dict):
                        inq_date_str = inq.get("inquiryDate") or ""
                        if inq_date_str:
                            inq_dt = _parse_date(inq_date_str)
                            if inq_dt:
                                days_diff = (ref_dt - inq_dt).days
                                if 0 <= days_diff <= 180:
                                    l6m_count += 1
                                if 0 <= days_diff <= 90:
                                    l3m_count += 1
                                    purpose = str(inq.get("inquiryPurpose") or "").strip()
                                    if _is_secured_inquiry(purpose):
                                        l3m_secured += 1
                                    else:
                                        l3m_unsecured += 1
        else:
            for inq in inquiries_list:
                if isinstance(inq, dict):
                    inq_date_str = inq.get("dateOfInquiry") or inq.get("inquiryDate") or inq.get("date") or inq.get("date_opened") or ""
                    if inq_date_str:
                         inq_dt = _parse_date(inq_date_str)
                         if inq_dt:
                             days_diff = (ref_dt - inq_dt).days
                             if 0 <= days_diff <= 180:
                                 l6m_count += 1
                             if 0 <= days_diff <= 90:
                                 l3m_count += 1
                                 purpose = str(inq.get("inquiryPurpose") or inq.get("purpose") or inq.get("InquiryPurpose") or "").strip()
                                 if _is_secured_inquiry(purpose):
                                     l3m_secured += 1
                                 else:
                                     l3m_unsecured += 1
        
        # Override the metrics with computed figures
        metrics["enquiries_l6m"] = l6m_count
        metrics["enquiries_l3m"] = l3m_count
        metrics["enquiries_l3m_secured"] = l3m_secured
        metrics["enquiries_l3m_unsecured"] = l3m_unsecured
        logger.info(f"[NORMALIZE] Overrode enquiries_l6m with calculated value: {l6m_count}")

    # Extract tips if provided
    tips = data.get("tips", data.get("recommendations", data.get("suggestions", [])))
    if not isinstance(tips, list) or not tips:
        tips = _generate_tips_from_metrics(metrics, score)

    # Extract PDF URL
    pdf_url = None
    for key in ["pdf_url", "pdfUrl", "report_pdf", "pdf", "htmlUrl", "result_pdf"]:
        val = data.get(key) or raw_data.get(key)
        
        # Check inside result wrapper if present (Experian Digitap puts it here)
        if not val and isinstance(raw_data.get("result"), dict):
            val = raw_data["result"].get(key)
            
        if val and isinstance(val, str) and val.startswith("http"):
            pdf_url = val
            break

    # General parser fallbacks for gender, address, email, DOB, and age
    gender = data.get("gender", data.get("Gender", "-"))
    dob = data.get("date_of_birth", data.get("dateOfBirth", data.get("dob", "-")))
    if dob == "-" and "BirthDate" in data:
        bd = data["BirthDate"]
        if isinstance(bd, dict):
            day = bd.get("day")
            month = bd.get("month")
            year = bd.get("year")
            if day and month and year:
                try:
                    dob = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                except Exception:
                    pass

    age = data.get("age", data.get("Age", "-"))
    if age == "-" and dob != "-":
        try:
            birth_date = datetime.strptime(dob, "%Y-%m-%d")
            ref_dt = datetime.utcnow()
            age = ref_dt.year - birth_date.year - ((ref_dt.month, ref_dt.day) < (birth_date.month, birth_date.day))
        except Exception:
            pass

    address = data.get("address", data.get("Address", data.get("borrower_address", "-")))
    if address == "-" and "BorrowerAddress" in data:
        ba = data["BorrowerAddress"]
        if isinstance(ba, dict):
            # Check nested keys first
            best_addr = None
            latest_date = ""
            for k, v in ba.items():
                if isinstance(v, dict):
                    caddr = v.get("CreditAddress", {})
                    if isinstance(caddr, dict) and caddr.get("StreetAddress"):
                        dt = v.get("dateReported") or ""
                        if not best_addr or (dt and dt > latest_date):
                            best_addr = caddr.get("StreetAddress")
                            latest_date = dt
            if best_addr:
                address = best_addr
            else:
                credit_addr = ba.get("CreditAddress", {})
                if isinstance(credit_addr, dict):
                    address = credit_addr.get("StreetAddress") or "-"

    # Fallback for Experian CAIS_Account_DETAILS -> CAIS_Holder_Address_Details
    if address == "-":
        accounts_raw = data.get("accounts", data.get("account_details", data.get("credit_accounts",
                       data.get("tradeLines", data.get("AccountDetails", [])))))
        if not accounts_raw and "CAIS_Account" in data and isinstance(data["CAIS_Account"], dict):
            accounts_raw = data["CAIS_Account"].get("CAIS_Account_DETAILS", [])
        
        if isinstance(accounts_raw, list) and accounts_raw:
            for acc in accounts_raw:
                if isinstance(acc, dict) and "CAIS_Holder_Address_Details" in acc:
                    h_addrs = acc["CAIS_Holder_Address_Details"]
                    if isinstance(h_addrs, list) and h_addrs:
                        h_addr = h_addrs[0]
                        if isinstance(h_addr, dict):
                            addr_parts = []
                            for line in ["First_Line_Of_Address_non_normalized", "Second_Line_Of_Address_non_normalized", 
                                         "Third_Line_Of_Address_non_normalized", "City_non_normalized", 
                                         "Fifth_Line_Of_Address_non_normalized", "ZIP_Postal_Code_non_normalized"]:
                                val = h_addr.get(line)
                                if val and str(val).strip():
                                    addr_parts.append(str(val).strip())
                            if addr_parts:
                                address = ", ".join(addr_parts)
                                break

    email = data.get("email", data.get("Email", data.get("email_id", "-")))
    if email == "-" and "EmailAddress" in data:
        email_node = data["EmailAddress"]
        if isinstance(email_node, dict):
            if "1" in email_node and isinstance(email_node["1"], dict):
                email = email_node["1"].get("Email") or "-"
            if email == "-":
                for k, v in email_node.items():
                    if isinstance(v, dict) and v.get("Email"):
                        email = v.get("Email")
                        break

    # Experian email extraction from CAIS accounts
    if email == "-":
        accounts_raw = data.get("accounts", data.get("account_details", data.get("credit_accounts",
                       data.get("tradeLines", data.get("AccountDetails", [])))))
        if not accounts_raw and "CAIS_Account" in data and isinstance(data["CAIS_Account"], dict):
            accounts_raw = data["CAIS_Account"].get("CAIS_Account_DETAILS", [])
        
        if isinstance(accounts_raw, list) and accounts_raw:
            for acc in accounts_raw:
                if isinstance(acc, dict):
                    # Try phone details first
                    ph_details = acc.get("CAIS_Holder_Phone_Details", [])
                    if isinstance(ph_details, list) and ph_details:
                        for ph in ph_details:
                             if isinstance(ph, dict) and ph.get("EMailId"):
                                 email = ph.get("EMailId")
                                 break
                    if email != "-":
                        break
                    # Try ID details
                    id_details = acc.get("CAIS_Holder_ID_Details", [])
                    if isinstance(id_details, list) and id_details:
                        for id_d in id_details:
                             if isinstance(id_d, dict) and id_d.get("EMailId"):
                                 email = id_d.get("EMailId")
                                 break
                    if email != "-":
                        break

    # Extract employment type
    employment_type = data.get("employment_type", data.get("employmentType", "-"))
    if employment_type == "-":
        # Check Employer in data
        employer_node = data.get("Employer", {})
        if isinstance(employer_node, dict):
            employment_type = employer_node.get("OccupationCode", {}).get("description") or "-"
        elif isinstance(employer_node, list) and employer_node:
            first_emp = employer_node[0]
            if isinstance(first_emp, dict):
                employment_type = first_emp.get("OccupationCode", {}).get("description") or "-"
                
    if employment_type and isinstance(employment_type, str):
        et_lower = employment_type.lower()
        if "self" in et_lower:
            employment_type = "Self Employed"
        elif "salaried" in et_lower or "salary" in et_lower:
            employment_type = "Salaried"

    return {
        "score": score,
        "band": band,
        "pan": report_pan,
        "name": report_name,
        "phone": phone,
        "date_of_birth": dob,
        "age": age,
        "gender": gender,
        "address": address,
        "email": email,
        "employment_type": employment_type,
        "metrics": metrics,
        "accounts": accounts,
        "tips": tips,
        "pdf_url": pdf_url,
        "fetched_at": fetched_at or datetime.utcnow().isoformat()
    }


def _parse_date(date_str: str) -> Optional[datetime]:
    """Safely parse date in formats like YYYY-MM-DD, YYYY-MM-DD+HH:MM, YYYY/MM/DD, YYYYMMDD, etc."""
    if not date_str:
        return None
    # Remove timezone offset if present (+ or - after the year-month-day)
    clean_str = str(date_str).strip()
    if len(clean_str) > 10:
        if '+' in clean_str[10:]:
            clean_str = clean_str[:10 + clean_str[10:].index('+')]
        elif '-' in clean_str[10:]:
            clean_str = clean_str[:10 + clean_str[10:].index('-')]
    
    # Try different formats
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(clean_str[:10].strip(), fmt)
        except ValueError:
            continue
    return None


def _safe_int(val) -> int:
    """Safely convert a value to int."""
    if val is None:
        return 0
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return 0


def _add_months(sourcedate: datetime, months: int) -> datetime:
    """Add months to a datetime object, handling calendar month rollover."""
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return datetime(year, month, day, sourcedate.hour, sourcedate.minute, sourcedate.second)


def _generate_tips_from_metrics(metrics: Dict[str, Any], score: int) -> list:
    """Generate actionable tips from credit metrics."""
    tips = []
    utilization = metrics.get("credit_utilization_pct", 0)
    payment_pct = metrics.get("payment_on_time_pct", 100)
    enquiries = metrics.get("enquiries_l6m", 0)
    defaults = metrics.get("defaults", 0)
    write_offs = metrics.get("write_offs", 0)
    secured = metrics.get("secured_loans_count", 0)

    if utilization > 30:
        tips.append("Your credit card utilization is above the recommended 30%. Try paying off outstanding card balances to lower it.")
    if enquiries > 2:
        tips.append("You have multiple credit inquiries in the last 6 months. Avoid applying for new credit lines consecutively to protect your score.")
    if payment_pct < 95:
        tips.append("Missed or late payments are hurting your score. Set up auto-debit payments for your loan EMIs and credit cards.")
    if defaults > 0 or write_offs > 0:
        tips.append("Unresolved defaults/past-due accounts are flag markers on your report. Contact your lenders to resolve settlements and get a No Due Certificate (NDC).")
    if secured == 0:
        tips.append("Your credit profile lacks secured loans. Adding a secured credit line (like a gold loan or secure FD-backed card) will improve your credit mix.")
    
    if not tips:
        tips.append("Great job! Your credit habits are healthy. Keep utilization low and continue making timely payments to maintain this excellent score.")
    
    return tips
