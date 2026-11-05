
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ai_agent
from ai_agent import install_ai_routes
from approval_store import ApprovalStore
from main import InvoiceInput


@pytest.mark.parametrize("review_fails", [False, True])
def test_prepare_review_integration(
    tmp_path, monkeypatch, review_fails
):
    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "test-only-key"
    )

    extracted = {
        "customer_email": "buyer@example.com",
        "item_name": "AI consulting",
        "quantity": 1,
        "unit_price": "100.00"
    }

    class FakeGeminiClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return httpx.Response(
                200,
                json={
                    "candidates": [{
                        "content": {
                            "parts": [{
                                "text": json.dumps(extracted)
                            }]
                        }
                    }]
                }
            )

    monkeypatch.setattr(
        ai_agent.httpx,
        "AsyncClient",
        lambda **kwargs: FakeGeminiClient()
    )

    async def fake_create_invoice(*args, **kwargs):
        raise AssertionError(
            "No invoice should be created during prepare."
        )

    async def fake_reviewer(draft):
        assert draft["unit_price"] == "100.00"

        if review_fails:
            raise RuntimeError("Simulated history failure")

        return {
            "status": "complete",
            "review_recommended": True,
            "warnings": [{
                "code": "possible_duplicate",
                "message": "Possible duplicate invoice."
            }],
            "examined": 1,
            "skipped": 0,
            "message": "Review completed."
        }

    app = FastAPI()

    store = ApprovalStore(
        tmp_path / "review_prepare.sqlite3"
    )

    install_ai_routes(
        app,
        InvoiceInput,
        fake_create_invoice,
        approval_store=store,
        invoice_reviewer=fake_reviewer
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/ai/prepare",
            json={
                "message": (
                    "Create an invoice for buyer@example.com "
                    "for 1 hour of AI consulting at $100"
                )
            }
        )

    assert response.status_code == 200

    data = response.json()

    assert data["ready"] is True
    assert data["approval_id"]
    assert data["preview"]["total"] == "100.00"

    if review_fails:
        assert data["review"]["status"] == "unavailable"
        assert (
            data["review"]["review_recommended"]
            is None
        )
    else:
        assert data["review"]["status"] == "complete"
        assert data["review"]["review_recommended"] is True
        assert data["review"]["warnings"][0]["code"] == (
            "possible_duplicate"
        )
