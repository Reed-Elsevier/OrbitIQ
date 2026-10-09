from __future__ import annotations

from typing import Any, Dict, List

from backend.app.data.sample_data import (
    INVOICE_EXCEPTIONS,
    INVOICES,
    INVOICE_IDS,
    PAYMENTS,
    PREVIOUS_INVOICES,
    PURCHASE_ORDERS,
    SUPPLIERS,
)


def _duplicate_invoice(invoice: Dict[str, Any]) -> bool:
    for invoice_id, candidate in INVOICES.items():
        if invoice_id == invoice["invoice_id"]:
            continue
        if candidate["supplier_id"] == invoice["supplier_id"] and candidate["invoice_number"] == invoice["invoice_number"]:
            return True
    return False


def _near_duplicate(invoice: Dict[str, Any]) -> bool:
    supplier_id = invoice["supplier_id"]
    for invoice_id, candidate in INVOICES.items():
        if invoice_id == invoice["invoice_id"]:
            continue
        if candidate["supplier_id"] != supplier_id:
            continue
        amount_delta = abs(candidate["gross_amount"] - invoice["gross_amount"])
        if amount_delta <= 500 and abs(candidate["gross_amount"] - invoice["gross_amount"]) / max(invoice["gross_amount"], 1) <= 0.05:
            return True
    return False


def _build_ai_analysis(invoice: Dict[str, Any], po: Dict[str, Any], supplier: Dict[str, Any], exceptions: List[Dict[str, Any]], rule_flags: List[str]) -> Dict[str, Any]:
    reasons: List[str] = []
    evidence: List[str] = [invoice["invoice_id"], invoice["po_id"] or "NO_PO"]

    if "MISSING_PO" in rule_flags:
        reasons.append("Missing purchase order reference")
    if "PO_AMOUNT_EXCEEDED" in rule_flags:
        reasons.append("Invoice amount exceeds the approved PO")
    if "DUPLICATE_INVOICE" in rule_flags:
        reasons.append("Duplicate invoice number detected")
    if "BANK_DETAILS_CHANGED" in rule_flags:
        reasons.append("Bank details changed exception requires review")
    if not reasons:
        reasons.append("Routine invoice pattern with no blocking control violations")

    if supplier["exception_history"] > 1:
        reasons.append(f"Supplier has {supplier['exception_history']} recent exception signals")

    summary = (
        f"Invoice {invoice['invoice_id']} matches the supplier context and has a {min(len(reasons), 3)}-signal review path."
        if reasons
        else f"Invoice {invoice['invoice_id']} is consistent with the PO and supplier history."
    )

    recommendation = "AUTO-PROCESS CANDIDATE"
    risk_level = "low"
    if "MISSING_PO" in rule_flags or "DUPLICATE_INVOICE" in rule_flags or "BANK_DETAILS_CHANGED" in rule_flags:
        recommendation = "ESCALATE"
        risk_level = "high"
    elif "PO_AMOUNT_EXCEEDED" in rule_flags or "EXISTING_EXCEPTION" in rule_flags or supplier["exception_history"] > 1:
        recommendation = "REVIEW"
        risk_level = "medium"

    return {
        "summary": summary,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "reasons": reasons[:5],
        "evidence": evidence,
        "questions_for_analyst": [
            "Was the PO amended after invoice issuance?",
            "Should this be routed to a specialist reviewer?",
        ],
    }


def analyze_invoice(invoice_id: str) -> Dict[str, Any] | None:
    invoice = INVOICES.get(invoice_id)
    if invoice is None:
        return None

    supplier = SUPPLIERS.get(invoice["supplier_id"], {})
    po = PURCHASE_ORDERS.get(invoice["po_id"]) if invoice["po_id"] else None
    exceptions = INVOICE_EXCEPTIONS.get(invoice_id, [])
    payment = PAYMENTS.get(invoice_id, {})
    previous_invoices = PREVIOUS_INVOICES.get(invoice["supplier_id"], [])

    checks: List[Dict[str, Any]] = []
    rule_flags: List[str] = []

    if invoice["po_id"] is None:
        checks.append({"code": "MISSING_PO", "status": "fail", "title": "Missing PO", "details": "Invoice is missing a purchase order reference."})
        rule_flags.append("MISSING_PO")
    elif po and invoice["gross_amount"] > po["po_amount"]:
        checks.append({"code": "PO_AMOUNT_EXCEEDED", "status": "warning", "title": "PO amount mismatch", "details": f"Invoice gross amount {invoice['gross_amount']} exceeds PO limit {po['po_amount']}."})
        rule_flags.append("PO_AMOUNT_EXCEEDED")
    else:
        checks.append({"code": "PO_VALID", "status": "pass", "title": "PO validated", "details": "Invoice references a valid PO and does not exceed the allowed amount."})

    if _duplicate_invoice(invoice):
        checks.append({"code": "DUPLICATE_INVOICE", "status": "fail", "title": "Duplicate invoice", "details": "The same supplier and invoice number appeared in a prior invoice."})
        rule_flags.append("DUPLICATE_INVOICE")
    elif _near_duplicate(invoice):
        checks.append({"code": "NEAR_DUPLICATE", "status": "warning", "title": "Possible near duplicate", "details": "A similar invoice from the same supplier was recently processed."})
        rule_flags.append("NEAR_DUPLICATE")
    else:
        checks.append({"code": "NO_DUPLICATE", "status": "pass", "title": "No duplicate signal", "details": "No exact or near-duplicate invoice was found."})

    if exceptions:
        checks.append({"code": "EXISTING_EXCEPTION", "status": "warning", "title": "Existing exception", "details": f"{len(exceptions)} exception(s) already exist for this invoice."})
        rule_flags.append("EXISTING_EXCEPTION")
    else:
        checks.append({"code": "NO_EXCEPTION", "status": "pass", "title": "No existing exception", "details": "No exception record is currently attached to this invoice."})

    bank_details_changed = any(item.get("type") == "Bank details changed" for item in exceptions)
    if bank_details_changed:
        checks.append({"code": "BANK_DETAILS_CHANGED", "status": "fail", "title": "Bank details changed", "details": "Bank details changed exception was flagged and requires human review."})
        rule_flags.append("BANK_DETAILS_CHANGED")

    if invoice["approval_level"] == "manager" and invoice["gross_amount"] > 15000:
        checks.append({"code": "APPROVAL_THRESHOLD", "status": "warning", "title": "Approval threshold", "details": "High-value invoice may require specialist approval given policy thresholds."})

    if payment.get("status") in {"not_started", "on_hold"}:
        checks.append({"code": "PAYMENT_STATUS", "status": "warning", "title": "Payment status", "details": "Payment has not been matched or is on hold."})

    recommendation = "AUTO-PROCESS CANDIDATE"
    if "MISSING_PO" in rule_flags or "DUPLICATE_INVOICE" in rule_flags or "BANK_DETAILS_CHANGED" in rule_flags:
        recommendation = "ESCALATE"
    elif "PO_AMOUNT_EXCEEDED" in rule_flags or "EXISTING_EXCEPTION" in rule_flags or invoice["gross_amount"] > 15000:
        recommendation = "REVIEW"

    ai_analysis = _build_ai_analysis(invoice, po or {}, supplier, exceptions, rule_flags)
    decision_story = [
        "Invoice loaded",
        "PO and supplier context retrieved",
        "Exception and payment history checked",
        "Deterministic checks executed",
        "Rule-based demo summary generated; Bedrock integration pending",
        "Hard gate applied",
        "Human review recommendation recorded",
    ]

    if recommendation == "AUTO-PROCESS CANDIDATE":
        decision_story[-1] = "Auto-process candidate recorded for analyst approval"
    elif recommendation == "REVIEW":
        decision_story[-1] = "Manual review required before payment approval"
    else:
        decision_story[-1] = "Escalation required due to policy and risk signals"

    return {
        "invoice": invoice,
        "supplier": supplier,
        "po": po,
        "exceptions": exceptions,
        "checks": checks,
        "ai_analysis": ai_analysis,
        "recommendation": recommendation,
        "decision_story": decision_story,
        "available_invoice_ids": INVOICE_IDS,
        "data_source": "synthetic demo fixtures",
        "ai_enabled": False,
    }
