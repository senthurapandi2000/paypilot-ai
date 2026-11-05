"""Internal operator authorization for billing-period reviews.

Not exposed through public FastAPI routes.
A shared operator credential is not individual identity
verification; production requires additional controls.
"""

import secrets
from datetime import datetime, timezone
from invoice_fingerprint import invoice_fingerprint


class BillingReviewAuthorizationError(PermissionError):
    pass


class BillingPeriodReviewService:
    def __init__(
        self,
        store,
        *,
        admin_key,
        operator_id,
        demo_key=None,
    ):
        if not isinstance(admin_key, str) or len(admin_key) < 24:
            raise ValueError(
                "A separate strong operator credential is required."
            )

        if demo_key and secrets.compare_digest(
            admin_key, demo_key
        ):
            raise ValueError(
                "Operator credential must differ from demo key."
            )

        if not isinstance(operator_id, str) or not operator_id.strip():
            raise ValueError("Operator ID is required.")

        self._store = store
        self._admin_key = admin_key
        self._operator_id = operator_id.strip()

    def attest(
        self,
        *,
        credential,
        subject_type,
        subject_id,
        start_date,
        end_date,
        evidence_reference,
        invoice,
    ):
        """Record an operator attestation after credential check."""

        if (
            not isinstance(credential, str)
            or not secrets.compare_digest(
                credential, self._admin_key
            )
        ):
            raise BillingReviewAuthorizationError(
                "Reviewer authorization failed."
            )

        record = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "source": "operator_review",
            "verification_status": "approved",
            "reviewer_id": self._operator_id,
            "evidence_reference": evidence_reference,
            "invoice_fingerprint": invoice_fingerprint(invoice),
            "reviewed_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "billing_period": {
                "start_date": start_date,
                "end_date": end_date,
            },
        }

        self._store.save(record)

        return self._store.get(subject_type, subject_id)
