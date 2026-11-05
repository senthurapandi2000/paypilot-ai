from datetime import datetime, timedelta, timezone

from billing_period_store import BillingPeriodEvidenceStore
from billing_period_review_service import BillingPeriodReviewService
from billing_period_context import load_billing_context
from invoice_intelligence import review_invoice


NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
KEY = "test-only-billing-operator-key-123456"

DRAFT = {
    "customer_email": "buyer@example.com",
    "item_name": "Website maintenance",
    "quantity": 1,
    "unit_price": "100.00",
}

HISTORY = [{
    **DRAFT,
    "invoice_id": "INV2-TEST",
    "status": "DRAFT",
    "currency": "USD",
    "created_at": (
        NOW - timedelta(days=2)
    ).isoformat(),
}]


def setup_store(tmp_path):
    store = BillingPeriodEvidenceStore(
        tmp_path / "billing.sqlite3"
    )

    reviewer = BillingPeriodReviewService(
        store,
        admin_key=KEY,
        operator_id="test-reviewer",
        demo_key="public-demo-test-key",
    )

    return store, reviewer


def attest(reviewer, subject_type, subject_id, start, end):
    reviewer.attest(
        credential=KEY,
        subject_type=subject_type,
        subject_id=subject_id,
        start_date=start,
        end_date=end,
        evidence_reference="TEST-EVIDENCE-001",
    )


def review(store):
    context = load_billing_context(
        store, "APPROVAL-001", HISTORY
    )

    return review_invoice(
        DRAFT,
        HISTORY,
        now=NOW,
        verified_billing_context=context,
    )


def test_distinct_periods_avoid_duplicate_warning(tmp_path):
    store, reviewer = setup_store(tmp_path)

    attest(
        reviewer, "pending_approval", "APPROVAL-001",
        "2026-11-01", "2026-11-30"
    )

    attest(
        reviewer, "paypal_invoice", "INV2-TEST",
        "2026-10-01", "2026-10-31"
    )

    result = review(store)

    assert result["review_recommended"] is False
    assert result["warnings"] == []


def test_overlapping_periods_preserve_warning(tmp_path):
    store, reviewer = setup_store(tmp_path)

    attest(
        reviewer, "pending_approval", "APPROVAL-001",
        "2026-11-01", "2026-11-30"
    )

    attest(
        reviewer, "paypal_invoice", "INV2-TEST",
        "2026-11-01", "2026-11-15"
    )

    result = review(store)

    assert result["warnings"][0]["code"] == (
        "possible_duplicate"
    )


def test_missing_proposed_evidence_preserves_warning(tmp_path):
    store, reviewer = setup_store(tmp_path)

    attest(
        reviewer, "paypal_invoice", "INV2-TEST",
        "2026-10-01", "2026-10-31"
    )

    assert load_billing_context(
        store, "APPROVAL-001", HISTORY
    ) is None

    assert review(store)["warnings"][0]["code"] == (
        "possible_duplicate"
    )


def test_missing_historical_evidence_preserves_warning(tmp_path):
    store, reviewer = setup_store(tmp_path)

    attest(
        reviewer, "pending_approval", "APPROVAL-001",
        "2026-11-01", "2026-11-30"
    )

    context = load_billing_context(
        store, "APPROVAL-001", HISTORY
    )

    assert context["historical"] == {}

    assert review(store)["warnings"][0]["code"] == (
        "possible_duplicate"
    )


def test_inconsistent_subject_record_is_rejected():
    class MismatchedStore:
        def get(self, subject_type, subject_id):
            return {
                "subject_type": "pending_approval",
                "subject_id": "SOME-OTHER-APPROVAL",
                "source": "operator_review",
                "verification_status": "approved",
                "reviewer_id": "test-reviewer",
                "evidence_reference": "TEST-001",
                "reviewed_at": NOW.isoformat(),
                "billing_period": {
                    "start_date": "2026-11-01",
                    "end_date": "2026-11-30",
                },
            }

    context = load_billing_context(
        MismatchedStore(), "APPROVAL-001", HISTORY
    )

    assert context is None
