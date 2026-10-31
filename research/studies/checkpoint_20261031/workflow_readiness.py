"""Offline evidence-review summaries, never execution or promotion permission.

Canonical procedures are docs/research-development.md and
docs/operations/alpaca-paper.md. Callers assess those procedures and supply
explicit observations. This helper only checks coverage of those observations;
it cannot authenticate a reference, validate freshness, measure a budget, or
replace RSI contracts, receipt validation, native risk or broker reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


REVIEW_CHECKS = {
    "research_selection": (
        "prior_failures_reviewed", "distinct_mechanism", "source_rights",
        "free_local_data", "one_change_frozen", "controls_frozen",
        "budget_remaining", "deadline_open",
    ),
    "calmar_comparison": (
        "dates_calendar", "capital_cashflows", "costs_financing",
        "actions_currency", "exposure_controls", "metric_conventions",
        "audit_evidence", "growth_drawdown_underwater",
    ),
    "daily_reproduction": (
        "pinned_source_build", "daily_decision_reference", "daily_path_match",
        "account_ledger_reconciled",
    ),
    "paper_handoff": (
        "qualified_inputs", "fresh_inputs", "capital_exposure_limits",
        "native_execution_checks", "account_order_reconciliation",
        "no_unresolved_submissions", "restart_recovery", "session_owner_bounds",
    ),
}


@dataclass(frozen=True)
class ReviewCheck:
    """A reviewer observation, with explicit evidence or a missing-check reason."""

    status: str
    reference: str = ""
    reason: str = ""

    def __post_init__(self):
        if self.status not in {"met", "failed", "unknown"}:
            raise ValueError("Review status must be met, failed or unknown")
        if not isinstance(self.reference, str) or not isinstance(self.reason, str):
            raise ValueError("Review reference and reason must be text")
        if self.status == "met" and not self.reference.strip():
            raise ValueError("A met observation requires an evidence reference")
        if self.status != "met" and not self.reason.strip():
            raise ValueError("A failed or unknown observation requires a reason")


def summarize_review(review: str, checks: Mapping[str, ReviewCheck]) -> dict:
    """Return evidence gaps; missing observations remain unknown.

    'supported_by_declared_checks' means reviewer declarations cover the named
    checks. It is not independently verified truth, execution eligibility,
    financial acceptance or broker arming. No files or external services are read.
    """
    if review not in REVIEW_CHECKS:
        raise ValueError(f"Unknown evidence review: {review}")
    required = REVIEW_CHECKS[review]
    unexpected = set(checks) - set(required)
    if unexpected:
        raise ValueError(f"Unexpected checks for {review}: {sorted(unexpected)}")
    observations = {}
    for name in required:
        check = checks.get(name, ReviewCheck("unknown", reason="No observation supplied"))
        if not isinstance(check, ReviewCheck):
            raise ValueError(f"{name} must be a ReviewCheck")
        observations[name] = {
            "status": check.status, "reference": check.reference, "reason": check.reason,
        }
    failed = [name for name in required if observations[name]["status"] == "failed"]
    unknown = [name for name in required if observations[name]["status"] == "unknown"]
    status = ("blocked_by_declared_checks" if failed else
              "unverified_missing_checks" if unknown else "supported_by_declared_checks")
    return {
        "review": review, "status": status, "checks": observations,
        "failed": failed, "unknown": unknown,
        "independently_verified": False, "authorizes_execution": False,
    }
