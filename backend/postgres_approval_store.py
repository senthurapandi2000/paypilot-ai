
import json
import os
import time

import psycopg
from psycopg.rows import dict_row

from approval_store import TooManyApprovals


class PostgresApprovalStore:
    def __init__(self, database_url=None):
        self.database_url = (
            database_url or os.getenv("DATABASE_URL")
        )

        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is required for PostgreSQL approvals."
            )

        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    invoice_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expires_at DOUBLE PRECISION NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    paypal_invoice_id TEXT
                )
            """)

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            connect_timeout=10,
            prepare_threshold=None,
            row_factory=dict_row,
        )

    def create(self, approval_id, invoice, ttl=600, limit=50):
        now = time.time()

        with self._connect() as conn:
            # Serialize checks of the pending-approval limit.
            conn.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (772011,)
            )

            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM approvals
                WHERE status = 'pending'
                  AND expires_at > %s
                """,
                (now,)
            ).fetchone()

            if row["count"] >= limit:
                raise TooManyApprovals(
                    "Too many pending approvals."
                )

            conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, invoice_json, status,
                    expires_at, created_at, updated_at
                )
                VALUES (%s, %s, 'pending', %s, %s, %s)
                """,
                (
                    approval_id,
                    json.dumps(invoice),
                    now + ttl,
                    now,
                    now
                )
            )

    def claim(self, approval_id):
        now = time.time()

        with self._connect() as conn:
            # Lock this approval to prevent concurrent claims.
            row = conn.execute(
                """
                SELECT invoice_json, status, expires_at
                FROM approvals
                WHERE approval_id = %s
                FOR UPDATE
                """,
                (approval_id,)
            ).fetchone()

            if row is None:
                return "missing", None

            if row["status"] != "pending":
                return "used", None

            if row["expires_at"] <= now:
                conn.execute(
                    """
                    UPDATE approvals
                    SET status = 'expired', updated_at = %s
                    WHERE approval_id = %s
                    """,
                    (now, approval_id)
                )
                return "expired", None

            conn.execute(
                """
                UPDATE approvals
                SET status = 'processing', updated_at = %s
                WHERE approval_id = %s
                """,
                (now, approval_id)
            )

            return (
                "claimed",
                json.loads(row["invoice_json"])
            )

    def cancel(self, approval_id):
        now = time.time()

        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE approvals
                SET status = 'cancelled', updated_at = %s
                WHERE approval_id = %s
                  AND status = 'pending'
                  AND expires_at > %s
                """,
                (now, approval_id, now)
            )

            return result.rowcount == 1

    def complete(self, approval_id, paypal_invoice_id):
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE approvals
                SET status = 'completed',
                    paypal_invoice_id = %s,
                    updated_at = %s
                WHERE approval_id = %s
                  AND status = 'processing'
                """,
                (
                    paypal_invoice_id,
                    time.time(),
                    approval_id
                )
            )

            return result.rowcount == 1

    def mark_uncertain(self, approval_id):
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE approvals
                SET status = 'needs_review',
                    updated_at = %s
                WHERE approval_id = %s
                  AND status = 'processing'
                """,
                (
                    time.time(),
                    approval_id
                )
            )

            return result.rowcount == 1

    def get_status(self, approval_id):
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT status, paypal_invoice_id
                FROM approvals
                WHERE approval_id = %s
                """,
                (approval_id,)
            ).fetchone()


    def get_invoice(self, approval_id):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT invoice_json, status
                FROM approvals
                WHERE approval_id = %s
                """,
                (approval_id,)
            ).fetchone()

        if row is None:
            return None

        return {
            "invoice": json.loads(row["invoice_json"]),
            "status": row["status"]
        }
