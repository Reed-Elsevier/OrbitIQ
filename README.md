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
 The invoice review flow is wired to the six curated finance tables:
 - The source CSVs are synthetic and live under `backend/app/data/finance/`.
 - The API builds an ignored SQLite cache from those CSVs and joins invoices, lines, exceptions, POs, suppliers, and payments.
 - The React dashboard supports bounded invoice/supplier search, evidence tabs, and a SQLite-backed Decision Log.
 - Approve/reject/escalate decisions are persisted locally in SQLite.
 - Bedrock Claude is optional; when configured it returns validated structured analysis, and when unavailable the API returns a rules-only fallback requiring human review.
 - Each analysis includes an Analyst assessment, deterministic Red-Team Reviewer pass, and Red Gate. The reviewer is rules-based, not a second LLM agent.

 Only the six required curated CSVs are committed. Raw tables, Parquet duplicates, other data domains, and helper scripts are excluded. All provided records are synthetic and must not be described as real transactions or findings about actual suppliers. The `C:\Users\andradar\Downloads\center_data` folder contains unrelated fraud data and is not used.

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

 Open `http://localhost:5173`. The API health check is at `http://localhost:8000/health`; search invoices with `GET /api/invoices?query=INV0000001`, or analyze one with `GET /api/invoices/INV0000001/analyze`.

Bedrock is optional for local development. Set `AWS_BEARER_TOKEN_BEDROCK` in the backend process environment and optionally set `AWS_REGION` and `BEDROCK_MODEL_ID`; never commit credentials. Without a token, analysis uses a rule-based fallback and requires human review. Set `VITE_API_BASE_URL` only when the API is not on `http://localhost:8000`.

 Decision actions are saved to `backend\app\data\decisions.db`. The local finance cache is generated at `backend\app\data\finance\finance.db` and ignored by Git. The API accepts `POST /api/invoices/{invoice_id}/decisions` with `{"action":"approve"}`, `{"action":"reject"}`, or `{"action":"escalate"}`. Use `GET /api/decisions` to list entries, optionally filtered with `?invoice_id=INV0000001`. Set `ORBITIQ_DECISIONS_DB` to use a different decisions file and `ORBITIQ_FINANCE_DATA_DIR` to point to the curated CSV directory.

## Quick priority
> One invoice. One button. One complete decision.
