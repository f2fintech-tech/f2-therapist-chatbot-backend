import zipfile
import xml.etree.ElementTree as ET
import re
import os
import tempfile

excel_path = r"d:\FinHeal-Friend\f2-therapist-chatbot-frontend\attached_assets\CAM_format\CAM_REPORT_FORMAT.xlsx"
out_path = os.path.join(tempfile.gettempdir(), 'test_cam_inserted.xlsx')

def insert_rows_test():
    print(f"Modifying template: {excel_path}")
    main_ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    ET.register_namespace('', main_ns)
    
    # Let's say we have 7 accounts (need to insert 2 rows after row 6)
    accounts = [
        {"type": "PROFESSIONAL", "lender": "CHOLA", "sanction": 1519819, "balance": 1519819, "emi": 40000, "start": "2026-03-12"},
        {"type": "BL", "lender": "HDFC", "sanction": 285907, "balance": 279991, "emi": 10000, "start": "2026-02-10"},
        {"type": "PROFESSIONAL", "lender": "BAJAJ", "sanction": 1623729, "balance": 1623729, "emi": 20000, "start": "2025-06-15"},
        {"type": "AUTO", "lender": "HDFC", "sanction": 918998, "balance": 540105, "emi": 19000, "start": "2025-01-10"},
        {"type": "EDU", "lender": "CANERA", "sanction": 6750000, "balance": 6650000, "emi": 0, "start": "2024-11-05"},
        # New extra accounts:
        {"type": "PERSONAL", "lender": "SBI", "sanction": 500000, "balance": 450000, "emi": 12000, "start": "2025-08-20"},
        {"type": "CARD", "lender": "ICICI", "sanction": 150000, "balance": 45000, "emi": 3000, "start": "2026-01-01"},
    ]
    
    num_accounts = len(accounts)
    shift_amt = max(0, num_accounts - 5)
    
    with zipfile.ZipFile(excel_path, 'r') as zin:
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                
                if item.filename == 'xl/worksheets/sheet1.xml':
                    print(f"Modifying sheet1.xml (inserting {shift_amt} rows)...")
                    root = ET.fromstring(data)
                    ns = {'ns': main_ns}
                    
                    # 1. Update dimension ref (e.g. A1:K64 -> A1:K{64 + shift_amt})
                    dim_elem = root.find('ns:dimension', ns)
                    if dim_elem is not None:
                        ref_val = dim_elem.attrib.get('ref', '')
                        match = re.match(r'([A-Z0-9]+):([A-Z]+)([0-9]+)', ref_val)
                        if match:
                            start, col_letter, max_row_str = match.groups()
                            new_max_row = int(max_row_str) + shift_amt
                            new_ref = f"{start}:{col_letter}{new_max_row}"
                            dim_elem.set('ref', new_ref)
                            print(f"Updated sheet dimension from {ref_val} to {new_ref}")
                    
                    # 2. Extract sheetData element
                    sheet_data = root.find('ns:sheetData', ns)
                    if sheet_data is None:
                        raise Exception("sheetData not found in XML")
                        
                    # Find all existing rows
                    rows = list(sheet_data.findall('ns:row', ns))
                    
                    # Group existing rows by row number
                    existing_rows_by_num = {}
                    for r_elem in rows:
                        r_num = int(r_elem.attrib.get('r', 1))
                        existing_rows_by_num[r_num] = r_elem
                        
                    # Remove all rows from sheetData so we can append them in correct sorted order
                    for r_elem in rows:
                        sheet_data.remove(r_elem)
                        
                    # Build new rows list
                    max_original_row = max(existing_rows_by_num.keys())
                    new_rows_dict = {}
                    
                    # Rows 1 to 6 stay exactly as they are in original
                    for r in range(1, 7):
                        if r in existing_rows_by_num:
                            new_rows_dict[r] = existing_rows_by_num[r]
                            
                    # Generate/insert extra rows if shift_amt > 0
                    # Rows 7 to 6+shift_amt will be copy of row 6 (or newly created rows)
                    # Let's copy row 6 structure to keep styling, styles, and heights!
                    base_row_elem = existing_rows_by_num.get(6)
                    
                    for i in range(shift_amt):
                        new_r_num = 7 + i
                        if base_row_elem is not None:
                            # Deep copy row 6 element
                            # In python, we can do ET.fromstring(ET.tostring(elem))
                            new_row_str = ET.tostring(base_row_elem)
                            new_row_elem = ET.fromstring(new_row_str)
                            new_row_elem.set('r', str(new_r_num))
                            # Update cell references inside the row
                            for c in new_row_elem.findall('ns:c', ns):
                                ref = c.attrib.get('r', '')
                                match = re.match(r'([A-Z]+)([0-9]+)', ref)
                                if match:
                                    col_letter = match.group(1)
                                    c.set('r', f"{col_letter}{new_r_num}")
                            new_rows_dict[new_r_num] = new_row_elem
                        else:
                            # Fallback create empty row
                            new_row_elem = ET.Element(f'{{{main_ns}}}row')
                            new_row_elem.set('r', str(new_r_num))
                            new_rows_dict[new_r_num] = new_row_elem
                            
                    # Shift subsequent original rows (7 and above)
                    for orig_r in range(7, max_original_row + 1):
                        if orig_r in existing_rows_by_num:
                            orig_elem = existing_rows_by_num[orig_r]
                            new_r_num = orig_r + shift_amt
                            orig_elem.set('r', str(new_r_num))
                            
                            # Shift all cells inside this row
                            for c in orig_elem.findall('ns:c', ns):
                                ref = c.attrib.get('r', '')
                                match = re.match(r'([A-Z]+)([0-9]+)', ref)
                                if match:
                                    col_letter = match.group(1)
                                    c.set('r', f"{col_letter}{new_r_num}")
                                    
                                # If cell contains a formula (like SUM of ranges), update the range if needed
                                f_elem = c.find('ns:f', ns)
                                if f_elem is not None and f_elem.text:
                                    # E.g. SUM(G2:G6) -> SUM(G2:G8) in Row 10 (now Row 12)
                                    # Let's replace G6 with G{6 + shift_amt}, H6 with H{6 + shift_amt}, I6 with I{6 + shift_amt}
                                    orig_f = f_elem.text
                                    updated_f = re.sub(r'([A-Z])6\b', r'\g<1>' + str(6 + shift_amt), orig_f)
                                    if orig_f != updated_f:
                                        print(f"Updated formula in cell {col_letter}{new_r_num} from '{orig_f}' to '{updated_f}'")
                                        f_elem.text = updated_f
                                        
                            new_rows_dict[new_r_num] = orig_elem
                            
                    # Re-append all sorted rows to sheetData
                    for r_num in sorted(new_rows_dict.keys()):
                        sheet_data.append(new_rows_dict[r_num])
                        
                    # 3. Populate all account data in the active rows
                    # Accounts go into rows 2 to 6 + shift_amt (which corresponds to E2:K{6 + shift_amt})
                    for idx, acc in enumerate(accounts):
                        row_num = 2 + idx
                        row_elem = new_rows_dict.get(row_num)
                        if row_elem is not None:
                            # Populate Column E (Account Type)
                            _set_cell_text(row_elem, f"E{row_num}", acc["type"], ns, main_ns)
                            # Populate Column F (Lender Name)
                            _set_cell_text(row_elem, f"F{row_num}", acc["lender"], ns, main_ns)
                            # Populate Column G (Sanction Amount)
                            _set_cell_num(row_elem, f"G{row_num}", acc["sanction"], ns, main_ns)
                            # Populate Column H (Current Balance)
                            _set_cell_num(row_elem, f"H{row_num}", acc["balance"], ns, main_ns)
                            # Populate Column I (EMI Amount)
                            _set_cell_num(row_elem, f"I{row_num}", acc["emi"], ns, main_ns)
                            # Populate Column J (Start Date)
                            _set_cell_text(row_elem, f"J{row_num}", acc["start"], ns, main_ns)
                            # Populate Column K (Closed Date)
                            _set_cell_text(row_elem, f"K{row_num}", "", ns, main_ns)

                    # Update Row 10 (now Row 10 + shift_amt) totals
                    # Row index for totals:
                    total_row_num = 10 + shift_amt
                    totals_row = new_rows_dict.get(total_row_num)
                    if totals_row is not None:
                        # G: Total Sanction
                        _set_cell_num(totals_row, f"G{total_row_num}", sum(a["sanction"] for a in accounts), ns, main_ns)
                        # H: Total Outstanding
                        _set_cell_num(totals_row, f"H{total_row_num}", sum(a["balance"] for a in accounts), ns, main_ns)
                        # I: Total EMI
                        _set_cell_num(totals_row, f"I{total_row_num}", sum(a["emi"] for a in accounts), ns, main_ns)
                        # F: Total Count
                        _set_cell_num(totals_row, f"F{total_row_num}", num_accounts, ns, main_ns)

                    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                    
                zout.writestr(item, data)

    print(f"Created test output workbook: {out_path}")

def _set_cell_text(row_elem, cell_ref, text, ns, main_ns):
    c = _get_or_create_cell(row_elem, cell_ref, ns, main_ns)
    c.set('t', 'inlineStr')
    v_elem = c.find('ns:v', ns)
    if v_elem is not None:
        c.remove(v_elem)
    is_elem = c.find('ns:is', ns)
    if is_elem is not None:
        c.remove(is_elem)
    is_elem = ET.Element(f'{{{main_ns}}}is')
    t_elem = ET.Element(f'{{{main_ns}}}t')
    t_elem.text = str(text)
    is_elem.append(t_elem)
    c.append(is_elem)

def _set_cell_num(row_elem, cell_ref, number, ns, main_ns):
    c = _get_or_create_cell(row_elem, cell_ref, ns, main_ns)
    c.attrib.pop('t', None)
    is_elem = c.find('ns:is', ns)
    if is_elem is not None:
        c.remove(is_elem)
    v_elem = c.find('ns:v', ns)
    if v_elem is None:
        v_elem = ET.Element(f'{{{main_ns}}}v')
        c.append(v_elem)
    v_elem.text = str(number)

def _get_or_create_cell(row_elem, cell_ref, ns, main_ns):
    for c in row_elem.findall('ns:c', ns):
        if c.attrib.get('r') == cell_ref:
            return c
    # If not found, create it
    c = ET.Element(f'{{{main_ns}}}c')
    c.set('r', cell_ref)
    row_elem.append(c)
    return c

insert_rows_test()

# Inspect output
print("\n--- Inspecting generated test Excel file ---")
import sys
sys.path.append(r"d:\FinHeal-Friend\f2-therapist-chatbot-backend\scratch")
from inspect_excel import inspect_xlsx_raw
inspect_xlsx_raw(out_path)
