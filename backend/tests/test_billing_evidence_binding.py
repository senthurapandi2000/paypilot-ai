from billing_evidence_binding import evidence_matches_invoice
from invoice_fingerprint import invoice_fingerprint


INVOICE = {
    "customer_email": "buyer@example.com",
    "item_name": "Website maintenance",
    "quantity": 1,
    "unit_price": "100.00",
    "currency": "USD",
}

RECORD = {
    "subject_type": "paypal_invoice",
    "subject_id": "INV2-TEST",
    "source": "operator_review",
    "verification_status": "approved",
    "reviewer_id": "test-operator",
    "evidence_reference": "TEST-EVIDENCE-001",
    "reviewed_at": "2026-11-05T12:00:00+00:00",
    "billing_period": {
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    },
}


def reviewed_record():
    return {
        **RECORD,
        "invoice_fingerprint": invoice_fingerprint(INVOICE),
    }


def test_matching_invoice_fingerprint():
    assert evidence_matches_invoice(
        reviewed_record(), INVOICE
    ) is True


def test_missing_fingerprint_is_rejected():
    assert evidence_matches_invoice(
        RECORD, INVOICE
    ) is False


def test_malformed_fingerprint_is_rejected():
    record = {
        **RECORD,
        "invoice_fingerprint": "not-a-valid-fingerprint",
    }

    assert evidence_matches_invoice(
        record, INVOICE
    ) is False


def test_changed_invoice_details_are_rejected():
    changed_invoices = [
        {**INVOICE, "unit_price": "500.00"},
        {**INVOICE, "quantity": 2},
        {**INVOICE, "item_name": "Logo design"},
        {**INVOICE, "customer_email": "other@example.com"},
    ]

    for changed in changed_invoices:
        assert evidence_matches_invoice(
            reviewed_record(), changed
        ) is False


def test_unapproved_record_is_rejected():
    record = {
        **reviewed_record(),
        "verification_status": "pending",
    }

    assert evidence_matches_invoice(
        record, INVOICE
    ) is False


def test_invalid_current_invoice_is_rejected():
    invalid_invoice = {
        **INVOICE,
        "quantity": 0,
    }

    assert evidence_matches_invoice(
        reviewed_record(), invalid_invoice
    ) is False
