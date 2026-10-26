# Nurse Amma frontend starter

React + TypeScript + Vite patient intake and doctor review workspace, connected to the existing FastAPI API.

## Requirements

- Node.js 20+ and npm
- The Nurse Amma backend running at `http://127.0.0.1:8000`
- Backend CORS configured to allow `http://127.0.0.1:5173` (the merged application currently allows this origin)

## Run

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

To use a different API base URL, create `frontend/.env.local` with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not place backend secrets, database credentials, JWT signing secrets, or bootstrap tokens in frontend environment variables. Values prefixed with `VITE_` are exposed to browser code.

## Present scope

The UI uses existing endpoints for login, patient creation/retrieval, consultation creation/retrieval, clinical questions/responses, document upload/list/retrieval/reprocessing, and summary generation/retrieval. It fetches the OpenAPI schema to prepare editable JSON request templates where exact payloads are schema-defined.

The current backend does not expose a timeline endpoint or an explicit clinician summary/document verification endpoint. Those areas are marked unavailable/pending in the UI; this frontend does not pretend those operations exist.

The access token is kept in React memory and is lost on refresh. This is intentional for the academic prototype; log in again after a page refresh. This is not a production authentication architecture.

Use synthetic patient details and documents only. This application is an academic prototype, not a medical device or a substitute for professional clinical judgment.
