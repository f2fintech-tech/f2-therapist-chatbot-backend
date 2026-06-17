import os
import sys
import xml.etree.ElementTree as ET
import zipfile

backend_dir = r"d:\FinHeal-Friend\f2-therapist-chatbot-backend"
sys.path.append(backend_dir)

from src.utils.cam_generator import generate_cam_xlsx

# Setup mock accounts
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

import tempfile
excel_bytes = generate_cam_xlsx(report_data, "test_email@example.com")
out_path = os.path.join(tempfile.gettempdir(), "verify_generated_cam_new.xlsx")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "wb") as f:
    f.write(excel_bytes)
print(f"Generated report at: {out_path}")

# Check with 7 accounts, shift_amt = 2 (7 - 5)
shift_amt = 2

# Inspect sheet1.xml in zip
with zipfile.ZipFile(out_path, "r") as z:
    sheet1_xml = z.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet1_xml)
    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    
    # We want to check specific cells:
    # 1. FOIR (%) cell originally F13 -> F15
    # 2. Bank name in Current Address originally E19 -> E21
    # 3. Monthly Credit counts originally F32-K32 -> F34-K34
    # 4. TVR Status and Date originally B53, C53 (now static at B53, C53)
    # 5. Income head amounts originally F54-F59 -> F56-F61
    
    target_cells = [
        f"F{13 + shift_amt}",
        f"E{19 + shift_amt}",
        *[f"{col}{32 + shift_amt}" for col in ["F", "G", "H", "I", "J", "K"]],
        f"B{53}",
        f"C{53}",
        *[f"F{r + shift_amt}" for r in range(54, 60)]
    ]
    
    # Also add some check cells to verify static/shifted layout
    check_cells = {
        "B2": "Test CAM Customer",   # Name (static)
        "B16": "9988775544",         # Mobile (static)
        "E23": "5th",                # ABB daily balance (originally E21, shifted to E23)
        "E24": "10th",               # ABB daily balance (originally E22, shifted to E24)
        "E30": "ABB",                # ABB header (originally E28, shifted to E30)
    }
    
    # We also need to search the sharedStrings.xml since cells might refer to shared strings by index!
    sst_content = z.read("xl/sharedStrings.xml")
    sst_root = ET.fromstring(sst_content)
    shared_strings = [t.text for t in sst_root.findall('.//ns:t', ns)]
    
    print("\n--- Inspecting Cells in Generated Excel XML ---")
    cells_found = {}
    for row in root.findall('.//ns:row', ns):
        for c in row.findall('.//ns:c', ns):
            ref = c.attrib.get('r', '')
            if ref in target_cells:
                xml_str = ET.tostring(c).decode('utf-8')
                print(f"Cell {ref}: {xml_str}")
                cells_found[ref] = c
            elif ref in check_cells:
                t = c.attrib.get('t', '')
                val = ""
                v_elem = c.find('ns:v', ns)
                is_elem = c.find('ns:is', ns)
                if is_elem is not None:
                    t_elem = is_elem.find('ns:t', ns)
                    if t_elem is not None:
                        val = t_elem.text
                elif v_elem is not None:
                    if t == 's':
                        val = shared_strings[int(v_elem.text)]
                    else:
                        val = v_elem.text
                print(f"Check Cell {ref}: value='{val}' (Expected: '{check_cells[ref]}')")
                if val != check_cells[ref]:
                    print(f"ERROR: Check Cell {ref} mismatch!")
                    all_ok = False

    print("\n--- Summary Verification Results ---")
    all_ok = True
    for cell_ref in target_cells:
        if cell_ref not in cells_found:
            # Cell is omitted entirely from XML, which is perfectly blank/empty in Excel!
            print(f"Cell {cell_ref}: OK (Omitted from XML - completely blank)")
        else:
            c = cells_found[cell_ref]
            t_attrib = c.attrib.get('t')
            v_elem = c.find('ns:v', ns)
            is_elem = c.find('ns:is', ns)
            if t_attrib is None and v_elem is None and is_elem is None:
                print(f"Cell {cell_ref}: OK (Present but empty - completely blank)")
            else:
                print(f"Cell {cell_ref}: FAILED (t={t_attrib}, v={v_elem is not None}, is={is_elem is not None})")
                all_ok = False
                
    if all_ok:
        print("\nVerification SUCCESS! All target dummy cells are verified as completely blank.")
        # Print table definition contents from generated file
        print("\n--- Inspecting Table XMLs in Generated Excel File ---")
        print("table1.xml:")
        print(z.read("xl/tables/table1.xml").decode("utf-8"))
        print("\ntable2.xml:")
        print(z.read("xl/tables/table2.xml").decode("utf-8"))
    else:
        print("\nVerification FAILED! Some dummy cells are not empty.")


