# Invoice Intelligence Copilot — Team Overview

## Objective
Build a hackathon-sized invoice exception review workflow that lets an AP analyst:

- select an invoice,
- view the invoice context,
- see deterministic compliance checks,
- receive a Claude-backed recommendation,
- and choose approve / reject / escalate with a decision story.

This is a thin MVP focused on one invoice-to-decision flow. The main goal is to prove the end-to-end capability, not to build a full financial platform.

## Track decision
We are using the invoice PRD and not the fraud dataset from `C:\Users\andradar\Downloads\center_data`.

The reason:
- the repo and task ask for the Invoice-to-Pay workflow,
- the PRD defines a clear AI + deterministic control pattern,
- the invoice track has a crisp demo flow: input invoice -> context -> rules -> AI -> recommendation -> human decision.

## Data readiness and current phase
The six curated finance tables are committed under `backend/app/data/finance/`: invoices, invoice lines, invoice exceptions, purchase orders, suppliers, and payments. The data package is synthetic, so counts, amounts, exception patterns, and supplier examples must not be represented as real business outcomes. The unrelated `C:\Users\andradar\Downloads\center_data` fraud files are not used.

Initial handoff:
- You: own the CSV-backed context loader, deterministic rules, Bedrock integration, and hard gates.
- Lenada: validate the curated schema and edge cases, identify representative demo invoices, and prepare a QA matrix and limitations note. Do not use the fraud files for invoice insights or present synthetic fixture values as real findings.
- Frontend is wired to the curated API response and can continue using the synthetic dataset for the demo.

The API builds an ignored SQLite cache from the six CSVs at `backend/app/data/finance/finance.db`. Bedrock Claude is optional; when credentials are absent the API uses a rules-only fallback and requires human review. Approve/reject/escalate actions are persisted locally in `backend/app/data/decisions.db`.

Each analysis includes the Analyst assessment, a deterministic Red-Team Reviewer pass, and a Red Gate. The reviewer may challenge an assessment below the control floor; the gate preserves or raises risk and never lowers it. The reviewer is not a second LLM agent.

## Team split

### You — Backend + AI lead
Own the live analysis path:

- FastAPI service
- invoice data loading
- schema joins across invoice-related tables
- deterministic rule engine
- Bedrock / Claude evidence call
- hard-rule enforcement
- SQLite decision log
- endpoint: `GET /api/invoices/{invoice_id}/analyze`

Your deliverable:
- one supplied invoice record successfully analyzed,
- structured response payload returned from backend,
- final recommendation and decision story grounded in the provided synthetic data and clearly disclosed as such.

### Lenada — Data + QA + pitch support
Own the evidence and demo quality:

- identify demo cases:
  - normal invoice
  - missing PO
  - duplicate suspected
  - price mismatch
  - changed bank details
- validate negative and edge cases:
  - invalid invoice ID
  - invoice with no payment
  - invoice with multiple exceptions
  - invoice with approval threshold issue
- calculate pitch-support metrics:
  - exception counts
  - most common exception
  - average exception resolution time
  - supplier exception patterns
  - channel vs exception rate
- help write the BEFORE/AFTER analyst story and limitations section

Her deliverable:
- real demo cases ready for testing,
- QA checklist completed,
- pitch-ready insights and story.

## Required data only
Use the invoice-related data required for the MVP, not broad unrelated files.

Minimum relevant tables / datasets:

- `invoices`
- `invoice_lines`
- `invoice_exceptions`
- `purchase_orders`
- `suppliers`
- `payments`

Optional but useful for context:
- prior invoice history for same supplier
- approval level metadata
- status and amount fields needed for deterministic checks

Do not build:
- OCR ingestion
- document upload parsing
- auth
- full payment execution
- multi-agent orchestration
- RAG / graph DB / LangGraph / CrewAI
- large AWS deployment beyond minimal Bedrock access

## MVP scope
The app must support:

1. Invoice selection via invoice ID or row selection.
2. One backend API call that returns all relevant analysis.
3. Deterministic rules before AI analysis.
4. Claude interpreting compact evidence and returning structured JSON.
5. Hard gates to prevent unsafe final statuses.
6. UI showing invoice details, context, checks, reasoning, and recommendation.
7. Approve / reject / escalate buttons.
8. Decision logging to SQLite.

## Functional flow
```text
INVOICE
  ↓
INGEST + NORMALIZE
  ↓
CONTEXT ENRICHMENT
    - supplier
    - PO
    - invoice lines
    - existing exceptions
    - payment
    - supplier history
  ↓
DETERMINISTIC CHECKS
  ↓
TRIAGE
    - AUTO-PROCESS CANDIDATE
    - REVIEW
    - ESCALATE / BLOCK
  ↓
CLAUDE / BEDROCK ANALYSIS
  ↓
HARD RULES / GATES
  ↓
FINAL RECOMMENDATION
  ↓
HUMAN AP ANALYST DECISION
  ↓
DECISION STORY
```

## Required rule checks
These are the required checks for the MVP:

- missing PO
- PO amount mismatch
- duplicate invoice number
- possible near duplicate
- existing exception already on invoice
- bank details changed
- approval threshold checks

These should run before the AI model and should be stored in structured output.

## AI contract
Claude should receive a compact evidence object with:

- invoice
- purchase_order
- supplier summary
- previous invoices
- exceptions
- rule flags

Claude returns structured JSON that includes:

- summary
- risk_level
- recommendation
- reasons
- evidence IDs
- questions_for_analyst

Then the application applies deterministic hard gates after AI output.

## API contract
Backend response should match the following structure:

```json
{
  "invoice": {},
  "supplier": {},
  "po": {},
  "exceptions": [],
  "checks": [],
  "ai_analysis": {},
  "recommendation": "REVIEW",
  "decision_story": []
}
```

The service should be accessible via:

```text
GET /api/invoices/{invoice_id}/analyze
```

## Frontend requirement
Frontend should be a single dashboard with:

- left: invoice details
- center: evidence and context cards
- right: recommendation and action buttons
- bottom: decision story

Frontend can initially use mocked JSON while backend development is underway, but it must convert to live API data before the final demo.

## Demo goal
The success criteria are:

- invoice selected
- backend loads related data
- rules actually run
- AI analyzes real evidence
- recommendation appears in UI
- evidence IDs shown
- user can approve / reject / escalate
- decision is logged

## Working order
1. Set up repo, backend skeleton, and frontend shell.
2. Load invoice data and analyze the schema.
3. Create deterministic invoice checks.
4. Add Bedrock / Claude analysis.
5. Build the dashboard with mock data.
6. Replace mock data with the real API.
7. Run QA against demo cases.
8. Demo and pitch.

## Definition of done for MVP
A successful MVP is:

- one real invoice path works end-to-end,
- invoice context is shown,
- rules produce actionable flags,
- AI recommendation is grounded in evidence,
- frontend displays the result clearly,
- human approval remains central.

## Final instruction
Keep this project intentionally thin. The team priority is:

> One invoice. One button. One complete decision.

Everything else is bonus work.
