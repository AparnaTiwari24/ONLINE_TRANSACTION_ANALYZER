from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import cv2
import numpy as np
import re
import pandas as pd

ocr = PaddleOCR(lang="en")

PDF_PATH = "Paytm_data.pdf"
images = convert_from_path(PDF_PATH, dpi=300)

rows = []
current_flow = None
current_desc = None

for img in images:
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    result = ocr.predict(img)

    for block in result:
        text = block[1][0].lower().strip()

        # Detect transaction start
        if "paid to" in text or "money sent" in text:
            current_flow = "Expense"
            current_desc = text
            continue

        if "received from" in text or "money received" in text:
            current_flow = "Income"
            current_desc = text
            continue

        # Detect amount (often comes next)
        amt = re.search(r'rs\.?\s*([\d,]+(?:\.\d+)?)', text)
        if amt and current_flow and current_desc:
            rows.append({
                "description": current_desc,
                "amount": float(amt.group(1).replace(",", "")),
                "flow": current_flow
            })
            current_flow = None
            current_desc = None

df = pd.DataFrame(rows)

print("ROWS EXTRACTED:", len(df))
print(df.head(20))

df.to_csv("ocr_output_test.csv", index=False)
print("✅ Saved to ocr_output_test.csv")
