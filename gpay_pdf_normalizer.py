import re
import pandas as pd
from datetime import datetime

def normalize_gpay_ocr_text(raw_text: str) -> pd.DataFrame:
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    records = []
    current_date = None
    current_merchant = None
    current_flow = None

    for line in lines:
        # Date
        date_match = re.search(r"\d{1,2}\s\w+\s\d{4}", line)
        if date_match:
            try:
                current_date = datetime.strptime(date_match.group(), "%d %b %Y").date()
            except:
                current_date = None
            continue

        # Paid / Received
        if "paid to" in line.lower():
            current_merchant = line.split("Paid to")[-1].strip()
            current_flow = "Expense"
            continue

        if "received from" in line.lower():
            current_merchant = line.split("Received from")[-1].strip()
            current_flow = "Income"
            continue

        # Amount
        amt_match = re.search(r"₹\s?([\d,]+\.\d{2})", line)
        if amt_match and current_date and current_merchant:
            amount = float(amt_match.group(1).replace(",", ""))

            records.append({
                "txn_id": f"GPAY_{len(records)+1}",
                "date": current_date.strftime("%d-%m-%Y"),
                "description": f"{current_flow} to/from {current_merchant}",
                "amount": amount,
                "flow": current_flow,
                "source": "GPay",
                "account": "GPay Linked Account",
                "merchant": current_merchant,
                "category": ""
            })

            current_merchant = None
            current_flow = None

    return pd.DataFrame(records)
