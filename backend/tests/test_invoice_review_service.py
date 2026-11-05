
import asyncio
from datetime import datetime, timezone

import httpx

from invoice_review_service import review_draft_invoice
from paypal_history_reader import InvoiceHistoryError


DRAFT = {
    "customer_email": "buyer@example.com",
    "item_name": "AI consulting",
    "quantity": 1,
    "unit_price": "100.00",
}


async def fake_token(client):
    return "test-token"


def run_review(reader):
    return asyncio.run(
        review_draft_invoice(
            DRAFT,
            fake_token,
            "https://example.test",
            history_reader=reader,
        )
    )


def test_complete_history_detects_duplicate():
    async def reader(client, token, url, max_invoices):
        assert max_invoices == 10
        return {
            "coverage": "complete",
            "examined": 1,
            "skipped": 0,
            "invoices": [{
                **DRAFT,
                "invoice_id": "INV2-TEST",
                "currency": "USD",
                "status": "DRAFT",
                "created_at": (
                    datetime.now(timezone.utc)
                    .isoformat()
                ),
            }],
        }

    result = run_review(reader)

    assert result["status"] == "complete"
    assert result["review_recommended"] is True
    assert result["warnings"][0]["code"] == (
        "possible_duplicate"
    )


def test_partial_history_is_not_reported_clean():
    async def reader(client, token, url, max_invoices):
        return {
            "coverage": "partial",
            "examined": 5,
            "skipped": 1,
            "invoices": [],
        }

    result = run_review(reader)

    assert result["status"] == "partial"
    assert result["review_recommended"] is None
    assert result["warnings"] == []


def test_api_failure_is_reported_unavailable():
    async def reader(client, token, url, max_invoices):
        raise InvoiceHistoryError("Test API failure")

    result = run_review(reader)

    assert result["status"] == "unavailable"
    assert result["review_recommended"] is None
    assert result["examined"] == 0


def test_complete_empty_history_has_no_warnings():
    async def reader(client, token, url, max_invoices):
        return {
            "coverage": "complete",
            "examined": 0,
            "skipped": 0,
            "invoices": [],
        }

    result = run_review(reader)

    assert result["status"] == "complete"
    assert result["review_recommended"] is False
    assert result["warnings"] == []
