
from copy import deepcopy

from paypal_invoice_history import normalize_paypal_invoice


def sample_invoice():
    return {
        "id": "INV2-TEST-001",
        "status": "DRAFT",
        "detail": {
            "currency_code": "USD",
            "metadata": {
                "create_time": "2026-11-05T10:00:00Z"
            }
        },
        "primary_recipients": [{
            "billing_info": {
                "email_address": "buyer@example.com"
            }
        }],
        "items": [{
            "name": "AI consulting",
            "quantity": "2",
            "unit_amount": {
                "currency_code": "USD",
                "value": "25.00"
            }
        }]
    }


def test_valid_invoice():
    result = normalize_paypal_invoice(sample_invoice())

    assert result is not None
    assert result["customer_email"] == "buyer@example.com"
    assert result["quantity"] == 2
    assert result["unit_price"] == "25.00"
    assert result["invoice_id"] == "INV2-TEST-001"


def test_missing_creation_time():
    invoice = sample_invoice()
    del invoice["detail"]["metadata"]

    assert normalize_paypal_invoice(invoice) is None


def test_multiple_line_items_skipped():
    invoice = sample_invoice()
    invoice["items"].append(
        deepcopy(invoice["items"][0])
    )

    assert normalize_paypal_invoice(invoice) is None


def test_non_usd_invoice_skipped():
    invoice = sample_invoice()
    invoice["detail"]["currency_code"] = "EUR"

    assert normalize_paypal_invoice(invoice) is None


def test_multiple_recipients_skipped():
    invoice = sample_invoice()
    invoice["primary_recipients"].append(
        deepcopy(invoice["primary_recipients"][0])
    )

    assert normalize_paypal_invoice(invoice) is None


def test_fractional_quantity_skipped():
    invoice = sample_invoice()
    invoice["items"][0]["quantity"] = "1.5"

    assert normalize_paypal_invoice(invoice) is None
