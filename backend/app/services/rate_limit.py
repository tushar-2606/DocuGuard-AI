"""Simple in-memory sliding-window rate limiter (single-process)."""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

from app import config

_lock = Lock()
_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _client_key(request: Request, namespace: str) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return f"{namespace}:{peer}"

    if not any(
        peer_address.version == network.version and peer_address in network
        for network in config.TRUSTED_PROXY_NETWORKS
    ):
        return f"{namespace}:{peer}"

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return f"{namespace}:{peer}"

    try:
        forwarded_addresses = [
            ipaddress.ip_address(address.strip())
            for address in forwarded.split(",")
        ]
        if not forwarded_addresses:
            return f"{namespace}:{peer}"
    except ValueError:
        return f"{namespace}:{peer}"

    for address in reversed(forwarded_addresses):
        is_trusted = any(
            address.version == network.version and address in network
            for network in config.TRUSTED_PROXY_NETWORKS
        )
        if not is_trusted:
            return f"{namespace}:{address}"

    return f"{namespace}:{peer}"


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
