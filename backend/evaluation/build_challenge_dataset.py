import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
cases = []

def draft(service="Website maintenance", price="100.00", quantity=1):
    return {
        "customer_email": "buyer@example.com",
        "item_name": service,
        "quantity": quantity,
        "unit_price": price,
    }

def historical(invoice, days=7, **changes):
    row = {
        **invoice,
        "invoice_id": f"INV2-CHALLENGE-{len(cases):03d}",
        "status": "DRAFT",
        "currency": "USD",
        "created_at": (NOW - timedelta(days=days)).isoformat(),
    }
    row.update(changes)
    return row

def add(category, proposed, history, expected, rationale):
    cases.append({
        "case_id": f"CHALLENGE-{len(cases)+1:03d}",
        "category": category,
        "now": NOW.isoformat(),
        "draft": proposed,
        "history": history,
        "expected_codes": expected,
        "label_rationale": rationale,
    })

base = draft()

add("exact_duplicate", base, [historical(base)],
    ["possible_duplicate"], "Same work billed twice")

add("case_spacing_duplicate", base,
    [historical(base, item_name="  WEBSITE   MAINTENANCE  ")],
    ["possible_duplicate"], "Equivalent text")

add("legitimate_recurring", base, [historical(base)],
    [], "Separate authorized recurring billing period")

add("punctuation_duplicate", base,
    [historical(base, item_name="Website maintenance.")],
    ["possible_duplicate"], "Same service with punctuation")

add("hyphenated_duplicate", draft("Website-maintenance"),
    [historical(base)],
    ["possible_duplicate"], "Equivalent service wording")

add("different_customer", base,
    [historical(base, customer_email="other@example.com")],
    [], "Different buyer")

add("different_service", base,
    [historical(base, item_name="Logo design")],
    [], "Different work")

add("cancelled_history", base,
    [historical(base, status="CANCELLED")],
    [], "Prior invoice was cancelled")

add("refunded_history", base,
    [historical(base, status="REFUNDED")],
    [], "Prior invoice was refunded")

add("older_invoice", base,
    [historical(base, days=31)],
    [], "Outside the review window")

low_history = [
    historical(base, days=31+i, unit_price="100.00")
    for i in range(5)
]

add("four_times_baseline", draft(price="400.00"),
    low_history, ["unusual_amount"],
    "Four times established historical amount")

add("two_point_five_times_baseline", draft(price="250.00"),
    low_history, ["unusual_amount"],
    "Large increase for a stable-price service")

add("authorized_large_project", draft(price="400.00"),
    low_history, [],
    "Large amount explicitly approved for extra scope")

add("insufficient_history_large_spike", draft(price="1000.00"),
    low_history[:4], ["unusual_amount"],
    "Extreme increase despite limited history")

add("new_customer_high_amount",
    draft(price="5000.00"), [],
    [], "No evidence to establish an anomaly")

add("same_total_different_work",
    draft(price="50.00", quantity=2),
    [historical(base)],
    [], "Independent job with different billed units")

out = Path("evaluation/challenge_review_cases.jsonl")

with out.open("w", encoding="utf-8") as f:
    for case in cases:
        f.write(json.dumps(case) + "\n")

print("Challenge cases generated:", len(cases))
print("Expected risk cases:", sum(
    bool(c["expected_codes"]) for c in cases
))
print("Expected clean cases:", sum(
    not c["expected_codes"] for c in cases
))
print("Dataset:", out)
