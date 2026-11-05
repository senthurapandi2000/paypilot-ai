"""Read validated billing periods for local invoice review.

No write operations or public API endpoints.
"""

from billing_period_evidence import validate_reviewed_period


def _period_for(store, subject_type, subject_id):
    if not isinstance(subject_id, str) or not subject_id:
        return None

    record = store.get(subject_type, subject_id)

    if not isinstance(record, dict):
        return None

    validated = validate_reviewed_period(record)

    if validated is None:
        return None

    if (
        validated["subject_type"] != subject_type
        or validated["subject_id"] != subject_id
    ):
        return None

    return validated["billing_period"]


def load_billing_context(store, approval_id, history):
    """Build context from attested records only.

    If the proposed approval lacks valid evidence,
    return None and preserve normal duplicate checks.
    """

    proposed = _period_for(
        store, "pending_approval", approval_id
    )

    if proposed is None:
        return None

    historical = {}

    for invoice in history:
        if not isinstance(invoice, dict):
            continue

        invoice_id = invoice.get("invoice_id")

        period = _period_for(
            store, "paypal_invoice", invoice_id
        )

        if period is not None:
            historical[invoice_id] = period

    return {
        "proposed": proposed,
        "historical": historical,
    }
