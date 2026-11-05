"""Evaluate invoice-risk detection on labeled synthetic cases."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from invoice_intelligence import review_invoice


DATASET = Path("evaluation/invoice_review_cases.jsonl")
OUTPUT = Path("evaluation/invoice_review_metrics.json")


def safe_div(a, b):
    return a / b if b else 0.0


def calculate_metrics(pairs):
    tp = fp = tn = fn = 0

    for expected, predicted in pairs:
        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif expected and not predicted:
            fn += 1
        else:
            tn += 1

    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": safe_div(tp + tn, tp + tn + fp + fn),
        "precision": precision,
        "recall": recall,
        "f1": safe_div(
            2 * precision * recall,
            precision + recall
        ),
        "false_positive_rate": safe_div(fp, fp + tn)
    }


cases = [
    json.loads(line)
    for line in DATASET.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]

binary_pairs = []
type_pairs = {
    "possible_duplicate": [],
    "unusual_amount": [],
}
category_results = Counter()
category_correct = Counter()
mismatches = []

for case in cases:
    now = datetime.fromisoformat(case["now"])

    result = review_invoice(
        case["draft"],
        case["history"],
        now=now
    )

    expected = set(case["expected_codes"])
    predicted = {
        warning["code"]
        for warning in result["warnings"]
    }

    binary_pairs.append(
        (bool(expected), bool(predicted))
    )

    for warning_type in type_pairs:
        type_pairs[warning_type].append(
            (
                warning_type in expected,
                warning_type in predicted
            )
        )

    category = case["category"]
    category_results[category] += 1

    if expected == predicted:
        category_correct[category] += 1
    else:
        mismatches.append({
            "case_id": case["case_id"],
            "category": category,
            "expected": sorted(expected),
            "predicted": sorted(predicted),
        })


overall = calculate_metrics(binary_pairs)

report = {
    "dataset": str(DATASET),
    "dataset_type": "synthetic_rule_aligned",
    "total_cases": len(cases),
    "overall": overall,
    "by_warning_type": {
        name: calculate_metrics(pairs)
        for name, pairs in type_pairs.items()
    },
    "by_category": {
        name: {
            "total": count,
            "correct": category_correct[name],
            "accuracy": safe_div(
                category_correct[name],
                count
            )
        }
        for name, count in sorted(category_results.items())
    },
    "mismatches": mismatches,
}

OUTPUT.write_text(
    json.dumps(report, indent=2),
    encoding="utf-8"
)

print("\nPAYPILOT AI - INVOICE INTELLIGENCE EVALUATION")
print("=" * 52)
print("Total cases:", len(cases))

print("\nCONFUSION MATRIX")
print("True positives: ", overall["tp"])
print("False positives:", overall["fp"])
print("True negatives: ", overall["tn"])
print("False negatives:", overall["fn"])

print("\nPERFORMANCE METRICS")
for metric in (
    "accuracy",
    "precision",
    "recall",
    "f1",
    "false_positive_rate"
):
    print(
        f"{metric:22s}: "
        f"{overall[metric] * 100:.2f}%"
    )

print("\nPER-SCENARIO ACCURACY")
for category, values in report["by_category"].items():
    print(
        f"{category:30s} "
        f"{values['accuracy'] * 100:6.2f}% "
        f"({values['correct']}/{values['total']})"
    )

print("\nMismatched cases:", len(mismatches))
print("Report saved:", OUTPUT)
