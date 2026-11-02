import pdfplumber
import pandas as pd
import re

PDF_PATH = r"C:\Users\Aparna Tiwari\Downloads\OnlineAppAnalyzer\Gpay_data (1).pdf"
OUTPUT_CSV = "transactions_final_gpay.csv"

date_pattern = re.compile(r"\d{2}-\d{2}-\d{4}")
amount_pattern = re.compile(r"([\d,]+\.\d{2})\((Dr|Cr)\)")

rows = []

with pdfplumber.open(PDF_PATH) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue

        for line in text.split("\n"):
            # must contain date + amount
            if not date_pattern.search(line):
                continue
            if not amount_pattern.search(line):
                continue

            date = date_pattern.search(line).group()

            amt_match = amount_pattern.search(line)
            amount = float(amt_match.group(1).replace(",", ""))
            drcr = amt_match.group(2)

            flow = "Expense" if drcr == "Dr" else "Income"

            # description = remove date & amount
            desc = line
            desc = desc.replace(date, "")
            desc = desc.replace(amt_match.group(0), "")
            desc = re.sub(r"\s+", " ", desc).strip(" -")

            rows.append({
                "date": date,
                "description": desc,
                "amount": amount,
                "flow": flow,
                "source": "GPay",
                "account": "Bank Account"
            })

df = pd.DataFrame(rows)
df.to_csv(OUTPUT_CSV, index=False)

print(f"✅ Extracted {len(df)} transactions")
print(f"📁 Saved to {OUTPUT_CSV}")
