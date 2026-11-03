
import asyncio

import httpx
import pytest

from paypal_history_reader import (
    InvoiceHistoryError,
    fetch_review_history
)


BASE = "https://api-m.sandbox.paypal.com"


def sample_detail():
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
            "quantity": "1",
            "unit_amount": {
                "currency_code": "USD",
                "value": "100.00"
            }
        }]
    }


def run_reader(handler):
    async def run():
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport
        ) as client:
            return await fetch_review_history(
                client,
                "fake-test-token",
                BASE
            )

    return asyncio.run(run())


def test_fetches_and_normalizes_history():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"

        if request.url.path.endswith("/invoices"):
            assert request.url.params["total_required"] == "true"
            return httpx.Response(
                200,
                json={
                    "total_pages": 1,
                    "items": [{"id": "INV2-TEST-001"}]
                }
            )

        return httpx.Response(
            200,
            json=sample_detail()
        )

    result = run_reader(handler)

    assert result["coverage"] == "complete"
    assert result["examined"] == 1
    assert len(result["invoices"]) == 1
    assert result["invoices"][0]["unit_price"] == "100.00"
    assert len(requests) == 2


def test_multiple_pages_report_partial_coverage():
    def handler(request):
        if request.url.path.endswith("/invoices"):
            return httpx.Response(
                200,
                json={
                    "total_pages": 2,
                    "items": [{"id": "INV2-TEST-001"}]
                }
            )

        return httpx.Response(
            200,
            json=sample_detail()
        )

    result = run_reader(handler)

    assert result["coverage"] == "partial"


def test_unsupported_invoice_reports_partial():
    invalid = sample_detail()
    invalid["items"] = []

    def handler(request):
        if request.url.path.endswith("/invoices"):
            return httpx.Response(
                200,
                json={
                    "total_pages": 1,
                    "items": [{"id": "INV2-TEST-001"}]
                }
            )

        return httpx.Response(200, json=invalid)

    result = run_reader(handler)

    assert result["coverage"] == "partial"
    assert result["skipped"] == 1
    assert result["invoices"] == []


def test_history_api_error_is_not_silenced():
    def handler(request):
        return httpx.Response(502)

    with pytest.raises(InvoiceHistoryError):
        run_reader(handler)


def test_detail_api_error_is_not_silenced():
    def handler(request):
        if request.url.path.endswith("/invoices"):
            return httpx.Response(
                200,
                json={
                    "total_pages": 1,
                    "items": [{"id": "INV2-TEST-001"}]
                }
            )

        return httpx.Response(503)

    with pytest.raises(InvoiceHistoryError):
        run_reader(handler)
