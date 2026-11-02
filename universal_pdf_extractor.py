import pandas as pd
import camelot
import os
import re

def normalize_col(col):
    return re.sub(r"\s+", " ", str(col).strip().lower())

def convert_gpay_pdf_to_csv(pdf_path, output_csv):
    tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")

    if not tables:
        raise ValueError("No tables found in PDF")

    df = pd.concat([t.df for t in tables], ignore_index=True)

    # First row is header → fix it
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    # Normalize column names
    df.columns = [normalize_col(c) for c in df.columns]

    # ---- AUTO-DETECT DATE COLUMN ----
    date_col = None
    for c in df.columns:
        if "date" in c:
            date_col = c
            break

    if date_col is None:
        raise ValueError(f"No date column found. Columns: {df.columns.tolist()}")

    df.rename(columns={date_col: "date"}, inplace=True)

    # ---- AUTO-DETECT AMOUNT COLUMNS ----
    withdraw_col = None
    deposit_col = None

    for c in df.columns:
        if "withdraw" in c or "debit" in c or "(dr)" in c:
            withdraw_col = c
        if "deposit" in c or "credit" in c or "(cr)" in c:
            deposit_col = c

    # Clean numbers
    if withdraw_col:
        df["withdrawal"] = (
            df[withdraw_col]
            .astype(str)
            .str.replace(",", "")
            .str.replace(" ", "")
        )
    else:
        df["withdrawal"] = "0"

    if deposit_col:
        df["deposit"] = (
            df[deposit_col]
            .astype(str)
            .str.replace(",", "")
            .str.replace(" ", "")
        )
    else:
        df["deposit"] = "0"

    df["withdrawal"] = pd.to_numeric(df["withdrawal"], errors="coerce").fillna(0)
    df["deposit"] = pd.to_numeric(df["deposit"], errors="coerce").fillna(0)

    # Final amount + flow
    df["amount"] = df["deposit"] - df["withdrawal"]
    df["flow"] = df["amount"].apply(lambda x: "Income" if x > 0 else "Expense")

    # Parse date safely
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    # Narration / description
    narration_col = None
    for c in df.columns:
        if "narration" in c or "description" in c:
            narration_col = c
            break

    if narration_col:
        df.rename(columns={narration_col: "description"}, inplace=True)
    else:
        df["description"] = ""

    final_df = df[["date", "description", "amount", "flow"]].copy()

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    final_df.to_csv(output_csv, index=False)

    return final_df
