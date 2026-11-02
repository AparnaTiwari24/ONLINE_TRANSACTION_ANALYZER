"""
categorize_transactions.py — Enhanced Universal Categorizer (Paytm + GPay)
Now prioritizes merchant-based classification over keyword-based transfer detection.
"""

import re
import pandas as pd
from rapidfuzz import process, fuzz

# ------------------ CONFIGURATION ------------------

KNOWN_MERCHANTS = [
    # Food & Dining
    "McDonalds", "Dominos", "Pizza Hut", "Starbucks", "Cafe Coffee Day", "Jodhpur Sweets",
    "Barista", "KFC", "Burger King", "Subway", "Bikanervala", "Haldirams", "AV Foods",
    "Chai Dhuan Bar", "Spring Potato", "Swiggy", "Zomato", "Foodpanda",
    # Grocery & Delivery
    "Zepto", "Blinkit", "BigBasket", "Swiggy Instamart", "Dunzo", "Amazon Fresh", "Super Market", "Supermart",
    # Shopping & Retail
    "DMart", "Reliance Trends", "Big Bazaar", "Ajio", "Nykaa", "Flipkart", "Amazon", "Croma",
    "Tata Cliq", "Myntra", "Zudio", "Max Fashion", "Pantaloons",
    # Medical & Health
    "Apollo Pharmacy", "Netmeds", "1mg", "MedPlus", "Orange Chemist", "Aarav Ophthalmics",
    # Utilities & Bills
    "MSEDCL", "Tata Power", "Adani Electricity", "Jio", "Airtel", "Vi", "BSNL", "MTNL", "Municipal Corporation", "BESCOM",
    # Travel & Transport
    "Uber", "Ola", "IRCTC", "Indian Railways", "Auto Rickshaw", "Cab Service", "Yadav Transport", "Rapido",
    # Education
    "Byjus", "Unacademy", "Vedantu", "Coursera", "Udemy", "Shree Rahul Edu", "Allen", "Resonance",
    "Aakash Institute", "Edu Bridge", "Institute", "College", "School", "Tuition",
    # Entertainment & Subscriptions
    "Netflix", "Amazon Prime", "JioCinema", "JioHotstar", "Hotstar", "BookMyShow", "PVR", "Inox",
    "Spotify", "Zee5", "SonyLiv", "YouTube Premium", "Gaana", "JioSaavn",
    # Beauty, Fitness & Services
    "Lakme Salon", "Kaya Skin", "K S Beauty Center", "VLCC", "UrbanClap", "Urban Company",
    "Gym", "Salon", "Spa", "Beauty Center",
    # Payments & Wallets
    "Paytm", "GPay", "PhonePe", "UPI", "BHIM", "Wallet",
    # Income & Bank
    "Salary Credit", "Cash Deposit", "Refund", "Interest Credit", "UPI Reversal", "Reimbursement",
    "Inr Thane", "Cashback Earned",
    # Miscellaneous
    "Google", "Apple", "Microsoft", "Axis Bank", "Kotak Bank", "SBI", "HDFC Bank"
]

MERCHANT_FIXES = {
    "mcdonalds": "McDonalds",
    "mc donalds": "McDonalds",
    "orange chem 3": "Orange Chemist",
    "a v foods": "AV Foods",
    "chai dhuan": "Chai Dhuan Bar",
    "spring potato": "Spring Potato",
    "aarav ophthalmics pr": "Aarav Ophthalmics",
    "shivam": "Shivam Mishra",
    "ashutosh": "Ashutosh Dubey",
    "akbar": "Akbar Shaikh",
    "krishans super market": "Krishans Super Market",
    "swiggy ltd": "Swiggy",
    "swiggy": "Swiggy",
}

CATEGORY_KEYWORDS = {
    "Food & Dining": [
        "restaurant", "pizza", "food", "bar", "chai", "sweet", "hotel", "burger", "snack",
        "potato", "sweets", "swiggy", "zomato", "foodpanda"
    ],
    "Grocery & Delivery": [
        "grocery", "zepto", "blinkit", "instamart", "bigbasket", "bazaar", "super market", "supermart", "dunzo", "fresh"
    ],
    "Shopping & Retail": [
        "shop", "store", "amazon", "flipkart", "reliance", "dmart", "ajio", "nykaa", "myntra",
        "zudio", "pantaloons", "trend", "mall"
    ],
    "Medical & Health": [
        "chem", "pharm", "medical", "doctor", "clinic", "health", "hospital", "ophthalmic", "medicine"
    ],
    "Education": [
        "school", "college", "university", "edu", "tuition", "institute", "academy", "byjus", "vedantu", "unacademy"
    ],
    "Travel & Transport": [
        "uber", "ola", "auto", "rickshaw", "cab", "train", "rail", "irctc", "bus", "flight", "ticket", "travel"
    ],
    "Entertainment & Subscriptions": [
        "netflix", "prime", "hotstar", "bookmyshow", "pvr", "inox", "spotify", "ott",
        "subscription", "cinema", "jiosaavn", "gaana", "zee5", "jiocinema", "youtube", "movie"
    ],
    "Utilities & Bills": [
        "bill", "electric", "power", "gas", "wifi", "mobile", "internet", "broadband", "msedcl", "airtel", "jio", "bsnl", "vi"
    ],
    "Payments & Wallets": [
        "paytm", "gpay", "phonepe", "upi", "bhim", "wallet"
    ],
    "Beauty & Fitness": [
        "salon", "beauty", "spa", "gym", "wellness", "kaya", "lakme"
    ],
    "Charges & GST": [
        "gst", "fee", "charge", "commission", "surcharge", "tax"
    ],
    "Income": [
        "cashback", "refund", "credited", "deposit", "interest", "salary", "inward", "reversal", "received"
    ],
    "Transfer": [
        "sent to", "transfer", "to ", "from ", "upi payment", "pay to", "money sent"
    ],
    "Other": []
}

FUZZY_THRESHOLD = 80

# ------------------ HELPERS ------------------

def normalize_text(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s)


def clean_merchant(name: str) -> str:
    n = normalize_text(name)
    if n in MERCHANT_FIXES:
        return MERCHANT_FIXES[n]
    match, score, _ = process.extractOne(n, KNOWN_MERCHANTS, scorer=fuzz.token_sort_ratio) or (None, 0, None)
    return match if score >= FUZZY_THRESHOLD else name.strip().title()


def categorize(description: str):
    desc = description.lower()

    CATEGORY_KEYWORDS = {
        "Food & Dining": [
            "hotel", "restaurant", "cafe", "chai", "coffee", "sweet",
            "dhaba", "bakery", "pizza", "burger", "bar", "canteen"
        ],
        "Groceries": [
            "super market", "supermarket", "mart", "grocery", "kirana"
        ],
        "Medical & Health": [
            "medical", "chemist", "pharma", "hospital", "clinic", "ophthalmic"
        ],
        "Shopping": [
            "amazon", "flipkart", "myntra", "shopping", "store", "mall"
        ],
        "Transport": [
            "uber", "ola", "rapido", "metro", "bus", "fuel", "petrol", "diesel"
        ],
        "Rent": [
            "rent", "landlord", "house rent"
        ],
        "Utilities": [
            "electricity", "water", "gas", "recharge", "broadband", "wifi"
        ]
    }

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc:
                return category

    if "received" in desc or "credited" in desc:
        return "Income"

    if "sent" in desc or "paid" in desc or "debit" in desc:
        return "Transfers"

    return "Others"



# ------------------ MAIN ------------------

def main(input_csv=r"C:\Users\Aparna Tiwari\Downloads\OnlineAppAnalyzer\paytm_transactions_final.csv",
         output_csv="transactions_categorized.csv"):

    print(f"📂 Reading: {input_csv}")
    df = pd.read_csv(input_csv, dtype=str)
    for col in ['merchant', 'description', 'flow']:
        df[col] = df[col].fillna("")

    df['merchant'] = df['merchant'].apply(clean_merchant)
    df['category'] = df.apply(categorize, axis=1)

    df.to_csv(output_csv, index=False)
    print(f"✅ Categorization complete → {output_csv}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", dest="csv_in", default=r"C:\Users\Aparna Tiwari\Downloads\OnlineAppAnalyzer\paytm_transactions_final.csv", help="Input CSV file")
    parser.add_argument("--output", dest="csv_out", default="transactions_categorized_paytm.csv", help="Output CSV file")
    args = parser.parse_args()
    main(args.csv_in, args.csv_out)
