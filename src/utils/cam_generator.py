import zipfile
import xml.etree.ElementTree as ET
import re
import os
import io

# CAM generator — v2025-06-25 (direct range formulas, no Table refs)
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

    # Look in backend's static assets (production package)
    excel_path = os.path.join(src_dir, "static", "CAM_format", "CAM_REPORT_FORMAT.xlsx")
    if not os.path.exists(excel_path):
        # Fallback to local development sibling path
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
        
    employment_type = report_data.get("employment_type") or "-"
    
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

    # Pre-compute key row anchors used in both sheet1.xml and table1.xml processing:
    #   Loan data rows span 2..last_data_row  (= 6 + shift_amt = num_accounts + 1)
    #   Totals row is always at tot_row_num   (= 10 + shift_amt)
    last_data_row = 6 + shift_amt
    tot_row_num   = 10 + shift_amt

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

                    # A. Update dimensions
                    dim_elem = root.find('ns:dimension', ns)
                    if dim_elem is not None:
                        new_max_row = (max(existing_rows_by_num.keys()) if existing_rows_by_num else 64) + shift_amt + 5
                        dim_elem.set('ref', f"A1:M{new_max_row}")

                    # A1. Update column widths to shift table to Column E
                    cols_elem = root.find('ns:cols', ns)
                    if cols_elem is not None:
                        cols_elem.clear()
                        col_specs = [
                            (1, 1, 45.6640625, 1),
                            (2, 2, 39.33203125, 1),
                            (3, 3, 46, 1),
                            (4, 4, 3, 1),
                            (5, 5, 18, 1),
                            (6, 12, 19.5546875, 1),
                            (13, 13, 15, 1),
                        ]
                        for c_min, c_max, c_width, c_cust in col_specs:
                            col_el = ET.Element(f'{{{main_ns}}}col')
                            col_el.set('min', str(c_min))
                            col_el.set('max', str(c_max))
                            col_el.set('width', str(c_width))
                            col_el.set('customWidth', str(c_cust))
                            cols_elem.append(col_el)

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
                        
                        # Map shifted columns to original template columns E to K
                        template_col_map = {
                            'E': 'E', # Ownership -> TRADELINES
                            'F': 'E', # TRADELINES -> TRADELINES
                            'G': 'F', # MEMBER NAME -> MEMBER NAME
                            'H': 'G', # SANCTION AMOUNT -> SANCTION AMOUNT
                            'I': 'H', # CURRENT BALANCE -> CURRENT BALANCE
                            'J': 'I', # EMI AMOUNT -> EMI AMOUNT
                            'K': 'J', # START -> START
                            'L': 'K', # Tenure -> CLOSED
                            'M': 'K', # Ending Date -> CLOSED
                        }
                        t_col = template_col_map.get(col, col)
                        return template_styles.get((t_col, style_row))

                    new_rows_dict = {}

                    max_original_row = max(existing_rows_by_num.keys()) if existing_rows_by_num else 64
                    max_new_row = max_original_row + shift_amt + 5

                    for R in range(1, max_new_row + 1):
                        base_r = None
                        if R == 1:
                            # Keep row 1 completely unchanged
                            if 1 in existing_rows_by_num:
                                base_r = ET.fromstring(ET.tostring(existing_rows_by_num[1]))
                            else:
                                base_r = ET.Element(f'{{{main_ns}}}row')
                                base_r.set('r', '1')
                            
                            # Write headers in row 1 (E1 to M1)
                            # Copy the header style of E1 if available
                            header_style = None
                            c_e1 = _get_or_create_cell(base_r, "E1", ns, main_ns)
                            if c_e1 is not None:
                                header_style = c_e1.attrib.get('s')
                            
                            _set_cell_text(base_r, "E1", "OWNERSHIP", ns, main_ns, header_style)
                            _set_cell_text(base_r, "F1", "TRADELINES", ns, main_ns, header_style)
                            _set_cell_text(base_r, "G1", "MEMBER NAME", ns, main_ns, header_style)
                            _set_cell_text(base_r, "H1", "SANCTION AMOUNT", ns, main_ns, header_style)
                            _set_cell_text(base_r, "I1", "CURRENT BALANCE", ns, main_ns, header_style)
                            _set_cell_text(base_r, "J1", "EMI AMOUNT", ns, main_ns, header_style)
                            _set_cell_text(base_r, "K1", "START", ns, main_ns, header_style)
                            _set_cell_text(base_r, "L1", "Tenure(in months)", ns, main_ns, header_style)
                            _set_cell_text(base_r, "M1", "Ending Date", ns, main_ns, header_style)
                            
                            new_rows_dict[1] = base_r
                            continue

                        # Determine target row indices to copy from original template.
                        # A-D (static panel) index:
                        if R < 32:
                            orig_ad_r = R
                        elif R == 32:
                            orig_ad_r = None
                        elif R < 42:
                            orig_ad_r = R - 1
                        elif R in [42, 43]:
                            orig_ad_r = None
                        else:
                            orig_ad_r = R - 3
                        
                        # E and beyond (shifted table/formulas) index:
                        orig_ez_r = None
                        if R > 6 + shift_amt:
                            if R < 11 + shift_amt:
                                orig_ez_r = R - shift_amt
                            elif R in [11 + shift_amt, 12 + shift_amt]:
                                orig_ez_r = None
                            elif R < 32:
                                orig_ez_r = R - shift_amt - 2
                            elif R == 32:
                                orig_ez_r = None
                            elif R < 42:
                                orig_ez_r = R - shift_amt - 3
                            elif R in [42, 43]:
                                orig_ez_r = None
                            else:
                                orig_ez_r = R - shift_amt - 5

                        if orig_ad_r is not None and orig_ad_r <= max_original_row and orig_ad_r in existing_rows_by_num:
                            # Start with original row orig_ad_r
                            base_r = ET.fromstring(ET.tostring(existing_rows_by_num[orig_ad_r]))
                            base_r.set('r', str(R))
                            # Remove columns E and beyond, as they will be remapped
                            for c in list(base_r.findall('ns:c', ns)):
                                ref = c.attrib.get('r', '')
                                col = _get_column_letter(ref)
                                if col not in ['A', 'B', 'C', 'D']:
                                    base_r.remove(c)
                                else:
                                    # Update cell ref row coordinate to R
                                    c.set('r', f"{col}{R}")
                        elif orig_ez_r is not None and orig_ez_r in existing_rows_by_num:
                            # Start with original row orig_ez_r (preserves columns E-Z layout/height)
                            base_r = ET.fromstring(ET.tostring(existing_rows_by_num[orig_ez_r]))
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

                        # If R == 32, it's the new PAN row. Let's initialize A32 and B32 and copy styles from original row 32
                        if R == 32:
                            style_a = None
                            style_b = None
                            if 32 in existing_rows_by_num:
                                orig_32 = existing_rows_by_num[32]
                                for c in orig_32.findall('ns:c', ns):
                                    ref = c.attrib.get('r', '')
                                    if ref.startswith('A'):
                                        style_a = c.attrib.get('s')
                                    elif ref.startswith('B'):
                                        style_b = c.attrib.get('s')
                            
                            _set_cell_text(base_r, "A32", "PAN", ns, main_ns, style_a)
                            _set_cell_text(base_r, "B32", report_data.get("pan") or "-", ns, main_ns, style_b)

                        # Populate columns E and beyond
                        # Case A: Accounts rows (2 <= R <= 6 + shift_amt)
                        if 2 <= R <= 6 + shift_amt:
                            idx = R - 2
                            if idx < num_accounts:
                                acc = accounts[idx]
                                _set_cell_text(base_r, f"E{R}", acc.get("ownership") or "Individual", ns, main_ns, get_acc_style("E", R))
                                _set_cell_text(base_r, f"F{R}", acc.get("type") or "-", ns, main_ns, get_acc_style("F", R))
                                _set_cell_text(base_r, f"G{R}", acc.get("lender") or "-", ns, main_ns, get_acc_style("G", R))
                                _set_cell_num(base_r, f"H{R}", int(float(acc.get("sanctioned_amount") or 0)), ns, main_ns, get_acc_style("H", R))
                                _set_cell_num(base_r, f"I{R}", int(float(acc.get("outstanding_balance") or 0)), ns, main_ns, get_acc_style("I", R))
                                _set_cell_num(base_r, f"J{R}", int(float(acc.get("emi") or 0)), ns, main_ns, get_acc_style("J", R))
                                _set_cell_text(base_r, f"K{R}", acc.get("open_date") or "-", ns, main_ns, get_acc_style("K", R))
                                tenure_val = acc.get("tenure_months")
                                tenure_str = str(tenure_val) if tenure_val is not None else "-"
                                _set_cell_text(base_r, f"L{R}", tenure_str, ns, main_ns, get_acc_style("L", R))
                                _set_cell_text(base_r, f"M{R}", acc.get("end_date") or "-", ns, main_ns, get_acc_style("M", R))
                            elif R <= 6:
                                # Clear padding template slots
                                for col in ["E", "F", "G", "H", "I", "J", "K", "L", "M"]:
                                    _set_cell_text(base_r, f"{col}{R}", "-", ns, main_ns, get_acc_style(col, R))

                        # Case B: Shifted template cells (R > 6 + shift_amt)
                        else:
                            if orig_ez_r is not None and orig_ez_r in existing_rows_by_num:
                                orig_row_elem = existing_rows_by_num[orig_ez_r]
                                for c in orig_row_elem.findall('ns:c', ns):
                                    ref = c.attrib.get('r', '')
                                    col = _get_column_letter(ref)
                                    if col not in ['A', 'B', 'C', 'D']:
                                        if orig_ez_r in [12, 13, 14, 15, 16] and col in ['E', 'F']:
                                            continue
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
                    _set_cell_text(new_rows_dict[8], f"B8", employment_type, ns, main_ns) # Employment Type
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
                    # Row 32 is PAN (written during R loop)
                    _set_cell_num(new_rows_dict[33], f"B33", cibil_score, ns, main_ns) # CIBIL Score shifted to 33
                    
                    # Restore B9 SUM formula and clear sub-income cells to blank
                    _set_cell_formula(new_rows_dict[9], f"B9", "SUM(B10:B12)", ns, main_ns)  # Total Monthly Income = sum of sub-items
                    _set_cell_text(new_rows_dict[10], f"B10", "", ns, main_ns)        # Monthly Salary (user fills)
                    _set_cell_text(new_rows_dict[11], f"B11", "", ns, main_ns)        # Additional Income (user fills)
                    _set_cell_text(new_rows_dict[12], f"B12", "", ns, main_ns)        # Consultancy (user fills)
                    _set_cell_text(new_rows_dict[13], f"B13", "", ns, main_ns)        # ITR Details (user fills)
                    
                    # B35 = Average Monthly Credit — reference the ABB average row dynamically
                    avg_monthly_credit_row = 30 + shift_amt
                    _set_cell_formula(new_rows_dict[35], f"B35", f"F{avg_monthly_credit_row}", ns, main_ns)

                    # Sidebar summary formulas (B36/B37/B38)
                    # Direct cell ranges over 2..last_data_row (defined at function scope above).
                    _set_cell_formula(new_rows_dict[36], "B36",
                        f"COUNTA(G2:G{last_data_row})&\" | LOANS\"", ns, main_ns)
                    _set_cell_formula(new_rows_dict[37], "B37",
                        f"_xlfn.TEXTJOIN(\" | \",TRUE,G2:G{last_data_row})", ns, main_ns)
                    _set_cell_formula(new_rows_dict[38], "B38",
                        f"SUM(J2:J{last_data_row})", ns, main_ns)

                    _set_cell_text(new_rows_dict[39], f"B39", "-", ns, main_ns)        # ABB Last 6 Month (shifted to 39)
                    _set_cell_text(new_rows_dict[40], f"B40", "-", ns, main_ns)        # Total Bouncing (shifted to 40)
                    
                    # Helper to extract cell style
                    def _get_cell_style(row_elem, cell_ref, ns_dict):
                        for c in row_elem.findall('ns:c', ns_dict):
                            if c.attrib.get('r') == cell_ref:
                                return c.attrib.get('s')
                        return None
                    
                    # Enquiry rows — all written to column B, aligned with the template A/B layout.
                    # Row 41: Total enquiries (last 3 months) — value in B41
                    _set_cell_num(new_rows_dict[41], f"B41",
                        report_data.get("metrics", {}).get("enquiries_l3m", 0), ns, main_ns)

                    # Borrow style from row 41 for sub-rows
                    style_enq_a = _get_cell_style(new_rows_dict[41], "A41", ns)
                    style_enq_b = _get_cell_style(new_rows_dict[41], "B41", ns)

                    # Row 42: Secured enquiries sub-row (indented label, value in B)
                    _set_cell_text(new_rows_dict[42], "A42", "Secured Enquiries",   ns, main_ns, style_enq_a)
                    _set_cell_num (new_rows_dict[42], "B42",
                        report_data.get("metrics", {}).get("enquiries_l3m_secured",   0), ns, main_ns, style_enq_b)

                    # Row 43: Unsecured enquiries sub-row
                    _set_cell_text(new_rows_dict[43], "A43", "Unsecured Enquiries", ns, main_ns, style_enq_a)
                    _set_cell_num (new_rows_dict[43], "B43",
                        report_data.get("metrics", {}).get("enquiries_l3m_unsecured", 0), ns, main_ns, style_enq_b)

                    # Row 44: Total enquiries (last 6 months) — value in B44
                    _set_cell_num(new_rows_dict[44], f"B44",
                        report_data.get("metrics", {}).get("enquiries_l6m", 0), ns, main_ns)

                    # D. Tradelines are already populated in Case A above (lines 319-337).
                    # No duplicate block needed here.

                    # E. Fill totals row and secured/unsecured sub-rows
                    # tot_row_num and last_data_row are computed at function scope (before zip loop).
                    totals_row = new_rows_dict.get(tot_row_num)
                    if totals_row is not None:
                        style_f = _get_cell_style(totals_row, f"E{tot_row_num}", ns)
                        style_g = _get_cell_style(totals_row, f"F{tot_row_num}", ns)
                        style_h = _get_cell_style(totals_row, f"G{tot_row_num}", ns)
                        style_i = _get_cell_style(totals_row, f"H{tot_row_num}", ns)
                        style_j = _get_cell_style(totals_row, f"I{tot_row_num}", ns)

                        # Grand-total row — direct SUM/COUNTA over the data range
                        _set_cell_text(totals_row, f"E{tot_row_num}", "TOTAL", ns, main_ns, style_f)
                        # F{tot_row_num}: explicitly blank to clear any #REF! from shifted template formula
                        _set_cell_text(totals_row, f"F{tot_row_num}", "", ns, main_ns, style_g)
                        _set_cell_formula(totals_row, f"G{tot_row_num}",
                            f"COUNTA(G2:G{last_data_row})", ns, main_ns, style_g)
                        _set_cell_formula(totals_row, f"H{tot_row_num}",
                            f"SUM(H2:H{last_data_row})", ns, main_ns, style_h)
                        _set_cell_formula(totals_row, f"I{tot_row_num}",
                            f"SUM(I2:I{last_data_row})", ns, main_ns, style_i)
                        _set_cell_formula(totals_row, f"J{tot_row_num}",
                            f"SUM(J2:J{last_data_row})", ns, main_ns, style_j)

                        # Secured loans summary row
                        # SUMPRODUCT+ISNUMBER(SEARCH) for OR matching across secured keywords.
                        # F column = TRADELINES (loan type), so we search F2:F{last_data_row}.
                        sec_search_parts = "+".join(
                            f'ISNUMBER(SEARCH("{kw}",F2:F{last_data_row}))'
                            for kw in secured_keywords
                        )
                        sec_match_expr = f"({sec_search_parts})>0"

                        sec_row_idx = tot_row_num + 1
                        sec_tot_row = new_rows_dict.get(sec_row_idx)
                        if sec_tot_row is not None:
                            _set_cell_text(sec_tot_row, f"E{sec_row_idx}", "Secured", ns, main_ns, style_f)
                            _set_cell_text(sec_tot_row, f"F{sec_row_idx}", "", ns, main_ns, style_g)  # blank F
                            _set_cell_formula(sec_tot_row, f"G{sec_row_idx}",
                                f"SUMPRODUCT(({sec_match_expr})*1)",
                                ns, main_ns, style_g)
                            _set_cell_formula(sec_tot_row, f"H{sec_row_idx}",
                                f"SUMPRODUCT(({sec_match_expr})*H2:H{last_data_row})",
                                ns, main_ns, style_h)
                            _set_cell_formula(sec_tot_row, f"I{sec_row_idx}",
                                f"SUMPRODUCT(({sec_match_expr})*I2:I{last_data_row})",
                                ns, main_ns, style_i)
                            _set_cell_formula(sec_tot_row, f"J{sec_row_idx}",
                                f"SUMPRODUCT(({sec_match_expr})*J2:J{last_data_row})",
                                ns, main_ns, style_j)

                        # Unsecured loans summary row — Grand Total minus Secured
                        unsec_row_idx = tot_row_num + 2
                        unsec_tot_row = new_rows_dict.get(unsec_row_idx)
                        if unsec_tot_row is not None:
                            _set_cell_text(unsec_tot_row, f"E{unsec_row_idx}", "Unsecured", ns, main_ns, style_f)
                            _set_cell_text(unsec_tot_row, f"F{unsec_row_idx}", "", ns, main_ns, style_g)  # blank F
                            _set_cell_formula(unsec_tot_row, f"G{unsec_row_idx}",
                                f"G{tot_row_num}-G{sec_row_idx}", ns, main_ns, style_g)
                            _set_cell_formula(unsec_tot_row, f"H{unsec_row_idx}",
                                f"H{tot_row_num}-H{sec_row_idx}", ns, main_ns, style_h)
                            _set_cell_formula(unsec_tot_row, f"I{unsec_row_idx}",
                                f"I{tot_row_num}-I{sec_row_idx}", ns, main_ns, style_i)
                            _set_cell_formula(unsec_tot_row, f"J{unsec_row_idx}",
                                f"J{tot_row_num}-J{sec_row_idx}", ns, main_ns, style_j)

                    # F. Populate other indicators in the shifted rows
                    # Write the FOIR table values and formulas explicitly in Columns F and G
                    inc_row_num = 14 + shift_amt
                    foir_row_num = 15 + shift_amt
                    emi_row_num = 16 + shift_amt
                    sec_row_num = 17 + shift_amt
                    unsec_row_num = 18 + shift_amt

                    # Monthly Income
                    inc_row = new_rows_dict.get(inc_row_num)
                    if inc_row is not None:
                        _set_cell_text(inc_row, f"F{inc_row_num}", "MONTHLY INCOME", ns, main_ns)
                        _set_cell_formula(inc_row, f"G{inc_row_num}", "B9", ns, main_ns)

                    # FOIR (%)
                    foir_row = new_rows_dict.get(foir_row_num)
                    if foir_row is not None:
                        _set_cell_text(foir_row, f"F{foir_row_num}", "FOIR (%)", ns, main_ns)
                        _set_cell_formula(foir_row, f"G{foir_row_num}", f"IF(G{inc_row_num}<50000,50%,IF(G{inc_row_num}<=100000,60%,70%))", ns, main_ns)

                    # Existing EMI — reference the grand-total EMI cell (SUM of J column)
                    # tot_row_num is already defined above in section E
                    emi_row = new_rows_dict.get(emi_row_num)
                    if emi_row is not None:
                        _set_cell_text(emi_row, f"F{emi_row_num}", "EXISTING EMI", ns, main_ns)
                        _set_cell_formula(emi_row, f"G{emi_row_num}",
                            f"J{tot_row_num}", ns, main_ns)

                    # Secured Cap
                    sec_row = new_rows_dict.get(sec_row_num)
                    if sec_row is not None:
                        _set_cell_text(sec_row, f"F{sec_row_num}", "SECURED CAP", ns, main_ns)
                        _set_cell_formula(sec_row, f"G{sec_row_num}", f"((G{inc_row_num}*G{foir_row_num})-G{emi_row_num})*100", ns, main_ns)

                    # Unsecured Cap
                    unsec_row = new_rows_dict.get(unsec_row_num)
                    if unsec_row is not None:
                        _set_cell_text(unsec_row, f"F{unsec_row_num}", "UNSECURED CAP", ns, main_ns)
                        _set_cell_formula(unsec_row, f"G{unsec_row_num}", f"G{sec_row_num}/2", ns, main_ns)

                    # Clear/Blank out all template sample values from the Banking table
                    # And write E column labels
                    
                    # First clear banking header row (dates row: orig row 20, maps to 22+shift_amt)
                    banking_header_row_num = 22 + shift_amt
                    banking_header_row = new_rows_dict.get(banking_header_row_num)
                    if banking_header_row is not None:
                        for col in ["F", "G", "H", "I", "J", "K"]:
                            _set_cell_text(banking_header_row, f"{col}{banking_header_row_num}", "-", ns, main_ns)

                    banking_labels = ["5th", "10th", "15th", "20th", "25th", "30th"]
                    for idx, label in enumerate(banking_labels):
                        r_num = 23 + shift_amt + idx
                        r_elem = new_rows_dict.get(r_num)
                        if r_elem is not None:
                            _set_cell_text(r_elem, f"E{r_num}", label, ns, main_ns)
                            for col in ["F", "G", "H", "I", "J", "K"]:
                                _set_cell_text(r_elem, f"{col}{r_num}", "-", ns, main_ns)
                                
                    # ABB row: 29+shift_amt
                    r_num_29 = 29 + shift_amt
                    r_elem_29 = new_rows_dict.get(r_num_29)
                    if r_elem_29 is not None:
                        _set_cell_text(r_elem_29, f"E{r_num_29}", "ABB", ns, main_ns)
                        for col in ["F", "G", "H", "I", "J", "K"]:
                            formula = f"IFERROR(AVERAGE({col}{23+shift_amt}:{col}{28+shift_amt}),\"Banking Missing\")"
                            _set_cell_formula(r_elem_29, f"{col}{r_num_29}", formula, ns, main_ns)

                    # Average monthly balance cell across all months: 30+shift_amt
                    r_num_30 = 30 + shift_amt
                    r_elem_30 = new_rows_dict.get(r_num_30)
                    if r_elem_30 is not None:
                        _set_cell_text(r_elem_30, f"E{r_num_30}", "Average Monthly Credit", ns, main_ns)
                        formula = f"IFERROR(AVERAGE(F{29+shift_amt}:K{29+shift_amt}),\"Banking Not Provided\")"
                        _set_cell_formula(r_elem_30, f"F{r_num_30}", formula, ns, main_ns)
                    
                    # 2. Row 33 column F (AVERAGE MONTHLY CREDIT) maps to Row 36 + shift_amt in output
                    r_num_36 = 36 + shift_amt
                    r_elem_36 = new_rows_dict.get(r_num_36)
                    if r_elem_36 is not None:
                        _set_cell_text(r_elem_36, f"F{r_num_36}", "-", ns, main_ns)
                        
                    # 3. Bounce data (originally rows 37-41) maps to:
                    # [40 + shift_amt, 41 + shift_amt, 44 + shift_amt, 45 + shift_amt, 46 + shift_amt]
                    for r_num in [40 + shift_amt, 41 + shift_amt, 44 + shift_amt, 45 + shift_amt, 46 + shift_amt]:
                        r_elem = new_rows_dict.get(r_num)
                        if r_elem is not None:
                            for col in ["F", "G"]:
                                _set_cell_text(r_elem, f"{col}{r_num}", "-", ns, main_ns)

                    # 4. FOIR (%) cell (originally F13, now F15 + shift_amt) -> we do NOT overwrite it!

                    # 5. Bank name in Current Address row (originally E19, now E21 + shift_amt)
                    bank_row_num = 21 + shift_amt
                    bank_row = new_rows_dict.get(bank_row_num)
                    if bank_row is not None:
                        _set_cell_text(bank_row, f"E{bank_row_num}", "-", ns, main_ns)

                    # 6. Monthly Credit Report dummy '0' counts (originally F32-K32, now F35-K35 + shift_amt)
                    credit_row_num = 35 + shift_amt
                    credit_row = new_rows_dict.get(credit_row_num)
                    if credit_row is not None:
                        for col in ["F", "G", "H", "I", "J", "K"]:
                             _set_cell_text(credit_row, f"{col}{credit_row_num}", "-", ns, main_ns)

                    # 7. TVR Status and Date details (originally B53 and C53, now static B56 and C56)
                    _set_cell_text(new_rows_dict[56], f"B56", "-", ns, main_ns)
                    _set_cell_text(new_rows_dict[56], f"C56", "-", ns, main_ns)

                    # 8. Income Head Amount dummy values (originally F54-F59, now F59-F64 + shift_amt)
                    for r in range(54, 60):
                        r_num = r + shift_amt + 5
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
                    # Update table reference range to span header + all loan data rows only.
                    # Do NOT include totals row in table ref — let sheet formulas handle totals
                    # independently. This avoids the double-definition XML conflict that corrupts
                    # table1.xml when both totalsRowFunction and sheet cell formulas exist.
                    root.set('ref', f"E1:M{last_data_row}")
                    root.attrib.pop('totalsRowCount', None)  # Remove totals row from table
                    root.attrib.pop('headerRowShown', None)

                    # Update autoFilter to match new data range
                    af_elem = root.find(f'{{{main_ns}}}autoFilter') or root.find('autoFilter')
                    if af_elem is not None:
                        af_elem.set('ref', f"E1:M{last_data_row}")

                    tc_elem = root.find(f'{{{main_ns}}}tableColumns') or root.find('tableColumns')
                    if tc_elem is not None:
                        tc_elem.clear()
                        tc_elem.set('count', '9')
                        # No totalsRowFunction — sheet formulas handle totals independently
                        cols_def = [
                            ("OWNERSHIP", 1),
                            ("TRADELINES", 2),
                            ("MEMBER NAME", 3),
                            ("SANCTION AMOUNT", 4),
                            ("CURRENT BALANCE", 5),
                            ("EMI AMOUNT", 6),
                            ("START", 7),
                            ("Tenure(in months)", 8),
                            ("Ending Date", 9),
                        ]
                        for name_str, col_id in cols_def:
                            col_el = ET.Element(f'{{{main_ns}}}tableColumn')
                            col_el.set('id', str(col_id))
                            col_el.set('name', name_str)
                            tc_elem.append(col_el)

                    tsi_elem = root.find(f'{{{main_ns}}}tableStyleInfo') or root.find('tableStyleInfo')
                    if tsi_elem is not None:
                        # TableStyleMedium9 = blue header row + banded data rows (built-in Excel style)
                        tsi_elem.set('name', 'TableStyleMedium9')
                        tsi_elem.set('showFirstColumn', '0')
                        tsi_elem.set('showLastColumn', '0')
                        tsi_elem.set('showRowStripes', '1')
                        tsi_elem.set('showColumnStripes', '0')
                    elif root is not None:
                        # Create tableStyleInfo if missing
                        tsi_elem = ET.SubElement(root, f'{{{main_ns}}}tableStyleInfo')
                        tsi_elem.set('name', 'TableStyleMedium9')
                        tsi_elem.set('showFirstColumn', '0')
                        tsi_elem.set('showLastColumn', '0')
                        tsi_elem.set('showRowStripes', '1')
                        tsi_elem.set('showColumnStripes', '0')

                    file_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                elif item.filename == 'xl/tables/table2.xml':
                    root = ET.fromstring(file_bytes)
                    new_ref = f"E{50 + shift_amt}:F{56 + shift_amt}"
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
    if not formula_text:
        return formula_text
    
    def repl(match):
        col = match.group(1)
        row_str = match.group(2)
        r = int(row_str)
        if col in ['A', 'B', 'C', 'D']:
            if r >= 32:
                return f"{col}{r + 1}"
            return f"{col}{r}"
        
        # Columns E-Z shift dynamically based on their original row position:
        if r <= 5:
            return f"{col}{r}"
        elif r <= 10:
            return f"{col}{r + shift_amt}"
        elif r < 30:
            return f"{col}{r + shift_amt + 2}"
        elif r < 39:
            return f"{col}{r + shift_amt + 3}"
        else:
            return f"{col}{r + shift_amt + 5}"

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

def _set_cell_formula(row_elem, cell_ref, formula_text, ns, main_ns, style_id=None):
    c = _get_or_create_cell(row_elem, cell_ref, ns, main_ns, style_id)
    c.attrib.pop('t', None)
    
    # Remove any existing is or v or f elements inside cell
    for child in list(c):
        if child.tag.endswith('}is') or child.tag == 'is' or child.tag.endswith('}v') or child.tag == 'v' or child.tag.endswith('}f') or child.tag == 'f':
            c.remove(child)

    if formula_text:
        f_elem = ET.Element(f'{{{main_ns}}}f')
        f_elem.text = formula_text
        c.append(f_elem)

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
