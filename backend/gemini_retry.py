"""Bounded retries for transient Gemini API failures."""

import asyncio

import httpx


RETRYABLE_STATUSES = {500, 502, 503, 504}


async def generate_with_retry(
    client,
    url,
    headers,
    body,
    sleep=asyncio.sleep,
):
    """Try at most twice; never retry quota or client errors."""

    for attempt in range(2):
        try:
            response = await client.post(
                url,
                headers=headers,
                json=body,
            )

        except httpx.RequestError:
            if attempt == 1:
                raise

            await sleep(0.8)
            continue

        if (
            response.status_code in RETRYABLE_STATUSES
            and attempt == 0
        ):
            await sleep(0.8)
            continue

        return response
