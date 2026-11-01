
import time
from collections import deque
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, max_keys=1000, clock=None):
        self._requests = {}
        self._lock = Lock()
        self._max_keys = max_keys
        self._clock = clock or time.monotonic

    def allow(self, key, limit, window_seconds):
        if limit < 1 or window_seconds <= 0:
            raise ValueError("Invalid rate limit settings.")

        now = self._clock()

        with self._lock:
            if key not in self._requests:
                if len(self._requests) >= self._max_keys:
                    # Remove inactive clients.
                    for old_key, record in list(
                        self._requests.items()
                    ):
                        timestamps, window = record
                        cutoff = now - window

                        while (
                            timestamps
                            and timestamps[0] <= cutoff
                        ):
                            timestamps.popleft()

                        if not timestamps:
                            del self._requests[old_key]

                if len(self._requests) >= self._max_keys:
                    return False

                self._requests[key] = (
                    deque(),
                    window_seconds
                )

            timestamps, stored_window = (
                self._requests[key]
            )

            if stored_window != window_seconds:
                raise ValueError(
                    "Window changed for existing key."
                )

            cutoff = now - window_seconds

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= limit:
                return False

            timestamps.append(now)
            return True
