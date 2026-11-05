"""Validate billing-period review records.

Schema validation is not authentication. Call this only
with records retrieved from a trusted server-side store.
"""

from datetime import datetime
from billing_periods import compare_billing_periods


def validate_reviewed_period(record):
    if not isinstance(record, dict):
        return None

    if record.get("verification_status") != "approved":
        return None

    if record.get("source") != "operator_review":
        return None

    if record.get("subject_type") not in (
        "pending_approval",
        "paypal_invoice",
    ):
        return None

    for field in (
        "subject_id",
        "reviewer_id",
        "evidence_reference",
    ):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            return None

    timestamp = record.get("reviewed_at")
    if not isinstance(timestamp, str):
        return None

    try:
        reviewed_at = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if reviewed_at.tzinfo is None:
        return None

    period = record.get("billing_period")

    if compare_billing_periods(
        period, period
    ) != "overlapping":
        return None

    return {
        "subject_type": record["subject_type"],
        "subject_id": record["subject_id"],
        "billing_period": {
            "start_date": period["start_date"],
            "end_date": period["end_date"],
        },
        "reviewer_id": record["reviewer_id"],
        "evidence_reference": record["evidence_reference"],
        "reviewed_at": reviewed_at.isoformat(),
    }
