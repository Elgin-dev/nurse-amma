from pathlib import Path

import pytesseract
from PIL import Image

TESSERACT_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)


def extract_image_text(image_path: str) -> dict:
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError("Image file was not found.")

    try:
        with Image.open(path) as image:
            text = pytesseract.image_to_string(image).strip()

        return {
            "filename": path.name,
            "text": text,
            "extraction_method": "OCR",
            "verification_status": "unverified",
        }
    except Exception as exc:
        raise ValueError(f"Unable to extract text from image: {exc}") from exc