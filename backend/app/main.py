from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.services.decision_log import list_decisions, record_decision
from backend.app.services.finance_data import get_invoice_count, list_invoices
from backend.app.services.invoice_analysis import analyze_invoice

app = FastAPI(title="OrbitIQ Invoice Intelligence Copilot")


class DecisionRequest(BaseModel):
    action: Literal["approve", "reject", "escalate"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/invoices")
def search_invoices(query: str = "", limit: int = 25) -> dict:
    return {"items": list_invoices(query, limit), "total_count": get_invoice_count()}


@app.get("/api/invoices/{invoice_id}/analyze")
def analyze(invoice_id: str) -> dict:
    result = analyze_invoice(invoice_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return result


@app.post("/api/invoices/{invoice_id}/decisions", status_code=201)
def create_decision(invoice_id: str, request: DecisionRequest) -> dict:
    if analyze_invoice(invoice_id) is None:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return record_decision(invoice_id, request.action)


@app.get("/api/decisions")
def get_decisions(invoice_id: str | None = None) -> list[dict[str, int | str]]:
    return list_decisions(invoice_id)
