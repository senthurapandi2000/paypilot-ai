import pytest

from billing_period_store import BillingPeriodEvidenceStore
from billing_period_evidence import validate_reviewed_period


RECORD = {
    "subject_type": "paypal_invoice",
    "subject_id": "INV2-TEST-001",
    "source": "operator_review",
    "verification_status": "approved",
    "reviewer_id": "test-reviewer",
    "evidence_reference": "TEST-EVIDENCE-001",
    "reviewed_at": "2026-11-05T12:00:00+00:00",
    "billing_period": {
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    },
}


def test_record_persists_across_instances(tmp_path):
    path = tmp_path / "evidence.sqlite3"

    first = BillingPeriodEvidenceStore(path)
    first.save(RECORD)

    second = BillingPeriodEvidenceStore(path)
    result = second.get(
        "paypal_invoice", "INV2-TEST-001"
    )

    assert result is not None
    assert result["billing_period"] == RECORD["billing_period"]
    assert validate_reviewed_period(result) is not None


def test_invalid_evidence_is_rejected(tmp_path):
    store = BillingPeriodEvidenceStore(
        tmp_path / "evidence.sqlite3"
    )

    invalid = {
        **RECORD,
        "verification_status": "pending",
    }

    with pytest.raises(ValueError):
        store.save(invalid)

    assert store.get(
        "paypal_invoice", "INV2-TEST-001"
    ) is None


def test_existing_evidence_cannot_be_overwritten(tmp_path):
    store = BillingPeriodEvidenceStore(
        tmp_path / "evidence.sqlite3"
    )

    store.save(RECORD)

    replacement = {
        **RECORD,
        "billing_period": {
            "start_date": "2026-11-01",
            "end_date": "2026-11-30",
        },
    }

    with pytest.raises(ValueError):
        store.save(replacement)

    saved = store.get(
        "paypal_invoice", "INV2-TEST-001"
    )

    assert saved["billing_period"] == RECORD["billing_period"]


def test_unknown_invoice_returns_none(tmp_path):
    store = BillingPeriodEvidenceStore(
        tmp_path / "evidence.sqlite3"
    )

    assert store.get(
        "paypal_invoice", "DOES-NOT-EXIST"
    ) is None


def test_subject_types_are_isolated(tmp_path):
    store = BillingPeriodEvidenceStore(
        tmp_path / "evidence.sqlite3"
    )

    store.save(RECORD)

    pending = {
        **RECORD,
        "subject_type": "pending_approval",
    }

    store.save(pending)

    assert store.get(
        "paypal_invoice", "INV2-TEST-001"
    ) is not None

    assert store.get(
        "pending_approval", "INV2-TEST-001"
    ) is not None
