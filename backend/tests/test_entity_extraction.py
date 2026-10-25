from app.services.entity_extraction import (
    extract_laboratory_entities,
)


def test_extracts_multiple_laboratory_results():

    text = """
    Name: Glucose
    Result: 95
    Unit: mg/dL

    Name: Hemoglobin
    Result: 12.5
    Unit: g/dL
    """

    results = extract_laboratory_entities(
        text=text,
        page_number=2,
    )

    assert len(results) == 2

    assert results[0]["name"] == "Glucose"
    assert results[0]["value"] == "95"
    assert results[0]["unit"] == "mg/dL"

    assert results[1]["name"] == "Hemoglobin"
    assert results[1]["value"] == "12.5"
    assert results[1]["unit"] == "g/dL"

    assert results[0]["source_page"] == 2

    assert all(
        item["verification_status"] == "unverified"
        for item in results
    )


def test_returns_empty_list_for_unrecognized_text():

    text = "This document contains no matching laboratory fields."

    results = extract_laboratory_entities(text)

    assert results == []