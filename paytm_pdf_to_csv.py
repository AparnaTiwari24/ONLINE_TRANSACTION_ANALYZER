import os
import re
import sys
import pandas as pd
import pdfplumber

print("🔥 RUNNING paytm_pdf_to_csv.py – PAYTM FINAL FIX 🔥")

# =========================
# PATHS
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PDF_PATH = os.path.join(UPLOAD_DIR, "input.pdf")
OUTPUT_CSV = os.path.join(UPLOAD_DIR, "transactions.csv")

if not os.path.exists(PDF_PATH):
    print("❌ PDF not found:", PDF_PATH)
    sys.exit(1)

print("✅ PDF found:", PDF_PATH)

# =========================
# REGEX (MATCHES YOUR PDF LINE STYLE)
# =========================
UPI_REF_PAT = re.compile(r"UPI\s*Ref\s*No\s*:\s*(\d{8,25})", re.IGNORECASE)

# Example line:
# 16 Aug Received from Ashutosh Dubey Tag: State Bank + Rs.100
TXN_LINE_PAT = re.compile(
    r"(?P<date>\d{1,2}\s+[A-Za-z]{3})\s+"
    r"(?P<desc>.+?)\s+"
    r"(?P<sign>[+-])\s*Rs\.?\s*(?P<amt>[\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE
)

def clean_amount(x: str) -> float:
    return float(x.replace(",", "").strip())

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def detect_flow(sign: str) -> str:
    return "Income" if sign == "+" else "Expense"

# =========================
# EXTRACT TRANSACTIONS PAGE-WISE
# =========================
txns = []
pending = None  # store txn line until we find its UPI ref

with pdfplumber.open(PDF_PATH) as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if not text.strip():
            continue

        lines = [normalize_spaces(l) for l in text.split("\n") if l.strip()]

        for ln in lines:
            # 1) Find transaction main line (date + desc + amount)
            m = TXN_LINE_PAT.search(ln)
            if m:
                date_val = m.group("date").strip()
                desc_val = m.group("desc").strip()

                # remove extra words after description
                desc_val = desc_val.replace("Tag:", "").strip()

                sign = m.group("sign").strip()
                amt = clean_amount(m.group("amt"))

                # Skip self transfer if it appears
                if "transferred to self" in desc_val.lower():
                    pending = None
                    continue

                pending = {
                    "date": date_val,
                    "description": desc_val[:160],
                    "amount": round(amt, 2),
                    "flow": detect_flow(sign),
                    "upi_ref": ""
                }
                continue

            # 2) Attach UPI ref to the pending transaction
            if pending:
                upi_m = UPI_REF_PAT.search(ln)
                if upi_m:
                    pending["upi_ref"] = upi_m.group(1).strip()
                    txns.append(pending)
                    pending = None

# =========================
# SAVE CSV
# =========================
df = pd.DataFrame(txns)

if df.empty:
    print("⚠️ No transactions found (Paytm). Empty CSV saved:", OUTPUT_CSV)
    pd.DataFrame(columns=["date", "description", "amount", "flow"]).to_csv(OUTPUT_CSV, index=False)
    sys.exit(0)

# remove duplicates
df["upi_ref"] = df["upi_ref"].astype(str).str.strip()
df = df[df["upi_ref"] != ""]
df = df.drop_duplicates(subset=["upi_ref"]).reset_index(drop=True)

df = df[["date", "description", "amount", "flow"]]
df.to_csv(OUTPUT_CSV, index=False)

print(f"✅ Extracted {len(df)} UNIQUE Paytm transactions")
print("✅ CSV saved:", OUTPUT_CSV)

income_total = df[df["flow"] == "Income"]["amount"].sum()
expense_total = df[df["flow"] == "Expense"]["amount"].sum()

print(f"💰 Income : ₹{income_total:,.2f}")
print(f"💸 Expense: ₹{expense_total:,.2f}")
