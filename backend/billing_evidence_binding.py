"""Check whether reviewed evidence matches invoice contents.

A matching fingerprint proves content consistency,
not that the reviewer was genuinely authorized.
"""

import re
import secrets

from billing_period_evidence import validate_reviewed_period
from invoice_fingerprint import invoice_fingerprint


def evidence_matches_invoice(record, invoice):
    """Fail closed on missing, invalid, or stale evidence."""

    if validate_reviewed_period(record) is None:
        return False

    stored = record.get("invoice_fingerprint")

    if not isinstance(stored, str):
        return False

    if re.fullmatch(r"[0-9a-f]{64}", stored) is None:
        return False

    try:
        current = invoice_fingerprint(invoice)
    except ValueError:
        return False

    return secrets.compare_digest(stored, current)
