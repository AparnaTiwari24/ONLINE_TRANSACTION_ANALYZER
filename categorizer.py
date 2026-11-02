import pandas as pd
import re

INPUT_CSV = "transactions_final_gpay.csv"
OUTPUT_CSV = "transactions_categorized_gpay.csv"

# ===== YOUR INPUT (USED AS-IS, LOWERCASED INTERNALLY) =====
KEYWORDS = {
    "Food & Dining": ["food", "restaurant", "mcdonald", "domino", "pizza hut", "kfc", "subway", "burger", "chai", "sweets", "swiggy", "zomato"],
    "Grocery & Delivery": ["grocery", "milk", "vegetable", "fruit", "dmart", "bigbasket", "blinkit"],
    "Medical & Health": ["hospital", "clinic", "pharmacy", "apollo", "medic", "health", "lab", "chemist"],
    "Travel & Transport": ["uber", "ola", "irctc", "train", "flight", "bus", "taxi", "travel", "metro"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "zudio", "reliance"],
    "Payment Services": ["payment", "qr", "charge", "fee"],
    "Government / Governance": ["mseb", "electricity", "water", "municipal", "tax", "passport"],
    "Education": ["school", "college", "fees", "course", "program", "tuition"]
}

KNOWN_MERCHANTS = [
    "mcdonald", "dominos", "pizza hut", "kfc", "subway",
    "starbucks", "jodhpur sweets", "chai dhuaan bar",
    "shivam chinese", "swiggy", "zomato", "dmart",
    "amazon", "flipkart", "irctc", "uber", "ola",
    "apollo pharmacy", "mseb", "myntra", "ajio"
]

# =========================================================

def categorize(row):
    desc = str(row["description"]).lower()
    flow = row["flow"]

    # 1️⃣ Income (absolute priority)
    if flow == "Income":
        return "Income"

    # 2️⃣ Known merchant match (strongest real-world signal)
    for merchant in KNOWN_MERCHANTS:
        if merchant in desc:
            for category, words in KEYWORDS.items():
                if any(w in merchant for w in words):
                    return category
            # merchant found but category unclear
            return "Shopping"

    # 3️⃣ Keyword-based category detection
    for category, words in KEYWORDS.items():
        if any(word in desc for word in words):
            return category

    # 4️⃣ Transfer (ONLY person-to-person)
    # If UPI exists but no merchant / business keyword
    business_words = [
        "hotel", "restaurant", "store", "mart", "medical",
        "chemist", "pharmacy", "school", "college", "fee",
        "electricity", "bill", "recharge", "petrol"
    ]

    if "upi/" in desc and not any(b in desc for b in business_words):
        return "Transfer"

    # 5️⃣ Fallback
    return "Other"


def main():
    df = pd.read_csv(INPUT_CSV)
    df["category"] = df.apply(categorize, axis=1)
    df.to_csv(OUTPUT_CSV, index=False)

    print("✅ Categorization completed using real-world logic")
    print(df["category"].value_counts())


if __name__ == "__main__":
    main()
