from __future__ import annotations

from decimal import Decimal
import logging
from typing import Any, Dict, List

from backend.app.services.bedrock_analysis import BedrockAnalysisError, assess_evidence

from backend.app.data.sample_data import (
    INVOICE_EXCEPTIONS,
    INVOICES,
    INVOICE_IDS,
    PAYMENTS,
    PREVIOUS_INVOICES,
    PURCHASE_ORDERS,
    SUPPLIERS,
)

logger = logging.getLogger(__name__)


def _duplicate_matches(invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {key: candidate[key] for key in ("invoice_id", "supplier_id", "invoice_number", "invoice_date", "status")}
        for candidate in INVOICES.values()
        if candidate["invoice_id"] != invoice["invoice_id"]
        and candidate["supplier_id"] == invoice["supplier_id"]
        and candidate["invoice_number"] == invoice["invoice_number"]
    ]


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


def _build_rule_analysis(invoice: Dict[str, Any], supplier: Dict[str, Any], checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    signals = [check for check in checks if check["status"] in {"warning", "fail"}]
    reasons = [check["details"] for check in signals]
    recommendation = "ESCALATE" if any(check["status"] == "fail" for check in signals) else "REVIEW"
    summary = f"Invoice {invoice['invoice_id']} requires {'escalation' if recommendation == 'ESCALATE' else 'manual review'}"
    summary += f" due to {', '.join(check['title'].lower() for check in signals)}." if signals else " because a validated Claude assessment is unavailable."
    if supplier.get("exception_history", 0) > 0:
        reasons.append(f"Supplier has {supplier['exception_history']} recorded historical exceptions.")
    if not reasons:
        reasons.append("No blocking rule signals detected; manual review is required because AI is unavailable.")
    return {
        "summary": summary,
        "risk_level": "high" if recommendation == "ESCALATE" else "medium",
        "recommendation": recommendation,
        "reasons": reasons,
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
    duplicate_matches = _duplicate_matches(invoice)

    checks: List[Dict[str, Any]] = []
    rule_flags: List[str] = []

    if invoice["po_id"] is None:
        checks.append({"code": "MISSING_PO", "status": "fail", "title": "Missing PO", "details": "Invoice is missing a purchase order reference."})
        rule_flags.append("MISSING_PO")
    elif po is None:
        checks.append({"code": "INVALID_PO", "status": "fail", "title": "Invalid PO", "details": "The referenced purchase order could not be found."})
        rule_flags.append("INVALID_PO")
    elif po and invoice["gross_amount"] > po["po_amount"]:
        difference = Decimal(str(invoice["gross_amount"])) - Decimal(str(po["po_amount"]))
        percentage = difference / Decimal(str(po["po_amount"])) * 100 if po["po_amount"] > 0 else None
        variance = f" ({percentage:.2f}%)" if percentage is not None else ""
        checks.append({"code": "PO_AMOUNT_EXCEEDED", "status": "warning", "title": "PO amount mismatch", "details": f"Invoice gross amount {invoice['gross_amount']} exceeds PO limit {po['po_amount']} by {difference:.2f}{variance} {invoice['currency']}.", "amount_over_po": float(difference), "percent_over_po": float(percentage) if percentage is not None else None})
        rule_flags.append("PO_AMOUNT_EXCEEDED")
    else:
        checks.append({"code": "PO_VALID", "status": "pass", "title": "PO validated", "details": "Invoice references a valid PO and does not exceed the allowed amount."})

    if duplicate_matches:
        matching_ids = [item["invoice_id"] for item in duplicate_matches]
        checks.append({"code": "DUPLICATE_INVOICE", "status": "fail", "title": "Duplicate invoice", "details": f"The same supplier and invoice number occur in other loaded invoice records: {', '.join(matching_ids)}. This does not establish prior processing or payment.", "evidence_ids": [invoice_id, *matching_ids]})
        rule_flags.append("DUPLICATE_INVOICE")
    elif _near_duplicate(invoice):
        checks.append({"code": "NEAR_DUPLICATE", "status": "warning", "title": "Possible near duplicate", "details": "Another loaded invoice from the same supplier has a similar amount; processing status and recency are not established."})
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

    approval_level = invoice.get("approval_level")
    supplier_level = supplier.get("approval_threshold")
    if approval_level and supplier_level and approval_level == supplier_level:
        checks.append({"code": "APPROVAL_LEVEL", "status": "pass", "title": "Approval level", "details": f"Invoice requires {approval_level} approval and supplier policy also specifies {supplier_level} approval."})
    else:
        checks.append({"code": "APPROVAL_LEVEL", "status": "warning", "title": "Approval level", "details": f"Invoice approval level ({approval_level or 'unknown'}) and supplier policy ({supplier_level or 'unknown'}) do not establish a matching approval requirement; analyst verification is required."})
        rule_flags.append("APPROVAL_LEVEL")

    if payment.get("status") in {"not_started", "on_hold"}:
        checks.append({"code": "PAYMENT_STATUS", "status": "warning", "title": "Payment status", "details": "Payment has not been matched or is on hold."})
        rule_flags.append("PAYMENT_STATUS")

    evidence = {
        "invoice": {**invoice, "duplicate_matches": duplicate_matches},
        "purchase_order": dict(po) if po else None,
        "supplier": dict(supplier),
        "previous_invoices": [dict(item) for item in previous_invoices[:10]],
        "exceptions": [dict(item) for item in exceptions],
        "rule_flags": list(rule_flags),
    }
    ai_enabled = False
    ai_failure_reason = None
    try:
        ai_analysis = assess_evidence(evidence)
        ai_enabled = True
    except BedrockAnalysisError as error:
        ai_failure_reason = error.code
        logger.warning("Claude assessment unavailable for invoice %s; failure_code=%s; using rule_based_fallback", invoice_id, error.code)
        ai_analysis = _build_rule_analysis(invoice, supplier, checks)
        ai_analysis["evidence_ids"] = [invoice_id]
        if po:
            ai_analysis["evidence_ids"].append(po["po_id"])
        ai_analysis["evidence_ids"].extend(item["invoice_id"] for item in duplicate_matches)
        ai_analysis["evidence_ids"].extend(item["exception_id"] for item in exceptions)
        if supplier:
            ai_analysis["evidence_ids"].append(supplier["supplier_id"])
    ai_analysis["evidence"] = ai_analysis["evidence_ids"]
    ai_analysis["source"] = "bedrock_claude" if ai_enabled else "rule_based_fallback"

    decision_rank = {"AUTO-PROCESS CANDIDATE": 0, "REVIEW": 1, "ESCALATE": 2}
    gate_recommendation = "AUTO-PROCESS CANDIDATE"
    if {"MISSING_PO", "INVALID_PO", "DUPLICATE_INVOICE", "BANK_DETAILS_CHANGED"}.intersection(rule_flags):
        gate_recommendation = "ESCALATE"
    elif rule_flags or not ai_enabled:
        gate_recommendation = "REVIEW"
    recommendation = max(
        (ai_analysis["recommendation"], gate_recommendation), key=decision_rank.__getitem__
    )
    triggered_by = list(rule_flags)
    if not ai_enabled:
        triggered_by.append("AI_UNAVAILABLE")
    elif decision_rank[ai_analysis["recommendation"]] > decision_rank[gate_recommendation]:
        triggered_by.append("CLAUDE_RECOMMENDATION")
    decision_story = [
        "Invoice loaded",
        "PO and supplier context retrieved",
        "Exception and payment history checked",
        "Deterministic checks executed",
        "Claude evidence assessment validated" if ai_enabled else "AI unavailable; rule-based fallback generated and manual review required",
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
        "duplicate_matches": duplicate_matches,
        "analysis": ai_analysis,
        **({"ai_analysis": ai_analysis} if ai_enabled else {}),
        "recommendation": recommendation,
        "final_decision": {
            "recommendation": recommendation,
            "triggered_by": triggered_by,
            "human_review_required": True,
        },
        "decision_story": decision_story,
        "available_invoice_ids": INVOICE_IDS,
        "data_source": "synthetic demo fixtures",
        "ai_enabled": ai_enabled,
        "ai_status": "success" if ai_enabled else "unavailable",
        "ai_failure_reason": ai_failure_reason,
    }
