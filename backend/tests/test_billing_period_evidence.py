from billing_period_evidence import validate_reviewed_period


RECORD = {
    "subject_type": "paypal_invoice",
    "subject_id": "INV2-SYNTH-001",
    "source": "operator_review",
    "verification_status": "approved",
    "reviewer_id": "test-reviewer",
    "evidence_reference": "TEST-REVIEW-001",
    "reviewed_at": "2026-11-05T12:00:00+00:00",
    "billing_period": {
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    },
}


def test_accepts_complete_review_record():
    result = validate_reviewed_period(RECORD)

    assert result is not None
    assert result["billing_period"] == RECORD["billing_period"]


def test_rejects_unapproved_record():
    record = {
        **RECORD,
        "verification_status": "pending",
    }

    assert validate_reviewed_period(record) is None


def test_rejects_missing_reviewer():
    record = {**RECORD, "reviewer_id": ""}

    assert validate_reviewed_period(record) is None


def test_rejects_missing_evidence():
    record = {
        **RECORD,
        "evidence_reference": "",
    }

    assert validate_reviewed_period(record) is None


def test_rejects_invalid_period():
    record = {
        **RECORD,
        "billing_period": {
            "start_date": "2026-10-31",
            "end_date": "2026-10-01",
        },
    }

    assert validate_reviewed_period(record) is None


def test_rejects_timestamp_without_timezone():
    record = {
        **RECORD,
        "reviewed_at": "2026-11-05T12:00:00",
    }

    assert validate_reviewed_period(record) is None
