from __future__ import annotations
import time
from collections import OrderedDict, deque
from typing import Callable

from fastapi import Request


def client_key(request: Request) -> str:
    """The caller's IP. Behind Cloud Run the Google front end APPENDS the address it
    saw to X-Forwarded-For, so the right-most entry is the one a client cannot forge;
    anything to its left came from the client itself."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd.strip():
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """A sliding-window limit per client key, held in process memory. With min
    instances 1 / max 3 each instance counts on its own, which is fine for a light
    abuse brake. The client table is bounded: past max_clients the least recently
    seen client is forgotten."""

    def __init__(self, limit: int, window_seconds: float, max_clients: int = 10_000,
                 now: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.now = now                  # indirection so tests can move the clock
        self.hits: "OrderedDict[str, deque[float]]" = OrderedDict()

    def limited(self, key: str) -> bool:
        """True when this call is over the limit. A refused call is not recorded."""
        now = self.now()
        q = self.hits.get(key)
        if q is None:
            q = deque()
            self.hits[key] = q
            while len(self.hits) > self.max_clients:
                self.hits.popitem(last=False)
        else:
            self.hits.move_to_end(key)
        while q and now - q[0] >= self.window_seconds:
            q.popleft()
        if len(q) >= self.limit:
            return True
        q.append(now)
        return False

    def clear(self) -> None:
        self.hits.clear()
