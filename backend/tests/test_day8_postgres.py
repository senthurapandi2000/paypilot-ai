
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from dotenv import dotenv_values

from postgres_approval_store import PostgresApprovalStore


TEST_INVOICE = {
    "customer_email": "buyer@example.com",
    "item_name": "AI consulting test",
    "quantity": 2,
    "unit_price": "25.00"
}


@pytest.fixture
def neon_store():
    if os.getenv("RUN_NEON_TESTS") != "1":
        pytest.skip("Neon tests require explicit opt-in.")

    env_file = Path(__file__).resolve().parents[1] / ".env"
    config = dotenv_values(env_file)

    database_url = (
        os.getenv("DATABASE_URL")
        or config.get("DATABASE_URL")
    )

    if not database_url:
        pytest.fail("DATABASE_URL is not configured.")

    store = PostgresApprovalStore(database_url)
    created_ids = []

    def new_id():
        approval_id = f"day8-test-{uuid.uuid4().hex}"
        created_ids.append(approval_id)
        return approval_id

    yield store, new_id

    # Delete only records created by these tests.
    with store._connect() as conn:
        conn.execute(
            "DELETE FROM approvals WHERE approval_id = ANY(%s)",
            (created_ids,)
        )


def test_persistence_after_reconnect(neon_store):
    store, new_id = neon_store
    approval_id = new_id()

    store.create(
        approval_id, TEST_INVOICE, limit=100000
    )

    restarted = PostgresApprovalStore(
        store.database_url
    )

    status, payload = restarted.claim(approval_id)

    assert status == "claimed"
    assert payload == TEST_INVOICE

    assert restarted.complete(
        approval_id, "INV2-TEST-ONLY"
    )

    record = store.get_status(approval_id)

    assert record["status"] == "completed"
    assert record["paypal_invoice_id"] == "INV2-TEST-ONLY"


def test_duplicate_claim_is_blocked(neon_store):
    store, new_id = neon_store
    approval_id = new_id()

    store.create(
        approval_id, TEST_INVOICE, limit=100000
    )

    first, _ = store.claim(approval_id)
    second, _ = store.claim(approval_id)

    assert first == "claimed"
    assert second == "used"


def test_concurrent_claims(neon_store):
    store, new_id = neon_store
    approval_id = new_id()

    store.create(
        approval_id, TEST_INVOICE, limit=100000
    )

    def attempt(_):
        status, _ = store.claim(approval_id)
        return status

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))

    assert results.count("claimed") == 1
    assert results.count("used") == 5


def test_cancellation(neon_store):
    store, new_id = neon_store
    approval_id = new_id()

    store.create(
        approval_id, TEST_INVOICE, limit=100000
    )

    assert store.cancel(approval_id) is True

    status, payload = store.claim(approval_id)

    assert status == "used"
    assert payload is None


def test_expiration(neon_store):
    store, new_id = neon_store
    approval_id = new_id()

    store.create(
        approval_id,
        TEST_INVOICE,
        ttl=-1,
        limit=100000
    )

    status, payload = store.claim(approval_id)

    assert status == "expired"
    assert payload is None


def test_uncertain_result(neon_store):
    store, new_id = neon_store
    approval_id = new_id()

    store.create(
        approval_id, TEST_INVOICE, limit=100000
    )

    status, _ = store.claim(approval_id)
    assert status == "claimed"

    assert store.mark_uncertain(approval_id)

    record = store.get_status(approval_id)

    assert record["status"] == "needs_review"

    repeated, _ = store.claim(approval_id)

    assert repeated == "used"


def test_get_invoice_read_only(neon_store):
    store, new_id = neon_store
    approval_id = new_id()

    store.create(
        approval_id,
        TEST_INVOICE,
        limit=100000
    )

    before = store.get_status(approval_id)

    record = store.get_invoice(approval_id)

    assert record is not None
    assert record["invoice"] == TEST_INVOICE
    assert record["status"] == "pending"

    # Reading must not change the approval.
    assert store.get_status(approval_id) == before

    assert store.get_invoice(
        "nonexistent-day8-approval"
    ) is None
