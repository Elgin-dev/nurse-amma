from pathlib import Path

ROOT = Path(__file__).resolve().parent
router_path = ROOT / "backend/app/routers/clinical_history.py"
test_path = ROOT / "backend/tests/test_clinical_history_api.py"

router = router_path.read_text(encoding="utf-8")
old_hpi = '    hpi = (\n        f"Patient reports {payload.chief_complaint} {duration_str}. "\n        f"Severity: {payload.symptom_details.severity or \'unspecified\'}. "\n        f"Progression: {payload.symptom_details.progression or \'unspecified\'}. "\n        f"Associated symptoms: {associated_symptoms_text}."\n    )'
new_hpi = '    hpi = (\n        f"Patient reports {payload.chief_complaint} {duration_str}. "\n        f"Severity: {payload.symptom_details.severity or \'unspecified\'}. "\n        f"Progression: {payload.symptom_details.progression or \'unspecified\'}. "\n        f"Associated symptoms: {associated_symptoms_text}."\n    )\n    if payload.answer_text:\n        question_label = payload.question_text or "the clinical follow-up question"\n        hpi += f" Patient\'s answer to \'{question_label}\': {payload.answer_text}."'
if old_hpi in router:
    router = router.replace(old_hpi, new_hpi, 1)
    router_path.write_text(router, encoding="utf-8")
    print("Updated summary generation to include the saved patient answer.")
elif new_hpi in router:
    print("Summary answer handling already exists; router left unchanged.")
else:
    raise SystemExit("Expected HPI block not found. No router change was written; inspect clinical_history.py manually.")

tests = test_path.read_text(encoding="utf-8")
test_name = "test_follow_up_question_and_answer_are_persisted_and_summarized"
if f"def {test_name}(" not in tests:
    tests = tests.rstrip() + '\n\n\ndef test_follow_up_question_and_answer_are_persisted_and_summarized(client):\n    consultation_id = create_consultation(client)\n    payload = history_payload(consultation_id)\n    payload.update({\n        "question_key": "duration",\n        "question_text": "How long have you had the fever?",\n        "answer_text": "Two days, with mild body aches.",\n    })\n\n    saved = client.post(\n        f"/api/v1/consultations/{consultation_id}/responses",\n        json=payload,\n    )\n    assert saved.status_code == 201, saved.text\n    saved_payload = saved.json()["payload"]\n    assert saved_payload["question_key"] == "duration"\n    assert saved_payload["question_text"] == "How long have you had the fever?"\n    assert saved_payload["answer_text"] == "Two days, with mild body aches."\n    assert saved_payload["source"] == "patient_reported"\n\n    summary = client.post(\n        f"/api/v1/consultations/{consultation_id}/summary",\n        json=payload,\n    )\n    assert summary.status_code == 200, summary.text\n    assert "Two days, with mild body aches." in summary.json()["history_of_present_illness"]\n' + "\n"
    test_path.write_text(tests, encoding="utf-8")
    print("Added a regression test for follow-up answer persistence and summary inclusion.")
else:
    print("Regression test already exists; not adding a duplicate.")
