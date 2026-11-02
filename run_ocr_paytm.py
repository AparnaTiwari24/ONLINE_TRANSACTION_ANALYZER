from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import cv2, re, pandas as pd, numpy as np

ocr = PaddleOCR(lang="en")
PDF_PATH = "Paytm_data.pdf"

images = convert_from_path(PDF_PATH, dpi=300)
rows = []
current_flow, current_desc = None, None

for img in images:
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    result = ocr.predict(img)

    for block in result:
        text = block[1][0].lower().strip()

        if "paid to" in text or "money sent" in text:
            current_flow = "Expense"
            current_desc = text
            continue

        if "received from" in text:
            current_flow = "Income"
            current_desc = text
            continue

        amt = re.search(r'rs\.?\s*([\d,]+(?:\.\d+)?)', text)
        if amt and current_flow:
            rows.append({
                "description": current_desc,
                "amount": float(amt.group(1).replace(",", "")),
                "flow": current_flow
            })
            current_flow, current_desc = None, None

df = pd.DataFrame(rows)
df.to_csv("transactions_final.csv", index=False)

print("✅ OCR DONE. Rows:", len(df))
