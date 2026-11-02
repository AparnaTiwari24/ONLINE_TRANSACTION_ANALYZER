import pandas as pd
import re
 
def auto_category(description):
    desc = description.lower()

    MAP = {
        "Food & Dining": ["hotel", "restaurant", "sweet", "chai", "coffee", "bakery"],
        "Shopping": ["amazon", "flipkart", "myntra", "store"],
        "Medical & Health": ["medical", "chemist", "pharma", "hospital"],
        "Groceries": ["mart", "supermarket", "grocery"],
        "Transport": ["uber", "ola", "rapido", "fuel", "petrol"],
    }

    for cat, keys in MAP.items():
        if any(k in desc for k in keys):
            return cat

    if "upi" in desc or "transfer" in desc:
        return "Transfers"

    return "Others"
