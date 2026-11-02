import re
import pandas as pd
from pdfplumber import open as pdf_open

OUTPUT_CSV = "transactions_categorized_paytm.csv"

CATEGORY_KEYWORDS = {
    "Food": ["restaurant", "food", "hotel", "zomato", "swiggy"],
    "Shopping": ["amazon", "flipkart", "mall"],
    "Medical": ["hospital", "pharmacy", "clinic"],
    "Transport": ["uber", "ola", "metro"],
}

def auto_category(desc, amount):
    d = desc.lower()

    if "upi" in d:
        if amount <= 300:
            return "Food"
        elif amount <= 2000:
            return "Shopping"
        else:
            return "Transfers"

    return "Others"


def extract_paytm_transactions(pdf_path):
    rows = []

    with pdf_open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                if "Paid to" in line or "Received from" in line:
                    try:
                        date = re.search(r"\d{2}-\d{2}-\d{4}", line).group()
                        amount = float(
                            re.search(r"₹\s?([\d,]+\.\d{2})", line).group(1).replace(",", "")
                        )

                        if "Received" in line:
                            flow = "Income"
                        else:
                            flow = "Expense"

                        desc = line.split(date)[-1].strip()
                        category = auto_category(desc)

                        # 🚫 Ignore garbage micro amounts
                        if amount < 5:
                            continue

                        rows.append([
                            date, desc, amount, flow,
                            "Paytm", "Bank A/C", category
                        ])
                    except:
                        continue

    df = pd.DataFrame(
        rows,
        columns=["date", "description", "amount", "flow", "source", "account", "category"]
    )

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Paytm extracted correctly → {OUTPUT_CSV}")
    return df
