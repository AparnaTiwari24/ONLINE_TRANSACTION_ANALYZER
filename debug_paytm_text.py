import os
import pdfplumber

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BASE_DIR, "uploads", "input.pdf")

print("PDF PATH:", PDF_PATH)

with pdfplumber.open(PDF_PATH) as pdf:
    print("Total pages:", len(pdf.pages))
    text = pdf.pages[0].extract_text() or ""
    print("\n===== PAGE 1 RAW TEXT (first 2000 chars) =====\n")
    print(text[:2000])
    print("\n===== END =====\n")
