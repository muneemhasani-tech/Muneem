"""Small shared helpers: PII masking, timestamps, in-flight call de-duplication."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo


def mask_phone(p: str | None) -> str:
    """+8801711223344 -> +88017****344 (safe for INFO logs)."""
    if not p:
        return ""
    return p if len(p) <= 9 else f"{p[:6]}****{p[-3:]}"


def mask_email(e: str | None) -> str:
    if not e or "@" not in e:
        return "***"
    local, _, dom = e.partition("@")
    return f"{local[:1]}***@{dom}"


def now_iso(tz: str = "Asia/Dhaka") -> str:
    return datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")


def today(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")


class InFlight:
    """Collapse concurrent identical lookups into one call (200 leads, one domain -> one request)."""

    def __init__(self) -> None:
        self._tasks: dict[Any, asyncio.Task] = {}

    async def once(self, key: Any, fn: Callable[[], Awaitable[Any]]) -> Any:
        task = self._tasks.get(key)
        if task is None:
            task = asyncio.ensure_future(fn())
            self._tasks[key] = task
        return await task
