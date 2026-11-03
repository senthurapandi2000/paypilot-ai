
import math
import os
import statistics
import threading
import time
import uuid

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from postgres_approval_store import PostgresApprovalStore


load_dotenv(Path(__file__).with_name(".env"))

ROUNDS = 5
WORKERS = 4

INVOICE = {
    "customer_email": "buyer@example.com",
    "item_name": "Neon benchmark only",
    "quantity": 1,
    "unit_price": "1.00"
}


def percentile(values, percentage):
    ordered = sorted(values)
    index = math.ceil(
        len(ordered) * percentage / 100
    ) - 1
    return ordered[index]


def attempt_claim(store, approval_id, barrier):
    barrier.wait(timeout=15)

    started = time.perf_counter()

    status, _ = store.claim(approval_id)

    latency_ms = (
        time.perf_counter() - started
    ) * 1000

    return status, latency_ms


def main():
    if os.getenv("RUN_NEON_BENCHMARK") != "1":
        raise SystemExit(
            "Set RUN_NEON_BENCHMARK=1 to opt in."
        )

    store = PostgresApprovalStore()
    created_ids = []
    latencies = []
    claimed = 0
    blocked = 0

    started = time.perf_counter()

    try:
        with ThreadPoolExecutor(
            max_workers=WORKERS
        ) as pool:

            for _ in range(ROUNDS):
                approval_id = (
                    "day10-benchmark-"
                    + uuid.uuid4().hex
                )

                created_ids.append(approval_id)

                store.create(
                    approval_id,
                    INVOICE,
                    ttl=600,
                    limit=100000
                )

                barrier = threading.Barrier(WORKERS)

                futures = [
                    pool.submit(
                        attempt_claim,
                        store,
                        approval_id,
                        barrier
                    )
                    for _ in range(WORKERS)
                ]

                results = [
                    future.result(timeout=60)
                    for future in futures
                ]

                statuses = [
                    result[0] for result in results
                ]

                assert statuses.count("claimed") == 1
                assert statuses.count("used") == WORKERS - 1

                claimed += 1
                blocked += WORKERS - 1

                latencies.extend(
                    result[1] for result in results
                )

        elapsed = time.perf_counter() - started

        print("\n=== Neon PostgreSQL Benchmark ===")
        print(f"Rounds: {ROUNDS}")
        print(f"Concurrent attempts: {WORKERS}")
        print(f"Total claims attempted: {ROUNDS * WORKERS}")
        print(f"Unique claims: {claimed}")
        print(f"Duplicate attempts blocked: {blocked}")
        print("Duplicate successful claims: 0")
        print(
            f"P50: {statistics.median(latencies):.2f} ms"
        )
        print(
            f"P95: {percentile(latencies, 95):.2f} ms"
        )
        print(f"Runtime: {elapsed:.2f} seconds")
        print("All concurrency assertions passed.")

    finally:
        if created_ids:
            with store._connect() as conn:
                conn.execute(
                    """
                    DELETE FROM approvals
                    WHERE approval_id = ANY(%s)
                    """,
                    (created_ids,)
                )

            print("Benchmark records cleaned up.")


if __name__ == "__main__":
    main()
