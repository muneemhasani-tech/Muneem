"""HTTP helper: retry on timeouts, transport errors, 5xx and 429 only. Never on other 4xx."""
from __future__ import annotations

import asyncio

import httpx


async def request(
    client: httpx.AsyncClient, method: str, url: str, retry: dict, **kw
) -> httpx.Response | None:
    """Returns the final response (which may be a 4xx/5xx once retries run out),
    or None if every attempt failed at the transport level."""
    attempts = int(retry.get("attempts", 3))
    backoff = list(retry.get("backoff_seconds", [2, 8, 30]))
    resp: httpx.Response | None = None
    for i in range(attempts):
        try:
            resp = await client.request(method, url, **kw)
            if resp.status_code < 500 and resp.status_code != 429:
                return resp
        except (httpx.TimeoutException, httpx.TransportError):
            resp = None
        if i < attempts - 1:
            await asyncio.sleep(backoff[min(i, len(backoff) - 1)] if backoff else 0)
    return resp
