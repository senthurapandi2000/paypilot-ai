
"""Advisory invoice intelligence checks."""

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from statistics import median


IGNORED_STATUSES = {"CANCELLED", "REFUNDED"}


def _total(invoice):
    return (
        Decimal(str(invoice["unit_price"]))
        * int(invoice["quantity"])
    ).quantize(Decimal("0.01"))


def _normalized_email(value):
    return str(value).strip().casefold()


def _normalized_service(value):
    return " ".join(
        re.sub(r"[^\w]+", " ", str(value).casefold()).split()
    )


def review_invoice(draft, history, now=None):
    """
    Review a proposed invoice against historical invoices.

    Historical records should contain:
    customer_email, item_name, quantity, unit_price,
    created_at (ISO-8601 with timezone), and status.

    Returns advisory warnings only.
    Does not create, cancel, or modify invoices.
    """
    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("now must include a timezone")

    email = _normalized_email(draft["customer_email"])
    item = _normalized_service(draft["item_name"])
    total = _total(draft)

    recent_matches = []
    historical_totals = []

    for previous in history:
        try:
            if _normalized_email(previous["customer_email"]) != email:
                continue

            if _normalized_service(previous["item_name"]) != item:
                continue

            if str(
                previous.get("status", "")
            ).upper() in IGNORED_STATUSES:
                continue

            if str(
                previous.get("currency", "USD")
            ).upper() != "USD":
                continue

            created = datetime.fromisoformat(
                str(previous["created_at"]).replace(
                    "Z", "+00:00"
                )
            )

            if created.tzinfo is None:
                continue

            age = now - created

            if age < timedelta(0) or age > timedelta(days=90):
                continue

            old_total = _total(previous)

        except (
            KeyError,
            ValueError,
            TypeError,
            InvalidOperation,
            OverflowError
        ):
            continue

        historical_totals.append(old_total)

        if (
            age <= timedelta(days=30)
            and old_total == total
            and int(previous["quantity"]) == int(draft["quantity"])
        ):
            recent_matches.append(
                previous.get("invoice_id")
            )

    warnings = []

    if recent_matches:
        warnings.append({
            "code": "possible_duplicate",
            "message": (
                "A similar invoice for this customer, "
                "service, and total was found "
                "in the last 30 days."
            ),
            "matching_invoice_ids": [
                invoice_id
                for invoice_id in recent_matches
                if invoice_id
            ]
        })

    if len(historical_totals) >= 5:
        baseline = median(historical_totals)

        if baseline > 0 and total > baseline * 3:
            warnings.append({
                "code": "unusual_amount",
                "message": (
                    "This invoice total is more than "
                    "three times the historical median "
                    "for this customer and service."
                )
            })

    sample_size = len(historical_totals)

    return {
        "review_recommended": bool(warnings),
        "warnings": warnings,
        "amount_baseline": {
            "status": (
                "ready" if sample_size >= 5
                else "insufficient"
            ),
            "sample_size": sample_size,
            "minimum_sample_size": 5,
        },
    }
