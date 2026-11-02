import re
from difflib import get_close_matches

def clean_text(text):
    """
    Normalize OCR text before parsing.
    - Removes broken lines, unwanted symbols
    - Joins split merchant names
    - Ensures each transaction is one clean line
    """
    text = text.replace('\n', ' ')
    text = re.sub(r'\s{2,}', ' ', text)  # remove double spaces
    text = re.sub(r'[^A-Za-z0-9/().\-\s]', '', text)  # remove junk chars
    return text.strip().lower()

def extract_merchant_normalized(desc):
    """
    Extract merchant from 'upi/merchantname/...'
    and clean to readable form.
    """
    match = re.search(r'upi/([a-z\s&]+?)/', desc)
    if match:
        name = match.group(1).strip().title()
        return re.sub(r'\s+', ' ', name)
    return "Unknown"

def categorize_smart(desc):
    """
    Categorize based on clean keywords + fuzzy matching.
    """
    desc = desc.lower()

    categories = {
        "Food": ["mcdonald", "restaurant", "swiggy", "zomato", "chai", "coffee", "juice", "sweets"],
        "Shopping": ["amazon", "myntra", "blinkit", "zepto", "store", "mart", "bazaar", "fashion"],
        "Medical": ["chemist", "medical", "pharmacy", "hospital", "clinic"],
        "Education": ["college", "fees", "school", "academy", "tuition"],
        "Transport": ["auto", "cab", "train", "fuel", "metro", "bus"],
        "Entertainment": ["netflix", "hotstar", "movie", "music", "jiosaavn", "theatre"],
        "Transfer": ["upi", "transfer", "payment", "fund", "to", "self"],
        "Income": ["deposit", "cashback", "credit", "refund", "received"],
        "Bills": ["recharge", "electricity", "gas", "bill", "postpaid"]
    }

    for cat, keywords in categories.items():
        for word in keywords:
            if word in desc:
                return cat

    # fuzzy fallback (catch OCR typos like "mc donlds" → "mcdonald")
    all_keywords = [kw for group in categories.values() for kw in group]
    close = get_close_matches(desc, all_keywords, n=1, cutoff=0.8)
    if close:
        for cat, group in categories.items():
            if close[0] in group:
                return cat

    return "Other"
