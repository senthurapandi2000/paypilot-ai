
import os
from datetime import datetime, timezone

import psycopg


class PostgresDailyQuota:
    def __init__(self, database_url=None):
        self.database_url = (
            database_url or os.getenv("DATABASE_URL")
        )

        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is required for daily quotas."
            )

        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_daily_quotas (
                    quota_name TEXT NOT NULL,
                    quota_day DATE NOT NULL,
                    used INTEGER NOT NULL
                        CHECK (used >= 0),
                    PRIMARY KEY (quota_name, quota_day)
                )
            """)

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            connect_timeout=10,
            prepare_threshold=None
        )

    def allow(self, name, limit):
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
        ):
            raise ValueError("Invalid quota settings.")

        today = datetime.now(timezone.utc).date()

        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO api_daily_quotas (
                    quota_name,
                    quota_day,
                    used
                )
                VALUES (%s, %s, 1)
                ON CONFLICT (quota_name, quota_day)
                DO UPDATE SET
                    used = api_daily_quotas.used + 1
                WHERE api_daily_quotas.used < %s
                RETURNING used
                """,
                (name, today, limit)
            ).fetchone()

            return row is not None
