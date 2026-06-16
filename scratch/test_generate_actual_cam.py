import os
import sys
import xml.etree.ElementTree as ET
import zipfile
import tempfile

# Add src to python path
backend_dir = r"d:\FinHeal-Friend\f2-therapist-chatbot-backend"
sys.path.append(backend_dir)

from src.utils.cam_generator import generate_cam_xlsx

mock_accounts = [
    {"type": "Personal Loan", "lender": "SBI", "sanctioned_amount": 500000, "outstanding_balance": 450000, "emi": 12000, "open_date": "2025-08-20", "is_active": True},
    {"type": "Credit Card", "lender": "ICICI", "sanctioned_amount": 150000, "outstanding_balance": 45000, "emi": 3000, "open_date": "2026-01-01", "is_active": True},
    {"type": "Car Loan", "lender": "HDFC", "sanctioned_amount": 918998, "outstanding_balance": 540105, "emi": 19000, "open_date": "2025-01-10", "is_active": True},
    {"type": "Education Loan", "lender": "CANERA", "sanctioned_amount": 6750000, "outstanding_balance": 6650000, "emi": 0, "open_date": "2024-11-05", "is_active": True},
    {"type": "Business Loan", "lender": "HDFC", "sanctioned_amount": 285907, "outstanding_balance": 279991, "emi": 10000, "open_date": "2026-02-10", "is_active": True},
    {"type": "Home Loan", "lender": "CHOLA", "sanctioned_amount": 1519819, "outstanding_balance": 1519819, "emi": 40000, "open_date": "2026-03-12", "is_active": True},
    {"type": "Gold Loan", "lender": "AXIS", "sanctioned_amount": 200000, "outstanding_balance": 180000, "emi": 5000, "open_date": "2025-05-15", "is_active": True},
]

report_data = {
    "score": 750,
    "band": "Excellent",
    "pan": "ABCDE1234F",
    "name": "Test CAM Customer",
    "phone": "9988775544",
    "metrics": {
        "payment_on_time_pct": 100,
        "credit_utilization_pct": 15,
        "credit_history_age_years": 4.5,
        "enquiries_l6m": 1,
        "secured_loans_count": 3,
        "unsecured_loans_count": 4,
        "write_offs": 0,
        "defaults": 0
    },
    "accounts": mock_accounts,
    "tips": ["Keep up the good work!"],
    "pdf_url": "http://example.com/report.pdf",
    "fetched_at": "2026-06-15T12:00:00Z"
}

out_path = os.path.join(tempfile.gettempdir(), "test_generated_output.xlsx")
excel_bytes = generate_cam_xlsx(report_data, "test_email@example.com")

with open(out_path, "wb") as f:
    f.write(excel_bytes)
print(f"Generated Excel report at {out_path}")

with zipfile.ZipFile(out_path, "r") as z:
    gen_sheet1_xml = z.read("xl/worksheets/sheet1.xml")

print("\n--- GENERATED SHEET1.XML (First 1500 chars) ---")
print(gen_sheet1_xml[:1500].decode('utf-8'))
