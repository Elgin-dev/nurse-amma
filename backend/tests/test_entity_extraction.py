from app.services.entity_extraction import extract_laboratory_entities


def test_extracts_multiple_laboratory_results():
    text = """
    Name: Glucose
    Result: 95
    Unit: mg/dL

    Name: Hemoglobin
    Result: 12.5
    Unit: g/dL
    """

    results = extract_laboratory_entities(text=text, page_number=2)

    assert len(results) == 2
    assert results[0]["name"] == "Glucose"
    assert results[0]["value"] == "95"
    assert results[0]["unit"] == "mg/dL"
    assert results[1]["name"] == "Hemoglobin"
    assert results[1]["value"] == "12.5"
    assert results[1]["unit"] == "g/dL"
    assert results[0]["source_page"] == 2
    assert all(item["verification_status"] == "unverified" for item in results)


def test_returns_empty_list_for_unrecognized_text():
    text = "This document contains no matching laboratory fields."
    assert extract_laboratory_entities(text) == []


def test_extracts_rows_from_pdf_table_text_with_reference_ranges():
    text = """
    SYNTHETIC CLINICAL LAB REPORT
    Laboratory Results
    Test
    Result
    Unit
    Reference Range
    Hemoglobin
    13.8
    g/dL
    12.0 - 16.0
    White Blood Cell Count
    6.4
    10^9/L
    4.0 - 11.0
    Platelet Count
    250
    10^9/L
    150 - 400
    Fasting Glucose
    92
    mg/dL
    70 - 99
    Creatinine
    0.9
    mg/dL
    0.6 - 1.2
    Interpretation
    This file contains fabricated values solely for software integration testing.
    """

    results = extract_laboratory_entities(text=text, page_number=1)

    assert len(results) == 5
    assert [item["name"] for item in results] == [
        "Hemoglobin",
        "White Blood Cell Count",
        "Platelet Count",
        "Fasting Glucose",
        "Creatinine",
    ]
    assert [item["value"] for item in results] == ["13.8", "6.4", "250", "92", "0.9"]
    assert results[0]["unit"] == "g/dL"
    assert results[0]["reference_range"] == "12.0 - 16.0"
    assert results[1]["unit"] == "10^9/L"
    assert results[1]["reference_range"] == "4.0 - 11.0"
    assert all(item["source_page"] == 1 for item in results)
    assert all(item["verification_status"] == "unverified" for item in results)


def test_extracts_qualitative_result_from_table():
    text = """
    Test
    Result
    Unit
    Blood Culture
    Negative
    status
    """
    results = extract_laboratory_entities(text)
    assert len(results) == 1
    assert results[0]["name"] == "Blood Culture"
    assert results[0]["value"] == "Negative"
    assert results[0]["unit"] == "status"
    assert results[0]["verification_status"] == "unverified"
