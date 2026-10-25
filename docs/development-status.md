# Nurse Amma — Development Status

**Last updated:** 25 October 2026
**Project:** Nurse Amma — AI-Powered Multimodal Clinical History-Taking and Medical Document Intelligence System
**Responsible member:** Member 3 — Backend, Database, Frontend and Integration
**Repository:** [Elgin-dev/nurse-amma](https://github.com/Elgin-dev/nurse-amma)
**Current local branch:** `integration/backend-foundation`
**Integration commit:** `03c9801` — `merge: integrate backend foundation with speech and NLP`
**Publication status:** Integration branch has been pushed to GitHub and **PR #1 is open**.

> **Current status:** The database foundation and the latest speech/NLP code are integrated on `integration/backend-foundation` and published for review in PR #1. The clinical-history router validates consultation UUIDs and preserves the speech endpoint. The latest local test run reports **17 passed, 1 non-blocking warning**. Clinical-history responses and summaries are still not persisted. This is not yet an end-to-end application.

---

## 1. Project Overview

Nurse Amma is an AI-assisted pre-consultation healthcare application intended to collect patient-reported history, process medical documents, organize clinical information into a timeline, identify configured red flags, and prepare a draft summary for healthcare professional review.

**Target workflow:**

`Patient intake → Clinical history → Document processing → Medical timeline → Draft clinical summary → Healthcare professional review`

The application organizes information; it does not autonomously diagnose diseases or prescribe treatment. Use synthetic patients and documents during development. Never commit real patient information, private medical documents, credentials, or API keys.

### Team ownership

| Member | Ownership |
|---|---|
| Member 1 | Clinical history, conversational interaction, adaptive questioning, speech/NLP module, and red-flag rules |
| Member 2 | Medical document processing, OCR, entity extraction, and timeline generation |
| Member 3 | Shared backend, database and migrations, patient/consultation APIs, frontend, doctor dashboard, and system integration |

Members should maintain their own modules and coordinate shared schemas, models, and API changes rather than duplicate each other's work.

---

## 2. Current Remote and Local Git State

The following state was verified locally after fetching the remote branches. Re-run `git fetch --all --prune` before relying on these remote references for a later integration decision.

| Branch/reference | Commit | Meaning |
|---|---|---|
| `origin/main` | `6866fc6` | Latest fetched main; includes the speech endpoint and NLP extractor |
| `origin/feature/backend-foundation` | `23afeab` | Database foundation, patient/consultation APIs, migration, and health check |
| `origin/feature/clinical-history` | `9c613ce` | Earlier clinical-history implementation; ancestor of the fetched `main` |
| Local `integration/backend-foundation` | `03c9801` | Local merge commit integrating backend foundation with the fetched main branch |

### Pending local work

- `backend/app/routers/clinical_history.py` — reconciled to validate consultation UUIDs while retaining `/process-speech`; pushed on `integration/backend-foundation` and under review in PR #1.
- `backend/tests/test_clinical_history_api.py` — API integration tests were committed and pushed with the clinical-history validation changes.
- `docs/development-status.md` — kept current as integration and review status changes.
- `stash@{0}` — retained as a recovery copy of the earlier clinical-history validation change. Do not drop it until the final changes are committed, pushed, and verified on GitHub.

The integration branch was created from the fetched `origin/main`; the backend-foundation changes merged without conflicts, and merge commit `03c9801` was created locally. The branch is now published and PR #1 is open for review. Do not push directly to `main`.

---

## 3. Technology Stack and Local Environment

| Component | Technology/status |
|---|---|
| Backend | Python 3.11.9, FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL 18.6, Psycopg 3 |
| ORM and migrations | SQLAlchemy 2.x, Alembic |
| Tests | pytest, FastAPI TestClient, HTTPX |
| Speech/NLP | Speech route and deterministic NLP extractor are present; Whisper is optional and not installed in the current `.venv` |
| Document processing | Dependencies are declared, but the upload/OCR/entity pipeline is not implemented |
| Frontend target | React, TypeScript, Vite; not yet implemented |
| Configuration | Local `.env` (ignored by Git) and `.env.example` (tracked on the integration branch) |

### Environment notes

- Use the repository's `.venv` with Python **3.11.9**. The default system `python` has been observed to resolve to Python 3.10.11 and does not have the project test/migration packages installed.
- `.env` contains local database configuration and must never be committed or copied into the status document.
- `.venv/`, `.env`, bytecode, and test caches are local/generated files and should remain untracked.
- Core dependencies are installed in `.venv`; `pip check` previously reported no broken requirements.
- The optional AI dependencies (including `openai-whisper` and PyTorch) are not installed. Core backend tests should not require them. Install optional AI packages only when real inference/OCR implementation is scheduled and after checking platform compatibility.

---

## 4. Current Implementation Matrix

| Component | Status | Evidence / limitation |
|---|---|---|
| Central FastAPI application | Implemented and locally inspected | `backend/app/main.py`; one shared application |
| Root endpoint | Implemented | `GET /` |
| Database-backed health check | Implemented and tested | Executes `SELECT 1`; returns HTTP 503 on SQLAlchemy database errors |
| Environment configuration | Implemented | `backend/app/core/config.py`, `.env.example` |
| SQLAlchemy session and base | Implemented | `backend/app/db/session.py`, `backend/app/db/base.py` |
| Patient model/API | Implemented and locally tested | UUID model, create/retrieve endpoints |
| Consultation model/API | Implemented and locally tested | UUID model, patient foreign key, create/retrieve endpoints |
| Initial Alembic migration | Applied locally | Revision `14b36a1e2a74`; creates `patients` and `consultations` tables and patient index |
| Clinical question engine | Implemented; unit-tested | Deterministic fever, cough, and abdominal-pain pathways plus fallback |
| Red-flag service | Partially implemented; unit-tested | Two initial hard-coded rules; requires broader testing and agreed clinical review |
| NLP extractor | Implemented, limited scope | Deterministic duration/severity extraction; must not turn unknown values into asserted facts |
| Speech endpoint | Implemented in code | `POST /api/v1/consultations/{consultation_id}/process-speech`; returns text fallback if transcription is unavailable |
| Whisper loading | Refactored to lazy-load | Core imports work without Whisper. Real transcription has not been verified because Whisper is not installed |
| Clinical-history consultation validation | Implemented and pushed | UUID consultation IDs are checked against the database; missing consultations return 404 |
| Summary body/path ID consistency | Implemented and pushed | Conflicting or invalid body IDs are rejected with HTTP 422 |
| Clinical-history response persistence | Not implemented | No response model/migration or saved-response workflow |
| Summary/red-flag persistence | Not implemented | Draft summary and flags are returned in memory only |
| Summary retrieval/update/review | Not implemented | No saved-summary GET/PATCH or professional review API |
| Document upload/storage/OCR | Not implemented | Dependencies only; no completed document pipeline |
| Medical entity provenance and timeline | Not implemented | No persistent entities/timeline models or APIs |
| React patient interface | Not implemented | No `frontend/` application yet |
| Doctor dashboard | Not implemented | No frontend or review workflow |
| Authentication/authorization | Not implemented | Required before exposing real patient data or review operations |
| End-to-end workflow | Not implemented | No test covering the full history-to-document-to-summary-to-review flow |
| README/onboarding | Incomplete | Root README needs reproducible backend, database, migration, and eventual frontend setup instructions |
| CI | Not evidenced | No verified workflow running tests and migration checks |

---

## 5. Current API Surface

OpenAPI inspection on the integration branch showed these paths:

| Method | Path | Purpose/status |
|---|---|---|
| `GET` | `/` | Application information |
| `GET` | `/health` | Database connectivity check |
| `POST` | `/api/v1/patients` | Create a patient |
| `GET` | `/api/v1/patients/{patient_id}` | Retrieve a patient |
| `POST` | `/api/v1/consultations` | Create a consultation for an existing patient |
| `GET` | `/api/v1/consultations/{consultation_id}` | Retrieve a consultation |
| `POST` | `/api/v1/consultations/{consultation_id}/next-question` | Generate next clinical-history question; validates consultation locally |
| `POST` | `/api/v1/consultations/{consultation_id}/summary` | Generate an in-memory draft summary; validates consultation and rejects mismatched IDs locally |
| `POST` | `/api/v1/consultations/{consultation_id}/process-speech` | Process uploaded audio or return text fallback; consultation validation added locally |

The endpoints above were confirmed in the local OpenAPI path list. This does not mean the full clinical workflow is complete. The summary endpoint still does not persist a saved draft, and real Whisper inference remains unverified.

---

## 6. Latest Verification Results

**Last recorded local verification:** 24 October 2026.

| Check | Result |
|---|---|
| Full test suite on integrated local branch | `17 passed, 1 warning` |
| Warning | Non-blocking Starlette/HTTPX deprecation warning from `TestClient` |
| OpenAPI path inspection | Patient, consultation, clinical-history, speech, root, and health paths found |
| PostgreSQL connectivity | Previously verified using the project `.venv` |
| Alembic current revision | `14b36a1e2a74 (head)` |
| `alembic check` | `No new upgrade operations detected` |
| `git diff --check` | Passed after the latest documentation whitespace fix, before final documentation replacement |
| Clean-database migration test from scratch | Not yet verified |
| Real Whisper transcription | Not verified; optional Whisper package/model unavailable |
| End-to-end frontend workflow | Not implemented / not verified |

The tests use isolated SQLite fixtures for API tests. Passing these tests does not replace a PostgreSQL migration/CRUD test or prove that the complete application works end-to-end.

---

## 7. Development History

### Milestone 0 — Repository and environment setup

**Status:** Complete.

- Cloned the shared repository.
- Created the Python `.venv` and configured local PostgreSQL.
- Started the FastAPI application and ran the initial clinical-history tests.

### Milestone 1 — Database connectivity foundation

**Status:** Committed and pushed on `feature/backend-foundation`.

- Commit: `cead837` — `feat: establish database connectivity foundation`
- Added app settings, SQLAlchemy base/session, and `.env.example`.
- Verified a database connection using SQLAlchemy.

### Milestone 2 — Patient and consultation persistence

**Status:** Committed and pushed on `feature/backend-foundation`.

- Commit: `8735b7f` — `feat: add patient and consultation persistence`
- Added Patient and Consultation models, schemas, APIs, tests, and the initial Alembic migration.
- Manually tested patient and consultation creation/retrieval with synthetic data.

### Milestone 3 — Database health check

**Status:** Committed and pushed on `feature/backend-foundation`.

- Commit: `23afeab` — `fix: report actual database health`
- `/health` now performs a real database query and reports HTTP 503 when the database check fails.
- Added tests for healthy and unavailable database behavior.

### Milestone 4 — Local backend + speech/NLP integration

**Status:** Merge and follow-up clinical-history validation changes committed and pushed; PR #1 is open.

- Started a new `integration/backend-foundation` branch from fetched `origin/main` at `6866fc6`.
- Merged the backend foundation without file conflicts.
- Merge commit: `03c9801` — `merge: integrate backend foundation with speech and NLP`.
- Retained the speech endpoint and refactored Whisper to load lazily rather than at import time.
- Replaced the speech test's real-model assumption with a deterministic mocked model test and removed the dependency on `pytest-asyncio`.
- Reconciled clinical-history routes to validate consultation UUIDs while retaining speech processing.
- Local test suite reports 17 passed, with one non-blocking warning.

---

## 8. Current Known Gaps

### P0 — Must address next

1. Agree on shared clinical-history input/response, summary, provenance, and review-state contracts with Member 1.
2. Persist clinical-history responses, generated summaries, and red-flag results in PostgreSQL.
3. Add summary retrieval and persistence-focused tests.
4. Address review feedback on PR #1 and keep the integration branch up to date with verified fixes.
5. Reconcile `docs/project-specification.md` examples and folder layout with the canonical UUID/API convention and actual `backend/alembic/` location.

### P1 — After clinical-history persistence

1. Coordinate with Member 2 on document metadata, file storage, OCR output, entity provenance, errors, and timeline contracts.
2. Implement document upload validation and controlled storage.
3. Implement text extraction/OCR and source-linked medical entities.
4. Add PostgreSQL integration tests and fresh-database migration checks.
5. Expand README setup instructions and define a repeatable dependency installation workflow.

### P2 — User interface and access control

1. Build a React/TypeScript/Vite patient-intake flow after the API contracts stabilize.
2. Build the doctor dashboard for summaries, red flags, sources, corrections, and review status.
3. Implement authentication and authorization before any use with real patient data.
4. Add a CI workflow and end-to-end test coverage.

---

## 9. Next Development Milestone — Persistent Clinical History

### Objective

Complete one durable workflow:

`Existing consultation → structured patient responses → generated draft → persisted summary and red flags → retrieve saved draft`

### Required design agreement

Coordinate with Member 1 before adding shared database models. Confirm:

- Canonical UUID identifiers and whether the URL is the sole authoritative consultation ID.
- Whether to store each answer as a separate row, a structured payload per submission, or both.
- Summary schema and versioning behavior when a summary is regenerated.
- Shared provenance states for patient-reported, document-extracted, AI-generated, unknown, and clinician-verified information.
- Allowed review statuses and who may change them.

Proposed initial approach: store a structured response snapshot and generated summary as versioned records linked by foreign key to the existing consultation; keep provenance and review status explicit. Finalize this with the module owner before creating the migration.

### Acceptance criteria

- A non-existent consultation returns HTTP 404 from relevant history and speech operations.
- Invalid/mismatched identifiers are rejected consistently.
- Submitted history and generated summaries are stored and can be retrieved after separate requests.
- Red-flag output is stored with its explanation and review state.
- A new draft is not automatically marked clinician-approved.
- Tests cover successful persistence, retrieval, invalid consultations, ID conflicts, and rollback behavior.
- A PostgreSQL migration is applied and checked locally.
- All existing tests remain green.

---

## 10. Local Verification Commands

Run these from PowerShell. Use the project interpreter explicitly if the system Python points to a different version.

### Full test suite

```powershell
cd C:\Projects\nurse-amma\backend
& "..\.venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider
```

### Migration verification

```powershell
cd C:\Projects\nurse-amma\backend
& "..\.venv\Scripts\python.exe" -m alembic current
& "..\.venv\Scripts\python.exe" -m alembic heads
& "..\.venv\Scripts\python.exe" -m alembic check
```

Expected current revision for the existing foundation migration: `14b36a1e2a74`.

### Start the API

```powershell
cd C:\Projects\nurse-amma\backend
& "..\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

### Git review before a commit

```powershell
cd C:\Projects\nurse-amma
git status
git diff --check
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

Never stage `.env`, `.venv`, caches, secrets, API keys, or real patient information.

---

## 11. Team Coordination Rules

- Keep one FastAPI app in `backend/app/main.py` and one shared database configuration/session.
- Use SQLAlchemy models and Alembic migrations for database schema changes.
- Agree on shared schemas and identifiers with the owning member before changing cross-module contracts.
- Member 1 owns clinical conversation logic and red-flag rule content; coordinate shared persistence with them rather than rewriting their module without review.
- Member 2 owns document processing logic; agree on document storage, entity output, and source references before implementing dependent database/API work.
- Keep AI-generated information distinct from patient-reported, document-extracted, unknown, and clinician-verified information.
- Use synthetic records and synthetic medical documents only.
- Run tests before committing; inspect all staged files.
- Do not push ordinary work directly to `main`. Use the integration branch and a reviewed pull request.
- Update this document after each meaningful, verified milestone; preserve historical test counts as historical records rather than rewriting them.

---

## 12. Immediate Next Actions

1. Address all open PR #1 review findings and push verified fixes on `integration/backend-foundation`.
2. Rerun the backend test suite after each meaningful fix batch.
3. Keep `stash@{0}` until review feedback is resolved and remote verification is complete; then decide whether to drop the recovery stash.
4. Ask Member 1 to review the proposed clinical-history persistence contract before creating the next migration.
5. Proceed with persistence implementation only after review feedback is fully resolved.

**Primary success criterion:** a reproducible, tested, integrated application—not merely separate modules that exist in the repository.
