import pytest

from invoice_fingerprint import invoice_fingerprint


INVOICE = {
    "customer_email": "buyer@example.com",
    "item_name": "Website maintenance",
    "quantity": 1,
    "unit_price": "100.00",
    "currency": "USD",
}


def test_fingerprint_is_deterministic():
    first = invoice_fingerprint(INVOICE)
    second = invoice_fingerprint(dict(reversed(
        list(INVOICE.items())
    )))

    assert first == second
    assert len(first) == 64


def test_equivalent_price_and_email_normalization():
    modified = {
        **INVOICE,
        "customer_email": "BUYER@EXAMPLE.COM",
        "unit_price": "100.0",
    }

    assert invoice_fingerprint(modified) == (
        invoice_fingerprint(INVOICE)
    )


def test_customer_change_invalidates_fingerprint():
    modified = {
        **INVOICE,
        "customer_email": "other@example.com",
    }

    assert invoice_fingerprint(modified) != (
        invoice_fingerprint(INVOICE)
    )


def test_service_change_invalidates_fingerprint():
    modified = {
        **INVOICE,
        "item_name": "Logo design",
    }

    assert invoice_fingerprint(modified) != (
        invoice_fingerprint(INVOICE)
    )


def test_quantity_change_invalidates_fingerprint():
    modified = {
        **INVOICE,
        "quantity": 2,
    }

    assert invoice_fingerprint(modified) != (
        invoice_fingerprint(INVOICE)
    )


def test_price_change_and_invalid_fields():
    modified = {
        **INVOICE,
        "unit_price": "500.00",
    }

    assert invoice_fingerprint(modified) != (
        invoice_fingerprint(INVOICE)
    )

    for invalid in (
        {**INVOICE, "quantity": 0},
        {**INVOICE, "quantity": True},
        {**INVOICE, "unit_price": "-10.00"},
        {**INVOICE, "currency": "EUR"},
    ):
        with pytest.raises(ValueError):
            invoice_fingerprint(invalid)
