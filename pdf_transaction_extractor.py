import pdfplumber
import pandas as pd
import re

def extract_transactions_from_pdf(pdf_path):
    rows = []

    date_pattern = re.compile(r"\d{2}-\d{2}-\d{4}")
    amount_pattern = re.compile(r"([\d,]+\.\d{2})\((Dr|Cr)\)")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                line = line.strip()

                # 🔴 IGNORE HEADER / DETAILS
                if not date_pattern.search(line):
                    continue
                if not amount_pattern.search(line):
                    continue

                date = date_pattern.search(line).group()

                amt_match = amount_pattern.search(line)
                amount = float(amt_match.group(1).replace(",", ""))
                flow = "Expense" if amt_match.group(2) == "Dr" else "Income"

                description = line
                description = description.replace(date, "")
                description = description.replace(amt_match.group(0), "")
                description = re.sub(r"\s+", " ", description).strip(" -/")

                rows.append({
                    "date": date,
                    "description": description,
                    "amount": amount,
                    "flow": flow,
                    "source": "GPay",
                    "account": "Bank Account"
                })

    return pd.DataFrame(rows)
