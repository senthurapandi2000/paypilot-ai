
import asyncio

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import paypal_recovery
from ai_agent import install_ai_routes
from approval_store import ApprovalStore
from main import InvoiceInput


def test_lost_response_blocks_retry_and_supports_recovery(
    tmp_path, monkeypatch, capsys
):
    store = ApprovalStore(
        tmp_path / "day10_lost_response.sqlite3"
    )

    approval_id = "day10-lost-response-approval-001"
    invoice_id = "INV2-DAY10-MOCK"

    invoice = {
        "customer_email": "buyer@example.com",
        "item_name": "AI consulting",
        "quantity": 1,
        "unit_price": "1.00"
    }

    store.create(approval_id, invoice)

    # Simulate PayPal creating a draft, but the
    # backend losing the success response.
    created_drafts = []

    async def fake_create_invoice(
        data, idempotency_key=None
    ):
        created_drafts.append({
            "id": invoice_id,
            "reference": f"PAYPILOT-{idempotency_key}"
        })

        raise HTTPException(
            status_code=502,
            detail="PayPal response lost after draft creation."
        )

    app = FastAPI()

    install_ai_routes(
        app,
        InvoiceInput,
        fake_create_invoice,
        approval_store=store
    )

    with TestClient(app) as client:
        first = client.post(
            "/api/ai/approve",
            json={"approval_id": approval_id}
        )

        assert first.status_code == 502

        record = store.get_status(approval_id)
        assert record["status"] == "needs_review"

        # A second approval must not create another draft.
        second = client.post(
            "/api/ai/approve",
            json={"approval_id": approval_id}
        )

        assert second.status_code == 404

    assert len(created_drafts) == 1

    # The recovery checker reads the same test store.
    monkeypatch.setattr(
        paypal_recovery,
        "make_approval_store",
        lambda: store
    )

    async def fake_token(client):
        return "test-token"

    monkeypatch.setattr(
        paypal_recovery,
        "get_paypal_token",
        fake_token
    )

    class FakePayPalClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            assert url.endswith(
                "/v2/invoicing/search-invoices"
            )

            assert kwargs["json"]["reference"] == (
                f"PAYPILOT-{approval_id}"
            )

            return httpx.Response(
                200,
                json={
                    "total_pages": 1,
                    "items": [{
                        "id": invoice_id,
                        "status": "DRAFT",
                        "detail": {
                            "reference": (
                                f"PAYPILOT-{approval_id}"
                            )
                        },
                        "primary_recipients": [{
                            "billing_info": {
                                "email_address":
                                    "buyer@example.com"
                            }
                        }],
                        "amount": {
                            "currency_code": "USD",
                            "value": "1.00"
                        }
                    }]
                }
            )

    monkeypatch.setattr(
        paypal_recovery.httpx,
        "AsyncClient",
        lambda **kwargs: FakePayPalClient()
    )

    before = store.get_status(approval_id)

    asyncio.run(
        paypal_recovery.check_invoice(approval_id)
    )

    output = capsys.readouterr().out

    assert "One matching invoice candidate found." in output
    assert invoice_id in output

    # Recovery must not silently change approval status.
    assert store.get_status(approval_id) == before
    assert store.get_status(approval_id)["status"] == (
        "needs_review"
    )

    # No second invoice creation occurred.
    assert len(created_drafts) == 1
