import pytesseract
from PIL import Image

# Set the path to your Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Print Tesseract version to confirm it's working
print("✅ Tesseract version:", pytesseract.get_tesseract_version())
