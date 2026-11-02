#!/usr/bin/env python3
# master_categorizer.py
# Intelligent master categorizer (keyword-first + merchant-fuzzy + ML fallback)
# Usage:
#   python master_categorizer.py transactions_corrected_gpay.csv transactions_categorized_paytm.csv
# If you don't pass files it'll try the default uploaded samples:
#   /mnt/data/transactions_corrected_gpay.csv
#   /mnt/data/transactions_categorized_paytm.csv

import argparse
import pandas as pd
import os
import re
from rapidfuzz import process, fuzz
import joblib
from collections import Counter

# ----------------------------
# CONFIG — Tweak these lists to improve accuracy
# ----------------------------
FUZZY_THRESHOLD = 85  # merchant canonicalization threshold
MODEL_PATH = "category_model.pkl"
VECTORIZER_PATH = "tfidf_vectorizer.pkl"

# Keyword lists (order matters — higher priority groups first)
KEYWORDS = {
    "Income": ["salary", "payroll", "credited", "received", "refund", "interest"],
    "Payment Services": ["upi", "payment", "pay", "pg", "razorpay", "google pay", "gpay", "paytm"],
    "Food & Dining": ["restaurant", "food", "dine", "mcdonald", "dominos", "pizza", "kfc", "zomato", "swiggy"],
    "Grocery & Delivery": ["grocery", "dmart", "bigbasket", "supermarket", "vegetable", "store", "milk", "fruit"],
    "Travel & Transport": ["uber", "ola", "irctc", "train", "flight", "bus", "taxi", "railway", "ticket"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "zara", "shop", "paytm mall", "snapdeal"],
    "Medical & Health": ["hospital", "clinic", "pharmacy", "apollo", "medic", "lab", "doctor"],
    "Education": ["school", "college", "tuition", "exam", "course", "fees"],
    "Transfer": ["transfer", "sent to", "sent", "to a/c", "fund transfer", "neft", "imps", "rtgs"],
    "Charges & Fees": ["fee", "charge", "penalty", "gst", "tds"],
    "Railway": ["irctc", "railway", "rail"],
    "Travel & Transport - Fuel": ["fuel", "petrol", "diesel", "hpcl", "indianoil", "ioex"],
    "Donations / Temple": ["donation", "temple", "dargah", "mosque", "church", "gift"],
    "Medical": ["pharmacy", "chemists"]
}

# Merchant canonical list (extend with real merchants you see)
KNOWN_MERCHANTS = [
    "McDonalds", "Dominos", "Pizza Hut", "KFC", "Subway", "Burger King",
    "Starbucks", "Swiggy", "Zomato", "DMart", "Amazon", "Flipkart", "IRCTC",
    "Uber", "Ola", "Apollo Pharmacy", "Myntra", "Ajio", "BPCL", "HPCL", "IndianOil"
]

# ----------------------------
# Helper utilities
# ----------------------------
def load_model_and_vectorizer():
    """Attempt to load ML model + vectorizer. Returns (model, vectorizer) or (None, None)."""
    model = None
    vectorizer = None
    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
            model = joblib.load(MODEL_PATH)
            vectorizer = joblib.load(VECTORIZER_PATH)
            print(f"✔ Loaded ML model: {MODEL_PATH} and vectorizer: {VECTORIZER_PATH}")
        else:
            print("ℹ ML model or vectorizer not found — will use rules-only fallback.")
    except Exception as e:
        print("⚠ Failed to load model/vectorizer:", e)
    return model, vectorizer

def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s)
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def keyword_category(text):
    """Keyword-first detection — returns category or None."""
    t = text.lower()
    # exact keyword match precedence by KEYWORDS dict order
    for cat, keys in KEYWORDS.items():
        for k in keys:
            if k in t:
                return cat
    return None

def detect_merchant(text):
    """Fuzzy match the text to known merchants. Returns canonical merchant or original small-clean string."""
    try:
        best = process.extractOne(text, KNOWN_MERCHANTS, scorer=fuzz.token_sort_ratio)
        if best:
            name, score, _ = best
            if score >= FUZZY_THRESHOLD:
                return name
    except Exception:
        pass
    # fallback: simple heuristic: first capitalized word-sequence or short token
    tokens = re.findall(r"[A-Za-z0-9&\.\- ]{3,}", text)
    if tokens:
        s = tokens[0].strip()
        if len(s) > 60:
            s = s[:60]
        return s
    return text[:60]

def ml_predict(text, model, vectorizer):
    """Use ML fallback if model available, else None."""
    if model is None or vectorizer is None:
        return None
    try:
        v = vectorizer.transform([text])
        pred = model.predict(v)[0]
        return pred
    except Exception:
        return None

# ----------------------------
# Per-row categorization pipeline
# ----------------------------
def categorize_row(row, model=None, vectorizer=None):
    desc = normalize_text(row.get("description", "") or row.get("narration", ""))
    merchant_field = normalize_text(row.get("merchant", ""))
    combined = f"{desc} {merchant_field}".strip()

    # 1) Keyword-first on combined text
    cat = keyword_category(combined)
    if cat:
        return cat

    # 2) Merchant fuzzy canonicalization -> merchant-based category if merchant maps to keyword category
    canonical = detect_merchant(combined)
    # check canonical against keywords
    mcat = keyword_category(canonical)
    if mcat:
        return mcat

    # 3) ML fallback
    mlc = ml_predict(combined, model, vectorizer)
    if mlc:
        return mlc

    # 4) Last-resort heuristics
    # If amount is positive and flow contains income-like -> Income
    flow = str(row.get("flow", "")).lower()
    if "income" in flow or "credit" in flow or "cr" == flow:
        return "Income"
    # Transfers
    if "transfer" in combined or re.search(r"\bto\b.*\bupi\b|\bfrom\b.*\bupi\b", combined.lower()):
        return "Transfer"
    return "Other"

# ----------------------------
# Process a single CSV file
# ----------------------------
def process_file(path, out_dir="out_master"):
    print(f"\nProcessing file: {path}")
    df = pd.read_csv(path, dtype=str)  # read everything as strings to avoid surprises

    # try to map expected columns to names
    col_map = {c.lower().strip(): c for c in df.columns}
    def pick(*names):
        for n in names:
            k = n.lower()
            if k in col_map:
                return col_map[k]
        return None

    # Map common columns
    txn_col = pick("txn_id", "id", "transaction_id", "transaction id") or None
    date_col = pick("date", "txn_date", "transaction_date") or None
    desc_col = pick("description", "details", "narration", "desc") or None
    amt_col = pick("amount", "amt", "value") or None
    flow_col = pick("flow", "type", "dr/cr", "credit/debit") or None
    src_col = pick("source") or None
    acct_col = pick("account", "account_no", "account number") or None
    cat_col = pick("category") or None
    merch_col = pick("merchant", "payee", "beneficiary") or None

    # Create a normalized DF for processing
    norm = pd.DataFrame()
    norm["txn_id"] = df[txn_col] if txn_col in df.columns else df.index.astype(str)
    # Parse date robustly: try dd-mm-yyyy then dayfirst
    if date_col and date_col in df.columns:
        try:
            norm["date"] = pd.to_datetime(df[date_col], format="%d-%m-%Y", errors="coerce")
            norm["date"] = norm["date"].fillna(pd.to_datetime(df[date_col], dayfirst=True, errors="coerce"))
        except Exception:
            norm["date"] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
    else:
        norm["date"] = pd.NaT

    norm["description"] = df[desc_col] if desc_col in df.columns else ""
    norm["amount"] = pd.to_numeric(df[amt_col], errors="coerce").fillna(0.0) if amt_col in df.columns else 0.0
    # Normalize flow
    if flow_col and flow_col in df.columns:
        flows = df[flow_col].astype(str).str.lower()
        norm["flow"] = flows.apply(lambda x: "Income" if "credit" in x or "cr" in x or "in" in x and "out" not in x else ("Expense" if "debit" in x or "dr" in x else "Expense"))
    else:
        # Heuristic: negative amounts => Expense
        norm["flow"] = df[amt_col].apply(lambda x: "Expense" if pd.to_numeric(x, errors="coerce") < 0 else "Income") if amt_col in df.columns else "Expense"

    # source, account, category, merchant
    norm["source"] = df[src_col] if src_col in df.columns else ""
    norm["account"] = df[acct_col] if acct_col in df.columns else ""
    norm["category_original"] = df[cat_col] if cat_col in df.columns else ""
    norm["merchant"] = df[merch_col] if merch_col in df.columns else ""

    # Load model
    model, vectorizer = load_model_and_vectorizer()

    # Apply merchant canonicalization first (to keep merchant field consistent)
    norm["merchant_canonical"] = norm["merchant"].fillna("").apply(lambda x: detect_merchant(x if x else norm.get("description","")[:120]))

    # Apply categorization pipeline
    norm["category_master"] = norm.apply(lambda r: categorize_row({
        "description": r["description"],
        "merchant": r["merchant_canonical"],
        "flow": r["flow"],
        "amount": r["amount"]
    }, model=model, vectorizer=vectorizer), axis=1)

    # Save outputs — merge back original columns and new category/merchant
    out = df.copy()
    out["merchant_canonical"] = norm["merchant_canonical"]
    out["category_master"] = norm["category_master"]

    # Prepare output filename
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(path)
    name, ext = os.path.splitext(base)
    out_path = os.path.join(out_dir, f"{name}_master_categorized{ext}")
    out.to_csv(out_path, index=False)

    # Print summary
    cnt = Counter(out["category_master"].fillna("Other"))
    print(f"✔ Saved categorized file: {out_path}")
    print("Category counts:")
    for k, v in cnt.most_common():
        print(f"  {k}: {v}")

    return out_path, cnt

# ----------------------------
# Main CLI
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Master Categorizer (keyword + merchant fuzzy + ML fallback)")
    parser.add_argument("files", nargs="*", help="CSV file(s) to categorize (if none provided defaults used)")
    parser.add_argument("--out_dir", default="out_master", help="Output directory")
    args = parser.parse_args()

    files = args.files if args.files else [
        "/mnt/data/transactions_corrected_gpay.csv",
        "/mnt/data/transactions_categorized_paytm.csv"
    ]

    all_counts = Counter()
    processed = []
    for f in files:
        if not os.path.exists(f):
            print(f"⚠ File not found, skipping: {f}")
            continue
        out_path, cnt = process_file(f, out_dir=args.out_dir)
        all_counts.update(cnt)
        processed.append(out_path)

    print("\n=== FINAL SUMMARY ===")
    for k, v in all_counts.most_common():
        print(f"{k}: {v}")
    print(f"Processed files: {len(processed)}")
    print("finished")

if __name__ == "__main__":
    main()
