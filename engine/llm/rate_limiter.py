"""Caveman rate limiter — tracks RPM and TPM and sleeps when needed."""
from __future__ import annotations

import time
from collections import deque

from engine import progress as prog


class RateLimiter:
    """Simple sliding-window rate limiter.

    Tracks requests-per-minute (RPM) and tokens-per-minute (TPM).
    Before each LLM call, call ``wait_if_needed(estimated_tokens)``.
    After each call, call ``record(tokens_used)``.
    """

    WINDOW = 60.0   # seconds

    def __init__(self, max_rpm: int = 15, max_tpm: int = 30_000,
                 min_delay: float = 2.0):
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.min_delay = min_delay
        self._req_times: deque[float] = deque()   # timestamps of requests
        self._tok_log: deque[tuple[float, int]] = deque()  # (timestamp, tokens)
        self._last_call: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wait_if_needed(self, estimated_tokens: int = 500):
        """Block until it is safe to make the next LLM call."""
        now = time.monotonic()

        # Mandatory minimum delay between consecutive calls
        elapsed = now - self._last_call
        if elapsed < self.min_delay:
            sleep_for = self.min_delay - elapsed
            self._sleep(sleep_for, f"min delay ({sleep_for:.1f}s)")
            now = time.monotonic()

        # RPM check
        self._prune(now)
        if len(self._req_times) >= self.max_rpm:
            oldest = self._req_times[0]
            sleep_for = self.WINDOW - (now - oldest) + 0.1
            if sleep_for > 0:
                self._sleep(sleep_for,
                            f"RPM limit ({len(self._req_times)}/{self.max_rpm} rpm)")
            now = time.monotonic()
            self._prune(now)

        # TPM check
        used = self._tokens_in_window(now)
        if used + estimated_tokens > self.max_tpm:
            sleep_for = self.WINDOW + 1.0
            self._sleep(sleep_for,
                        f"TPM limit ({used}/{self.max_tpm} tokens used this minute)")
            now = time.monotonic()
            self._prune(now)

    def record(self, tokens_used: int):
        """Record a completed call."""
        now = time.monotonic()
        self._req_times.append(now)
        self._tok_log.append((now, tokens_used))
        self._last_call = now

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune(self, now: float):
        cutoff = now - self.WINDOW
        while self._req_times and self._req_times[0] < cutoff:
            self._req_times.popleft()
        while self._tok_log and self._tok_log[0][0] < cutoff:
            self._tok_log.popleft()

    def _tokens_in_window(self, now: float) -> int:
        cutoff = now - self.WINDOW
        return sum(t for ts, t in self._tok_log if ts >= cutoff)

    @staticmethod
    def _sleep(seconds: float, reason: str):
        prog.emit(0, "Rate Limiter", "waiting",
                  f"Sleeping {seconds:.1f}s — {reason}")
        time.sleep(seconds)
