import re
import pandas as pd
import pytesseract
from pdf2image import convert_from_path

# UPDATE THESE PATHS
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\Library\bin"

def _ocr_pdf(pdf_path):
    images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img, config="--psm 6")
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text


def extract_gpay(pdf_path):
    text = _ocr_pdf(pdf_path)

    pattern = re.findall(
        r'(\d{1,2}\s\w+\s\d{4}).*?(Paid to|Received from)\s+(.*?)\s+₹\s?([\d,]+\.\d{2})',
        text
    )

    rows = []
    for date, tx_type, desc, amount in pattern:
        rows.append({
            "App": "GPay",
            "Date": date,
            "Type": "Debit" if "Paid" in tx_type else "Credit",
            "Description": desc.strip(),
            "Amount": float(amount.replace(",", "")),
            "Category": "Uncategorized"
        })

    return pd.DataFrame(rows)


def extract_paytm(pdf_path):
    text = _ocr_pdf(pdf_path)

    pattern = re.findall(
        r'(\d{1,2}\s\w+\s\d{4})\s+(Paid to|Received from)\s+(.*?)\s+₹\s?([\d,]+\.\d{2})',
        text
    )

    rows = []
    for date, tx_type, desc, amount in pattern:
        rows.append({
            "App": "Paytm",
            "Date": date,
            "Type": "Debit" if "Paid" in tx_type else "Credit",
            "Description": desc.strip(),
            "Amount": float(amount.replace(",", "")),
            "Category": "Uncategorized"
        })

    return pd.DataFrame(rows)
def auto_category(desc):
    desc = desc.lower()

    if any(k in desc for k in ["amazon", "flipkart", "myntra"]):
        return "Shopping"
    if any(k in desc for k in ["zomato", "swiggy", "restaurant", "hotel"]):
        return "Food"
    if any(k in desc for k in ["uber", "ola", "rapido"]):
        return "Transport"
    if any(k in desc for k in ["electricity", "recharge", "bill"]):
        return "Bills"
    if any(k in desc for k in ["rent"]):
        return "Rent"

    return "Others"
