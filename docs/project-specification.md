# NURSE AMMA

## Final Project Specification, Team Responsibilities, Technology Stack and GitHub Collaboration Plan

**Project category:** Artificial Intelligence / Machine Learning / Healthcare Technology

**Project title:** Nurse Amma — An AI-Powered Multimodal Clinical History-Taking and Medical Document Intelligence System for Pre-Consultation Healthcare

**Team size:** 3 members

**Repository:** One central GitHub repository shared by the team

**Application type:** Web-based patient intake and healthcare professional dashboard

**Primary development language:** Python and TypeScript

**Primary backend:** FastAPI

**Primary database:** PostgreSQL

**Primary AI components:** Conversational clinical history-taking, OCR, medical entity extraction, medical timeline generation, structured clinical summarization and red-flag identification

---

# 1. Project Overview

## 1.1 What is Nurse Amma?

Nurse Amma is an AI-assisted healthcare application designed to collect and organize patient information before a consultation with a healthcare professional.

In a conventional consultation, the doctor or clinical staff must ask questions about the patient's symptoms, previous illnesses, medications, allergies, surgeries and investigations. Patients may also bring previous prescriptions, laboratory reports, discharge summaries and other documents.

This information may be incomplete, difficult to understand or distributed across several documents.

Nurse Amma aims to organize this process into one workflow.

The patient can:

1. Register or start a consultation session.
2. Answer clinical questions through voice or touch.
3. Answer additional questions based on the reported symptoms.
4. Upload previous medical documents.
5. Allow the system to extract relevant information from those documents.
6. View or confirm the information collected, where appropriate.

The application then combines the available information into a medical timeline and structured clinical summary.

A healthcare professional can review the patient's information, inspect the original documents, correct mistakes and approve the final summary.

## 1.2 Main objective

The main objective is to build a working prototype that demonstrates the complete flow:

**Patient interaction → Clinical history collection → Medical document processing → Medical information extraction → Medical timeline → Red-flag identification → Structured clinical summary → Healthcare professional review**

The project is not merely a chatbot, an OCR tool or a medical records database. Its value comes from integrating these components into a single pre-consultation workflow.

## 1.3 Project boundaries

The initial version will:

- Collect patient-reported information.
- Process uploaded medical documents.
- Extract structured information.
- Organize historical events chronologically.
- Generate a draft clinical summary.
- Flag predefined potentially urgent symptoms.
- Store the information in a database.
- Provide a healthcare professional review interface.

The initial version will **not**:

- Independently diagnose diseases.
- Prescribe medicines.
- Automatically change a patient's medication.
- Replace emergency services or clinical triage.
- Claim that extracted information is always correct.
- Claim live integration with ABDM, ABHA or a hospital information system without the required access and implementation.

Use synthetic patient records and sample medical documents during development. Do not upload real patient health information to public AI tools or commit it to GitHub.

---

# 2. Final Technology Stack

All members must follow this common stack unless the team agrees to a documented change before implementation.

## 2.1 Frontend

| Technology                                      | Purpose                                                               |
| ----------------------------------------------- | --------------------------------------------------------------------- |
| React                                           | Build the user interface                                              |
| TypeScript                                      | Add type safety to frontend code                                      |
| Vite                                            | Frontend development server and build tool                            |
| CSS                                             | Styling and responsive layouts                                        |
| Fetch API                                       | Communicate with the backend                                          |
| Browser speech APIs or a backend speech service | Voice interaction, depending on browser support and selected provider |

The frontend will contain two main experiences:

**Patient interface**

- Patient identification or session creation
- Language selection
- Voice and touch interaction
- Clinical questions
- Document upload
- Review of collected information
- Completion status

**Healthcare professional interface**

- Patient/consultation list
- Clinical summary
- Medical timeline
- Extracted medication and investigation information
- Original uploaded documents
- Red-flag alerts
- Verification and correction controls

The initial version should use a responsive web application rather than separate Android and iOS applications.

## 2.2 Backend

| Technology          | Purpose                                  |
| ------------------- | ---------------------------------------- |
| Python 3.11 or 3.12 | Primary backend language                 |
| FastAPI             | REST API and module integration          |
| Pydantic            | Request validation and structured output |
| SQLAlchemy 2.x      | Database access and ORM                  |
| Alembic             | Database schema migrations               |
| Uvicorn             | Run the FastAPI application              |
| pytest              | Automated backend tests                  |
| HTTPX               | API integration testing                  |

All backend modules must connect to **one FastAPI application**. Individual team members must not create separate production entry points or duplicate the same backend.

Members can develop their modules independently, but they must integrate through the shared application and agreed API contracts.

## 2.3 Database

**PostgreSQL** will be the primary database.

It will store:

- Patient records
- Consultation sessions
- Patient responses
- Symptoms
- Medical history
- Medication information
- Allergies
- Investigations
- Uploaded document metadata
- Extracted medical entities
- Timeline events
- Clinical summaries
- Red-flag alerts
- Review and verification status
- Consent and audit information

Use SQLAlchemy models and Alembic migrations so that all members work against the same schema.

**Important:** PostgreSQL stores structured records and references to files. The actual PDF or image can be stored in a controlled file-storage location. The database should store its metadata, storage reference, owner and processing status.

## 2.4 AI and Natural Language Processing

The AI layer can use:

- A compatible large language model through a configured API or a locally available model.
- Pydantic schemas to validate structured AI output.
- Hugging Face Transformers or suitable NLP libraries for extraction tasks.
- Deterministic Python rules for selected clinical question pathways and red-flag checks.

Keep the LLM provider configurable. The application should not require every member to use the same AI assistant for writing code, but the application itself must have a documented and consistent model integration.

AI outputs must be validated before they are stored or shown as verified clinical facts.

## 2.5 Speech Processing

For the prototype:

- Speech-to-text: a suitable Whisper-based implementation, browser speech recognition where appropriate, or an approved Indian-language speech service.
- Text-to-speech: browser speech synthesis or a suitable configured speech service.
- Language handling: start with English and one selected Indian language, preferably Tamil if that fits the intended demonstration.

Do not promise support for every Indian language at the beginning.

Voice input must have a text or touch fallback. The application must remain usable if the speech service is unavailable.

## 2.6 Medical Document Processing

| Technology                           | Purpose                                                             |
| ------------------------------------ | ------------------------------------------------------------------- |
| PyMuPDF or an equivalent PDF library | Extract text from digital PDFs and render scanned pages when needed |
| Pillow / OpenCV                      | Image preprocessing                                                 |
| PaddleOCR or Tesseract               | OCR                                                                 |
| Python                               | Normalize and validate extracted results                            |
| NLP/LLM with structured output       | Identify medical entities from extracted text                       |

For the first prototype, prioritize printed laboratory reports and clear prescriptions. Handwritten prescriptions can be tested as an additional capability, but they should not be treated as reliably readable in all cases.

Use OCR confidence or review flags where available. Never silently convert uncertain extraction into confirmed clinical information.

## 2.7 File Storage

During local development, use a dedicated uploads directory outside the public frontend directory.

Store:

- A generated document ID
- Patient and consultation references
- Original filename
- MIME type
- File size
- Storage path or key
- Upload time
- OCR processing status

Restrict file types and size. Validate uploaded content and do not allow uploaded files to be executed.

Cloud object storage can be introduced later if necessary.

## 2.8 Development and Collaboration Tools

- Git and GitHub: version control and code review
- VS Code: development environment
- Python virtual environment: backend dependency isolation
- Node.js and npm: frontend dependency management
- `.env`: local configuration
- `.env.example`: documented environment variables without secrets
- Swagger/OpenAPI: API documentation generated by FastAPI
- GitHub Issues: task tracking
- GitHub Pull Requests: review and merging

Docker can be added once the local version works. It is not necessary to introduce every deployment technology before the first working prototype.

---

# 3. Team Structure

The team will have three clearly defined owners.

## MEMBER 1 — AI CLINICAL HISTORY AND CONVERSATION ENGINE

**Primary responsibility:** Collect patient history through a guided conversational interface and generate a structured draft clinical summary from patient responses.

### 3.1 Module ownership

Member 1 owns the clinical conversation and patient-history processing module.

The main workflow is:

**Patient Response → Speech-to-Text if required → Text Normalization → Clinical Information Extraction → Question Selection → Structured History → Draft Summary**

### 3.2 Tasks

#### A. Clinical history design

Define the fields required for a basic pre-consultation history:

- Chief complaint
- Symptom onset
- Duration
- Severity
- Location, where relevant
- Symptom progression
- Associated symptoms
- Previous illnesses
- Previous surgeries
- Current medications
- Allergies
- Family history
- Relevant lifestyle information

Questions should be appropriate to the reported complaint.

Do not ask every patient every possible question. Build a small set of configurable pathways for the initial demonstration.

#### B. Conversational interview

Implement a mechanism that:

1. Presents a question.
2. Accepts voice, text or touch-based input.
3. Converts voice to text when necessary.
4. Identifies the information provided.
5. Determines whether required fields are missing.
6. Selects the next question.
7. Stores the response.
8. Ends the interview when the required fields are completed or the session is stopped.

For example:

Patient: "I have had a fever for three days."

The system should capture the reported symptom and duration, then ask an appropriate follow-up question.

Do not assume that every patient response is medically correct or complete. Record it as patient-reported information.

#### C. Adaptive questioning

Build a controlled question-selection mechanism.

Start with a small set of symptom pathways, such as fever, cough and abdominal pain.

A practical implementation is a combination of predefined question rules and an LLM for language interpretation. Do not let an unrestricted LLM invent an arbitrary clinical interview without validation.

#### D. Speech integration

Implement the speech interface through the chosen speech provider or browser capabilities.

Requirements:

- Support the selected languages.
- Display recognized text so the patient can correct it.
- Allow the patient to switch to typing or touch.
- Handle failed recognition without losing the session.
- Avoid recording or retaining raw audio unnecessarily.

#### E. Structured clinical summary

Produce a draft summary from the structured patient-history data.

Example:

- Chief complaint: fever
- Duration: 3 days
- Associated symptoms: as reported by the patient
- Past medical history: not yet provided
- Medication history: not yet verified
- Allergies: not yet provided

Use explicit states such as `reported`, `extracted`, `unknown` and `verified` where appropriate. A missing answer must not be interpreted as a negative answer.

#### F. Red-flag rules

Implement the initial rule-based symptom flagging component in collaboration with the team and, where possible, a qualified healthcare professional.

The rules must:

- Be documented.
- Have test cases.
- Display the reason for each alert.
- Avoid asserting a diagnosis.
- Allow urgent alerts to be surfaced without waiting for the full interview to finish.

The system must not reassure the patient that they are safe merely because no configured flag was triggered.

### 3.3 Technology for Member 1

- Python
- Pydantic
- FastAPI router integration
- A configurable LLM client
- Whisper-based or other selected speech recognition
- Browser speech synthesis or a configured TTS service
- pytest

### 3.4 Suggested files

```text
backend/
└── app/
    ├── routers/
    │   └── clinical_history.py
    ├── services/
    │   ├── conversation_service.py
    │   ├── question_engine.py
    │   ├── speech_service.py
    │   ├── summary_service.py
    │   └── red_flag_service.py
    └── schemas/
        └── clinical_history.py

tests/
└── test_clinical_history.py
```

The exact shared folder structure is defined later. These are suggested ownership areas, not permission to create duplicate application entry points.

### 3.5 Deliverables

Member 1 must provide:

1. Clinical history field specification.
2. Interview question definitions.
3. Working conversational history module.
4. Speech integration or documented fallback.
5. Validated structured output.
6. Draft clinical summary generation.
7. Documented red-flag rules and tests.
8. API router and Pydantic schemas.
9. A README explaining setup, limitations and sample requests.
10. Synthetic test scenarios.

### 3.6 Definition of done

Member 1's work is complete when:

- A test patient can complete a clinical interview.
- Responses are returned in the agreed JSON schema.
- Missing fields are represented accurately.
- The question flow adapts to selected symptoms.
- Speech failure does not block touch/text interaction.
- Summary generation can be tested independently.
- Red-flag tests pass.
- The module integrates with the shared FastAPI application.

---

## MEMBER 2 — MEDICAL DOCUMENT INTELLIGENCE AND TIMELINE

**Primary responsibility:** Process uploaded medical documents, extract relevant information, and create chronological medical events.

### 3.7 Module ownership

Member 2 owns the document processing pipeline:

**Uploaded Document → Validation → Text Extraction/OCR → Medical Entity Extraction → Normalization → Review Flags → Timeline Events**

### 3.8 Tasks

#### A. Document upload processing

Support:

- PDF files
- JPEG images
- PNG images

Initially prioritize printed laboratory reports and clear prescriptions.

Implement:

- File-type validation
- Size limits
- Unique document identifiers
- Secure storage references
- Processing status
- Error handling

Do not place uploaded documents in a publicly accessible frontend folder.

#### B. PDF and image handling

Detect whether a PDF contains extractable digital text.

If it contains readable digital text, extract that text directly.

If it is scanned or image-based, render the page and apply OCR.

Preprocess images when necessary:

- Rotation correction
- Cropping
- Contrast enhancement
- Noise reduction

Do not apply expensive image transformations unless they improve the result.

#### C. OCR pipeline

Use PaddleOCR or Tesseract for the initial implementation.

The module should return:

- Extracted text
- Page information where available
- OCR confidence where available
- Processing status
- Errors or warnings

OCR output is not automatically correct. Preserve the original document so that healthcare professionals can compare extracted text with the source.

#### D. Medical entity extraction

Extract relevant information from the OCR text.

Initial entity categories:

- Medication name
- Dosage
- Frequency
- Duration, if available
- Diagnosis or condition
- Symptom
- Laboratory test
- Laboratory value
- Unit
- Date
- Procedure
- Allergy information, when documented

For example:

Source text:
"Metformin 500 mg twice daily."

Extracted information:

```json
{
  "type": "medication",
  "name": "Metformin",
  "dose": "500 mg",
  "frequency": "twice daily",
  "source": "document"
}
```

This example demonstrates a data format; it does not establish that a patient is currently taking the medicine.

Medication information should be labeled as document-derived until current use is confirmed.

#### E. Data normalization

Normalize dates and units when possible, but preserve the original text.

If the system cannot confidently interpret a field, it should return an uncertain or review-required status instead of inventing a value.

Do not treat a laboratory value as abnormal without suitable reference information and clinical context.

#### F. Medical timeline generation

Generate timeline events from dates and extracted entities.

Example:

| Date       | Event             | Source            |
| ---------- | ----------------- | ----------------- |
| 2025-06-12 | Laboratory report | Uploaded document |
| 2025-08-02 | Prescription      | Uploaded document |
| 2026-01-10 | Discharge summary | Uploaded document |

When dates are missing or ambiguous, retain the event without assigning a fabricated date.

Timeline generation should combine events from documents with relevant consultation events supplied by Member 1 or stored by Member 3.

#### G. Document evidence and traceability

Every extracted entity should retain a link to its source document and, where possible, the relevant page or text segment.

For example:

```text
Medication: Metformin 500 mg
Source: Prescription document DOC-001
Page: 1
Status: Requires confirmation
```

This makes the information easier to verify.

### 3.9 Technology for Member 2

- Python
- PyMuPDF or equivalent PDF text extraction
- Pillow or OpenCV
- PaddleOCR or Tesseract
- Pydantic
- NLP/LLM structured extraction
- SQLAlchemy models provided by the shared backend
- pytest

### 3.10 Suggested files

```text
backend/
└── app/
    ├── routers/
    │   └── documents.py
    ├── services/
    │   ├── document_service.py
    │   ├── pdf_service.py
    │   ├── image_preprocessing.py
    │   ├── ocr_service.py
    │   ├── entity_extraction.py
    │   └── timeline_service.py
    └── schemas/
        └── documents.py

tests/
└── test_documents.py
```

### 3.11 Deliverables

Member 2 must provide:

1. Document upload and validation.
2. PDF and image text extraction.
3. OCR pipeline.
4. Medical entity extraction.
5. Structured extracted output.
6. Timeline generation.
7. Source references for extracted information.
8. Error handling and review flags.
9. API router and schemas.
10. Synthetic sample documents and automated tests.
11. Setup instructions and documented limitations.

### 3.12 Definition of done

Member 2's work is complete when:

- Supported sample documents can be uploaded.
- Digital PDFs and scanned documents follow the appropriate extraction path.
- OCR output is returned in a consistent format.
- Extracted entities follow the agreed schema.
- Uncertain or missing fields are not fabricated.
- Timeline events are sorted when dates are available.
- Source document references are preserved.
- Tests cover successful extraction and common failures.
- The module integrates with the shared database and FastAPI application.

---

## MEMBER 3 — BACKEND, DATABASE, FRONTEND AND SYSTEM INTEGRATION

**Primary responsibility:** Build the shared application foundation, database, patient and doctor interfaces, and integration of all three modules.

This member owns integration, but the other two members must provide working modules, tests and documentation. Member 3 is not responsible for rewriting the entire application when a module fails integration.

### 3.13 Module ownership

Member 3 owns the shared infrastructure:

**React Frontend → FastAPI → Shared Services → PostgreSQL → File Storage → Doctor Dashboard**

### 3.14 Tasks

#### A. Repository and project setup

Set up:

- Shared GitHub repository
- Python environment
- React + TypeScript + Vite frontend
- FastAPI application
- Environment variable configuration
- Dependency files
- `.gitignore`
- README
- Testing configuration

Provide a reliable local setup process so that every member can run the project.

#### B. Database design

Create SQLAlchemy models and database migrations for:

- Patients
- Consultations
- Clinical responses
- Documents
- Extracted entities
- Timeline events
- Clinical summaries
- Red-flag alerts
- Consent records
- Audit events

Use foreign keys and suitable constraints to prevent unrelated patient records from being mixed.

Agree on the schema with Members 1 and 2 before they implement database-dependent functions.

#### C. API integration

Integrate the routers provided by Members 1 and 2 into the shared FastAPI application.

The central entry point should be:

```text
backend/app/main.py
```

It should register the routers, configure middleware and expose API documentation.

Do not create a separate `main.py` inside each member's module.

#### D. Patient interface

Build the common React application and patient-facing screens:

- Start consultation
- Enter patient/session details
- Select language
- Display questions
- Submit touch/text answers
- Trigger voice interaction
- Upload medical documents
- Display completion status

The clinical conversation engine should be implemented by Member 1. The document processing pipeline should be implemented by Member 2. The frontend communicates with these capabilities through the shared API.

#### E. Healthcare professional dashboard

Build screens that display:

- Patient and consultation details
- Current complaint
- Structured clinical summary
- Medical timeline
- Extracted medication information
- Previous investigations
- Source documents
- Red-flag alerts
- Verification status

Include actions for correcting information and marking a summary as reviewed.

The dashboard must distinguish:

- Patient-reported data
- Document-extracted data
- AI-generated summaries
- Healthcare professional-verified information

#### F. Error handling and integration

Handle:

- Backend unavailable
- Invalid input
- OCR failure
- AI provider timeout
- Unsupported file type
- Database connection failure
- Incomplete consultation
- Failed summary generation

The frontend must show a useful error or retry option instead of silently losing patient input.

#### G. Testing and release

Member 3 coordinates end-to-end testing with the other members.

The team must verify that:

1. A patient can start a consultation.
2. History responses can be saved.
3. Documents can be uploaded.
4. OCR and entity extraction can run.
5. Timeline events can be retrieved.
6. The summary can be generated.
7. The doctor dashboard displays the information.
8. Corrections and review status persist in the database.

### 3.15 Technology for Member 3

- React
- TypeScript
- Vite
- CSS
- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic
- GitHub
- pytest
- Browser developer tools

### 3.16 Suggested files

```text
frontend/
├── src/
│   ├── components/
│   ├── pages/
│   │   ├── PatientIntake.tsx
│   │   ├── DocumentUpload.tsx
│   │   └── DoctorDashboard.tsx
│   ├── services/
│   │   └── api.ts
│   ├── types/
│   └── App.tsx
└── package.json

backend/
└── app/
    ├── main.py
    ├── core/
    │   ├── config.py
    │   └── security.py
    ├── db/
    │   ├── session.py
    │   └── base.py
    ├── models/
    ├── routers/
    ├── schemas/
    └── services/

alembic/
tests/
```

### 3.17 Deliverables

Member 3 must provide:

1. Working central repository.
2. Backend and frontend setup.
3. Database schema and migrations.
4. Patient and consultation APIs.
5. Shared file-storage mechanism.
6. Integrated FastAPI application.
7. Patient-facing interface.
8. Doctor dashboard.
9. Environment configuration.
10. Integration tests.
11. Complete README and run instructions.
12. A working end-to-end demonstration.

### 3.18 Definition of done

Member 3's work is complete when all three modules run together from the shared repository and a test patient can complete the intended workflow from patient intake through healthcare professional review.

---

# 4. Central System Architecture

```text
                         NURSE AMMA
                              |
                 +------------+------------+
                 |                         |
                 v                         v
          PATIENT INTERFACE         DOCTOR DASHBOARD
            React + TS                React + TS
                 |                         ^
                 +------------+------------+
                              |
                         REST API
                           HTTPS
                              |
                              v
                     FASTAPI APPLICATION
                              |
              +---------------+----------------+
              |                                |
              v                                v
      CLINICAL HISTORY MODULE          DOCUMENT MODULE
           Member 1                       Member 2
              |                                |
              v                                v
      Speech / NLP / LLM               PDF / OCR / NLP
              |                                |
              v                                v
       Patient Responses                 Extracted Entities
              |                                |
              +---------------+----------------+
                              |
                              v
                     SHARED DATA LAYER
                         Member 3
                              |
                 +------------+------------+
                 |                         |
                 v                         v
            PostgreSQL                File Storage
         Structured Records         PDFs and Images
                 |
                 v
        TIMELINE + CLINICAL SUMMARY
                 |
                 v
       RED-FLAG REVIEW + VERIFICATION
                 |
                 v
       HEALTHCARE PROFESSIONAL REVIEW
                 |
                 v
             FINAL RECORD
```

The diagram represents logical responsibilities. The actual implementation will use shared services and database models rather than three separate applications.

---

# 5. Shared API Contract

All members must agree on the data structures before implementing dependent functions.

The API contract is the boundary between modules. Members may use different AI coding tools, but their outputs must follow these agreed formats.

## 5.1 Core identifiers

Use generated identifiers for:

- `patient_id`
- `consultation_id`
- `document_id`
- `timeline_event_id`
- `summary_id`

Use UUIDs or another consistent identifier format agreed upon during initial setup.

Do not use patient names as database primary keys.

## 5.2 Patient history response

Example:

```json
{
  "consultation_id": "CONSULT-001",
  "chief_complaint": "Fever",
  "duration": {
    "value": 3,
    "unit": "days"
  },
  "associated_symptoms": ["body pain"],
  "source": "patient_reported",
  "verification_status": "unverified"
}
```

This is illustrative. The final implementation should use generated identifiers and a versioned Pydantic schema.

## 5.3 Document processing response

Example:

```json
{
  "document_id": "DOC-001",
  "document_type": "lab_report",
  "processing_status": "completed",
  "entities": [
    {
      "type": "laboratory_result",
      "name": "Hemoglobin",
      "value": "12.5",
      "unit": "g/dL",
      "date": "2026-08-15",
      "source_page": 1,
      "verification_status": "unverified"
    }
  ]
}
```

All document-derived information must retain its source reference. Do not present the example as actual patient data.

## 5.4 Clinical summary response

Example:

```json
{
  "summary_id": "SUM-001",
  "consultation_id": "CONSULT-001",
  "chief_complaint": "Fever",
  "history_of_present_illness": [],
  "past_medical_history": [],
  "medication_history": [],
  "allergies": [],
  "investigation_history": [],
  "red_flags": [],
  "review_status": "pending"
}
```

Empty arrays mean that no items have been supplied to that field; they must not automatically mean that the patient has no relevant history.

## 5.5 Standard API endpoints

Member 3 will own the shared API routing structure. Members 1 and 2 will implement their assigned endpoints within it.

| Method | Endpoint                                            | Responsibility                        |
| ------ | --------------------------------------------------- | ------------------------------------- |
| POST   | `/api/v1/patients`                                  | Create patient record                 |
| GET    | `/api/v1/patients/{patient_id}`                     | Retrieve patient record               |
| POST   | `/api/v1/consultations`                             | Start consultation                    |
| POST   | `/api/v1/consultations/{consultation_id}/responses` | Save patient response                 |
| GET    | `/api/v1/consultations/{consultation_id}`           | Retrieve consultation                 |
| POST   | `/api/v1/consultations/{consultation_id}/documents` | Upload document                       |
| POST   | `/api/v1/documents/{document_id}/process`           | Start or retry processing             |
| GET    | `/api/v1/documents/{document_id}`                   | Retrieve document status and metadata |
| GET    | `/api/v1/consultations/{consultation_id}/timeline`  | Retrieve timeline                     |
| POST   | `/api/v1/consultations/{consultation_id}/summary`   | Generate draft summary                |
| GET    | `/api/v1/consultations/{consultation_id}/summary`   | Retrieve summary                      |
| PATCH  | `/api/v1/summaries/{summary_id}`                    | Correct summary fields                |
| POST   | `/api/v1/summaries/{summary_id}/review`             | Record authorized professional review |

These are the proposed contracts, not proof that the endpoints already exist. The team should document request/response schemas, authentication requirements, error formats and processing behavior in the OpenAPI documentation.

---

# 6. Central GitHub Repository

## 6.1 Repository name

Recommended:

`nurse-amma`

Use one repository containing the backend, frontend, tests, configuration and documentation.

Do not create a separate repository for every member's module unless there is a specific reason to do so.

## 6.2 Final folder structure

```text
nurse-amma/
|
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |-- pages/
|   |   |-- services/
|   |   |-- types/
|   |   `-- App.tsx
|   `-- package.json
|
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- core/
|   |   |-- db/
|   |   |-- models/
|   |   |-- routers/
|   |   |-- schemas/
|   |   `-- services/
|   |-- requirements.txt
|   `-- pyproject.toml
|
|-- alembic/
|-- tests/
|   |-- unit/
|   |-- integration/
|   `-- e2e/
|
|-- sample_data/
|   `-- README.md
|
|-- docs/
|   |-- architecture.md
|   |-- api-contract.md
|   |-- database-schema.md
|   `-- development-guide.md
|
|-- .env.example
|-- .gitignore
|-- README.md
`-- LICENSE
```

The `LICENSE` file should only be added after the team agrees on a license.

The `sample_data` folder should contain only synthetic, non-sensitive examples. Never commit real patient records, API keys, access tokens, passwords or private uploaded medical documents.

## 6.3 Branch strategy

Use the following branches:

- `main` — stable, tested code
- `develop` — shared integration branch, if the team chooses to maintain one
- `feature/clinical-history`
- `feature/document-intelligence`
- `feature/backend-dashboard`

Each member should work on a separate feature branch and submit a pull request.

Example:

```bash
git clone <YOUR_REPOSITORY_URL>
cd nurse-amma

git switch -c feature/clinical-history
```

After implementation:

```bash
git add .
git commit -m "feat: implement clinical history module"
git push -u origin feature/clinical-history
```

Then open a pull request on GitHub and request review from another team member.

Never commit directly to `main` for ordinary feature development.

## 6.4 Commit message examples

```text
feat: add clinical history question engine
feat: implement medical document OCR
feat: add timeline generation
feat: create patient dashboard
fix: handle OCR extraction failure
test: add clinical history tests
docs: update API contract
refactor: centralize database session
```

Each commit should represent a small, understandable change.

## 6.5 Pull request checklist

Before merging, confirm:

- [ ] Code follows the agreed folder structure.
- [ ] API schemas match the shared contract.
- [ ] Tests pass.
- [ ] No secrets or patient data are committed.
- [ ] Error cases are handled.
- [ ] Dependencies are documented.
- [ ] README or relevant documentation is updated.
- [ ] The change does not duplicate an existing service or database model.
- [ ] At least one other team member has reviewed the change.

---

# 7. Shared Development Rules

These rules apply to all members, regardless of which AI coding tool they use.

## Rule 1: Do not change the stack independently

Do not introduce Django, MongoDB, another frontend framework, a second database or a new AI provider into the core application without team agreement.

## Rule 2: Do not duplicate the backend

There must be one main FastAPI application, one shared configuration system and one database session setup.

## Rule 3: Do not create duplicate database models

Agree on shared models and schemas first. A member may propose changes, but database changes must be coordinated with Member 3 and documented through migrations.

## Rule 4: Follow the API contract

If a member changes a field name or response format, the change must be discussed and reflected in the API documentation before the dependent module is modified.

## Rule 5: Keep AI output structured

Where possible, return validated JSON matching a Pydantic schema rather than an unpredictable paragraph. Preserve provenance, uncertainty and review status.

## Rule 6: Separate AI-generated information from verified information

The AI must not mark its own output as clinician-verified. Only an authorized healthcare professional's explicit review can establish that status.

## Rule 7: Never invent missing medical information

If the patient does not provide a medication history, record it as unknown or not provided. Do not infer that the patient takes no medicines.

## Rule 8: Test with synthetic information

Use fabricated patients, sample prescriptions and generated laboratory reports. Do not use real patient documents unless there is proper authorization and an approved secure environment.

## Rule 9: Do not expose secrets

Use `.env` for local configuration and `.env.example` for variable names and placeholders. Never commit API keys.

## Rule 10: Build incrementally

Get one complete workflow working before adding advanced features. Do not attempt multilingual speech, complex handwriting recognition, FHIR integration and deployment simultaneously.

---

# 8. Suggested Development Timeline

A four-week schedule is a starting point. Adjust it to the actual submission deadline and each member's availability.

## Week 1 — Foundation and Contracts

**Member 1**

- Define clinical history fields.
- Create question pathways.
- Define Pydantic input/output schemas.

**Member 2**

- Collect synthetic sample documents.
- Implement PDF text extraction and basic OCR.
- Define entity extraction schemas.

**Member 3**

- Create repository and frontend/backend skeleton.
- Set up PostgreSQL and SQLAlchemy.
- Define shared API contracts.
- Create the first database migration.

**Milestone:** The application starts locally, the database connects, and all members agree on the data formats.

## Week 2 — Independent Modules

**Member 1**

- Implement the conversational history engine.
- Generate structured history responses.
- Add initial unit tests.

**Member 2**

- Implement upload processing.
- Add OCR and entity extraction.
- Return structured document information.

**Member 3**

- Implement patient and consultation APIs.
- Create patient intake screens.
- Build the initial dashboard layout.

**Milestone:** Each module works independently with synthetic test data.

## Week 3 — Integration

**Member 1**

- Integrate history data with the shared consultation model.
- Implement summary generation and red-flag rules.

**Member 2**

- Store extracted entities.
- Generate timeline events.
- Preserve source-document references.

**Member 3**

- Connect the frontend to the shared APIs.
- Display the summary, timeline and document information.
- Add review and correction controls.

**Milestone:** A test patient can complete the workflow from history collection to dashboard display.

## Week 4 — Testing and Demonstration

**All members**

- Test a normal consultation.
- Test incomplete patient responses.
- Test OCR failures and unclear documents.
- Test red-flag scenarios.
- Verify source references and review status.
- Fix integration issues.
- Complete documentation and prepare the demonstration.

**Milestone:** A reproducible end-to-end demonstration runs from the central repository.

---

# 9. Testing and Acceptance Criteria

The project should be evaluated using observable behavior rather than claims that the AI is intelligent.

## 9.1 Clinical history tests

- Does the application save patient responses?
- Does it ask relevant follow-up questions?
- Does it preserve unknown fields as unknown?
- Does the structured response follow the agreed schema?
- Can the patient continue if voice recognition fails?

## 9.2 Document tests

- Can a valid PDF be uploaded?
- Can a scanned image be processed?
- Does OCR return text or a clear processing error?
- Are extracted entities linked to the original document?
- Are uncertain values marked for review?
- Are missing dates left unresolved rather than invented?

## 9.3 Timeline tests

- Are events sorted by date where possible?
- Are undated events preserved?
- Are source documents linked to relevant events?
- Are duplicate events handled appropriately?

## 9.4 Summary tests

- Does the summary include the information supplied by the patient and documents?
- Can a healthcare professional identify where each important fact came from?
- Does the system distinguish reported, extracted and verified information?
- Can the summary be corrected?
- Does the system avoid unsupported diagnoses or recommendations?

## 9.5 Integration tests

- Can the frontend communicate with FastAPI?
- Can the backend persist and retrieve data from PostgreSQL?
- Can the patient flow and document flow share a consultation ID?
- Does the doctor dashboard show the correct consultation?
- Do errors appear clearly without silently losing input?

The team should record actual results. Do not claim an accuracy percentage until it has been measured on an appropriate labeled test set.

---

# 10. Security and Healthcare Safety Requirements

Because Nurse Amma processes health information, safety and privacy must be built into the prototype rather than added at the end.

Minimum requirements:

1. Collect only the information necessary for the intended workflow.
2. Provide clear information about data collection and obtain appropriate consent.
3. Use authentication and authorization for protected records.
4. Restrict access to patient documents.
5. Validate uploaded files and limit file size and type.
6. Avoid logging raw sensitive medical content unnecessarily.
7. Never store secrets in source control.
8. Keep an audit trail for relevant access and review actions.
9. Mark AI-generated summaries as drafts.
10. Make red-flag reasons visible.
11. Keep emergency-related alerts separate from routine summary generation.
12. Do not represent absence of an alert as proof that a patient is safe.
13. Use clinician-reviewed rules for red-flag logic wherever possible.
14. Clearly label the application as a prototype that does not replace professional medical care.

For future deployment, the team must separately assess applicable Indian data-protection requirements, institutional policies, security controls and clinical validation requirements.

---

# 11. What Every Member Must Do When Using Another AI Tool

This project specification must be shared with any AI coding assistant used by a team member.

Each member should provide the assistant with:

1. The complete project specification.
2. Their assigned role.
3. The central repository folder structure.
4. The agreed API schemas.
5. The relevant files already present in the repository.
6. The current implementation status.
7. The task they intend to complete.

The AI assistant should be instructed to inspect existing code before generating replacements.

It must not create a second backend, invent unavailable files, change shared schemas without approval, or rewrite another member's module unnecessarily.

All generated code must be reviewed and tested by the responsible member before it is pushed to GitHub.

---

# 12. Individual AI Coding Instructions

## Member 1 prompt — Clinical history engine

> You are assisting with the Nurse Amma project. I am responsible for the AI clinical history and conversation engine. The application uses Python, FastAPI, Pydantic, SQLAlchemy and PostgreSQL, with React and TypeScript on the frontend.
>
> Your task is to help implement my assigned clinical history module only. Before writing code, inspect the existing repository files and read the shared project specification and API contract.
>
> Implement the clinical interview, adaptive question pathways, structured patient responses, optional speech integration, draft clinical summary generation and documented red-flag rules as appropriate to the current task.
>
> Follow the existing folder structure and shared Pydantic schemas. Do not create another FastAPI application, database connection, patient model or duplicate API contract. Do not change shared interfaces without identifying the change and its impact.
>
> Use synthetic test data. Treat information as patient-reported unless verified. Do not create autonomous diagnoses or prescriptions. Make uncertain and missing information explicit. Add tests, error handling, dependency documentation and setup instructions.
>
> Work incrementally: explain which files you will create or modify, implement the smallest useful change, and provide the test commands. Do not claim that a feature works until it has been run and verified.

## Member 2 prompt — Medical document intelligence

> You are assisting with the Nurse Amma project. I am responsible for medical document processing, OCR, medical entity extraction and timeline generation. The application uses Python, FastAPI, Pydantic, SQLAlchemy and PostgreSQL.
>
> Your task is to help implement my assigned document intelligence module only. Inspect the existing repository, shared project specification and API contract before changing code.
>
> Implement validated PDF/image upload processing, PDF text extraction, OCR, structured extraction of medical entities, source-document references, review flags and chronological timeline events. Preserve original text and document provenance. Do not fabricate dates, medication use, diagnoses, units or laboratory values.
>
> Follow the existing folder structure and shared schemas. Do not create another FastAPI application, database session, document model or duplicate patient model. Coordinate shared database changes with the repository owner.
>
> Use synthetic medical documents only. Add tests for successful extraction, low-quality OCR, missing dates, invalid files and processing errors. Include setup instructions and document known limitations, especially handwriting recognition.
>
> Explain each file to be changed, implement incrementally, and provide reproducible test commands. Do not claim untested accuracy.

## Member 3 prompt — Backend, database, frontend and integration

> You are assisting with the Nurse Amma project. I am responsible for the shared backend, database, React/TypeScript frontend, doctor dashboard and integration of the clinical history and document intelligence modules.
>
> The agreed stack is Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, React, TypeScript and Vite.
>
> Inspect the central repository before generating code. Maintain one FastAPI application, one shared database configuration, shared SQLAlchemy models and the documented API contract. Do not duplicate Member 1's clinical history engine or Member 2's OCR/entity extraction pipeline.
>
> Build the common application foundation, database migrations, patient and consultation APIs, secure file references, patient interface, doctor dashboard and integration tests. Clearly distinguish patient-reported information, document-extracted information, AI-generated summaries and healthcare professional-verified information.
>
> Use environment variables for configuration and never commit secrets or real patient data. Coordinate schema changes through documented migrations and reviewed pull requests.
>
> Implement incrementally. For every task, list the files changed, explain how the modules connect, provide setup and test commands, and identify anything that still requires verification.

---

# 13. Final Definition of a Successful Project

Nurse Amma will be considered a successful academic prototype when the team can demonstrate the following complete scenario:

1. A synthetic patient starts a consultation.
2. The patient reports symptoms through touch, text or supported voice input.
3. The clinical history module asks relevant follow-up questions.
4. The patient uploads a sample medical report or prescription.
5. The document module extracts text and medical entities.
6. The application stores the information in PostgreSQL.
7. Historical events are organized into a medical timeline.
8. The system generates a structured clinical summary.
9. Potential red flags are displayed with their reasons.
10. The healthcare professional opens the consultation, checks the original sources, corrects information if needed and records the review.
11. The application retains the consultation data and review status.
12. The complete process can be repeated from the central GitHub repository using documented setup instructions.

**The most important measure of success is a working, integrated system—not the number of AI models used.**

All three members should be able to explain the overall architecture, their own module, the shared data contracts, the database design, the safety limitations and how the complete application runs.

---

# 14. Immediate Next Steps

Before the team starts parallel coding, complete these tasks in order:

1. Create the central GitHub repository named `nurse-amma`.
2. Add this specification to `docs/project-specification.md`.
3. Agree on the shared folder structure and API schemas.
4. Create the initial FastAPI and React projects.
5. Configure PostgreSQL and the first database migration.
6. Add synthetic test data and `.env.example`.
7. Create the three feature branches.
8. Begin independent module development.
9. Integrate continuously through reviewed pull requests.
10. Run the complete end-to-end workflow before adding optional features.

**Recommended first milestone:** By the end of the first development phase, the frontend should be able to create a consultation, the backend should store it in PostgreSQL, and the team should have agreed on the exact JSON structures used by all modules. This foundation will prevent most integration problems later.
