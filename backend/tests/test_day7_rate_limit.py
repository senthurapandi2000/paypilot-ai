
from concurrent.futures import ThreadPoolExecutor

import pytest

from rate_limit import SlidingWindowLimiter


def test_allows_requests_until_limit():
    limiter = SlidingWindowLimiter()

    assert limiter.allow("user-a", 3, 60)
    assert limiter.allow("user-a", 3, 60)
    assert limiter.allow("user-a", 3, 60)

    assert not limiter.allow("user-a", 3, 60)


def test_limit_resets_after_window():
    now = [100.0]

    limiter = SlidingWindowLimiter(
        clock=lambda: now[0]
    )

    assert limiter.allow("user-a", 1, 60)
    assert not limiter.allow("user-a", 1, 60)

    now[0] += 61

    assert limiter.allow("user-a", 1, 60)


def test_clients_have_separate_limits():
    limiter = SlidingWindowLimiter()

    assert limiter.allow("user-a", 1, 60)
    assert not limiter.allow("user-a", 1, 60)

    assert limiter.allow("user-b", 1, 60)


def test_expired_clients_free_capacity():
    now = [100.0]

    limiter = SlidingWindowLimiter(
        max_keys=2,
        clock=lambda: now[0]
    )

    assert limiter.allow("user-a", 1, 60)
    assert limiter.allow("user-b", 1, 60)

    assert not limiter.allow("user-c", 1, 60)

    now[0] += 61

    assert limiter.allow("user-c", 1, 60)


def test_concurrent_requests_respect_limit():
    limiter = SlidingWindowLimiter()

    def attempt(_):
        return limiter.allow(
            "shared-client", 3, 60
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(attempt, range(20)))

    assert results.count(True) == 3
    assert results.count(False) == 17
