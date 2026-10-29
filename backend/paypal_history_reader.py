
"""Read PayPal Sandbox invoices for intelligence checks."""

from paypal_invoice_history import normalize_paypal_invoice


class InvoiceHistoryError(RuntimeError):
    pass


async def fetch_review_history(
    client,
    token,
    base_url,
    max_invoices=10
):
    """
    Fetch one invoice list page and its details.

    Uses GET requests only. Reports partial coverage
    when some invoices cannot be evaluated.
    """
    if not 1 <= max_invoices <= 20:
        raise ValueError("max_invoices must be 1 to 20")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = await client.get(
        f"{base_url}/v2/invoicing/invoices",
        headers=headers,
        params={
            "page": 1,
            "page_size": max_invoices,
            "total_required": "true"
        }
    )

    if response.status_code != 200:
        raise InvoiceHistoryError(
            "Could not retrieve PayPal invoice history."
        )

    try:
        payload = response.json()
        items = payload["items"]

        if not isinstance(items, list):
            raise ValueError("Invalid invoice list")

    except (ValueError, KeyError, TypeError):
        raise InvoiceHistoryError(
            "PayPal returned invalid invoice history."
        )

    records = []
    skipped = 0

    for entry in items[:max_invoices]:
        invoice_id = (
            entry.get("id")
            if isinstance(entry, dict)
            else None
        )

        if not isinstance(invoice_id, str) or not invoice_id:
            skipped += 1
            continue

        detail_response = await client.get(
            f"{base_url}/v2/invoicing/invoices/{invoice_id}",
            headers=headers
        )

        if detail_response.status_code != 200:
            raise InvoiceHistoryError(
                "Could not retrieve complete invoice details."
            )

        try:
            detail = detail_response.json()
        except ValueError:
            raise InvoiceHistoryError(
                "PayPal returned invalid invoice details."
            )

        normalized = normalize_paypal_invoice(detail)

        if normalized is None:
            skipped += 1
        else:
            records.append(normalized)

    total_pages = payload.get("total_pages")

    complete = (
        total_pages in (0, 1)
        and skipped == 0
        and len(items) <= max_invoices
    )

    return {
        "invoices": records,
        "coverage": "complete" if complete else "partial",
        "examined": min(len(items), max_invoices),
        "skipped": skipped
    }
