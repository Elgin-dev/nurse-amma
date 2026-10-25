import re


def extract_laboratory_entities(
    text: str,
    page_number: int = 1,
) -> list[dict]:

    entities = []

    # Find each laboratory test block.
    pattern = re.compile(
        r"Name\s*:\s*(?P<name>[^\r\n]+)\s*\r?\n"
        r"\s*Result\s*:\s*(?P<value>[^\r\n]+)\s*\r?\n"
        r"\s*Unit\s*:\s*(?P<unit>[^\r\n]+)",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):

        name = match.group("name").strip()
        value = match.group("value").strip()
        unit = match.group("unit").strip()

        # Avoid returning empty fields.
        if not name or not value or not unit:
            continue

        entities.append({
            "entity_type": "laboratory_result",
            "name": name,
            "value": value,
            "unit": unit,
            "source_page": page_number,
            "source_text": match.group(0).strip(),
            "verification_status": "unverified",
        })

    return entities