from billing_periods import compare_billing_periods


def period(start, end):
    return {
        "start_date": start,
        "end_date": end,
    }


def test_separate_months():
    october = period("2026-10-01", "2026-10-31")
    november = period("2026-11-01", "2026-11-30")

    assert compare_billing_periods(
        november, october
    ) == "distinct"


def test_same_period():
    monthly = period("2026-11-01", "2026-11-30")

    assert compare_billing_periods(
        monthly, monthly
    ) == "overlapping"


def test_partially_overlapping_periods():
    previous = period("2026-10-15", "2026-11-15")
    proposed = period("2026-11-01", "2026-11-30")

    assert compare_billing_periods(
        proposed, previous
    ) == "overlapping"


def test_shared_boundary_day():
    previous = period("2026-10-01", "2026-11-01")
    proposed = period("2026-11-01", "2026-11-30")

    assert compare_billing_periods(
        proposed, previous
    ) == "overlapping"


def test_missing_billing_period():
    proposed = period("2026-11-01", "2026-11-30")

    assert compare_billing_periods(
        proposed, None
    ) == "unknown"


def test_invalid_billing_period():
    proposed = period("2026-11-30", "2026-11-01")
    previous = period("2026-10-01", "2026-10-31")

    assert compare_billing_periods(
        proposed, previous
    ) == "unknown"
