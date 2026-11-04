
import pytest
from fastapi.testclient import TestClient

import main
from rate_limit import SlidingWindowLimiter


DEMO_KEY = "day7-test-key"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "PAYPILOT_DEMO_KEY",
        DEMO_KEY
    )

    # Each test gets fresh rate-limit counters.
    monkeypatch.setattr(
        main,
        "limiter",
        SlidingWindowLimiter()
    )

    with TestClient(main.app) as test_client:
        yield test_client


def auth_headers():
    return {"X-Demo-Key": DEMO_KEY}


def test_health_remains_public(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_demo_verification_is_rate_limited(client):
    for _ in range(10):
        response = client.get(
            "/api/demo/verify",
            headers=auth_headers()
        )
        assert response.status_code == 200

    blocked = client.get(
        "/api/demo/verify",
        headers=auth_headers()
    )

    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"


def test_ai_preparation_is_rate_limited(client):
    for _ in range(10):
        response = client.post(
            "/api/ai/prepare",
            headers=auth_headers(),
            json={"message": "x"}
        )

        # Invalid request, so Gemini is never called.
        assert response.status_code == 422

    blocked = client.post(
        "/api/ai/prepare",
        headers=auth_headers(),
        json={"message": "x"}
    )

    assert blocked.status_code == 429


def test_invoice_creation_is_rate_limited(client):
    # Both endpoints share one creation limit.
    for index in range(6):
        path = (
            "/api/invoices/draft"
            if index % 2 == 0
            else "/api/ai/approve"
        )

        response = client.post(
            path,
            headers=auth_headers(),
            json={}
        )

        # Invalid input prevents PayPal calls.
        assert response.status_code == 422

    blocked = client.post(
        "/api/invoices/draft",
        headers=auth_headers(),
        json={}
    )

    assert blocked.status_code == 429


def test_unauthorized_requests_are_rejected(client):
    response = client.post(
        "/api/ai/prepare",
        json={"message": "test message"}
    )

    assert response.status_code == 401
