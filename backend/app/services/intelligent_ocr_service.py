import json
import logging
import os
from typing import Any

import httpx
import pymupdf

from app.core.config import settings
from app.schemas.intelligent_ocr import (
    IntelligentDocumentExtraction,
    LabResult,
    PatientDemographics,
    PrescribedMedication,
)
from app.services.ocr_service import extract_image_text_from_bytes


logger = logging.getLogger(__name__)
OLLAMA_ENDPOINT = os.getenv(
    "OLLAMA_CHAT_URL",
    settings.ollama_chat_url,
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", settings.ollama_model)
SYSTEM_INSTRUCTION = """You structure OCR text from medical documents for clinician review.
Return STRICT JSON only, with keys: cleaned_text, patient_demographics, prescribed_medications, lab_results, clinical_diagnosis, doctor_notes.

RULES:
1. patient_demographics: Extract name, age, gender. Use null if missing.
2. prescribed_medications: Extract ALL medications. They often appear in bullet points (•) or start with "Tab." or "Cap.". Extract the drug_name, dosage (e.g., 500 mg), and frequency (e.g., twice daily). Do not skip any.
3. lab_results: Look for "Test:", "Result:", "Unit:", "Reference Range:". Extract test_name, value, unit, reference_range, abnormality_flag.
4. clinical_diagnosis: Extract any explicitly stated diagnoses (e.g., "Type 2 Diabetes").
5. doctor_notes: Extract the doctor's final notes.
Do not invent or infer missing medical facts. Preserve uncertainty."""


class IntelligentOCRService:
    @classmethod
    def process_image(
        cls,
        image_bytes: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """OCR an uploaded image and structure it using local Ollama when available."""
        ocr_result = extract_image_text_from_bytes(image_bytes)
        raw_text = ocr_result["text"]
        try:
            structured = cls._structure_with_ollama(raw_text)
            source = "ollama"
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            json.JSONDecodeError,
        ):
            logger.warning(
                "Ollama document structuring failed; using deterministic extraction.",
                exc_info=True,
            )
            structured = cls._offline_structure(raw_text)
            source = "offline"

        return {
            "filename": filename,
            "extraction_method": "Tesseract OCR",
            "raw_ocr_text": raw_text,
            "structured_data": {
                **structured,
                "fhir_bundle": cls.generate_fhir_bundle(structured)
            },
            "verification_status": "unverified",
            "structuring_source": source,
            "page_count": 1,
        }
    @classmethod
    def generate_fhir_bundle(cls, structured_data: dict) -> dict:
        """Convert extracted AI data into an HL7 FHIR Bundle."""
        entries = []

        # 1. Patient Demographics
        demo = structured_data.get("patient_demographics", {})
        if demo.get("name"):
            entries.append({
                "resource": {
                    "resourceType": "Patient",
                    "name": [{"text": demo.get("name")}],
                    "gender": demo.get("gender", "unknown").lower(),
                }
            })

        # 2. Prescribed Medications
        for med in structured_data.get("prescribed_medications", []):
            entries.append({
                "resource": {
                    "resourceType": "MedicationRequest",
                    "status": "active",
                    "intent": "order",
                    "medicationCodeableConcept": {"text": med.get("drug_name") or "Unknown"},
                    "dosageInstruction": [{
                        "text": f"{med.get('dosage', '')} - {med.get('frequency', '')}".strip()
                    }]
                }
            })

        # 3. Lab Results
        for lab in structured_data.get("lab_results", []):
            entries.append({
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": lab.get("test_name") or "Unknown Test"},
                    "valueString": f"{lab.get('value', '')} {lab.get('unit', '')}".strip(),
                    "interpretation": [{"text": str(lab.get("abnormality_flag"))}]
                }
            })

        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": entries
        }
    @classmethod
    def process_pdf(
        cls,
        pdf_bytes: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """Extract text from a digital PDF and structure it using local Ollama."""
        try:
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
                raw_text = "\n".join(page.get_text("text") for page in doc)
                page_count = doc.page_count
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raw_text = ""
            page_count = 1

        try:
            structured = cls._structure_with_ollama(raw_text)
            source = "ollama"
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            json.JSONDecodeError,
        ):
            logger.warning(
                "Ollama PDF structuring failed; using deterministic extraction.",
                exc_info=True,
            )
            structured = cls._offline_structure(raw_text)
            source = "offline"

        return {
            "filename": filename,
            "extraction_method": "PDF text extraction",
            "raw_ocr_text": raw_text,
            "structured_data": {
                **structured,
                "fhir_bundle": cls.generate_fhir_bundle(structured)
            },
            "verification_status": "unverified",
            "structuring_source": source,
            "page_count": page_count,
        }

    @staticmethod
    def _structure_with_ollama(raw_text: str) -> dict[str, Any]:
        response = httpx.post(
            OLLAMA_ENDPOINT,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {
                        "role": "user",
                        "content": f"Structure this OCR text:\n\n{raw_text}",
                    },
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty document extraction")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama document response must be a JSON object")
        structured = IntelligentDocumentExtraction.model_validate(parsed).model_dump()
        offline = IntelligentOCRService._offline_structure(raw_text)

        demographics = structured["patient_demographics"]
        for field in ("name", "age", "gender"):
            if demographics[field] is None:
                demographics[field] = offline["patient_demographics"][field]

        for field in (
            "prescribed_medications",
            "lab_results",
            "clinical_diagnosis",
        ):
            if not structured[field]:
                structured[field] = offline[field]

        offline_labs = {
            result["test_name"].casefold(): result
            for result in offline["lab_results"]
        }
        for result in structured["lab_results"]:
            fallback = offline_labs.get(result["test_name"].casefold())
            if fallback is not None and result["unit"] is None and fallback["unit"]:
                result["value"] = fallback["value"]
                result["unit"] = fallback["unit"]
                if result["reference_range"] is None:
                    result["reference_range"] = fallback["reference_range"]
                if result["abnormality_flag"] is None:
                    result["abnormality_flag"] = fallback["abnormality_flag"]

        return structured

    @staticmethod
    def _offline_structure(raw_text: str) -> dict[str, Any]:
        """Return conservative, explicitly supported fields when Ollama is offline."""
        import re

        name_match = re.search(
            r"(?im)^\s*(?:patient\s*name|name)\s*[:\-]\s*(.+?)\s*$",
            raw_text,
        )
        age_match = re.search(
            r"(?im)^\s*age\s*[:\-]\s*(\d{1,3}\s*(?:years?|yrs?)?)\s*$",
            raw_text,
        )
        gender_match = re.search(
            r"(?im)^\s*(?:gender|sex)\s*[:\-]\s*(male|female|other)\s*$",
            raw_text,
        )
        diagnoses = re.findall(
            r"(?im)^\s*(?:diagnosis|impression)\s*[:\-]\s*(.+?)\s*$",
            raw_text,
        )
        notes_match = re.search(
            r"(?im)^\s*(?:doctor'?s?\s*notes?|clinical\s*notes?)\s*[:\-]\s*(.+?)\s*$",
            raw_text,
        )

        extracted = IntelligentDocumentExtraction(
            cleaned_text=raw_text.strip(),
            patient_demographics=PatientDemographics(
                name=name_match.group(1).strip() if name_match else None,
                age=age_match.group(1).strip() if age_match else None,
                gender=gender_match.group(1).strip() if gender_match else None,
            ),
            prescribed_medications=IntelligentOCRService._extract_medications(raw_text),
            lab_results=IntelligentOCRService._extract_lab_results(raw_text),
            clinical_diagnosis=[diagnosis.strip() for diagnosis in diagnoses],
            doctor_notes=notes_match.group(1).strip() if notes_match else None,
        )
        return extracted.model_dump()

    @staticmethod
    def _extract_medications(raw_text: str) -> list[PrescribedMedication]:
        import re
        medications = []
        # This regex now looks for "Tab.", "Cap.", or bullets, followed by drug name and dosage
        pattern = re.compile(
            r"(?im)^\s*(?:•|-|\*|Tab\.?|Cap\.?)?\s*"
            r"([A-Za-z][A-Za-z0-9 -]{2,50}?)\s+"
            r"(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?))"
            r"(?:\s*[-–]\s*(.+))?$"
        )
        for match in pattern.finditer(raw_text):
            drug = match.group(1).strip()
            if drug.casefold() in {"patient name", "diagnosis", "impression", "result"}:
                continue
            medications.append(
                PrescribedMedication(
                    drug_name=drug,
                    dosage=match.group(2).strip(),
                    frequency=match.group(3).strip() if match.group(3) else None,
                )
            )
        return medications

    @staticmethod
    def _extract_lab_results(raw_text: str) -> list[LabResult]:
        import re

        results = []
        pattern = re.compile(
            r"(?im)^\s*([A-Za-z][A-Za-z0-9 /()-]{1,50}?)\s*[:\-]\s*"
            r"([<>]?\s*\d+(?:\.\d+)?)\s*"
            r"([A-Za-z/%µμ]+(?:/[A-Za-z]+)?)?"
            r"(?:\s*\(?\s*(?:ref(?:erence)?\.?\s*)?range\s*[:=]?\s*"
            r"([0-9.<>=\-\s]+)\)?)?"
            r"(?:\s+(high|low|abnormal|normal))?\s*$"
        )
        excluded_labels = {
            "name",
            "patient name",
            "age",
            "gender",
            "sex",
            "diagnosis",
            "impression",
            "doctor notes",
            "clinical notes",
        }
        for match in pattern.finditer(raw_text):
            test_name = match.group(1).strip()
            if test_name.casefold() in excluded_labels:
                continue
            abnormality = match.group(5)
            results.append(
                LabResult(
                    test_name=test_name,
                    value=match.group(2).strip(),
                    unit=match.group(3).strip() if match.group(3) else None,
                    reference_range=match.group(4).strip() if match.group(4) else None,
                    abnormality_flag=(
                        abnormality.casefold() in {"high", "low", "abnormal"}
                        if abnormality
                        else None
                    ),
                )
            )
        return results