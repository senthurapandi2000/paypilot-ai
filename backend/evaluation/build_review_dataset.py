"""Generate reproducible synthetic invoice review cases."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
cases = []


def historical(draft, days_ago=5, **changes):
    record = {
        **draft,
        "invoice_id": f"INV2-SYNTH-{len(cases):03d}",
        "status": "DRAFT",
        "currency": "USD",
        "created_at": (
            NOW - timedelta(days=days_ago)
        ).isoformat(),
    }
    record.update(changes)
    return record


def add(category, draft, history, expected):
    cases.append({
        "case_id": f"CASE-{len(cases) + 1:03d}",
        "category": category,
        "now": NOW.isoformat(),
        "draft": draft,
        "history": history,
        "expected_codes": expected,
    })


for i in range(100):
    price = 100 + i * 7

    draft = {
        "customer_email": f"buyer{i}@example.com",
        "item_name": f"AI consulting {i}",
        "quantity": 1,
        "unit_price": f"{price:.2f}",
    }

    # Clearly matching invoice
    add(
        "exact_duplicate",
        draft,
        [historical(draft)],
        ["possible_duplicate"],
    )

    # Equivalent text with different capitalization/spacing
    add(
        "normalized_duplicate",
        draft,
        [historical(
            draft,
            customer_email=draft["customer_email"].upper(),
            item_name=f"  AI   consulting  {i}  ",
        )],
        ["possible_duplicate"],
    )

    # Duplicate at the 30-day boundary
    add(
        "duplicate_30_day_boundary",
        draft,
        [historical(draft, days_ago=30)],
        ["possible_duplicate"],
    )

    # Different customer
    add(
        "different_customer",
        draft,
        [historical(
            draft,
            customer_email=f"other{i}@example.com",
        )],
        [],
    )

    # Different service
    add(
        "different_service",
        draft,
        [historical(draft, item_name="Design work")],
        [],
    )

    # Different invoice total
    add(
        "different_total",
        draft,
        [historical(
            draft,
            unit_price=f"{price - 1:.2f}",
        )],
        [],
    )

    # Outside the duplicate-review window
    add(
        "older_than_30_days",
        draft,
        [historical(draft, days_ago=31)],
        [],
    )

    # Cancelled invoices should not trigger
    add(
        "cancelled_invoice",
        draft,
        [historical(draft, status="CANCELLED")],
        [],
    )

    # Five lower-priced historical invoices
    add(
        "unusual_amount",
        draft,
        [
            historical(
                draft,
                days_ago=31 + j,
                invoice_id=f"INV2-SYNTH-{i}-{j}",
                unit_price="20.00",
            )
            for j in range(5)
        ],
        ["unusual_amount"],
    )

    # Four records are insufficient for anomaly baseline
    add(
        "insufficient_history",
        draft,
        [
            historical(
                draft,
                days_ago=31 + j,
                invoice_id=f"INV2-LOW-{i}-{j}",
                unit_price="20.00",
            )
            for j in range(4)
        ],
        [],
    )


assert len(cases) == 1000

path = Path("evaluation/invoice_review_cases.jsonl")

with path.open("w", encoding="utf-8") as file:
    for case in cases:
        file.write(json.dumps(case) + "\n")

print("Evaluation cases generated:", len(cases))
print("Duplicate cases:", sum(
    "possible_duplicate" in c["expected_codes"]
    for c in cases
))
print("Amount anomaly cases:", sum(
    "unusual_amount" in c["expected_codes"]
    for c in cases
))
print("Clean cases:", sum(
    not c["expected_codes"] for c in cases
))
print("Dataset:", path)
