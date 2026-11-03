
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv

from postgres_daily_quota import PostgresDailyQuota


@pytest.fixture
def quota_setup():
    if os.getenv("RUN_NEON_QUOTA_TESTS") != "1":
        pytest.skip("Neon quota tests require opt-in.")

    load_dotenv(
        Path(__file__).resolve().parents[1] / ".env"
    )

    quota = PostgresDailyQuota()
    created_names = []

    def new_name():
        name = "day10-quota-test-" + uuid.uuid4().hex
        created_names.append(name)
        return name

    try:
        yield quota, new_name
    finally:
        if created_names:
            with quota._connect() as conn:
                conn.execute(
                    """
                    DELETE FROM api_daily_quotas
                    WHERE quota_name = ANY(%s)
                    """,
                    (created_names,)
                )


def test_daily_limit(quota_setup):
    quota, new_name = quota_setup
    name = new_name()

    assert quota.allow(name, 2) is True
    assert quota.allow(name, 2) is True
    assert quota.allow(name, 2) is False


def test_separate_quotas(quota_setup):
    quota, new_name = quota_setup

    ai_name = new_name()
    invoice_name = new_name()

    assert quota.allow(ai_name, 1) is True
    assert quota.allow(ai_name, 1) is False

    assert quota.allow(invoice_name, 1) is True
    assert quota.allow(invoice_name, 1) is False


def test_usage_persists_between_instances(quota_setup):
    quota, new_name = quota_setup
    name = new_name()

    assert quota.allow(name, 1) is True

    restarted = PostgresDailyQuota(
        quota.database_url
    )

    assert restarted.allow(name, 1) is False


def test_concurrent_quota_enforcement(quota_setup):
    quota, new_name = quota_setup
    name = new_name()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: quota.allow(name, 2),
                range(4)
            )
        )

    assert results.count(True) == 2
    assert results.count(False) == 2

    today = datetime.now(timezone.utc).date()

    with quota._connect() as conn:
        row = conn.execute(
            """
            SELECT used
            FROM api_daily_quotas
            WHERE quota_name = %s
              AND quota_day = %s
            """,
            (name, today)
        ).fetchone()

    assert row[0] == 2
