"""Simple in-memory sliding-window rate limiter (single-process)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

_lock = Lock()
_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _client_key(request: Request, namespace: str) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"{namespace}:{ip}"


def check_rate_limit(request: Request, namespace: str, limit: int, window_seconds: int = 60) -> None:
    if limit <= 0:
        return

    key = _client_key(request, namespace)
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a moment and try again.",
            )
        bucket.append(now)
