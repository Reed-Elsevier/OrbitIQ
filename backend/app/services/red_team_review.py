from __future__ import annotations

from typing import Any


RECOMMENDATION_RANK = {
    "AUTO-PROCESS CANDIDATE": 0,
    "REVIEW": 1,
    "ESCALATE": 2,
}
HARD_STOP_FLAGS = {"MISSING_PO", "PO_NOT_FOUND", "DUPLICATE_INVOICE", "BANK_DETAILS_CHANGED"}


def review_recommendation(
    analyst_recommendation: str,
    rule_flags: list[str],
    ai_enabled: bool,
) -> dict[str, Any]:
    hard_flags = [flag for flag in rule_flags if flag in HARD_STOP_FLAGS]
    if hard_flags:
        recommendation_floor = "ESCALATE"
        challenged_flags = hard_flags
    elif rule_flags or not ai_enabled:
        recommendation_floor = "REVIEW"
        challenged_flags = list(rule_flags)
    else:
        recommendation_floor = "AUTO-PROCESS CANDIDATE"
        challenged_flags = []

    challenged = RECOMMENDATION_RANK[analyst_recommendation] < RECOMMENDATION_RANK[recommendation_floor]
    if challenged:
        summary = f"Raised the Analyst recommendation to {recommendation_floor} based on deterministic controls."
    else:
        summary = "Analyst recommendation meets or exceeds the deterministic control floor."

    return {
        "status": "CHALLENGE" if challenged else "PASS",
        "recommendation_floor": recommendation_floor,
        "summary": summary,
        "checked_flags": list(rule_flags),
        "challenged_flags": challenged_flags if challenged else [],
        "source": "deterministic_control_review",
    }


def apply_red_gate(analyst_recommendation: str, review: dict[str, Any]) -> dict[str, Any]:
    floor = review["recommendation_floor"]
    recommendation = max(
        (analyst_recommendation, floor),
        key=RECOMMENDATION_RANK.__getitem__,
    )
    return {
        "status": "BLOCK" if recommendation == "ESCALATE" else "REVIEW" if recommendation == "REVIEW" else "CLEAR",
        "recommendation": recommendation,
        "overrode_analyst": recommendation != analyst_recommendation,
    }