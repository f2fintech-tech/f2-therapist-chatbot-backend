import zipfile
import xml.etree.ElementTree as ET
import re
import os
import io

def generate_cam_xlsx(report_data: dict, user_email: str) -> bytes:
    """
    Generates a CAM Excel report based on the standard CAM REPORT FORMAT.xlsx template.
    Populates user profile fields and dynamic account lists using pure OpenXML manipulation.
    """
    # 1. Resolve path to template file
    utils_dir = os.path.dirname(os.path.abspath(__file__)) # src/utils
    src_dir = os.path.dirname(utils_dir) # src
    backend_dir = os.path.dirname(src_dir) # f2-therapist-chatbot-backend
    workspace_dir = os.path.dirname(backend_dir) # FinHeal-Friend
    excel_path = os.path.join(workspace_dir, "f2-therapist-chatbot-frontend", "attached_assets", "CAM_format", "CAM_REPORT_FORMAT.xlsx")

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"CAM Excel template not found at: {excel_path}")

    # Register main OpenXML namespace and all common namespaces globally
    # This ensures prefixes like mc, r, and xr are preserved on write
    namespaces = {
        '': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
        'x14ac': 'http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac',
        'xr': 'http://schemas.microsoft.com/office/spreadsheetml/2014/revision',
        'xr2': 'http://schemas.microsoft.com/office/spreadsheetml/2015/revision2',
        'xr3': 'http://schemas.microsoft.com/office/spreadsheetml/2016/revision3',
    }
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    main_ns = namespaces['']
    ns = {'ns': main_ns}

    # 2. Extract CIBIL variables
    customer_name = report_data.get("name") or "-"
    gender = report_data.get("gender") or "-"
    mobile = report_data.get("phone") or "-"
    cibil_score = report_data.get("score") or 0
    dob = report_data.get("date_of_birth") or "-"
    if dob != "-":
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', dob)
        if match:
            year, month, day = match.groups()
            dob = f"{day}/{month}/{year}"

    age = report_data.get("age") or "-"
    address = report_data.get("address") or "-"
    
    email = report_data.get("email") or user_email or "-"
    if any(pat in email.lower() for pat in ["admin@", "advisor@", "employee@", "f2finheal"]):
        email = "-"
    
    # Filter active loans
    accounts = []
    for acc in report_data.get("accounts", []):
        is_act = acc.get("is_active")
        if is_act is True or str(is_act).lower() == 'true':
            accounts.append(acc)

    # Sort active loans by sanctioned amount descending
    accounts.sort(key=lambda x: float(x.get("sanctioned_amount") or 0), reverse=True)
    num_accounts = len(accounts)
    
    # The template has 5 slots for accounts (rows 2 to 6).
    # If there are more than 5 accounts, we need to insert rows.
    shift_amt = max(0, num_accounts - 5)

    # Calculate Secured and Unsecured Caps
    secured_keywords = ["home", "housing", "car", "auto", "gold", "property", "secured", "lap", "vehicle"]
    secured_cap = 0
    unsecured_cap = 0
    total_emi = 0
    
    lenders = []
    for acc in accounts:
        sanction = float(acc.get("sanctioned_amount") or 0)
        acc_type = str(acc.get("type") or "").lower()
        is_secured = any(kw in acc_type for kw in secured_keywords)
        
        if is_secured:
            secured_cap += sanction
        else:
            unsecured_cap += sanction
            
        emi = float(acc.get("emi") or 0)
        total_emi += emi
        
        lender_name = acc.get("lender")
        if lender_name:
            lenders.append(str(lender_name))

    lenders_joined = " | ".join(lenders) if lenders else "-"

    # 3. Read template and compile dynamic sheet1.xml
    bytes_io = io.BytesIO()
    
    with zipfile.ZipFile(excel_path, 'r') as zin:
        with zipfile.ZipFile(bytes_io, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == 'xl/calcChain.xml':
                    # Omit calcChain to force Excel to recalculate and rebuild chain on load
                    continue

                file_bytes = zin.read(item.filename)
                
                if item.filename == 'xl/worksheets/sheet1.xml':
                    root = ET.fromstring(file_bytes)
                    
                    # A. Update dimensions
                    dim_elem = root.find('ns:dimension', ns)
                    if dim_elem is not None:
                        ref_val = dim_elem.attrib.get('ref', '')
                        match = re.match(r'([A-Z0-9]+):([A-Z]+)([0-9]+)', ref_val)
                        if match:
                            start, col_letter, max_row_str = match.groups()
                            new_max_row = int(max_row_str) + shift_amt
                            dim_elem.set('ref', f"{start}:{col_letter}{new_max_row}")

                    # B. Fetch sheetData and perform row shifting/insertions
                    sheet_data = root.find('ns:sheetData', ns)
                    if sheet_data is None:
                        raise ValueError("sheetData element not found in worksheet XML")

                    orig_rows = list(sheet_data.findall('ns:row', ns))
                    existing_rows_by_num = {}
                    for r_elem in orig_rows:
                        r_num = int(r_elem.attrib.get('r', 1))
                        existing_rows_by_num[r_num] = r_elem
                        sheet_data.remove(r_elem)

                    new_rows_dict = {}
                    
                    # Rows 1 to 6 remain untouched in terms of row index
                    for r in range(1, 7):
                        if r in existing_rows_by_num:
                            new_rows_dict[r] = existing_rows_by_num[r]

                    # Insert new rows if shift_amt > 0
                    base_row_elem = existing_rows_by_num.get(6)
                    for i in range(shift_amt):
                        new_r_num = 7 + i
                        if base_row_elem is not None:
                            new_row_str = ET.tostring(base_row_elem)
                            new_row_elem = ET.fromstring(new_row_str)
                            new_row_elem.set('r', str(new_r_num))
                            # Reset cells inside new row to target row index
                            for c in new_row_elem.findall('ns:c', ns):
                                ref = c.attrib.get('r', '')
                                match = re.match(r'([A-Z]+)([0-9]+)', ref)
                                if match:
                                    col_letter = match.group(1)
                                    c.set('r', f"{col_letter}{new_r_num}")
                            new_rows_dict[new_r_num] = new_row_elem
                        else:
                            new_row_elem = ET.Element(f'{{{main_ns}}}row')
                            new_row_elem.set('r', str(new_r_num))
                            new_rows_dict[new_r_num] = new_row_elem

                    # Shift subsequent original rows (7 and above)
                    max_original_row = max(existing_rows_by_num.keys()) if existing_rows_by_num else 64
                    for orig_r in range(7, max_original_row + 1):
                        if orig_r in existing_rows_by_num:
                            orig_elem = existing_rows_by_num[orig_r]
                            new_r_num = orig_r + shift_amt
                            orig_elem.set('r', str(new_r_num))
                            
                            for c in orig_elem.findall('ns:c', ns):
                                ref = c.attrib.get('r', '')
                                match = re.match(r'([A-Z]+)([0-9]+)', ref)
                                if match:
                                    col_letter = match.group(1)
                                    c.set('r', f"{col_letter}{new_r_num}")
                                    
                                # Shift formulas referencing ranges
                                f_elem = c.find('ns:f', ns)
                                if f_elem is not None and f_elem.text:
                                    orig_f = f_elem.text
                                    # Update formulas summing ranges dynamically: e.g. SUM(G2:G6) -> SUM(G2:G8)
                                    updated_f = re.sub(r'([A-Z])6\b', r'\g<1>' + str(6 + shift_amt), orig_f)
                                    if orig_f != updated_f:
                                        f_elem.text = updated_f
                                        
                            new_rows_dict[new_r_num] = orig_elem

                    # C. Populate profile data (Column B) - dynamically shifted by shift_amt for rows 7+
                    _set_cell_text(new_rows_dict[2], f"B2", customer_name, ns, main_ns)
                    _set_cell_text(new_rows_dict[4], f"B4", gender, ns, main_ns)
                    _set_cell_text(new_rows_dict[5], f"B5", "-", ns, main_ns)          # Marital Status
                    _set_cell_text(new_rows_dict[6], f"B6", "-", ns, main_ns)          # Mother Name
                    
                    _set_cell_text(new_rows_dict[7 + shift_amt], f"B{7 + shift_amt}", "-", ns, main_ns)          # Father Name
                    _set_cell_text(new_rows_dict[8 + shift_amt], f"B{8 + shift_amt}", "-", ns, main_ns)          # Employment Type
                    _set_cell_text(new_rows_dict[14 + shift_amt], f"B{14 + shift_amt}", dob, ns, main_ns)        # DOB
                    _set_cell_text(new_rows_dict[15 + shift_amt], f"B{15 + shift_amt}", f"{age} YEARS OLD" if age and age != '-' else "-", ns, main_ns)
                    _set_cell_text(new_rows_dict[16 + shift_amt], f"B{16 + shift_amt}", mobile, ns, main_ns)
                    _set_cell_text(new_rows_dict[17 + shift_amt], f"B{17 + shift_amt}", email, ns, main_ns)
                    _set_cell_text(new_rows_dict[19 + shift_amt], f"B{19 + shift_amt}", address, ns, main_ns)    # Current Address
                    _set_cell_text(new_rows_dict[22 + shift_amt], f"B{22 + shift_amt}", "-", ns, main_ns)        # Working Address
                    _set_cell_text(new_rows_dict[23 + shift_amt], f"B{23 + shift_amt}", address, ns, main_ns)    # Permanent Address
                    _set_cell_text(new_rows_dict[25 + shift_amt], f"B{25 + shift_amt}", "-", ns, main_ns)        # Profession Details
                    _set_cell_text(new_rows_dict[26 + shift_amt], f"B{26 + shift_amt}", "-", ns, main_ns)        # Highest Degree
                    _set_cell_text(new_rows_dict[27 + shift_amt], f"B{27 + shift_amt}", "-", ns, main_ns)        # Registration Year
                    _set_cell_text(new_rows_dict[28 + shift_amt], f"B{28 + shift_amt}", "-", ns, main_ns)        # Experience
                    _set_cell_text(new_rows_dict[29 + shift_amt], f"B{29 + shift_amt}", "-", ns, main_ns)        # PG Pursuing
                    _set_cell_num(new_rows_dict[32 + shift_amt], f"B{32 + shift_amt}", cibil_score, ns, main_ns)
                    
                    # Clear monthly income cells to empty them
                    _set_cell_text(new_rows_dict[9 + shift_amt], f"B{9 + shift_amt}", "-", ns, main_ns)          # Total Monthly Income
                    _set_cell_text(new_rows_dict[10 + shift_amt], f"B{10 + shift_amt}", "-", ns, main_ns)        # Monthly Salary
                    _set_cell_text(new_rows_dict[11 + shift_amt], f"B{11 + shift_amt}", "-", ns, main_ns)        # Additional Income
                    _set_cell_text(new_rows_dict[12 + shift_amt], f"B{12 + shift_amt}", "-", ns, main_ns)        # Consultancy
                    _set_cell_text(new_rows_dict[12 + shift_amt], f"F{12 + shift_amt}", "-", ns, main_ns)        # Monthly Income F12
                    _set_cell_text(new_rows_dict[13 + shift_amt], f"B{13 + shift_amt}", "-", ns, main_ns)        # ITR Details
                    
                    _set_cell_text(new_rows_dict[34 + shift_amt], f"B{34 + shift_amt}", "-", ns, main_ns)        # Average Monthly Credit
                    _set_cell_text(new_rows_dict[35 + shift_amt], f"B{35 + shift_amt}", f"{num_accounts} | LOANS", ns, main_ns)
                    _set_cell_text(new_rows_dict[36 + shift_amt], f"B{36 + shift_amt}", lenders_joined, ns, main_ns)
                    _set_cell_num(new_rows_dict[37 + shift_amt], f"B{37 + shift_amt}", int(total_emi), ns, main_ns)
                    _set_cell_text(new_rows_dict[38 + shift_amt], f"B{38 + shift_amt}", "-", ns, main_ns)        # ABB Last 6 Month
                    _set_cell_text(new_rows_dict[39 + shift_amt], f"B{39 + shift_amt}", "-", ns, main_ns)        # Total Bouncing
                    _set_cell_text(new_rows_dict[40 + shift_amt], f"B{40 + shift_amt}", "-", ns, main_ns)        # Enquiry 3M
                    _set_cell_num(new_rows_dict[41 + shift_amt], f"B{41 + shift_amt}", report_data.get("metrics", {}).get("enquiries_l6m", 0), ns, main_ns)

                    # D. Populate tradelines columns (E to K) - overwrite up to 5 slots to clear dummy loans
                    for idx in range(max(5, num_accounts)):
                        row_num = 2 + idx
                        row_elem = new_rows_dict.get(row_num)
                        if row_elem is not None:
                            if idx < num_accounts:
                                acc = accounts[idx]
                                _set_cell_text(row_elem, f"E{row_num}", acc.get("type") or "-", ns, main_ns)
                                _set_cell_text(row_elem, f"F{row_num}", acc.get("lender") or "-", ns, main_ns)
                                _set_cell_num(row_elem, f"G{row_num}", int(float(acc.get("sanctioned_amount") or 0)), ns, main_ns)
                                _set_cell_num(row_elem, f"H{row_num}", int(float(acc.get("outstanding_balance") or 0)), ns, main_ns)
                                _set_cell_num(row_elem, f"I{row_num}", int(float(acc.get("emi") or 0)), ns, main_ns)
                                _set_cell_text(row_elem, f"J{row_num}", acc.get("open_date") or "-", ns, main_ns)
                                _set_cell_text(row_elem, f"K{row_num}", "-", ns, main_ns)
                            else:
                                # Clear any template sample data in remaining slots
                                for col in ["E", "F", "G", "H", "I", "J", "K"]:
                                    _set_cell_text(row_elem, f"{col}{row_num}", "-", ns, main_ns)

                    # E. Fill totals row (now row 10 + shift_amt)
                    tot_row_num = 10 + shift_amt
                    totals_row = new_rows_dict.get(tot_row_num)
                    if totals_row is not None:
                        _set_cell_num(totals_row, f"F{tot_row_num}", num_accounts, ns, main_ns)
                        _set_cell_num(totals_row, f"G{tot_row_num}", sum(int(float(a.get("sanctioned_amount") or 0)) for a in accounts), ns, main_ns)
                        _set_cell_num(totals_row, f"H{tot_row_num}", sum(int(float(a.get("outstanding_balance") or 0)) for a in accounts), ns, main_ns)
                        _set_cell_num(totals_row, f"I{tot_row_num}", int(total_emi), ns, main_ns)

                    # F. Populate other indicators in the shifted rows
                    # EXISTING EMI (originally row 14, now row 14 + shift_amt)
                    emi_row_num = 14 + shift_amt
                    emi_row = new_rows_dict.get(emi_row_num)
                    if emi_row is not None:
                        _set_cell_num(emi_row, f"F{emi_row_num}", int(total_emi), ns, main_ns)

                    # SECURED CAP (originally row 15, now row 15 + shift_amt)
                    sec_row_num = 15 + shift_amt
                    sec_row = new_rows_dict.get(sec_row_num)
                    if sec_row is not None:
                        _set_cell_num(sec_row, f"F{sec_row_num}", int(secured_cap), ns, main_ns)

                    # UNSECURED CAP (originally row 16, now row 16 + shift_amt)
                    unsec_row_num = 16 + shift_amt
                    unsec_row = new_rows_dict.get(unsec_row_num)
                    if unsec_row is not None:
                        _set_cell_num(unsec_row, f"F{unsec_row_num}", int(unsecured_cap), ns, main_ns)

                    # Clear/Blank out all fabricated bank statement cells
                    # 1. Row 20-29 columns F to K (Historical balance sheets)
                    for r in range(20, 30):
                        r_num = r + shift_amt
                        r_elem = new_rows_dict.get(r_num)
                        if r_elem is not None:
                            for col in ["F", "G", "H", "I", "J", "K"]:
                                _set_cell_text(r_elem, f"{col}{r_num}", "-", ns, main_ns)
                    
                    # 2. Row 33 column F (AVERAGE MONTHLY CREDIT)
                    r_num_33 = 33 + shift_amt
                    r_elem_33 = new_rows_dict.get(r_num_33)
                    if r_elem_33 is not None:
                        _set_cell_text(r_elem_33, f"F{r_num_33}", "-", ns, main_ns)
                        
                    # 3. Row 37-41 columns F and G (Bounce data)
                    for r in range(37, 42):
                        r_num = r + shift_amt
                        r_elem = new_rows_dict.get(r_num)
                        if r_elem is not None:
                            for col in ["F", "G"]:
                                _set_cell_text(r_elem, f"{col}{r_num}", "-", ns, main_ns)

                    # Ensure cells in each row are sorted alphabetically by column index (A, B, C, ...)
                    # to prevent Excel parsing errors (XML validation failures)
                    for r_elem in new_rows_dict.values():
                        _sort_row_cells(r_elem, ns)

                    # Re-append all sorted rows back to sheetData
                    for r_num in sorted(new_rows_dict.keys()):
                        sheet_data.append(new_rows_dict[r_num])

                    # Re-serialize worksheet to XML
                    file_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)

                    # Inject missing namespace definitions referenced in mc:Ignorable string
                    missing_decls = []
                    if b'xmlns:x14ac=' not in file_bytes:
                        missing_decls.append(b'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac"')
                    if b'xmlns:xr2=' not in file_bytes:
                        missing_decls.append(b'xmlns:xr2="http://schemas.microsoft.com/office/spreadsheetml/2015/revision2"')
                    if b'xmlns:xr3=' not in file_bytes:
                        missing_decls.append(b'xmlns:xr3="http://schemas.microsoft.com/office/spreadsheetml/2016/revision3"')

                    if missing_decls:
                        decls_str = b' ' + b' '.join(missing_decls)
                        file_bytes = file_bytes.replace(b'<worksheet', b'<worksheet' + decls_str, 1)

                zout.writestr(item, file_bytes)
                
    return bytes_io.getvalue()

def _sort_row_cells(row_elem, ns):
    cells = list(row_elem.findall('ns:c', ns))
    for c in cells:
        row_elem.remove(c)
    
    def col_key(c_elem):
        ref = c_elem.attrib.get('r', '')
        match = re.match(r'([A-Z]+)', ref)
        if match:
            col_str = match.group(1)
            val = 0
            for char in col_str:
                val = val * 26 + (ord(char) - ord('A') + 1)
            return val
        return 0

    cells.sort(key=col_key)
    for c in cells:
        row_elem.append(c)

def _set_cell_text(row_elem, cell_ref, text, ns, main_ns):
    c = _get_or_create_cell(row_elem, cell_ref, ns, main_ns)
    
    # Remove any existing is or v elements inside cell
    for child in list(c):
        if child.tag in [f'{{{main_ns}}}is', f'{{{main_ns}}}v', f'ns:is', f'ns:v']:
            c.remove(child)

    if text is None or text == "" or text == "-":
        c.attrib.pop('t', None)
    else:
        c.set('t', 'inlineStr')
        is_elem = ET.Element(f'{{{main_ns}}}is')
        t_elem = ET.Element(f'{{{main_ns}}}t')
        t_elem.text = str(text)
        is_elem.append(t_elem)
        c.append(is_elem)

def _set_cell_num(row_elem, cell_ref, number, ns, main_ns):
    c = _get_or_create_cell(row_elem, cell_ref, ns, main_ns)
    c.attrib.pop('t', None)
    
    # Remove any existing is or v elements inside cell
    for child in list(c):
        if child.tag in [f'{{{main_ns}}}is', f'{{{main_ns}}}v', f'ns:is', f'ns:v']:
            c.remove(child)

    if number is not None and number != "" and number != "-":
        v_elem = ET.Element(f'{{{main_ns}}}v')
        v_elem.text = str(number)
        c.append(v_elem)

def _get_or_create_cell(row_elem, cell_ref, ns, main_ns):
    for c in row_elem.findall('ns:c', ns):
        if c.attrib.get('r') == cell_ref:
            return c
    c = ET.Element(f'{{{main_ns}}}c')
    c.set('r', cell_ref)
    row_elem.append(c)
    return c
