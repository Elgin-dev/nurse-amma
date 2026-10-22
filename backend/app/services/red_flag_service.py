from typing import List
from app.schemas.clinical_history import PatientResponseInput, RedFlagAlert


class RedFlagService:
    @staticmethod
    def evaluate_red_flags(data: PatientResponseInput) -> List[RedFlagAlert]:
        alerts = []

        # Rule 1: High risk fever duration
        if data.chief_complaint.lower() == "fever":
            if data.symptom_details.duration and data.symptom_details.duration.value >= 3:
                if "altered sensorium" in [s.lower() for s in data.associated_symptoms] or "confusion" in [s.lower() for s in data.associated_symptoms]:
                    alerts.append(
                        RedFlagAlert(
                            flag_id="RF-001",
                            severity="high",
                            trigger="Fever >= 3 days with cognitive/sensory alteration",
                            action_required="Immediate urgent triage and clinician evaluation required.",
                        )
                    )

        # Rule 2: Severe dyspnea / chest pain
        for symptom in data.associated_symptoms:
            if "chest pain" in symptom.lower() or "severe breathlessness" in symptom.lower():
                alerts.append(
                    RedFlagAlert(
                        flag_id="RF-002",
                        severity="high",
                        trigger=f"Reported critical symptom: {symptom}",
                        action_required="Escalate for immediate emergency medical assessment.",
                    )
                )

        return alerts