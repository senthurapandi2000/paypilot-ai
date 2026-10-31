
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "PAYPILOT_DEMO_KEY",
        "day5-test-key-only"
    )

    with TestClient(app) as test_client:
        yield test_client


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200


def test_missing_key_is_rejected(client):
    response = client.get("/api/demo/verify")
    assert response.status_code == 401


def test_wrong_key_is_rejected(client):
    response = client.get(
        "/api/demo/verify",
        headers={"X-Demo-Key": "wrong-key"}
    )
    assert response.status_code == 401


def test_correct_key_is_accepted(client):
    response = client.get(
        "/api/demo/verify",
        headers={"X-Demo-Key": "day5-test-key-only"}
    )
    assert response.status_code == 200
    assert response.json()["authorized"] is True


def test_invoice_api_requires_key(client):
    response = client.get("/api/invoices/list")
    assert response.status_code == 401


def test_missing_configuration(client, monkeypatch):
    monkeypatch.delenv("PAYPILOT_DEMO_KEY")

    response = client.get("/api/demo/verify")
    assert response.status_code == 503
