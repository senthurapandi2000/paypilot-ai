import asyncio

import httpx

from gemini_retry import generate_with_retry


def run_scenario(statuses):
    calls = []
    delays = []
    remaining = iter(statuses)

    def handler(request):
        calls.append(request)
        return httpx.Response(next(remaining))

    async def fake_sleep(seconds):
        delays.append(seconds)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await generate_with_retry(
                client,
                "https://example.test/generate",
                {"Content-Type": "application/json"},
                {"contents": []},
                sleep=fake_sleep,
            )

    response = asyncio.run(run())
    return response.status_code, len(calls), delays


def test_success_without_retry():
    status, calls, delays = run_scenario([200])
    assert (status, calls, delays) == (200, 1, [])


def test_recovers_from_503():
    status, calls, delays = run_scenario([503, 200])
    assert (status, calls, delays) == (200, 2, [0.8])


def test_stops_after_two_failures():
    status, calls, delays = run_scenario([503, 503])
    assert (status, calls, delays) == (503, 2, [0.8])


def test_does_not_retry_quota_error():
    status, calls, delays = run_scenario([429])
    assert (status, calls, delays) == (429, 1, [])


def test_does_not_retry_missing_model():
    status, calls, delays = run_scenario([404])
    assert (status, calls, delays) == (404, 1, [])


def test_recovers_from_connection_error():
    calls = []
    delays = []

    def handler(request):
        calls.append(request)

        if len(calls) == 1:
            raise httpx.ConnectError(
                "Simulated connection failure",
                request=request,
            )

        return httpx.Response(200)

    async def fake_sleep(seconds):
        delays.append(seconds)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await generate_with_retry(
                client,
                "https://example.test/generate",
                {},
                {},
                sleep=fake_sleep,
            )

    response = asyncio.run(run())

    assert response.status_code == 200
    assert len(calls) == 2
    assert delays == [0.8]
