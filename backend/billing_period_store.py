"""Local SQLite storage for billing-period evidence.

This module does not authenticate reviewers.
Do not expose its write methods to public API clients
or use records to suppress warnings until an authorized
review workflow is implemented.
"""

import re
import sqlite3
from contextlib import closing
from pathlib import Path

from billing_period_evidence import validate_reviewed_period


class BillingPeriodEvidenceStore:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS billing_period_evidence (
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    evidence_reference TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    invoice_fingerprint TEXT,
                    PRIMARY KEY (subject_type, subject_id)
                )
            """)
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(billing_period_evidence)"
                )
            }

            if "invoice_fingerprint" not in columns:
                conn.execute("""
                    ALTER TABLE billing_period_evidence
                    ADD COLUMN invoice_fingerprint TEXT
                """)

            conn.commit()

    def save(self, record):
        """Store a structurally valid record without overwriting."""
        validated = validate_reviewed_period(record)

        if validated is None:
            raise ValueError("Invalid billing-period evidence.")

        fingerprint = record.get("invoice_fingerprint")

        if fingerprint is not None and (
            not isinstance(fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
        ):
            raise ValueError("Invalid invoice fingerprint.")

        period = validated["billing_period"]

        try:
            with closing(sqlite3.connect(self.path)) as conn:
                with conn:
                    conn.execute("""
                        INSERT INTO billing_period_evidence (
                            subject_type,
                            subject_id,
                            start_date,
                            end_date,
                            reviewer_id,
                            evidence_reference,
                            reviewed_at,
                            source,
                            verification_status,
                            invoice_fingerprint
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        validated["subject_type"],
                        validated["subject_id"],
                        period["start_date"],
                        period["end_date"],
                        validated["reviewer_id"],
                        validated["evidence_reference"],
                        validated["reviewed_at"],
                        "operator_review",
                        "approved",
                        fingerprint,
                    ))
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Evidence already exists or violates storage constraints."
            ) from exc

    def get(self, subject_type, subject_id):
        """Retrieve one stored record, or None."""
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT *
                FROM billing_period_evidence
                WHERE subject_type = ?
                  AND subject_id = ?
            """, (subject_type, subject_id)).fetchone()

        if row is None:
            return None

        record = dict(row)

        return {
            "subject_type": record["subject_type"],
            "subject_id": record["subject_id"],
            "billing_period": {
                "start_date": record["start_date"],
                "end_date": record["end_date"],
            },
            "reviewer_id": record["reviewer_id"],
            "evidence_reference": record["evidence_reference"],
            "reviewed_at": record["reviewed_at"],
            "source": record["source"],
            "verification_status": record["verification_status"],
            "invoice_fingerprint": record["invoice_fingerprint"],
        }
