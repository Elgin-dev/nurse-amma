import pytest
from app.schemas.clinical_history import PatientResponseInput, Duration, DurationUnit, SymptomDetails
from app.services.question_engine import QuestionEngine
from app.services.red_flag_service import RedFlagService


def test_question_engine_fever_pathway():
    # Test first question for fever
    q1 = QuestionEngine.get_next_question("fever", [])
    assert q1.question_key == "duration"
    assert q1.is_complete is False

    # Test progression when duration is answered
    q2 = QuestionEngine.get_next_question("fever", ["duration"])
    assert q2.question_key == "associated"

    # Test completed pathway
    q_done = QuestionEngine.get_next_question("fever", ["duration", "associated"])
    assert q_done.is_complete is True


def test_red_flag_detection_high_risk_fever():
    payload = PatientResponseInput(
        consultation_id="CONSULT-101",
        chief_complaint="fever",
        symptom_details=SymptomDetails(
            duration=Duration(value=4, unit=DurationUnit.DAYS)
        ),
        associated_symptoms=["Altered Sensorium", "Chills"],
    )

    alerts = RedFlagService.evaluate_red_flags(payload)
    assert len(alerts) == 1
    assert alerts[0].flag_id == "RF-001"
    assert alerts[0].severity == "high"


def test_red_flag_detection_chest_pain():
    payload = PatientResponseInput(
        consultation_id="CONSULT-102",
        chief_complaint="cough",
        symptom_details=SymptomDetails(),
        associated_symptoms=["Chest Pain"],
    )

    alerts = RedFlagService.evaluate_red_flags(payload)
    assert len(alerts) == 1
    assert alerts[0].flag_id == "RF-002"