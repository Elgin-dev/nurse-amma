from typing import Dict, Any
from app.schemas.clinical_history import NextQuestionResponse

# Symptom decision pathways
PATHWAYS = {
    "fever": [
        {
            "key": "duration",
            "text": "How many days have you had the fever?",
            "type": "choice",
            "options": ["1-2 days", "3-5 days", "More than a week"],
        },
        {
            "key": "associated",
            "text": "Do you have any of these associated symptoms?",
            "type": "choice",
            "options": ["Chills/Rigors", "Severe Headache", "Body Ache", "Rashes", "None"],
        },
    ],
    "cough": [
        {
            "key": "type",
            "text": "Is your cough dry or producing sputum/phlegm?",
            "type": "choice",
            "options": ["Dry cough", "Productive (with phlegm)"],
        },
        {
            "key": "breathlessness",
            "text": "Are you experiencing any shortness of breath?",
            "type": "choice",
            "options": ["No", "Mild with exertion", "Severe at rest"],
        },
    ],
    "abdominal pain": [
        {
            "key": "location",
            "text": "Where is the pain located?",
            "type": "choice",
            "options": ["Upper abdomen", "Lower right side", "Lower left side", "All over"],
        },
        {
            "key": "associated",
            "text": "Do you have nausea, vomiting, or fever?",
            "type": "choice",
            "options": ["Nausea/Vomiting", "Fever", "Both", "Neither"],
        },
    ],
}


class QuestionEngine:
    @staticmethod
    def get_next_question(chief_complaint: str, answered_keys: list[str]) -> NextQuestionResponse:
        complaint_lower = chief_complaint.lower()
        pathway = PATHWAYS.get(complaint_lower)

        if not pathway:
            # Fallback for unconfigured chief complaints
            return NextQuestionResponse(
                question_key="general_details",
                question_text=f"Please describe your {chief_complaint} in detail (onset, duration, severity).",
                response_type="text",
                is_complete=True,
            )

        for q in pathway:
            if q["key"] not in answered_keys:
                return NextQuestionResponse(
                    question_key=q["key"],
                    question_text=q["text"],
                    response_type=q["type"],
                    options=q.get("options"),
                    is_complete=False,
                )

        return NextQuestionResponse(
            question_key="completed",
            question_text="Thank you. All clinical history questions for this pathway are complete.",
            response_type="text",
            is_complete=True,
        )