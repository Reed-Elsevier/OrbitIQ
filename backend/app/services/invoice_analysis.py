from __future__ import annotations

from decimal import Decimal
import logging
from typing import Any, Dict, List

from backend.app.services.bedrock_analysis import BedrockAnalysisError, assess_evidence
from backend.app.services.finance_data import get_invoice_context, get_invoice_count, list_invoices

logger = logging.getLogger(__name__)


def _amounts_are_near(first_amount: float, second_amount: float) -> bool:
    amount_delta = abs(first_amount - second_amount)
    return amount_delta <= 500 and amount_delta / max(first_amount, 1) <= 0.05


def _near_duplicate(invoice: Dict[str, Any], previous_invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    amount_usd = invoice.get("amount_usd")
    if amount_usd is None:
        return []
    return [
        candidate
        for candidate in previous_invoices
        if candidate.get("amount_usd") is not None
        and _amounts_are_near(amount_usd, candidate["amount_usd"])
    ]


def _build_rule_analysis(
    invoice: Dict[str, Any],
    checks: List[Dict[str, Any]],
    evidence_ids: List[str],
) -> Dict[str, Any]:
    signals = [check for check in checks if check["status"] in {"warning", "fail"}]
    reasons = [check["details"] for check in signals[:8]]
    recommendation = "ESCALATE" if any(check["status"] == "fail" for check in signals) else "REVIEW"
    summary = f"Invoice {invoice['invoice_id']} requires {recommendation.lower()}"
    summary += f" due to {', '.join(check['title'].lower() for check in signals[:4])}." if signals else " because a validated Claude assessment is unavailable."
    if not reasons:
        reasons.append("No blocking rule signals detected; analyst review is required because AI is unavailable.")
    return {
        "summary": summary,
        "risk_level": "high" if recommendation == "ESCALATE" else "medium",
        "recommendation": recommendation,
        "reasons": reasons,
        "evidence_ids": evidence_ids,
        "evidence": evidence_ids,
        "questions_for_analyst": ["Can the invoice approval policy be verified?"],
        "source": "rule_based_fallback",
    }


def analyze_invoice(invoice_id: str) -> Dict[str, Any] | None:
    context = get_invoice_context(invoice_id)
    if context is None:
        return None

    invoice = context["invoice"]
    supplier = context["supplier"]
    po = context["po"]
    exceptions = context["exceptions"]
    payments = context["payments"]
    previous_invoices = context["previous_invoices"]
    duplicate_matches = context["duplicate_matches"]

    checks: List[Dict[str, Any]] = []
    rule_flags: List[str] = []

    if invoice["po_id"] is None:
        checks.append({"code": "MISSING_PO", "status": "fail", "title": "Missing PO", "details": "Invoice is missing a purchase order reference."})
        rule_flags.append("MISSING_PO")
    elif po is None:
        checks.append({"code": "PO_NOT_FOUND", "status": "fail", "title": "PO not found", "details": f"Purchase order {invoice['po_id']} could not be found."})
        rule_flags.append("PO_NOT_FOUND")
    elif invoice.get("currency") != po.get("currency"):
        checks.append({"code": "PO_CURRENCY_MISMATCH", "status": "warning", "title": "PO currency mismatch", "details": f"Invoice currency {invoice.get('currency')} differs from PO currency {po.get('currency')}; amounts were not compared."})
        rule_flags.append("PO_CURRENCY_MISMATCH")
    elif invoice["gross_amount"] > po["po_amount"]:
        difference = Decimal(str(invoice["gross_amount"])) - Decimal(str(po["po_amount"]))
        percentage = difference / Decimal(str(po["po_amount"])) * 100 if po["po_amount"] > 0 else None
        checks.append({"code": "PO_AMOUNT_EXCEEDED", "status": "warning", "title": "PO amount mismatch", "details": f"Invoice amount exceeds PO by {difference:.2f} {invoice['currency']}" + (f" ({percentage:.2f}%)." if percentage is not None else "."), "amount_over_po": float(difference), "percent_over_po": float(percentage) if percentage is not None else None})
        rule_flags.append("PO_AMOUNT_EXCEEDED")
    else:
        checks.append({"code": "PO_VALID", "status": "pass", "title": "PO validated", "details": "Invoice references a valid PO and does not exceed the allowed amount."})

    if duplicate_matches:
        matching_ids = [item["invoice_id"] for item in duplicate_matches]
        checks.append({"code": "DUPLICATE_INVOICE", "status": "fail", "title": "Duplicate invoice", "details": f"The same supplier and invoice number appear in other loaded records: {', '.join(matching_ids)}. This does not establish prior processing or payment.", "evidence_ids": [invoice_id, *matching_ids]})
        rule_flags.append("DUPLICATE_INVOICE")
    elif near_matches := _near_duplicate(invoice, previous_invoices):
        checks.append({"code": "NEAR_DUPLICATE", "status": "warning", "title": "Possible near duplicate", "details": "Another invoice from the same supplier has a similar USD amount; processing status and recency are not established.", "evidence_ids": [invoice_id, *(item["invoice_id"] for item in near_matches)]})
        rule_flags.append("NEAR_DUPLICATE")
    else:
        checks.append({"code": "NO_DUPLICATE", "status": "pass", "title": "No duplicate signal", "details": "No exact or near-duplicate invoice was found."})

    if exceptions:
        checks.append({"code": "EXISTING_EXCEPTION", "status": "warning", "title": "Existing exception", "details": f"{len(exceptions)} exception(s) already exist for this invoice."})
        rule_flags.append("EXISTING_EXCEPTION")
    else:
        checks.append({"code": "NO_EXCEPTION", "status": "pass", "title": "No existing exception", "details": "No exception record is currently attached to this invoice."})

    bank_details_changed = any("bank" in item.get("type", "").lower() and "chang" in item.get("type", "").lower() for item in exceptions)
    if bank_details_changed:
        checks.append({"code": "BANK_DETAILS_CHANGED", "status": "fail", "title": "Bank details changed", "details": "Bank details changed exception was flagged and requires human review."})
        rule_flags.append("BANK_DETAILS_CHANGED")

    approval_level = invoice.get("approval_level")
    checks.append({"code": "APPROVAL_POLICY_UNVERIFIED", "status": "warning", "title": "Approval policy", "details": f"Recorded approval level: {approval_level or 'not provided'}. Monetary approval thresholds are not present in the curated finance tables."})
    rule_flags.append("APPROVAL_POLICY_UNVERIFIED")

    if payments:
        checks.append({"code": "PAYMENT_STATUS", "status": "pass", "title": "Payment record", "details": f"{len(payments)} payment record(s) are linked to this invoice."})
    elif str(invoice.get("status", "")).lower() not in {"paid", "partially paid"}:
        checks.append({"code": "PAYMENT_STATUS", "status": "warning", "title": "Payment status", "details": "No payment record is linked to this invoice."})
        rule_flags.append("PAYMENT_STATUS")

    evidence = {
        "invoice": {**invoice, "duplicate_matches": duplicate_matches},
        "purchase_order": po,
        "supplier": supplier,
        "invoice_lines": context["invoice_lines"],
        "previous_invoices": previous_invoices[:10],
        "exceptions": exceptions,
        "rule_flags": list(rule_flags),
    }
    evidence_ids = [invoice_id, *(item["invoice_id"] for item in duplicate_matches)]
    if po:
        evidence_ids.append(po["po_id"])
    if supplier:
        evidence_ids.append(supplier["supplier_id"])
    evidence_ids.extend(item["exception_id"] for item in exceptions)

    ai_enabled = False
    ai_failure_reason = None
    try:
        ai_analysis = assess_evidence(evidence)
        ai_enabled = True
    except BedrockAnalysisError as error:
        ai_failure_reason = error.code
        logger.warning("Claude assessment unavailable for invoice %s; failure_code=%s", invoice_id, error.code)
        ai_analysis = _build_rule_analysis(invoice, checks, evidence_ids)
    ai_analysis["evidence"] = ai_analysis["evidence_ids"]
    ai_analysis["source"] = "bedrock_claude" if ai_enabled else "rule_based_fallback"

    decision_rank = {"AUTO-PROCESS CANDIDATE": 0, "REVIEW": 1, "ESCALATE": 2}
    gate_recommendation = "AUTO-PROCESS CANDIDATE"
    if {"MISSING_PO", "PO_NOT_FOUND", "DUPLICATE_INVOICE", "BANK_DETAILS_CHANGED"}.intersection(rule_flags):
        gate_recommendation = "ESCALATE"
    elif rule_flags or not ai_enabled:
        gate_recommendation = "REVIEW"
    recommendation = max(
        (ai_analysis["recommendation"], gate_recommendation),
        key=decision_rank.__getitem__,
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
        "invoice_lines": context["invoice_lines"],
        "payments": payments,
        "checks": checks,
        "duplicate_matches": duplicate_matches,
        "analysis": ai_analysis,
        **({"ai_analysis": ai_analysis} if ai_enabled else {}),
        "recommendation": recommendation,
        "final_decision": {"recommendation": recommendation, "triggered_by": triggered_by, "human_review_required": True},
        "decision_story": decision_story,
        "available_invoice_ids": [item["invoice_id"] for item in list_invoices(limit=25)],
        "invoice_count": get_invoice_count(),
        "data_source": "curated synthetic finance CSVs",
        "ai_enabled": ai_enabled,
        "ai_status": "success" if ai_enabled else "unavailable",
        "ai_failure_reason": ai_failure_reason,
    }
