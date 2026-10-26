
import math
import statistics
import tempfile
import threading
import time

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from approval_store import ApprovalStore


ROUNDS = 30
WORKERS = 8

INVOICE = {
    "customer_email": "buyer@example.com",
    "item_name": "Benchmark only",
    "quantity": 1,
    "unit_price": "1.00",
}


def percentile(values, percentage):
    ordered = sorted(values)
    index = math.ceil(len(ordered) * percentage / 100) - 1
    return ordered[index]


def attempt_claim(store, approval_id, barrier):
    barrier.wait(timeout=10)

    start = time.perf_counter()
    status, _ = store.claim(approval_id)
    elapsed_ms = (time.perf_counter() - start) * 1000

    return status, elapsed_ms


def main():
    latencies = []
    total_claimed = 0
    total_blocked = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        store = ApprovalStore(
            Path(temp_dir) / "benchmark.sqlite3"
        )

        start_total = time.perf_counter()

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for i in range(ROUNDS):
                approval_id = f"benchmark-approval-{i}"

                store.create(
                    approval_id,
                    INVOICE,
                    limit=100000,
                )

                barrier = threading.Barrier(WORKERS)

                futures = [
                    pool.submit(
                        attempt_claim,
                        store,
                        approval_id,
                        barrier,
                    )
                    for _ in range(WORKERS)
                ]

                results = [
                    future.result(timeout=20)
                    for future in futures
                ]

                statuses = [status for status, _ in results]

                assert statuses.count("claimed") == 1, (
                    f"Unexpected winners in round {i}: {statuses}"
                )
                assert statuses.count("used") == WORKERS - 1

                total_claimed += statuses.count("claimed")
                total_blocked += statuses.count("used")

                latencies.extend(
                    latency for _, latency in results
                )

        duration = time.perf_counter() - start_total

    print("\n=== PayPilot AI Approval Benchmark ===")
    print("Database: Temporary local SQLite")
    print(f"Rounds: {ROUNDS}")
    print(f"Concurrent attempts per round: {WORKERS}")
    print(f"Total attempts: {ROUNDS * WORKERS}")
    print(f"Successful unique claims: {total_claimed}")
    print(f"Blocked duplicate claims: {total_blocked}")
    print("Duplicate successful claims: 0")
    print(f"Median (p50) latency: {statistics.median(latencies):.2f} ms")
    print(f"P95 latency: {percentile(latencies, 95):.2f} ms")
    print(f"Benchmark runtime: {duration:.2f} s")
    print("All concurrency assertions passed.")


if __name__ == "__main__":
    main()
