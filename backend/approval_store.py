
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class TooManyApprovals(Exception):
    pass


class ApprovalStore:
    def __init__(self, db_path=None):
        default_path = (
            Path(__file__).resolve().parent
            / "data"
            / "approvals.sqlite3"
        )

        self.path = Path(
            db_path
            or os.getenv("APPROVAL_DB_PATH")
            or default_path
        )

        self.path.parent.mkdir(
            parents=True, exist_ok=True
        )

        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    invoice_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    paypal_invoice_id TEXT
                )
            """)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create(self, approval_id, invoice, ttl=600, limit=50):
        now = time.time()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            count = conn.execute(
                """
                SELECT COUNT(*) FROM approvals
                WHERE status = 'pending'
                  AND expires_at > ?
                """,
                (now,)
            ).fetchone()[0]

            if count >= limit:
                raise TooManyApprovals(
                    "Too many pending approvals."
                )

            conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, invoice_json, status,
                    expires_at, created_at, updated_at
                )
                VALUES (?, ?, 'pending', ?, ?, ?)
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
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute(
                """
                SELECT invoice_json, status, expires_at
                FROM approvals
                WHERE approval_id = ?
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
                    SET status = 'expired', updated_at = ?
                    WHERE approval_id = ?
                    """,
                    (now, approval_id)
                )
                return "expired", None

            conn.execute(
                """
                UPDATE approvals
                SET status = 'processing', updated_at = ?
                WHERE approval_id = ?
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
                SET status = 'cancelled', updated_at = ?
                WHERE approval_id = ?
                  AND status = 'pending'
                  AND expires_at > ?
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
                    paypal_invoice_id = ?,
                    updated_at = ?
                WHERE approval_id = ?
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
                    updated_at = ?
                WHERE approval_id = ?
                  AND status = 'processing'
                """,
                (time.time(), approval_id)
            )

            return result.rowcount == 1

    def get_status(self, approval_id):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status, paypal_invoice_id
                FROM approvals
                WHERE approval_id = ?
                """,
                (approval_id,)
            ).fetchone()

            return dict(row) if row else None
