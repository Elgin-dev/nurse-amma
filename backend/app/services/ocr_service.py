from io import BytesIO
from pathlib import Path
from typing import Any

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

        return _ocr_result(path.name, text)
    except Exception as exc:
        raise ValueError(f"Unable to extract text from image: {exc}") from exc


def extract_image_text_from_bytes(image_bytes: bytes) -> dict[str, Any]:
    """Extract text from in-memory image bytes without creating a temporary file."""
    if not image_bytes:
        raise ValueError("Image content is empty.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Image dimensions must not exceed 40 megapixels.")
            image.load()
            text = pytesseract.image_to_string(image).strip()
        return _ocr_result("", text)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Unable to extract text from image: {exc}") from exc


def _ocr_result(filename: str, text: str) -> dict[str, str]:
    return {
        "filename": filename,
        "text": text,
        "extraction_method": "OCR",
        "verification_status": "unverified",
    }