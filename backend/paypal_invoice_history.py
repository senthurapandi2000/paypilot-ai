
"""Convert PayPal invoice details into review history."""

from datetime import datetime
from decimal import Decimal, InvalidOperation


def normalize_paypal_invoice(invoice):
    """
    Normalize one PayPal Invoicing v2 detail response.

    Skip unsupported or incomplete records rather
    than making unreliable risk assessments.
    """
    try:
        detail = invoice["detail"]
        recipients = invoice["primary_recipients"]
        items = invoice["items"]

        # Current PayPilot invoices have one recipient
        # and one line item.
        if len(recipients) != 1 or len(items) != 1:
            return None

        email = recipients[0]["billing_info"][
            "email_address"
        ]
        item = items[0]
        amount = item["unit_amount"]

        if (
            detail.get("currency_code") != "USD"
            or amount.get("currency_code") != "USD"
        ):
            return None

        quantity = Decimal(str(item["quantity"]))
        price = Decimal(str(amount["value"]))

        if not quantity.is_finite() or not price.is_finite():
            return None

        if (
            quantity < 1
            or quantity != quantity.to_integral_value()
            or price <= 0
            or price * 100 != (price * 100).to_integral_value()
        ):
            return None

        created_raw = detail["metadata"]["create_time"]
        created = datetime.fromisoformat(
            created_raw.replace("Z", "+00:00")
        )

        if created.tzinfo is None:
            return None

        invoice_id = invoice["id"]
        item_name = item["name"]
        status = invoice["status"]

        if not all((email, item_name, invoice_id, status)):
            return None

        return {
            "invoice_id": invoice_id,
            "customer_email": email,
            "item_name": item_name,
            "quantity": int(quantity),
            "unit_price": str(price),
            "currency": "USD",
            "status": status,
            "created_at": created.isoformat()
        }

    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        InvalidOperation
    ):
        return None
