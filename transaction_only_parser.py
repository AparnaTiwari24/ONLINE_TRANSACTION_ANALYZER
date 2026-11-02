import re
import pandas as pd


# ------------------- FILTER RULES -------------------
SUMMARY_KEYWORDS = [
    "opening balance",
    "closing balance",
    "total deposit",
    "total withdrawal",
    "withdrawal count",
    "deposit count",
    "statement summary",
    "available balance",
    "current balance",
    "balance",
]

# only accept lines that clearly indicate a transaction
TRANSACTION_KEYWORDS = [
    "paid", "sent", "debited",
    "received", "credited", "added",
    "transferred", "transfer", "upi"
]


def is_summary_line(line: str) -> bool:
    l = line.lower()
    return any(k in l for k in SUMMARY_KEYWORDS)


def is_transaction_line(line: str) -> bool:
    l = line.lower()
    return any(k in l for k in TRANSACTION_KEYWORDS)


def extract_amount(line: str):
    """
    Extract ONLY the transaction amount from a line.
    We take the LAST amount in the line (most PDFs show it at the end).
    """
    # capture amounts like: ₹1,234.56 or 1234.56 or 1,234
    matches = re.findall(r"(?:₹\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", line)

    if not matches:
        return None

    amt_str = matches[-1]  # last number is usually the amount
    amt_str = amt_str.replace(",", "").strip()

    try:
        amt = float(amt_str)
    except:
        return None

    # ignore 0 and negative
    if amt <= 0:
        return None

    return amt


def detect_type(line: str):
    l = line.lower()
    if any(x in l for x in ["credited", "received", "added"]):
        return "Income"
    if any(x in l for x in ["debited", "paid", "sent"]):
        return "Expense"
    return "Expense"  # default


def extract_date(line: str):
    # supports: 12 Jan 2025 | 12/01/2025 | 12-01-2025
    m = re.search(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", line)
    if m:
        return m.group(1)

    m = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", line)
    if m:
        return m.group(1)

    return ""


def parse_transactions_from_text(text: str):
    """
    MAIN FUNCTION:
    Takes raw extracted text (from pdfplumber or OCR)
    Returns dataframe with ONLY real transactions.
    """
    lines = [x.strip() for x in text.split("\n") if x.strip()]
    rows = []

    for line in lines:
        # 1) Skip summary/balance lines
        if is_summary_line(line):
            continue

        # 2) Only accept transaction lines
        if not is_transaction_line(line):
            continue

        # 3) Extract amount
        amt = extract_amount(line)
        if amt is None:
            continue

        # 4) HARD BLOCK: ignore huge amounts that look like totals
        # You can change this limit if needed
        if amt > 200000:
            continue

        rows.append({
            "Date": extract_date(line),
            "Description": line[:150],
            "Amount": amt,
            "Type": detect_type(line),
            "Category": "UPI Transfer"
        })

    df = pd.DataFrame(rows)

    # remove duplicates (common in OCR)
    if not df.empty:
        df = df.drop_duplicates(subset=["Date", "Amount", "Description"])

    return df
