
"""Coordinate read-only invoice risk reviews."""

import asyncio

import httpx
from fastapi import HTTPException

from invoice_intelligence import review_invoice
from paypal_history_reader import (
    InvoiceHistoryError,
    fetch_review_history,
)


def unavailable_review():
    return {
        "status": "unavailable",
        "review_recommended": None,
        "warnings": [],
        "amount_baseline": None,
        "examined": 0,
        "skipped": 0,
        "message": (
            "Invoice history could not be checked. "
            "Review the invoice manually."
        ),
    }


async def review_draft_invoice(
    draft,
    get_token,
    base_url,
    history_reader=None,
):
    """
    Review a draft without modifying PayPal.

    An unavailable or incomplete history must never
    be reported as a clean review.
    """
    reader = history_reader or fetch_review_history

    try:
        # Bound overall review time, including OAuth
        # and multiple invoice-detail requests.
        async with asyncio.timeout(20):
            async with httpx.AsyncClient(timeout=8) as client:
                token = await get_token(client)

                history = await reader(
                    client,
                    token,
                    base_url,
                    max_invoices=10,
                )

    except (
        HTTPException,
        InvoiceHistoryError,
        httpx.RequestError,
        TimeoutError,
    ):
        return unavailable_review()

    report = review_invoice(
        draft,
        history["invoices"],
    )

    status = history["coverage"]

    if report["review_recommended"]:
        recommendation = True
    elif status == "complete":
        recommendation = False
    else:
        recommendation = None

    message = (
        "Review completed for the available history."
        if status == "complete"
        else (
            "Only part of the invoice history was "
            "checked. Additional duplicates or "
            "anomalies may exist."
        )
    )

    return {
        "status": status,
        "review_recommended": recommendation,
        "warnings": report["warnings"],
        "amount_baseline": report["amount_baseline"],
        "examined": history["examined"],
        "skipped": history["skipped"],
        "message": message,
    }
