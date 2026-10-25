from pathlib import Path

from app.services.pdf_service import extract_pdf_text
from app.services.entity_extraction import extract_laboratory_entities


def process_medical_document(pdf_path: str) -> dict:
    """
    Extract text and laboratory results from a digital PDF.

    Extracted information is marked unverified.
    """

    document = extract_pdf_text(pdf_path)

    all_entities = []

    for page in document["pages"]:
        entities = extract_laboratory_entities(
            text=page["text"],
            page_number=page["page_number"],
        )

        all_entities.extend(entities)

    return {
        "filename": Path(pdf_path).name,
        "page_count": document["page_count"],
        "text": document["text"],
        "entities": all_entities,
        "verification_status": "unverified",
    }