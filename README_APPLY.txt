Nurse Amma: next-question and answer persistence fix

Apply this ZIP to the repository root (C:\Projects\nurse-amma):
1. Extract, allowing these files to overwrite: frontend/src/App.tsx and backend/app/schemas/clinical_history.py.
2. From the repository root, run: & ".\.venv\Scripts\python.exe" .\apply_next_question_fix.py
   The script narrowly patches the summary text in backend/app/routers/clinical_history.py and appends a regression test. It aborts if the expected code block is not found.
3. Validate in backend: ..\.venv\Scripts\python.exe -m pytest .\tests\test_clinical_history_api.py -q; then run the full test suite and alembic check.
4. Validate in frontend: npm run build.

It fixes the query-string contract for POST /next-question, preserves the question display after saving a response, and stores question_key, question_text, and answer_text in the existing JSON history payload. No database migration is expected because the payload is JSON.
