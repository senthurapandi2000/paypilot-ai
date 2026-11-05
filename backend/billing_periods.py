"""Compare structured invoice billing periods."""

import re
from datetime import date


def _parse_period(value):
    if not isinstance(value, dict):
        return None

    start_text = value.get("start_date")
    end_text = value.get("end_date")

    for text in (start_text, end_text):
        if not isinstance(text, str):
            return None

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return None

    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except ValueError:
        return None

    if start > end:
        return None

    return start, end


def compare_billing_periods(proposed, previous):
    """
    Compare inclusive billing date ranges.

    Returns:
      distinct    - different, nonoverlapping periods
      overlapping - periods share at least one day
      unknown     - missing or invalid metadata

    This comparison does not verify authorization.
    """

    current = _parse_period(proposed)
    historical = _parse_period(previous)

    if current is None or historical is None:
        return "unknown"

    current_start, current_end = current
    old_start, old_end = historical

    if current_end < old_start or old_end < current_start:
        return "distinct"

    return "overlapping"
