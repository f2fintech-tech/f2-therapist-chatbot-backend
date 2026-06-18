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

                    def _get_column_letter(cell_ref):
                        match = re.match(r'([A-Z]+)', cell_ref)
                        return match.group(1) if match else ''

                    # Extract template styles from columns E to K in rows 2 to 6
                    template_styles = {}
                    for r_num in [2, 3, 4, 5, 6]:
                        if r_num in existing_rows_by_num:
                            r_elem = existing_rows_by_num[r_num]
                            for c in r_elem.findall('ns:c', ns):
                                ref = c.attrib.get('r', '')
                                col = _get_column_letter(ref)
                                if col in ['E', 'F', 'G', 'H', 'I', 'J', 'K']:
                                    s_attr = c.attrib.get('s')
                                    if s_attr:
                                        template_styles[(col, r_num)] = s_attr

                    def get_acc_style(col, r_num):
                        if r_num == 2:
                            style_row = 2
                        elif r_num == 3:
                            style_row = 3
                        else:
                            style_row = 4 if r_num % 2 == 0 else 5
                        return template_styles.get((col, style_row))

                    new_rows_dict = {}

                    max_original_row = max(existing_rows_by_num.keys()) if existing_rows_by_num else 64
                    max_new_row = max_original_row + shift_amt

                    for R in range(1, max_new_row + 1):
                        base_r = None
                        if R == 1:
                            # Keep row 1 completely unchanged
                            if 1 in existing_rows_by_num:
                                base_r = ET.fromstring(ET.tostring(existing_rows_by_num[1]))
                            else:
                                base_r = ET.Element(f'{{{main_ns}}}row')
                                base_r.set('r', '1')
                            new_rows_dict[1] = base_r
                            continue

                        # Determine base row for R >= 2
                        if R <= max_original_row and R in existing_rows_by_num:
                            # Start with original row R (preserves columns A-D layout/height)
                            base_r = ET.fromstring(ET.tostring(existing_rows_by_num[R]))
                            # Remove columns E and beyond, as they will be remapped
                            for c in list(base_r.findall('ns:c', ns)):
                                ref = c.attrib.get('r', '')
                                col = _get_column_letter(ref)
                                if col not in ['A', 'B', 'C', 'D']:
                                    base_r.remove(c)
                        elif (R - shift_amt) in existing_rows_by_num:
                            # Start with original row R - shift_amt (preserves columns E-Z layout/height)
                            base_r = ET.fromstring(ET.tostring(existing_rows_by_num[R - shift_amt]))
                            base_r.set('r', str(R))
                            # Remove columns A-D, as they are not shifted to this row
                            for c in list(base_r.findall('ns:c', ns)):
                                ref = c.attrib.get('r', '')
                                col = _get_column_letter(ref)
                                if col in ['A', 'B', 'C', 'D']:
                                    base_r.remove(c)
                                else:
                                    # Update cell coordinate row index
                                    c.set('r', f"{col}{R}")
                                    
                                    # Shift formula reference inside the cell
                                    f_elem = c.find('ns:f', ns)
                                    if f_elem is not None and f_elem.text:
                                        f_elem.text = _update_formula_rows(f_elem.text, shift_amt)
                        else:
                            base_r = ET.Element(f'{{{main_ns}}}row')
                            base_r.set('r', str(R))

                        # Populate columns E and beyond
                        # Case A: Accounts rows (2 <= R <= 6 + shift_amt)
                        if 2 <= R <= 6 + shift_amt:
                            idx = R - 2
                            if idx < num_accounts:
                                acc = accounts[idx]
                                _set_cell_text(base_r, f"E{R}", acc.get("type") or "-", ns, main_ns, get_acc_style("E", R))
                                _set_cell_text(base_r, f"F{R}", acc.get("lender") or "-", ns, main_ns, get_acc_style("F", R))
                                _set_cell_num(base_r, f"G{R}", int(float(acc.get("sanctioned_amount") or 0)), ns, main_ns, get_acc_style("G", R))
                                _set_cell_num(base_r, f"H{R}", int(float(acc.get("outstanding_balance") or 0)), ns, main_ns, get_acc_style("H", R))
                                _set_cell_num(base_r, f"I{R}", int(float(acc.get("emi") or 0)), ns, main_ns, get_acc_style("I", R))
                                _set_cell_text(base_r, f"J{R}", acc.get("open_date") or "-", ns, main_ns, get_acc_style("J", R))
                                _set_cell_text(base_r, f"K{R}", "-", ns, main_ns, get_acc_style("K", R))
                            elif R <= 6:
                                # Clear padding template slots
                                for col in ["E", "F", "G", "H", "I", "J", "K"]:
                                    _set_cell_text(base_r, f"{col}{R}", "-", ns, main_ns, get_acc_style(col, R))

                        # Case B: Shifted template cells (R > 6 + shift_amt)
                        else:
                            r_orig = R - shift_amt
                            if r_orig in existing_rows_by_num:
                                orig_row_elem = existing_rows_by_num[r_orig]
                                for c in orig_row_elem.findall('ns:c', ns):
                                    ref = c.attrib.get('r', '')
                                    col = _get_column_letter(ref)
                                    if col not in ['A', 'B', 'C', 'D']:
                                        c_clone = ET.fromstring(ET.tostring(c))
                                        c_clone.set('r', f"{col}{R}")
                                        
                                        f_elem = c_clone.find('ns:f', ns)
                                        if f_elem is not None and f_elem.text:
                                            f_elem.text = _update_formula_rows(f_elem.text, shift_amt)
                                                
                                        # Deduplicate cell
                                        existing_c = None
                                        for ec in base_r.findall('ns:c', ns):
                                            if ec.attrib.get('r') == f"{col}{R}":
                                                existing_c = ec
                                                break
                                        if existing_c is not None:
                                            base_r.remove(existing_c)
                                        base_r.append(c_clone)

                        new_rows_dict[R] = base_r

                    # C. Populate profile data (Column B) - static row coordinates (non-shifting)
                    _set_cell_text(new_rows_dict[2], f"B2", customer_name, ns, main_ns)
                    _set_cell_text(new_rows_dict[4], f"B4", gender, ns, main_ns)
                    _set_cell_text(new_rows_dict[5], f"B5", "-", ns, main_ns)          # Marital Status
                    _set_cell_text(new_rows_dict[6], f"B6", "-", ns, main_ns)          # Mother Name
                    _set_cell_text(new_rows_dict[7], f"B7", "-", ns, main_ns)          # Father Name
                    _set_cell_text(new_rows_dict[8], f"B8", "-", ns, main_ns)          # Employment Type
                    _set_cell_text(new_rows_dict[14], f"B14", dob, ns, main_ns)        # DOB
                    _set_cell_text(new_rows_dict[15], f"B15", f"{age} YEARS OLD" if age and age != '-' else "-", ns, main_ns)
                    _set_cell_text(new_rows_dict[16], f"B16", mobile, ns, main_ns)
                    _set_cell_text(new_rows_dict[17], f"B17", email, ns, main_ns)
                    _set_cell_text(new_rows_dict[19], f"B19", address, ns, main_ns)    # Current Address
                    _set_cell_text(new_rows_dict[22], f"B22", "-", ns, main_ns)        # Working Address
                    _set_cell_text(new_rows_dict[23], f"B23", address, ns, main_ns)    # Permanent Address
                    _set_cell_text(new_rows_dict[25], f"B25", "-", ns, main_ns)        # Profession Details
                    _set_cell_text(new_rows_dict[26], f"B26", "-", ns, main_ns)        # Highest Degree
                    _set_cell_text(new_rows_dict[27], f"B27", "-", ns, main_ns)        # Registration Year
                    _set_cell_text(new_rows_dict[28], f"B28", "-", ns, main_ns)        # Experience
                    _set_cell_text(new_rows_dict[29], f"B29", "-", ns, main_ns)        # PG Pursuing
                    _set_cell_num(new_rows_dict[32], f"B32", cibil_score, ns, main_ns)
                    
                    # Clear monthly income cells to empty them
                    _set_cell_text(new_rows_dict[9], f"B9", "-", ns, main_ns)          # Total Monthly Income
                    _set_cell_text(new_rows_dict[10], f"B10", "-", ns, main_ns)        # Monthly Salary
                    _set_cell_text(new_rows_dict[11], f"B11", "-", ns, main_ns)        # Additional Income
                    _set_cell_text(new_rows_dict[12], f"B12", "-", ns, main_ns)        # Consultancy
                    _set_cell_text(new_rows_dict[12 + shift_amt], f"F{12 + shift_amt}", "-", ns, main_ns)        # Monthly Income F12 (shifted)
                    _set_cell_text(new_rows_dict[13], f"B13", "-", ns, main_ns)        # ITR Details
                    
                    _set_cell_text(new_rows_dict[34], f"B34", "-", ns, main_ns)        # Average Monthly Credit
                    _set_cell_text(new_rows_dict[35], f"B35", f"{num_accounts} | LOANS", ns, main_ns)
                    _set_cell_text(new_rows_dict[36], f"B36", lenders_joined, ns, main_ns)
                    _set_cell_num(new_rows_dict[37], f"B37", int(total_emi), ns, main_ns)
                    
                    # Update dynamic Excel formulas in column B to target the correct row range F2:F{6+shift_amt}
                    max_loan_row = 6 + shift_amt
                    
                    c35 = _get_or_create_cell(new_rows_dict[35], "B35", ns, main_ns)
                    f35 = c35.find('ns:f', ns)
                    if f35 is not None:
                        f35.text = f"COUNTA(F2:F{max_loan_row})&\" | LOANS\""
                    else:
                        f_elem = ET.Element(f'{{{main_ns}}}f')
                        f_elem.text = f"COUNTA(F2:F{max_loan_row})&\" | LOANS\""
                        c35.append(f_elem)

                    c36 = _get_or_create_cell(new_rows_dict[36], "B36", ns, main_ns)
                    f36 = c36.find('ns:f', ns)
                    if f36 is not None:
                        f36.text = f"_xlfn.TEXTJOIN(\" | \",TRUE,F2:F{max_loan_row})"
                    else:
                        f_elem = ET.Element(f'{{{main_ns}}}f')
                        f_elem.text = f"_xlfn.TEXTJOIN(\" | \",TRUE,F2:F{max_loan_row})"
                        c36.append(f_elem)

                    c37 = _get_or_create_cell(new_rows_dict[37], "B37", ns, main_ns)
                    f37 = c37.find('ns:f', ns)
                    if f37 is not None:
                        f37.text = f"SUM(I2:I{max_loan_row})"
                    else:
                        f_elem = ET.Element(f'{{{main_ns}}}f')
                        f_elem.text = f"SUM(I2:I{max_loan_row})"
                        c37.append(f_elem)

                    _set_cell_text(new_rows_dict[38], f"B38", "-", ns, main_ns)        # ABB Last 6 Month
                    _set_cell_text(new_rows_dict[39], f"B39", "-", ns, main_ns)        # Total Bouncing
                    _set_cell_text(new_rows_dict[40], f"B40", "-", ns, main_ns)        # Enquiry 3M
                    _set_cell_num(new_rows_dict[41], f"B41", report_data.get("metrics", {}).get("enquiries_l6m", 0), ns, main_ns)

                    # D. Populate tradelines columns (E to K) - overwrite up to 5 slots to clear dummy loans
                    for idx in range(max(5, num_accounts)):
                        row_num = 2 + idx
                        row_elem = new_rows_dict.get(row_num)
                        if row_elem is not None:
                            if idx < num_accounts:
                                acc = accounts[idx]
                                _set_cell_text(row_elem, f"E{row_num}", acc.get("type") or "-", ns, main_ns, get_acc_style("E", row_num))
                                _set_cell_text(row_elem, f"F{row_num}", acc.get("lender") or "-", ns, main_ns, get_acc_style("F", row_num))
                                _set_cell_num(row_elem, f"G{row_num}", int(float(acc.get("sanctioned_amount") or 0)), ns, main_ns, get_acc_style("G", row_num))
                                _set_cell_num(row_elem, f"H{row_num}", int(float(acc.get("outstanding_balance") or 0)), ns, main_ns, get_acc_style("H", row_num))
                                _set_cell_num(row_elem, f"I{row_num}", int(float(acc.get("emi") or 0)), ns, main_ns, get_acc_style("I", row_num))
                                _set_cell_text(row_elem, f"J{row_num}", acc.get("open_date") or "-", ns, main_ns, get_acc_style("J", row_num))
                                _set_cell_text(row_elem, f"K{row_num}", "-", ns, main_ns, get_acc_style("K", row_num))
                            else:
                                # Clear any template sample data in remaining slots
                                for col in ["E", "F", "G", "H", "I", "J", "K"]:
                                    _set_cell_text(row_elem, f"{col}{row_num}", "-", ns, main_ns, get_acc_style(col, row_num))

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

                    # 4. FOIR (%) cell (originally F13, now F13 + shift_amt)
                    foir_row_num = 13 + shift_amt
                    foir_row = new_rows_dict.get(foir_row_num)
                    if foir_row is not None:
                        _set_cell_text(foir_row, f"F{foir_row_num}", "-", ns, main_ns)

                    # 5. Bank name in Current Address row (originally E19, now E19 + shift_amt)
                    bank_row_num = 19 + shift_amt
                    bank_row = new_rows_dict.get(bank_row_num)
                    if bank_row is not None:
                        _set_cell_text(bank_row, f"E{bank_row_num}", "-", ns, main_ns)

                    # 6. Monthly Credit Report dummy '0' counts (originally F32-K32, now F32-K32 + shift_amt)
                    credit_row_num = 32 + shift_amt
                    credit_row = new_rows_dict.get(credit_row_num)
                    if credit_row is not None:
                        for col in ["F", "G", "H", "I", "J", "K"]:
                             _set_cell_text(credit_row, f"{col}{credit_row_num}", "-", ns, main_ns)

                    # 7. TVR Status and Date details (originally B53 and C53, now static)
                    _set_cell_text(new_rows_dict[53], f"B53", "-", ns, main_ns)
                    _set_cell_text(new_rows_dict[53], f"C53", "-", ns, main_ns)

                    # 8. Income Head Amount dummy values (originally F54-F59, now shifted)
                    for r in range(54, 60):
                        r_num = r + shift_amt
                        income_row = new_rows_dict.get(r_num)
                        if income_row is not None:
                            _set_cell_text(income_row, f"F{r_num}", "-", ns, main_ns)

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
                elif item.filename == 'xl/tables/table1.xml':
                    root = ET.fromstring(file_bytes)
                    root.set('ref', f"E1:K{10 + shift_amt}")
                    file_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                elif item.filename == 'xl/tables/table2.xml':
                    root = ET.fromstring(file_bytes)
                    new_ref = f"E{44 + shift_amt}:F{50 + shift_amt}"
                    root.set('ref', new_ref)
                    auto_filter = root.find('ns:autoFilter', ns)
                    if auto_filter is not None:
                        auto_filter.set('ref', new_ref)
                    file_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)

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

def _update_formula_rows(formula_text, shift_amt):
    if not formula_text or shift_amt == 0:
        return formula_text
    
    def repl(match):
        col = match.group(1)
        row_str = match.group(2)
        r = int(row_str)
        if col in ['A', 'B', 'C', 'D']:
            return f"{col}{r}"
        if r == 9:
            return f"{col}{9 + shift_amt}"
        elif r >= 10:
            return f"{col}{r + shift_amt}"
        return f"{col}{r}"

    return re.sub(r'\b([A-Z]+)([0-9]+)\b', repl, formula_text)

def _set_cell_text(row_elem, cell_ref, text, ns, main_ns, style_id=None):
    c = _get_or_create_cell(row_elem, cell_ref, ns, main_ns, style_id)
    
    # Remove any existing is or v elements inside cell
    for child in list(c):
        if child.tag.endswith('}is') or child.tag == 'is' or child.tag.endswith('}v') or child.tag == 'v':
            c.remove(child)

    if text is None or text == "" or text == "-":
        c.attrib.pop('t', None)
        # Strip formula element if setting to empty/None/"-"
        for child in list(c):
            if child.tag.endswith('}f') or child.tag == 'f':
                c.remove(child)
    else:
        c.set('t', 'inlineStr')
        is_elem = ET.Element(f'{{{main_ns}}}is')
        t_elem = ET.Element(f'{{{main_ns}}}t')
        t_elem.text = str(text)
        is_elem.append(t_elem)
        c.append(is_elem)

def _set_cell_num(row_elem, cell_ref, number, ns, main_ns, style_id=None):
    c = _get_or_create_cell(row_elem, cell_ref, ns, main_ns, style_id)
    c.attrib.pop('t', None)
    
    # Remove any existing is or v elements inside cell
    for child in list(c):
        if child.tag.endswith('}is') or child.tag == 'is' or child.tag.endswith('}v') or child.tag == 'v':
            c.remove(child)

    if number is None or number == "" or number == "-":
        # Strip formula element if setting to empty/None/"-"
        for child in list(c):
            if child.tag.endswith('}f') or child.tag == 'f':
                c.remove(child)
    else:
        v_elem = ET.Element(f'{{{main_ns}}}v')
        v_elem.text = str(number)
        c.append(v_elem)

def _get_or_create_cell(row_elem, cell_ref, ns, main_ns, style_id=None):
    for c in row_elem.findall('ns:c', ns):
        if c.attrib.get('r') == cell_ref:
            if style_id is not None:
                c.set('s', style_id)
            return c
    c = ET.Element(f'{{{main_ns}}}c')
    c.set('r', cell_ref)
    if style_id is not None:
        c.set('s', style_id)
    row_elem.append(c)
    return c
