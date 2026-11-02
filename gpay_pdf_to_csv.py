import re
import os
import pandas as pd
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import tempfile
import shutil

UPLOAD_DIR = "uploads"
PDF_PATH = os.path.join(UPLOAD_DIR, "input.pdf")
CSV_PATH = os.path.join(UPLOAD_DIR, "transactions.csv")
os.makedirs(UPLOAD_DIR, exist_ok=True)

SUMMARY_SKIP_WORDS = [
    "opening balance", "closing balance", "total withdrawal", "total deposit",
    "withdrawal count", "deposit count", "end of statement", "available balance",
    "current balance", "grand total", "any discrepancy", "system generated",
    "this is system generated report", "brought to the notice", "within one month"
]

DATE_PAT = re.compile(
    r"\b("
    r"\d{1,2}[-/ .]\d{1,2}[-/ .]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,|\s+)\d{2,4}|"
    r"\d{2}[-/]\d{2}[-/]\d{2}(?:\d{2})?"
    r")\b", re.IGNORECASE
)

AMT_PAT = re.compile(r"(?:₹\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", re.IGNORECASE)
AMT_DRCR_PAT = re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\((Dr|Cr)\)", re.I)
BALANCE_PAT = re.compile(r"(?:bal|balance|avail|closing)\s*[:=]?\s*\d", re.I)

DEBIT_PAT = re.compile(
    r"(?:Debit|Dr|Withdrawal|Paid|Debited|POS|UPI-)[^\d]*?(?:₹\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
    re.IGNORECASE
)
CREDIT_PAT = re.compile(
    r"(?:Credit|Cr|Deposit|Received|Credited|Salary|Refund)[^\d]*?(?:₹\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
    re.IGNORECASE
)

def detect_flow(desc: str, amount: float) -> str:
    d = str(desc).lower()
    income_keywords = [
        "received", "credited", "salary", "refund", "cashback",
        "credit", "payment received", "deposit", "reimbursement",
        "interest credited", "dividend", "bonus", "received from",
        "credit from", "reversal", "salary credit"
    ]
    expense_keywords = [
        "paid", "debited", "sent to", "payment to", "purchase",
        "debit", "withdrawn", "transfer to", "bill payment",
        "shopping", "food", "transport", "recharge", "paid to",
        "upi-", "merchant", "pos purchase", "atm"
    ]
    if any(kw in d for kw in income_keywords):
        return "Income"
    if any(kw in d for kw in expense_keywords):
        return "Expense"
    return "Expense" if amount < 0 else "Income"

def assign_category(desc: str, flow: str) -> str:
    d = str(desc).lower()
    
    if flow == "Income":
        if any(word in d for word in ["salary", "payment received", "salary credit"]):
            return "Salary"
        if any(word in d for word in ["refund", "cashback", "reversal"]):
            return "Refund/Cashback"
        if any(word in d for word in ["interest", "dividend"]):
            return "Interest/Investment"
        return "Other Income"

    if any(word in d for word in ["swiggy", "zomato", "restaurant", "food", "cafe", "hotel", "dominos", "mcdonald", "kfc", "pizza", "burger"]):
        return "Food & Dining"
    if any(word in d for word in ["amazon", "flipkart", "shopping", "myntra", "ajio", "mall", "store", "retail", "mart", "reliance", "trends"]):
        return "Shopping"
    if any(word in d for word in ["electricity", "bill", "water", "gas", "broadband", "internet", "recharge", "mobile", "postpaid", "prepaid", "electric", "dth"]):
        return "Bills & Utilities"
    if any(word in d for word in ["uber", "ola", "rapido", "metro", "bus", "petrol", "fuel", "parking", "taxi", "auto", "irctc"]):
        return "Transport"
    if any(word in d for word in ["transfer", "sent to", "upi", "imps", "neft", "rtgs", "to", "self"]):
        return "Transfer"
    if any(word in d for word in ["movie", "netflix", "prime", "hotstar", "spotify", "game", "entertainment", "cinema", "bookmyshow"]):
        return "Entertainment"
    if any(word in d for word in ["pharmacy", "hospital", "doctor", "medical", "medicine", "clinic", "health", "apollo", "1mg"]):
        return "Healthcare"
    if any(word in d for word in ["grocery", "supermarket", "blinkit", "instamart", "bigbasket", "dmart", "more", "reliance fresh"]):
        return "Groceries"
    
    return "Others"

def is_likely_summary_line(line: str) -> bool:
    t = line.lower().strip()
    if len(t) < 8:
        return True
    if any(w in t for w in SUMMARY_SKIP_WORDS):
        if not DATE_PAT.search(line) and not AMT_PAT.search(line):
            return True
    if BALANCE_PAT.search(t) and ("cr" in t or "dr" in t):
        return True
    return False

def is_summary_page(text: str) -> bool:
    lines = text.lower().splitlines()
    date_count = sum(1 for ln in lines if DATE_PAT.search(ln))
    if date_count >= 2:
        return False
    summary_count = sum(1 for w in SUMMARY_SKIP_WORDS if w in text.lower())
    return summary_count >= 2 and date_count == 0

def clean_amount(s: str) -> float | None:
    if not s:
        return None
    # Robust OCR error correction
    s = (s.replace("O", "0")
         .replace("o", "0")
         .replace("l", "1")
         .replace("I", "1")
         .replace(" ", "")
         .replace("₹", ""))
    
    s = s.replace(",", "")
    
    try:
        val = float(s)
        if val <= 0.01 or val > 5000000:
            return None
        return round(val, 2)
    except ValueError:
        if "." in s:
            parts = s.split(".")
            if len(parts) > 2:
                s = parts[0] + "." + parts[1]
                try:
                    val = float(s)
                    return round(val, 2)
                except:
                    pass
        return None

def crop_table_area(img):
    w, h = img.size
    # Wider crop to capture full debit/credit columns
    return img.crop((int(w*0.01), int(h*0.05), int(w*0.99), int(h*0.95)))

def get_txn_amount_and_flow(block: str):
    block = re.sub(r"\s{2,}", " ", block).strip().replace("\n", " ")
    lower_block = block.lower()

    # 1. Classic (Dr)/(Cr)
    drcr_matches = AMT_DRCR_PAT.findall(block)
    if drcr_matches:
        dr_matches = [m for m in drcr_matches if m[1].upper() == "DR"]
        if dr_matches:
            amt_str, drcr = dr_matches[0]
        else:
            amt_str, drcr = drcr_matches[0]
        amt = clean_amount(amt_str)
        if amt:
            flow = "Expense" if drcr.upper() == "DR" else "Income"
            print(f"  [DR/CR] {amt:12,.2f} → {flow:<8}  {amt_str} ({drcr})")
            return amt, flow, amt_str

    # 2. Keyword-based – debit first
    debit_m = DEBIT_PAT.search(block)
    if debit_m:
        amt = clean_amount(debit_m.group(1))
        if amt:
            print(f"  [DEBIT KW] {amt:12,.2f} → Expense")
            return amt, "Expense", debit_m.group(1)

    credit_m = CREDIT_PAT.search(block)
    if credit_m:
        amt = clean_amount(credit_m.group(1))
        if amt:
            print(f"  [CREDIT KW] {amt:12,.2f} → Income")
            return amt, "Income", credit_m.group(1)

    # 3. Multiple amounts – strong debit bias
    all_amts = []
    for m in AMT_PAT.finditer(block):
        amt = clean_amount(m.group(1))
        if amt and 0.1 < amt < 1500000:
            pos = m.start()
            after = block[m.end():m.end()+30].lower()
            is_debit_like = any(w in after for w in ["dr", "(dr", "debit", "withdrawal", "paid"])
            all_amts.append((amt, m.group(1), pos, is_debit_like))

    if all_amts:
        all_amts.sort(key=lambda x: (-x[3], x[2]))  # debit-like first, then leftmost
        amt, amt_str, pos, is_debit = all_amts[0]

        # Strong debit bias for Kotak statements
        if is_debit or any(w in lower_block for w in [
            "to ", "upi ", "paid ", "sent ", "merchant", "pos", "atm", "purchase",
            "dr ", "debit ", "withdrawal ", "debited ", "paid to"
        ]):
            flow = "Expense"
        elif any(w in lower_block for w in ["cr ", "credit ", "deposit ", "received ", "refund", "credited to"]):
            flow = "Income"
        else:
            flow = "Expense"  # default to expense unless strong credit signal

        print(f"  [MULTI {len(all_amts)}] {amt:12,.2f} → {flow:<8}  pos={pos} debit-like={is_debit}")
        return amt, flow, amt_str

    return None, None, None

def extract_transactions(lines):
    txns = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if is_likely_summary_line(line):
            i += 1
            continue

        date_match = DATE_PAT.search(line)
        if not date_match:
            i += 1
            continue

        date = date_match.group(1).strip()

        block_lines = [line]
        j = i + 1
        while j < len(lines) and len(block_lines) < 16:
            nl = lines[j].strip()
            if DATE_PAT.search(nl):
                break
            if len(nl) > 4 and not is_likely_summary_line(nl):
                block_lines.append(nl)
            j += 1

        block = " ".join(block_lines)
        block_clean = re.sub(r"\s{2,}", " ", block).strip()

        amt, flow, amt_str = get_txn_amount_and_flow(block_clean)
        if amt is None:
            if AMT_PAT.search(block_clean):
                print(f"  SKIPPED potential: {date} | {block_clean[:100]}...")
            i = j
            continue

        desc = block.replace(date, "", 1)
        if amt_str:
            desc = desc.replace(amt_str, "", 1)
        desc = re.sub(AMT_PAT, "", desc)
        desc = re.sub(AMT_DRCR_PAT, "", desc)
        desc = re.sub(r"\(\s*(?:Dr|Cr)\s*\)", "", desc, flags=re.I)
        desc = re.sub(r"\s{2,}", " ", desc).strip()

        if len(desc) < 5:
            i = j
            continue

        txns.append({
            "date": date,
            "description": desc,
            "amount": amt,
            "flow": flow
        })

        print(f"  → {date:10} {amt:12,.2f}  {flow:7}  {desc[:80]}...")

        i = j

    return txns

def safe_save_df(df, path):
    temp_fd, temp_path = tempfile.mkstemp(dir=UPLOAD_DIR, suffix=".csv")
    os.close(temp_fd)
    df.to_csv(temp_path, index=False)
    try:
        os.replace(temp_path, path)
    except PermissionError:
        backup = path + ".locked_backup"
        shutil.move(temp_path, backup)
        print(f"  CSV locked → saved backup: {backup}")

def main():
    if not os.path.exists(PDF_PATH):
        print("PDF not found")
        return

    print("Kotak OCR – final precision mode")
    print("="*65)

    pages = convert_from_path(PDF_PATH, dpi=420)
    all_txns = []

    for pageno, page in enumerate(pages, 1):
        print(f"\nPage {pageno}/{len(pages)}")
        cropped = crop_table_area(page)
        text = pytesseract.image_to_string(cropped, lang="eng",
                                           config="--oem 3 --psm 4")  # PSM 4 better for columns

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        print(f"  Lines: {len(lines)}   First few:")
        for ln in lines[:14]:
            print(f"    {ln}")

        if is_summary_page(text):
            print("  → summary page skipped")
            continue

        page_txns = extract_transactions(lines)
        print(f"  → {len(page_txns)} transactions this page")
        all_txns.extend(page_txns)

    print("\n" + "="*65)
    print(f"Total raw transactions: {len(all_txns)}")

    if not all_txns:
        print("No transactions found.")
        safe_save_df(pd.DataFrame(), CSV_PATH)
        return

    df = pd.DataFrame(all_txns)

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df[df["amount"] > 0.009].copy()  # allow very small amounts
    df = df[df["amount"] < 5000000].copy()

    df["category"] = df.apply(
        lambda row: assign_category(row["description"], row["flow"]), axis=1
    )

    def normalize_date(s):
        s = re.sub(r"[^0-9a-zA-Z/ -]", "", str(s)).strip()
        s = s.replace(" ", "-").replace("/", "-")
        for fmt in ["%d-%m-%Y", "%d-%m-%y", "%d-%b-%Y", "%d %b %Y", "%b %d %Y"]:
            try:
                return pd.to_datetime(s, format=fmt)
            except:
                pass
        return pd.NaT

    df["date_dt"] = df["date"].apply(normalize_date)
    df = df.dropna(subset=["date_dt"])
    df = df.sort_values("date_dt", ascending=False)
    df["date"] = df["date_dt"].dt.strftime("%d-%m-%Y")
    df.drop(columns=["date_dt"], inplace=True)

    df.insert(0, "txn_id", range(1, len(df)+1))

    safe_save_df(df, CSV_PATH)
    print(f"Saved {len(df)} cleaned transactions → {CSV_PATH}")

    income  = df[df["flow"] == "Income"]["amount"].sum()
    expense = df[df["flow"] == "Expense"]["amount"].sum()

    print("\nFinal Summary:")
    print(f"  Income  : ₹{income:,.2f}")
    print(f"  Expense : ₹{expense:,.2f}")
    print(f"  Net     : ₹{income - expense:,.2f}")

    expected_income = 1178994.35
    expected_expense = 1166187.71
    expected_net = 12806.64

    print("\nValidation:")
    print(f"  Expected Income: ₹{expected_income:,.2f} | Diff: ₹{income - expected_income:,.2f}")
    print(f"  Expected Expense: ₹{expected_expense:,.2f} | Diff: ₹{expense - expected_expense:,.2f}")
    print(f"  Expected Net: ₹{expected_net:,.2f} | Diff: ₹{(income - expense) - expected_net:,.2f}")

if __name__ == "__main__":
    main()