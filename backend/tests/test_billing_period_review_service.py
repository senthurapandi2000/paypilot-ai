import pytest

from billing_period_store import BillingPeriodEvidenceStore
from billing_period_review_service import (
    BillingPeriodReviewService,
    BillingReviewAuthorizationError,
)


ADMIN_KEY = "test-only-operator-secret-123456789"
DEMO_KEY = "test-public-demo-passphrase"


@pytest.fixture
def setup_review(tmp_path):
    store = BillingPeriodEvidenceStore(
        tmp_path / "review-evidence.sqlite3"
    )

    service = BillingPeriodReviewService(
        store,
        admin_key=ADMIN_KEY,
        operator_id="test-operator",
        demo_key=DEMO_KEY,
    )

    return service, store


def submit(service, credential=ADMIN_KEY, **overrides):
    values = {
        "credential": credential,
        "subject_type": "paypal_invoice",
        "subject_id": "INV2-TEST-001",
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
        "evidence_reference": "TEST-EVIDENCE-001",
    }
    values.update(overrides)
    return service.attest(**values)


def test_authorized_operator_can_record_evidence(setup_review):
    service, store = setup_review

    result = submit(service)

    assert result["verification_status"] == "approved"
    assert result["source"] == "operator_review"
    assert result["reviewer_id"] == "test-operator"
    assert result["reviewed_at"]

    assert store.get(
        "paypal_invoice", "INV2-TEST-001"
    ) is not None


def test_incorrect_credential_is_rejected(setup_review):
    service, store = setup_review

    with pytest.raises(BillingReviewAuthorizationError):
        submit(service, credential="wrong-secret")

    assert store.get(
        "paypal_invoice", "INV2-TEST-001"
    ) is None


def test_demo_passphrase_is_not_admin_access(setup_review):
    service, store = setup_review

    with pytest.raises(BillingReviewAuthorizationError):
        submit(service, credential=DEMO_KEY)

    assert store.get(
        "paypal_invoice", "INV2-TEST-001"
    ) is None


def test_missing_credential_is_rejected(setup_review):
    service, store = setup_review

    with pytest.raises(BillingReviewAuthorizationError):
        submit(service, credential=None)

    assert store.get(
        "paypal_invoice", "INV2-TEST-001"
    ) is None


def test_admin_key_cannot_equal_demo_key(tmp_path):
    store = BillingPeriodEvidenceStore(
        tmp_path / "evidence.sqlite3"
    )

    with pytest.raises(ValueError):
        BillingPeriodReviewService(
            store,
            admin_key=ADMIN_KEY,
            operator_id="test-operator",
            demo_key=ADMIN_KEY,
        )


def test_invalid_dates_are_rejected(setup_review):
    service, store = setup_review

    with pytest.raises(ValueError):
        submit(
            service,
            start_date="2026-10-31",
            end_date="2026-10-01",
        )

    assert store.get(
        "paypal_invoice", "INV2-TEST-001"
    ) is None


def test_existing_review_cannot_be_overwritten(setup_review):
    service, store = setup_review

    submit(service)

    with pytest.raises(ValueError):
        submit(
            service,
            start_date="2026-11-01",
            end_date="2026-11-30",
        )

    saved = store.get(
        "paypal_invoice", "INV2-TEST-001"
    )

    assert saved["billing_period"]["start_date"] == (
        "2026-10-01"
    )
