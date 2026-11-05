
from datetime import datetime, timedelta, timezone

from invoice_intelligence import review_invoice


NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)

DRAFT = {
    "customer_email": "buyer@example.com",
    "item_name": "AI consulting",
    "quantity": 1,
    "unit_price": "100.00"
}


def previous_invoice(
    days_ago=1,
    **overrides
):
    record = {
        **DRAFT,
        "invoice_id": "INV2-TEST",
        "status": "DRAFT",
        "currency": "USD",
        "created_at": (
            NOW - timedelta(days=days_ago)
        ).isoformat()
    }
    record.update(overrides)
    return record


def test_detects_duplicate_invoice():
    history = [previous_invoice()]

    result = review_invoice(DRAFT, history, now=NOW)

    assert result["review_recommended"] is True
    assert result["warnings"][0]["code"] == (
        "possible_duplicate"
    )
    assert (
        "INV2-TEST"
        in result["warnings"][0]["matching_invoice_ids"]
    )


def test_different_customer_is_not_duplicate():
    history = [
        previous_invoice(
            customer_email="another@example.com"
        )
    ]

    result = review_invoice(DRAFT, history, now=NOW)

    assert result["review_recommended"] is False
    assert result["warnings"] == []


def test_old_invoice_is_not_recent_duplicate():
    history = [
        previous_invoice(days_ago=31)
    ]

    result = review_invoice(DRAFT, history, now=NOW)

    assert result["review_recommended"] is False


def test_cancelled_invoice_is_ignored():
    history = [
        previous_invoice(status="CANCELLED")
    ]

    result = review_invoice(DRAFT, history, now=NOW)

    assert result["review_recommended"] is False


def test_detects_unusual_amount():
    history = [
        previous_invoice(
            days_ago=i + 31,
            unit_price="20.00"
        )
        for i in range(5)
    ]

    result = review_invoice(DRAFT, history, now=NOW)

    codes = [
        warning["code"]
        for warning in result["warnings"]
    ]

    assert "unusual_amount" in codes
    assert "possible_duplicate" not in codes


def test_insufficient_history_no_anomaly():
    history = [
        previous_invoice(
            days_ago=i + 31,
            unit_price="20.00"
        )
        for i in range(4)
    ]

    result = review_invoice(DRAFT, history, now=NOW)

    assert result["review_recommended"] is False
    assert result["warnings"] == []



def test_service_punctuation_and_hyphenation():
    proposed = {
        **DRAFT,
        "item_name": "Website maintenance"
    }

    for previous_name in (
        "Website maintenance.",
        "Website-maintenance"
    ):
        result = review_invoice(
            proposed,
            [previous_invoice(item_name=previous_name)],
            now=NOW
        )

        assert any(
            warning["code"] == "possible_duplicate"
            for warning in result["warnings"]
        )


def test_same_total_different_quantity_is_not_duplicate():
    proposed = {
        **DRAFT,
        "quantity": 2,
        "unit_price": "50.00"
    }

    result = review_invoice(
        proposed,
        [previous_invoice()],
        now=NOW
    )

    assert result["review_recommended"] is False



def test_amount_baseline_reports_limited_history():
    for count in (0, 4):
        history = [
            previous_invoice(
                days_ago=i + 31,
                unit_price="20.00",
            )
            for i in range(count)
        ]

        result = review_invoice(DRAFT, history, now=NOW)

        assert result["amount_baseline"] == {
            "status": "insufficient",
            "sample_size": count,
            "minimum_sample_size": 5,
        }


def test_amount_baseline_reports_ready_with_five_records():
    history = [
        previous_invoice(
            days_ago=i + 31,
            unit_price="20.00",
        )
        for i in range(5)
    ]

    result = review_invoice(DRAFT, history, now=NOW)

    assert result["amount_baseline"] == {
        "status": "ready",
        "sample_size": 5,
        "minimum_sample_size": 5,
    }

    assert any(
        warning["code"] == "unusual_amount"
        for warning in result["warnings"]
    )
