import pytesseract
from PIL import Image
from app.config import TESSERACT_CMD

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def extract_text(image_path: str) -> str:
    """Extract text from receipt image using Tesseract OCR.

    Uses Japanese + English language pack for best results.
    """
    image = Image.open(image_path)

    # Preprocess: convert to grayscale if needed
    if image.mode != "L":
        image = image.convert("L")

    text = pytesseract.image_to_string(image, lang="jpn+eng", config="--psm 6")
    return text.strip()
