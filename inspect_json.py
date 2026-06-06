import json

def inspect():
    with open("_last_cibil_raw_response.json", "r") as f:
        data = json.load(f)
    
    try:
        cibil_data = data["result"]["cibilData"]
    except KeyError:
        print("Could not find result.cibilData"); return
    
    success_node = cibil_data.get("GetCustomerAssetsResponse", {}).get("GetCustomerAssetsSuccess", {})
    asset = success_node.get("Asset", {})
    tl_report = asset.get("TrueLinkCreditReport", {})
    trade_partition = tl_report.get("TradeLinePartition", {})
    
    ACCOUNT_TYPES = {
        "01": "Auto Loan",
        "02": "Housing Loan",
        "03": "Property Loan",
        "04": "Loan Against Shares or Securities",
        "05": "Credit Card",
        "06": "Consumer Loan",
        "07": "Gold Loan",
        "08": "Education Loan",
        "09": "Professional Loan",
        "10": "Credit Card",
        "12": "Overdraft",
        "18": "Professional Loan",
        "31": "Business Loan",
        "37": "Professional Loan",
        "38": "Professional Loan",
        "51": "Business Loan",
        "61": "Business Loan",
    }
    
    open_accounts = []
    closed_accounts = []
    
    for k, part_val in trade_partition.items():
        tradeline = part_val.get("Tradeline", {})
        lender = tradeline.get("creditorName", "Unknown")
        symbol = part_val.get("accountTypeSymbol", "")
        acc_type = ACCOUNT_TYPES.get(symbol, part_val.get("accountTypeDescription") or f"Other({symbol})")
        is_active = "dateClosed" not in tradeline or not tradeline["dateClosed"]
        date_closed = tradeline.get("dateClosed", "N/A")
        current_balance = tradeline.get("currentBalance", 0)
        
        entry = {
            "lender": lender,
            "type": acc_type,
            "symbol": symbol,
            "is_active": is_active,
            "date_closed": date_closed,
            "balance": current_balance
        }
        
        if is_active:
            open_accounts.append(entry)
        else:
            closed_accounts.append(entry)
    
    print(f"\n=== OPEN ACCOUNTS ({len(open_accounts)}) ===")
    for acc in open_accounts:
        print(f"  [{acc['symbol']}] {acc['type']:30} | {acc['lender']:25} | Balance: {acc['balance']}")
    
    print(f"\n=== CLOSED ACCOUNTS ({len(closed_accounts)}) ===")
    for acc in closed_accounts:
        print(f"  [{acc['symbol']}] {acc['type']:30} | {acc['lender']:25} | Closed: {acc['date_closed']}")
    
    # Summary by category (open only)
    print(f"\n=== OPEN ACCOUNTS BY CATEGORY ===")
    categories = {}
    for acc in open_accounts:
        t = acc['type']
        # Normalize categories
        if "Credit Card" in t:
            cat = "Credit Card"
        elif "Business Loan" in t:
            cat = "Business Loan"
        elif "Auto Loan" in t or "Vehicle" in t or "Two Wheeler" in t:
            cat = "Auto Loan"
        elif "Personal Loan" in t:
            cat = "Personal Loan"
        elif "Overdraft" in t:
            cat = "Overdraft"
        elif "Professional Loan" in t:
            cat = "Professional Loan"
        elif "Housing Loan" in t or "Home Loan" in t:
            cat = "Housing Loan"
        else:
            cat = t
        
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(acc)
    
    for cat, accs in categories.items():
        print(f"  {cat}: {len(accs)} account(s)")
        for a in accs:
            print(f"    - {a['lender']} (Balance: {a['balance']})")

inspect()
