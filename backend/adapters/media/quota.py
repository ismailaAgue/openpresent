"""
Provider quota tracker — ADR-029 ("provider quotas" requirement,
spec Section 8). In-process, fixed-window (per hour) counter — no
database needed, since it only has to survive one process's lifetime
to prevent a burst of requests within that process from blowing past
a provider's documented free-tier limit. Resets on every
restart/deploy, which is fine: the provider's own rate limit is the
actual source of truth, this is just a proactive client-side guard
so a slow provider failure (repeated 429s) doesn't happen at all
under normal traffic.
"""

import time


class QuotaTracker:
    def __init__(self, limit_per_hour: int):
        self.limit_per_hour = limit_per_hour
        self._window_start = time.time()
        self._count = 0

    def has_quota(self) -> bool:
        self._maybe_reset_window()
        return self._count < self.limit_per_hour

    def record_request(self) -> None:
        self._maybe_reset_window()
        self._count += 1

    def _maybe_reset_window(self) -> None:
        if time.time() - self._window_start >= 3600:
            self._window_start = time.time()
            self._count = 0
