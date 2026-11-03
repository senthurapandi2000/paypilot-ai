
import pytest
from fastapi.testclient import TestClient

import main
from rate_limit import SlidingWindowLimiter


DEMO_KEY = "day10-test-passphrase"


class FakeDailyQuota:
    def __init__(self):
        self.counts = {}
        self.calls = []
        self.fail = False

    def allow(self, name, limit):
        self.calls.append((name, limit))

        if self.fail:
            raise ConnectionError(
                "Simulated Neon database outage"
            )

        used = self.counts.get(name, 0)

        if used >= limit:
            return False

        self.counts[name] = used + 1
        return True


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv(
        "PAYPILOT_DEMO_KEY",
        DEMO_KEY
    )

    monkeypatch.setenv(
        "ENABLE_DAILY_QUOTAS",
        "1"
    )

    # Reset per-minute counters for each test.
    monkeypatch.setattr(
        main,
        "limiter",
        SlidingWindowLimiter()
    )

    quota = FakeDailyQuota()

    monkeypatch.setattr(
        main,
        "get_daily_quota",
        lambda: quota
    )

    with TestClient(main.app) as client:
        yield client, quota


def headers():
    return {"X-Demo-Key": DEMO_KEY}


def test_ai_daily_quota_enforced(setup):
    client, quota = setup

    quota.counts["gemini_prepare"] = 49

    first = client.post(
        "/api/ai/prepare",
        headers=headers(),
        json={"message": "x"}
    )

    # Invalid input: Gemini is never called.
    assert first.status_code == 422

    second = client.post(
        "/api/ai/prepare",
        headers=headers(),
        json={"message": "x"}
    )

    assert second.status_code == 429
    assert "Daily demo quota" in (
        second.json()["detail"]
    )

    assert quota.counts["gemini_prepare"] == 50
    assert quota.calls == [
        ("gemini_prepare", 50),
        ("gemini_prepare", 50)
    ]


def test_invoice_endpoints_share_quota(setup):
    client, quota = setup

    quota.counts["invoice_create"] = 14

    first = client.post(
        "/api/ai/approve",
        headers=headers(),
        json={}
    )

    assert first.status_code == 422

    second = client.post(
        "/api/invoices/draft",
        headers=headers(),
        json={}
    )

    assert second.status_code == 429
    assert quota.counts["invoice_create"] == 15

    assert quota.calls == [
        ("invoice_create", 15),
        ("invoice_create", 15)
    ]


def test_database_failure_fails_closed(setup):
    client, quota = setup

    quota.fail = True

    response = client.post(
        "/api/ai/prepare",
        headers=headers(),
        json={"message": "x"}
    )

    assert response.status_code == 503
    assert "quota service is unavailable" in (
        response.json()["detail"]
    )


def test_disabled_quota_does_not_call_database(
    setup, monkeypatch
):
    client, quota = setup

    monkeypatch.setenv(
        "ENABLE_DAILY_QUOTAS",
        "0"
    )

    quota.fail = True

    response = client.post(
        "/api/ai/prepare",
        headers=headers(),
        json={"message": "x"}
    )

    assert response.status_code == 422
    assert quota.calls == []


def test_unauthorized_requests_do_not_use_quota(
    setup
):
    client, quota = setup

    response = client.post(
        "/api/ai/prepare",
        headers={"X-Demo-Key": "incorrect"},
        json={"message": "x"}
    )

    assert response.status_code == 401
    assert quota.calls == []
