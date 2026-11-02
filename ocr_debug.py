from pdf2image import convert_from_path
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

images = convert_from_path("paytm.pdf", dpi=300)

for i, img in enumerate(images):
    text = pytesseract.image_to_string(img)
    print(f"\n--- PAGE {i+1} ---\n")
    print(text)

