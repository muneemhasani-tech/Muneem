"""Daily quota tracking per provider, persisted in the cache DB.

`reserve()` is check-and-increment with no `await` in between, so it is safe under asyncio.
"""
from __future__ import annotations

from collections import Counter

from .cache import Cache
from .util import today


class Quota:
    def __init__(self, cache: Cache, providers: dict, default_tz: str = "Asia/Dhaka") -> None:
        self.cache = cache
        self.providers = providers
        self.default_tz = default_tz
        self.run_used: Counter[str] = Counter()  # credits spent by THIS run

    def day(self, provider: str) -> str:
        return today(self.providers.get(provider, {}).get("reset_tz", self.default_tz))

    def limit(self, provider: str) -> int:
        return int(self.providers.get(provider, {}).get("daily_limit", 0))

    def used(self, provider: str) -> int:
        row = self.cache.conn.execute(
            "SELECT used FROM quota WHERE provider=? AND day=?", (provider, self.day(provider))
        ).fetchone()
        return row[0] if row else 0

    def remaining(self, provider: str) -> int:
        return max(0, self.limit(provider) - self.used(provider))

    def _set(self, provider: str, used: int) -> None:
        self.cache.conn.execute(
            "INSERT OR REPLACE INTO quota (provider, day, used) VALUES (?,?,?)",
            (provider, self.day(provider), used),
        )
        self.cache.conn.commit()

    def reserve(self, provider: str) -> bool:
        """Take one credit if any remain. False means: stop calling this provider today."""
        used = self.used(provider)
        if used >= self.limit(provider):
            return False
        self._set(provider, used + 1)
        self.run_used[provider] += 1
        return True

    def refund(self, provider: str) -> None:
        """Give back a credit when the call never reached the provider."""
        used = self.used(provider)
        if used > 0:
            self._set(provider, used - 1)
            self.run_used[provider] = max(0, self.run_used[provider] - 1)

    def exhaust(self, provider: str) -> None:
        """Provider said 'no credits' (402/429): stop for the day regardless of our own count."""
        self._set(provider, max(self.used(provider), self.limit(provider)))
