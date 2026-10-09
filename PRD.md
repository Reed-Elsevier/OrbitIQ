# PRD — Invoice Intelligence Copilot

## Product name
Invoice Intelligence Copilot

## Problem
Accounts Payable teams process large numbers of supplier invoices and a meaningful share requires manual exception handling. The cost is not just in flagging exceptions; analysts still need to collect invoice context, check POs, supplier history, prior exceptions, payment records, and risk signals before deciding whether an invoice should proceed.

The goal is to reduce manual investigation effort by combining deterministic rule checks with AI-assisted interpretation of invoice evidence.

## Target user
- AP Analyst
- AP Team Lead / Manager

## Product goal
Create an AI-assisted invoice review system that:

- gathers invoice context,
- runs exact rule checks,
- uses Claude in a narrow evidence-backed way,
- and gives the AP analyst a clear recommendation with supporting evidence.

## Core user story
As an AP analyst, I want to select or submit an invoice and immediately see its PO, supplier history, exception signals, AI interpretation, and recommended next action so I can resolve the issue faster without manually checking multiple systems.

## Core flow
```text
INVOICE
  ↓
INGEST + NORMALIZE
  ↓
CONTEXT ENRICHMENT
    - Purchase Order
    - Supplier
    - Invoice History
    - Existing Exceptions
    - Payment History
  ↓
DETERMINISTIC CHECKS
  ↓
TRIAGE
    - SAFE
    - REVIEW
    - HIGH RISK
  ↓
CLAUDE ANALYSIS
  ↓
FINAL RECOMMENDATION
  ↓
HUMAN AP ANALYST
  ↓
DECISION STORY
```

## Inputs
For the MVP, do not build OCR or upload parsing.

Use an existing invoice record from the structured invoice data source.

The system should support:
- entering an invoice ID,
- or selecting an invoice from a table.

The invoice dataset already contains structured fields like supplier, PO, amount, approval level, payment status, and invoice metadata.

## Required data for the MVP
Only the invoice-related data needed to analyze a single invoice is required.

Minimum tables:
- `invoices`
- `invoice_lines`
- `invoice_exceptions`
- `purchase_orders`
- `suppliers`
- `payments`

Useful supporting data:
- prior invoices from the same supplier
- invoice approval level metadata
- exception history and payment history

## Deterministic checks
These checks should run before Claude.

### Rule 1 — Missing PO
```python
if invoice.po_id is None:
    flag("MISSING_PO")
```

### Rule 2 — PO amount mismatch
If invoice total exceeds PO amount, flag a mismatch.

### Rule 3 — Duplicate invoice number
A duplicate is detected when the same supplier and invoice number appear previously.

### Rule 4 — Possible near duplicate
A near duplicate can be signaled when the same supplier has a similar amount, date, or invoice number.

### Rule 5 — Existing exception
Surface any record in `invoice_exceptions`.

### Rule 6 — Changed bank details
If an exception says `Bank details changed`, the invoice requires human review.

### Rule 7 — Approval threshold
Use existing `approval_level` rules. AI must not override approval requirements.

## Triage outcome
The backend produces one of the following states:

- AUTO-PROCESS CANDIDATE
- REVIEW
- ESCALATE / BLOCK

The important wording is: 
> Auto-process candidate

not actual autonomous payment execution.

## Claude / AWS Bedrock role
Claude should only interpret evidence and provide reasoning. It should not decide basic arithmetic.

Input to Claude is a compact evidence object:

```json
{
  "invoice": {},
  "purchase_order": {},
  "supplier_summary": {},
  "previous_invoices": [],
  "exceptions": [],
  "rule_flags": []
}
```

Claude returns structured JSON:

```json
{
  "summary": "Invoice has a valid PO but the invoiced amount exceeds the remaining PO value.",
  "risk_level": "medium",
  "recommendation": "REVIEW",
  "reasons": [
    "PO amount mismatch",
    "Supplier has two recent price mismatch exceptions"
  ],
  "evidence": [
    "INV0045375",
    "PO0028918"
  ],
  "questions_for_analyst": [
    "Was the PO amended after invoice issuance?"
  ]
}
```

## Deterministic gates
After AI recommendation:

```python
if bank_details_changed:
    final_status = "HUMAN_REVIEW_REQUIRED"

if duplicate_suspected:
    final_status = "HUMAN_REVIEW_REQUIRED"

if po_missing:
    final_status = "HUMAN_REVIEW_REQUIRED"
```

Pitch:
> Claude interprets the exception. Code enforces financial controls.

## Frontend
One dashboard with three regions:

### Left
Invoice details:
- Invoice ID
- Supplier
- Amount
- Date
- PO
- Status

### Center
Evidence:
- Purchase Order
- Previous invoices
- Exceptions
- Payment status

### Right
Decision:
- Risk
- Recommendation
- Why
- Hard checks
- Approve / Reject / Escalate

Bottom section:
- Decision story explaining the path from invoice load to final recommendation.

## MVP success criteria
By demo time, the app should do the following:

- select an invoice,
- backend loads related records,
- deterministic rules actually run,
- Claude analyzes real supplied data,
- recommendation appears in UI,
- evidence IDs are shown,
- user can approve/reject/escalate,
- decision is logged.

## Out of scope
Do not build:

- Authentication
- Full invoice upload OCR
- MCP
- Docker
- PostgreSQL
- RAG
- Graph DB
- LangGraph
- CrewAI
- Five agents
- Real payment execution
- Complicated AWS deployment unless required

## Stack
Frontend:
- React + TypeScript

Backend:
- FastAPI + Python

AI:
- Claude through AWS Bedrock

Data:
- provided CSV / Parquet files + pandas

Storage:
- SQLite

## API contract
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

Endpoint:
```text
GET /api/invoices/{invoice_id}/analyze
```

## Team responsibilities
### You
- backend
- AI integration
- deterministic rules
- recommendation payload
- SQLite decision log

### Lenada
- data investigation
- QA
- demo case identification
- insights for the pitch
- assumptions and limitations documentation

## Final priority
> One invoice. One button. One complete decision.

Everything else is bonus work.
