"""Minimal per-host rate limiter for polite HTML scraping."""

from __future__ import annotations

from collections import defaultdict
import threading
import time


class RateLimiter:
    """Enforce a minimum delay between consecutive calls per host.

    Thread-safe. Blocks the caller in ``wait`` until the configured
    ``min_delay`` has elapsed since the last call for that host.
    """

    def __init__(self, min_delay_seconds: float) -> None:
        """Initialise with ``min_delay_seconds`` between requests per host."""
        self._min_delay = max(0.0, min_delay_seconds)
        self._last_call: dict[str, float] = defaultdict(lambda: 0.0)
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        """Block until the configured delay since the last ``host`` call passes."""
        if self._min_delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            earliest = self._last_call[host] + self._min_delay
            delay = earliest - now
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._last_call[host] = now
