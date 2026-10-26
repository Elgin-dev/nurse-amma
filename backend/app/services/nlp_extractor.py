import re

from app.schemas.clinical_history import SymptomDetails, Duration, DurationUnit

class NLPExtractor:
    @staticmethod
    def extract_symptom_details(patient_text: str) -> SymptomDetails:
        """
        Parses free-text responses using deterministic rules, with extensible 
        slots for LLM structured JSON output.
        """
        text_lower = patient_text.lower()
        duration_value = None
        duration_unit = DurationUnit.DAYS

        # Regex pattern matching for duration (e.g., "3 days", "2 weeks", "5 hours")
        duration_match = re.search(r"(\d+)\s*(hour|day|week|month)s?", text_lower)
        if duration_match:
            duration_value = int(duration_match.group(1))
            unit_str = duration_match.group(2)
            if "hour" in unit_str:
                duration_unit = DurationUnit.HOURS
            elif "week" in unit_str:
                duration_unit = DurationUnit.WEEKS
            elif "month" in unit_str:
                duration_unit = DurationUnit.MONTHS

        # Severity parsing
        severity = None
        if "severe" in text_lower or "high" in text_lower:
            severity = "severe"
        elif "moderate" in text_lower or "medium" in text_lower:
            severity = "moderate"
        elif "mild" in text_lower or "slight" in text_lower:
            severity = "mild"

        duration_obj = (
            Duration(value=duration_value, unit=duration_unit)
            if duration_value
            else None
        )

        return SymptomDetails(
            duration=duration_obj,
            severity=severity,
            progression="worsening" if "worse" in text_lower or "worsening" in text_lower else "constant"
        )