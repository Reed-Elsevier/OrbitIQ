# OrbitIQ

Invoice Intelligence Copilot MVP project for the hackathon.

## Documents
- [overview.md](./overview.md) — team responsibilities, workflow, and implementation guidance
- [PRD.md](./PRD.md) — product requirements and invoice-specific scope

## Goal
Build a thin end-to-end invoice decision flow: invoice context -> deterministic checks -> AI reasoning -> human recommendation.

## Scope summary
- Use the invoice PRD, not the fraud dataset from the downloaded exploratory files.
- Keep the project intentionally focused on one invoice analysis path.
- Do not build OCR, auth, broad deployment, or multi-agent complexity.

## Current phase
The first shared scaffold is ready for parallel work:
- FastAPI endpoint with deterministic checks and clearly labeled sample records.
- React dashboard that calls the API and can run in demo mode.
- Invoice demo data is synthetic; do not use it as real hackathon evidence.
- Bedrock, real invoice data loading, SQLite decisions, and decision-action wiring are not implemented yet.

The available `C:\Users\andradar\Downloads\center_data` folder was inspected and contains fraud-related data, not the invoice tables required by this PRD. Lenada should first locate/confirm the invoice dataset source; until then, keep data investigation to the required schema and QA scenarios, and do not report synthetic values as dataset findings.

## Run locally
Backend (from the repository root):
```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

Run backend tests (from the repository root):
```powershell
python -m unittest backend.test_api
```

Frontend (in a second terminal):
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173`. The API health check is at `http://localhost:8000/health`; the invoice endpoint is `http://localhost:8000/api/invoices/INV-1001/analyze`.

## Quick priority
> One invoice. One button. One complete decision.
