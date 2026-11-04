
import argparse
import asyncio
import json
import sqlite3
from decimal import Decimal

import httpx

from approval_store import ApprovalStore
from main import PAYPAL_BASE, get_paypal_token


async def check_invoice(approval_id):
    store = ApprovalStore()

    # Read the original validated invoice from SQLite.
    with sqlite3.connect(store.path) as conn:
        row = conn.execute(
            """
            SELECT invoice_json, status
            FROM approvals
            WHERE approval_id = ?
            """,
            (approval_id,)
        ).fetchone()

    if row is None:
        print("Approval not found.")
        return

    invoice = json.loads(row[0])
    status = row[1]

    reference = f"PAYPILOT-{approval_id}"
    email = invoice["customer_email"]
    expected_total = (
        Decimal(str(invoice["unit_price"]))
        * int(invoice["quantity"])
    ).quantize(Decimal("0.01"))

    print(f"Local approval status: {status}")
    print(f"Searching PayPal for: {reference}")

    # This API operation searches invoices.
    # It never creates, sends or deletes an invoice.
    async with httpx.AsyncClient(timeout=30) as client:
        token = await get_paypal_token(client)

        response = await client.post(
            f"{PAYPAL_BASE}/v2/invoicing/search-invoices",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            params={
                "page": 1,
                "page_size": 100,
                "total_required": "true"
            },
            json={
                "reference": reference,
                "recipient_email": email,
                "currency_code": "USD"
            }
        )

    if response.status_code != 200:
        print(
            f"Search failed: HTTP {response.status_code}."
        )
        print("Do not retry invoice creation.")
        return

    data = response.json()
    candidates = data.get("items", [])

    matches = []

    for item in candidates:
        detail = item.get("detail") or {}
        amount = item.get("amount") or {}
        recipients = item.get("primary_recipients") or []

        emails = [
            (recipient.get("billing_info") or {})
            .get("email_address", "")
            .lower()
            for recipient in recipients
        ]

        try:
            amount_matches = (
                amount.get("currency_code") == "USD"
                and Decimal(str(amount.get("value")))
                == expected_total
            )
        except (ValueError, TypeError, ArithmeticError):
            amount_matches = False

        if (
            detail.get("reference") == reference
            and email.lower() in emails
            and amount_matches
        ):
            matches.append(item)

    total_pages = data.get("total_pages", 1)

    if total_pages > 1:
        print("Multiple result pages. Manual review required.")
        print("Do not retry invoice creation.")
        return

    if len(matches) == 1:
        match = matches[0]

        print("One matching invoice candidate found.")
        print(f"Invoice ID: {match.get('id')}")
        print(f"PayPal status: {match.get('status')}")
        print("Verify invoice details in PayPal Sandbox.")
        print("SQLite status was NOT modified.")

    elif len(matches) > 1:
        print("Multiple matching invoices found.")
        print("Manual review required.")

    else:
        print("No exact matching invoice found.")
        print("This does NOT prove creation failed.")
        print("Do not automatically retry the request.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Read-only PayPal invoice recovery"
    )

    parser.add_argument(
        "approval_id",
        help="Existing SQLite approval ID"
    )

    args = parser.parse_args()

    asyncio.run(check_invoice(args.approval_id))
