
import asyncio

import httpx
import pytest

import paypal_recovery
from approval_store import ApprovalStore


APPROVAL_ID = "approval-recovery-test-001"
REFERENCE = f"PAYPILOT-{APPROVAL_ID}"


@pytest.fixture
def recovery_setup(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "APPROVAL_DB_PATH",
        str(tmp_path / "recovery.sqlite3")
    )

    store = ApprovalStore()

    store.create(
        APPROVAL_ID,
        {
            "customer_email": "buyer@example.com",
            "item_name": "AI consulting",
            "quantity": 2,
            "unit_price": "25.00"
        }
    )

    async def fake_token(client):
        return "fake-sandbox-token"

    monkeypatch.setattr(
        paypal_recovery,
        "get_paypal_token",
        fake_token
    )

    return store


def matching_invoice():
    return {
        "id": "INV2-TEST",
        "status": "DRAFT",
        "detail": {
            "reference": REFERENCE
        },
        "primary_recipients": [
            {
                "billing_info": {
                    "email_address": "buyer@example.com"
                }
            }
        ],
        "amount": {
            "currency_code": "USD",
            "value": "50.00"
        }
    }


@pytest.mark.parametrize(
    "scenario, expected",
    [
        ("found", "One matching invoice candidate found."),
        ("empty", "No exact matching invoice found."),
        ("wrong_amount", "No exact matching invoice found."),
        ("multiple", "Multiple matching invoices found."),
        ("pagination", "Multiple result pages."),
        ("api_error", "Search failed: HTTP 502.")
    ]
)
def test_recovery_scenarios(
    recovery_setup,
    monkeypatch,
    capsys,
    scenario,
    expected
):
    store = recovery_setup
    calls = []

    item = matching_invoice()

    data = {
        "total_pages": 1,
        "items": [item]
    }

    status_code = 200

    if scenario == "empty":
        data["items"] = []

    elif scenario == "wrong_amount":
        item["amount"]["value"] = "99.00"

    elif scenario == "multiple":
        second = matching_invoice()
        second["id"] = "INV2-SECOND"
        data["items"] = [item, second]

    elif scenario == "pagination":
        data["total_pages"] = 2

    elif scenario == "api_error":
        status_code = 502

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            calls.append(url)

            assert url.endswith(
                "/v2/invoicing/search-invoices"
            )

            assert kwargs["json"]["reference"] == REFERENCE
            assert kwargs["json"]["recipient_email"] == (
                "buyer@example.com"
            )
            assert kwargs["json"]["currency_code"] == "USD"

            return httpx.Response(
                status_code,
                json=data
            )

    monkeypatch.setattr(
        paypal_recovery.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient()
    )

    before = store.get_status(APPROVAL_ID)

    asyncio.run(
        paypal_recovery.check_invoice(APPROVAL_ID)
    )

    output = capsys.readouterr().out

    assert expected in output
    assert len(calls) == 1

    # Recovery must not update the approval.
    assert store.get_status(APPROVAL_ID) == before


def test_missing_approval_skips_paypal(
    recovery_setup,
    monkeypatch,
    capsys
):
    def forbidden_client(**kwargs):
        raise AssertionError(
            "No PayPal request should be made."
        )

    monkeypatch.setattr(
        paypal_recovery.httpx,
        "AsyncClient",
        forbidden_client
    )

    asyncio.run(
        paypal_recovery.check_invoice("missing-approval")
    )

    output = capsys.readouterr().out

    assert "Approval not found." in output
