"""Canonical content fingerprint for invoice review."""

import hashlib
import json
from decimal import Decimal, InvalidOperation


def invoice_fingerprint(invoice):
    """Hash validated invoice details deterministically."""

    if not isinstance(invoice, dict):
        raise ValueError("Invoice must be an object.")

    email = invoice.get("customer_email")
    service = invoice.get("item_name")
    quantity = invoice.get("quantity")
    currency = invoice.get("currency", "USD")

    if not isinstance(email, str) or not email.strip():
        raise ValueError("Invalid customer email.")

    if not isinstance(service, str) or not service.strip():
        raise ValueError("Invalid service.")

    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity < 1
    ):
        raise ValueError("Invalid quantity.")

    if (
        not isinstance(currency, str)
        or currency.strip().upper() != "USD"
    ):
        raise ValueError("Only USD is supported.")

    try:
        price = Decimal(str(invoice["unit_price"]))

        if (
            not price.is_finite()
            or price <= 0
            or price > Decimal("999999.99")
        ):
            raise ValueError("Invalid price.")

        rounded = price.quantize(Decimal("0.01"))

        if price != rounded:
            raise ValueError("Invalid price precision.")

    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError("Invalid unit price.") from exc

    canonical = {
        "customer_email": email.strip().casefold(),
        "item_name": service.strip(),
        "quantity": quantity,
        "unit_price": str(rounded),
        "currency": "USD",
    }

    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()
