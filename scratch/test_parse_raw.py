import json
import os
import sys
from datetime import datetime

# Mimic the extraction logic
def test_extraction(raw_bureau_json):
    actual_data = raw_bureau_json
    for wrapper_key in ["data", "result", "report", "response", "cibil_data", "credit_report"]:
        if wrapper_key in raw_bureau_json and isinstance(raw_bureau_json[wrapper_key], dict) and raw_bureau_json[wrapper_key]:
            actual_data = raw_bureau_json[wrapper_key]
            break

    cibil_data = actual_data.get("cibilData")
    success_node = cibil_data.get("GetCustomerAssetsResponse", {}).get("GetCustomerAssetsSuccess", {})
    asset = success_node.get("Asset", {})
    tl_report = asset.get("TrueLinkCreditReport", {})
    borrower = tl_report.get("Borrower", {})

    # Extract gender
    gender = borrower.get("Gender") or "-"

    # Extract address
    address = "-"
    addr_node = borrower.get("BorrowerAddress", {})
    if isinstance(addr_node, dict):
        credit_addr = addr_node.get("CreditAddress", {})
        if isinstance(credit_addr, dict):
            address = credit_addr.get("StreetAddress") or "-"

    # Extract DOB and Age
    dob = "-"
    age = "-"
    birth_node = borrower.get("Birth", {})
    if isinstance(birth_node, dict):
        dob_raw = birth_node.get("date") or ""
        if dob_raw:
            dob = dob_raw.split("+")[0].strip()  # "YYYY-MM-DD"
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
                # Fix reference date to 2026 to match local sandbox
                ref_dt = datetime(2026, 6, 15)
                age = ref_dt.year - birth_date.year - ((ref_dt.month, ref_dt.day) < (birth_date.month, birth_date.day))
            except Exception as e:
                print("Age parse error:", e)
                pass

    # Extract email
    email = "-"
    email_node = borrower.get("BorrowerEmail", {})
    if isinstance(email_node, dict):
        email = email_node.get("EmailAddress") or "-"
    elif isinstance(email_node, list) and email_node:
        email = email_node[0].get("EmailAddress") or "-"
    
    if email == "-":
        email_val = borrower.get("email") or borrower.get("Email")
        if isinstance(email_val, list) and email_val:
            email = email_val[0].get("emailAddress") or email_val[0].get("EmailAddress") or "-"
        elif isinstance(email_val, str):
            email = email_val

    print(f"Extracted DOB: {dob}")
    print(f"Calculated Age: {age}")
    print(f"Extracted Gender: {gender}")
    print(f"Extracted Address: {address}")
    print(f"Extracted Email: {email}")

# Load raw response
with open(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\_last_cibil_raw_response.json", "r") as f:
    raw_data = json.load(f)

test_extraction(raw_data)
