from unittest.mock import patch

from app.services.document_service import process_medical_document


def test_process_medical_document():
    mock_document = {
        "page_count": 1,
        "text": (
            "Name: Glucose\n"
            "Result: 95\n"
            "Unit: mg/dL"
        ),
        "pages": [
            {
                "page_number": 1,
                "text": (
                    "Name: Glucose\n"
                    "Result: 95\n"
                    "Unit: mg/dL"
                ),
            }
        ],
    }

    with patch(
        "app.services.document_service.extract_pdf_text",
        return_value=mock_document,
    ):
        result = process_medical_document("sample_lab_report.pdf")

    assert result["filename"] == "sample_lab_report.pdf"
    assert result["page_count"] == 1
    assert len(result["entities"]) == 1

    glucose = result["entities"][0]

    assert glucose["name"] == "Glucose"
    assert glucose["value"] == "95"
    assert glucose["unit"] == "mg/dL"
    assert glucose["source_page"] == 1
    assert glucose["verification_status"] == "unverified"

    assert result["verification_status"] == "unverified"


def test_process_document_with_no_matching_entities():
    mock_document = {
        "page_count": 1,
        "text": "This document has no recognized laboratory results.",
        "pages": [
            {
                "page_number": 1,
                "text": "This document has no recognized laboratory results.",
            }
        ],
    }

    with patch(
        "app.services.document_service.extract_pdf_text",
        return_value=mock_document,
    ):
        result = process_medical_document("empty_report.pdf")

    assert result["filename"] == "empty_report.pdf"
    assert result["entities"] == []
    assert result["verification_status"] == "unverified"