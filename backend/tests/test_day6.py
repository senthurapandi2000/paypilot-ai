
from concurrent.futures import ThreadPoolExecutor

import pytest

from approval_store import ApprovalStore, TooManyApprovals


@pytest.fixture
def store(tmp_path):
    return ApprovalStore(
        tmp_path / "test_day6.sqlite3"
    )


@pytest.fixture
def invoice():
    return {
        "customer_email": "buyer@example.com",
        "item_name": "AI consulting",
        "quantity": 2,
        "unit_price": "25.00"
    }


def test_approval_survives_restart(store, invoice):
    store.create("approval-1", invoice)

    # Simulate reopening the database after a restart.
    restarted = ApprovalStore(store.path)

    status, payload = restarted.claim("approval-1")

    assert status == "claimed"
    assert payload == invoice


def test_duplicate_approval_is_blocked(store, invoice):
    store.create("approval-2", invoice)

    first, _ = store.claim("approval-2")
    second, _ = store.claim("approval-2")

    assert first == "claimed"
    assert second == "used"


def test_concurrent_claims_only_allow_one(store, invoice):
    store.create("approval-3", invoice)

    def attempt_claim(_):
        connection = ApprovalStore(store.path)
        status, _ = connection.claim("approval-3")
        return status

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt_claim, range(8)))

    assert results.count("claimed") == 1
    assert results.count("used") == 7


def test_cancel_prevents_approval(store, invoice):
    store.create("approval-4", invoice)

    assert store.cancel("approval-4") is True
    assert store.cancel("approval-4") is False

    status, payload = store.claim("approval-4")

    assert status == "used"
    assert payload is None


def test_expired_approval_cannot_be_used(store, invoice):
    store.create(
        "approval-5",
        invoice,
        ttl=-1
    )

    status, payload = store.claim("approval-5")

    assert status == "expired"
    assert payload is None


def test_uncertain_result_blocks_retry(store, invoice):
    store.create("approval-6", invoice)

    status, _ = store.claim("approval-6")
    assert status == "claimed"

    assert store.mark_uncertain("approval-6") is True

    record = store.get_status("approval-6")
    assert record["status"] == "needs_review"

    repeated, _ = store.claim("approval-6")
    assert repeated == "used"


def test_completed_invoice_is_recorded(store, invoice):
    store.create("approval-7", invoice)

    status, _ = store.claim("approval-7")
    assert status == "claimed"

    assert store.complete(
        "approval-7",
        "INV2-TEST"
    ) is True

    record = store.get_status("approval-7")

    assert record["status"] == "completed"
    assert record["paypal_invoice_id"] == "INV2-TEST"

    repeated, _ = store.claim("approval-7")
    assert repeated == "used"


def test_pending_approval_limit(store, invoice):
    store.create(
        "approval-8",
        invoice,
        limit=1
    )

    with pytest.raises(TooManyApprovals):
        store.create(
            "approval-9",
            invoice,
            limit=1
        )

    assert store.cancel("approval-8") is True

    store.create(
        "approval-9",
        invoice,
        limit=1
    )
