"""Regression tests for legacy billing evidence migration."""

import sqlite3
from datetime import datetime, timedelta, timezone

from billing_period_store import BillingPeriodEvidenceStore
from billing_period_review_service import BillingPeriodReviewService
from billing_period_context import load_billing_context
from invoice_intelligence import review_invoice


NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)

DRAFT = {
    "customer_email": "buyer@example.com",
    "item_name": "Website maintenance",
    "quantity": 1,
    "unit_price": "100.00",
}

HISTORY = [{
    **DRAFT,
    "invoice_id": "INV2-LEGACY",
    "status": "DRAFT",
    "currency": "USD",
    "created_at": (NOW - timedelta(days=2)).isoformat(),
}]


def create_legacy_database(path):
    """Create the old schema without invoice_fingerprint."""

    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE billing_period_evidence (
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                evidence_reference TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                source TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                PRIMARY KEY (subject_type, subject_id)
            )
        """)

        conn.execute("""
            INSERT INTO billing_period_evidence
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "paypal_invoice",
            "INV2-LEGACY",
            "2026-10-01",
            "2026-10-31",
            "test-reviewer",
            "LEGACY-EVIDENCE",
            NOW.isoformat(),
            "operator_review",
            "approved",
        ))


def test_existing_database_migrates_without_data_loss(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    create_legacy_database(path)

    store = BillingPeriodEvidenceStore(path)

    saved = store.get("paypal_invoice", "INV2-LEGACY")

    assert saved is not None
    assert saved["billing_period"] == {
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }

    # Old evidence must not gain a trusted fingerprint.
    assert saved["invoice_fingerprint"] is None

    with sqlite3.connect(path) as conn:
        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(billing_period_evidence)"
            )
        ]

    assert "invoice_fingerprint" in columns


def test_legacy_evidence_cannot_suppress_duplicate(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    create_legacy_database(path)

    store = BillingPeriodEvidenceStore(path)

    reviewer = BillingPeriodReviewService(
        store,
        admin_key="test-only-operator-key-123456789",
        operator_id="test-reviewer",
        demo_key="public-demo-test-key",
    )

    reviewer.attest(
        credential="test-only-operator-key-123456789",
        subject_type="pending_approval",
        subject_id="APPROVAL-NEW",
        start_date="2026-11-01",
        end_date="2026-11-30",
        evidence_reference="NEW-REVIEW",
        invoice=DRAFT,
    )

    context = load_billing_context(
        store, "APPROVAL-NEW", DRAFT, HISTORY
    )

    assert context is not None
    assert context["historical"] == {}

    result = review_invoice(
        DRAFT,
        HISTORY,
        now=NOW,
        verified_billing_context=context,
    )

    codes = [
        warning["code"]
        for warning in result["warnings"]
    ]

    assert "possible_duplicate" in codes
