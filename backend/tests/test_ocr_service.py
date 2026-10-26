from PIL import Image, ImageDraw

from app.services import ocr_service
from app.services.ocr_service import extract_image_text


def test_extract_image_text(tmp_path, monkeypatch):
    image_path = tmp_path / "sample.png"

    image = Image.new("RGB", (800, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 50), "Glucose: 95 mg/dL", fill="black")
    image.save(image_path)

    monkeypatch.setattr(
        ocr_service.pytesseract,
        "image_to_string",
        lambda _image: "Glucose: 95 mg/dL",
    )
    result = extract_image_text(str(image_path))

    assert result["filename"] == "sample.png"
    assert "Glucose" in result["text"]
    assert result["extraction_method"] == "OCR"
    assert result["verification_status"] == "unverified"


def test_missing_image_raises_error(tmp_path):
    missing_path = tmp_path / "missing.png"

    try:
        extract_image_text(str(missing_path))
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass