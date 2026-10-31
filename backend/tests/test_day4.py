
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ai_agent
from ai_agent import install_ai_routes, PENDING, PENDING_LOCK
from main import InvoiceInput


@pytest.fixture
def test_app(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")

    state = {
        "extracted": {
            "customer_email": "buyer@example.com",
            "item_name": "AI consulting",
            "quantity": 2,
            "unit_price": "25.00"
        },
        "created": []
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
                                "text": json.dumps(state["extracted"])
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

    async def fake_create_invoice(
        invoice,
        idempotency_key=None
    ):
        state["created"].append({
            "invoice": invoice,
            "request_id": idempotency_key
        })

        return {
            "success": True,
            "invoice_id": "INV2-TEST",
            "status": "DRAFT"
        }

    with PENDING_LOCK:
        PENDING.clear()

    app = FastAPI()

    install_ai_routes(
        app,
        InvoiceInput,
        fake_create_invoice
    )

    with TestClient(app) as client:
        yield client, state

    with PENDING_LOCK:
        PENDING.clear()


def prepare(client):
    return client.post(
        "/api/ai/prepare",
        json={
            "message": (
                "Create an invoice for buyer@example.com "
                "for 2 hours of AI consulting at $25 per hour"
            )
        }
    )


def test_prepare_and_approve_once(test_app):
    client, state = test_app

    response = prepare(client)

    assert response.status_code == 200
    data = response.json()

    assert data["ready"] is True
    assert data["preview"]["total"] == "50.00"

    approval_id = data["approval_id"]

    approved = client.post(
        "/api/ai/approve",
        json={"approval_id": approval_id}
    )

    assert approved.status_code == 201
    assert len(state["created"]) == 1

    assert (
        state["created"][0]["request_id"]
        == approval_id
    )

    # A repeated approval must not create another invoice.
    repeated = client.post(
        "/api/ai/approve",
        json={"approval_id": approval_id}
    )

    assert repeated.status_code == 404
    assert len(state["created"]) == 1


def test_missing_customer_email(test_app):
    client, state = test_app

    state["extracted"]["customer_email"] = None

    response = prepare(client)

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["approval_id"] is None
    assert len(state["created"]) == 0


def test_cancel_prevents_approval(test_app):
    client, state = test_app

    approval_id = prepare(client).json()["approval_id"]

    cancelled = client.post(
        "/api/ai/cancel",
        json={"approval_id": approval_id}
    )

    assert cancelled.status_code == 200

    approved = client.post(
        "/api/ai/approve",
        json={"approval_id": approval_id}
    )

    assert approved.status_code == 404
    assert len(state["created"]) == 0


def test_expired_approval(test_app):
    client, state = test_app

    approval_id = prepare(client).json()["approval_id"]

    with PENDING_LOCK:
        PENDING[approval_id]["expires"] = -1

    approved = client.post(
        "/api/ai/approve",
        json={"approval_id": approval_id}
    )

    assert approved.status_code == 410
    assert len(state["created"]) == 0


def test_rejects_email_embedded_in_word(test_app):
    client, state = test_app

    response = client.post(
        "/api/ai/prepare",
        json={
            "message": (
                "Create an invoice for buyer@example.comand "
                "2 hours of AI consulting at $25 per hour."
            )
        }
    )

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["approval_id"] is None
    assert len(state["created"]) == 0
