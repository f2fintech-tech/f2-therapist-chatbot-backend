import os
import sys
import xml.etree.ElementTree as ET
import zipfile

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

excel_bytes = generate_cam_xlsx(report_data, "test_email@example.com")
import tempfile
out_path = os.path.join(tempfile.gettempdir(), "verify_generated_cam_new.xlsx")
with open(out_path, "wb") as f:
    f.write(excel_bytes)

with zipfile.ZipFile(out_path, "r") as z:
    xml_content = z.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(xml_content)
    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    
    sst_content = z.read("xl/sharedStrings.xml")
    sst_root = ET.fromstring(sst_content)
    shared_strings = [t.text for t in sst_root.findall('.//ns:t', ns)]
    
    print("--- Inspecting generated rows 18 to 40 ---")
    for row in root.findall('.//ns:row', ns):
        r_num = int(row.attrib.get('r', 0))
        if 18 <= r_num <= 40:
            cells_info = []
            for c in row.findall('.//ns:c', ns):
                ref = c.attrib.get('r', '')
                t = c.attrib.get('t', '')
                val = ""
                v_elem = c.find('ns:v', ns)
                if v_elem is not None:
                    if t == 's':
                        val = shared_strings[int(v_elem.text)]
                    else:
                        val = v_elem.text
                
                f_elem = c.find('ns:f', ns)
                formula_str = f" f='{f_elem.text}'" if f_elem is not None else ""
                cells_info.append(f"{ref}: '{val}'{formula_str}")
            print(f"Row {r_num}: {', '.join(cells_info)}")




