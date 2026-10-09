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
The available `C:\Users\andradar\Downloads\center_data` folder contains fraud-related files, not the invoice tables listed below. No invoice dataset has been added to this repository yet. The current five invoice records are synthetic demo fixtures for wiring and UI development only; their counts, amounts, and exception patterns must not be presented as real dataset findings.

Initial handoff:
- You: continue the API contract, rule checks, and backend integration using the synthetic fixtures until the invoice bundle is located.
- Lenada: verify where the invoice data bundle is, identify the required invoice datasets/columns once available, and prepare a QA case matrix. Do not analyze the fraud files for invoice insights or report fixture-derived metrics as real findings.
- Frontend work can proceed against the current API response and synthetic fixtures while the dataset is being confirmed.

The current scaffold does not yet include Bedrock or real-data loaders. Approve/reject/escalate actions are persisted locally in SQLite at `backend/app/data/decisions.db`; the current invoice records remain synthetic fixtures.

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
- one real invoice successfully analyzed,
- structured response payload returned from backend,
- final recommendation and decision story generated from real data.

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
