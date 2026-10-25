import re


# Retain support for the explicit multi-line format used by the original tests
# and parser integrations.
_BLOCK_PATTERN = re.compile(
    r"Name\s*:\s*(?P<name>[^\r\n]+)\s*\r?\n"
    r"\s*Result\s*:\s*(?P<value>[^\r\n]+)\s*\r?\n"
    r"\s*Unit\s*:\s*(?P<unit>[^\r\n]+)",
    re.IGNORECASE,
)

_NUMERIC_RESULT = re.compile(
    r"^[<>≤≥]?\s*[-+]?\d+(?:[.,]\d+)?"
    r"(?:\s*(?:x|×)\s*10\s*\^?\s*[-+]?\d+)?\s*%?$",
    re.IGNORECASE,
)
_QUALITATIVE_RESULTS = {
    "positive", "negative", "reactive", "non-reactive", "nonreactive",
    "detected", "not detected", "present", "absent", "normal", "abnormal",
    "trace", "none detected", "indeterminate",
}
_UNIT_LINE = re.compile(r"^[A-Za-zµμ0-9%/.*^()\- ]{1,24}$")
_TABLE_HEADERS = {"reference range", "reference interval"}


def _is_result(value: str) -> bool:
    normalized = value.strip().casefold()
    return bool(_NUMERIC_RESULT.fullmatch(normalized)) or normalized in _QUALITATIVE_RESULTS


def _is_unit(unit: str) -> bool:
    normalized = unit.strip()
    return bool(_UNIT_LINE.fullmatch(normalized)) and any(ch.isalpha() for ch in normalized)


def _entity(
    name: str,
    value: str,
    unit: str,
    page_number: int,
    source_text: str,
    reference_range: str | None = None,
) -> dict:
    item = {
        "entity_type": "laboratory_result",
        "name": name.strip(),
        "value": value.strip(),
        "unit": unit.strip(),
        "source_page": page_number,
        "source_text": source_text.strip(),
        "verification_status": "unverified",
    }
    if reference_range:
        item["reference_range"] = reference_range.strip()
    return item


def extract_laboratory_entities(
    text: str,
    page_number: int = 1,
) -> list[dict]:
    """Extract laboratory-result entities from supported text layouts.

    Supports:
    1. Explicit blocks: Name: ..., Result: ..., Unit: ...
    2. Text-extracted tables with a Test / Result / Unit header and optional
       Reference Range column. Values remain unverified and are not clinical
       interpretations.
    """
    entities: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    # Format 1: labelled blocks (backwards compatible).
    for match in _BLOCK_PATTERN.finditer(text):
        name = match.group("name").strip()
        value = match.group("value").strip()
        unit = match.group("unit").strip()
        if not name or not value or not unit:
            continue
        key = (name.casefold(), value.casefold(), unit.casefold())
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            _entity(name, value, unit, page_number, match.group(0))
        )

    # Format 2: PDF text extraction where each table cell becomes its own line.
    # Blank lines are removed, but line order is retained.
    lines = [line.strip() for line in text.replace("\x00", "").splitlines() if line.strip()]
    for i in range(len(lines) - 2):
        if (
            lines[i].casefold() == "test"
            and lines[i + 1].casefold() == "result"
            and lines[i + 2].casefold() == "unit"
        ):
            has_reference_range = (
                i + 3 < len(lines) and lines[i + 3].casefold() in _TABLE_HEADERS
            )
            row_width = 4 if has_reference_range else 3
            cursor = i + (4 if has_reference_range else 3)

            while cursor + row_width <= len(lines):
                row = lines[cursor:cursor + row_width]
                name, value, unit = row[:3]
                reference_range = row[3] if has_reference_range else None

                # Stop at narrative text or another section; do not guess from
                # arbitrary nearby prose.
                if (
                    not name
                    or len(name) > 120
                    or not _is_result(value)
                    or not _is_unit(unit)
                ):
                    break

                key = (name.casefold(), value.casefold(), unit.casefold())
                if key not in seen:
                    seen.add(key)
                    source_text = "\n".join(row)
                    entities.append(
                        _entity(
                            name,
                            value,
                            unit,
                            page_number,
                            source_text,
                            reference_range,
                        )
                    )
                cursor += row_width
            break  # Process the first matching table header on this page.

    return entities
