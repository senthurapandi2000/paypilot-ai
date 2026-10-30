"""Evaluate Invoice Intelligence on challenge scenarios."""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from invoice_intelligence import review_invoice


DATASET = Path(__file__).with_name(
    "challenge_review_cases.jsonl"
)
OUTPUT = Path(__file__).with_name(
    "challenge_review_metrics.json"
)

cases = [
    json.loads(line)
    for line in DATASET.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]

tp = fp = tn = fn = 0
mismatches = []

for case in cases:
    result = review_invoice(
        case["draft"],
        case["history"],
        now=datetime.fromisoformat(case["now"])
    )

    expected = set(case["expected_codes"])
    predicted = {
        warning["code"]
        for warning in result["warnings"]
    }

    if expected and predicted:
        tp += 1
    elif not expected and predicted:
        fp += 1
    elif not expected and not predicted:
        tn += 1
    else:
        fn += 1

    if expected != predicted:
        mismatches.append({
            "case_id": case["case_id"],
            "category": case["category"],
            "expected": sorted(expected),
            "predicted": sorted(predicted),
            "reason": case["label_rationale"]
        })


def divide(a, b):
    return a / b if b else 0.0


accuracy = divide(tp + tn, len(cases))
precision = divide(tp, tp + fp)
recall = divide(tp, tp + fn)
f1 = divide(
    2 * precision * recall,
    precision + recall
)
fpr = divide(fp, fp + tn)

report = {
    "dataset": "independently labeled synthetic challenge cases",
    "total_cases": len(cases),
    "confusion_matrix": {
        "TP": tp, "FP": fp, "TN": tn, "FN": fn
    },
    "metrics": {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fpr
    },
    "mismatches": mismatches
}

OUTPUT.write_text(
    json.dumps(report, indent=2),
    encoding="utf-8"
)

print("\nPAYPILOT AI - CHALLENGE EVALUATION")
print("=" * 45)
print("Total cases:", len(cases))

print("\nCONFUSION MATRIX")
print("True positives: ", tp)
print("False positives:", fp)
print("True negatives: ", tn)
print("False negatives:", fn)

print("\nPERFORMANCE METRICS")
for name, value in report["metrics"].items():
    print(f"{name:22s}: {value * 100:.2f}%")

print("\nINCORRECT SCENARIOS")
for mismatch in mismatches:
    print(
        f"{mismatch['case_id']} | "
        f"{mismatch['category']}"
    )
    print("  Expected:", mismatch["expected"])
    print("  Predicted:", mismatch["predicted"])

print("\nTotal mismatches:", len(mismatches))
print("Report saved:", OUTPUT)
