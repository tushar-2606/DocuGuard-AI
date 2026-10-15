import ipaddress

import pytest
from fastapi import HTTPException, Request

from app import config
from app.services.rate_limit import _buckets, _client_key, check_rate_limit


TRUSTED_PROXY_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("2001:db8:ffff::/48"),
)


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": (peer, 12345),
            "server": ("testserver", 80),
        }
    )


@pytest.fixture(autouse=True)
def clear_buckets(monkeypatch):
    _buckets.clear()
    monkeypatch.setattr(config, "TRUSTED_PROXY_NETWORKS", ())
    yield
    _buckets.clear()


def test_untrusted_peer_cannot_choose_rate_limit_identity():
    request = _request("198.51.100.20", "203.0.113.99")

    assert _client_key(request, "login") == "login:198.51.100.20"


def test_direct_client_without_forwarded_header_keeps_its_identity():
    request = _request("198.51.100.20")

    assert _client_key(request, "login") == "login:198.51.100.20"


def test_trusted_proxy_uses_forwarded_client_address(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_NETWORKS", TRUSTED_PROXY_NETWORKS)
    request = _request("10.1.2.3", "198.51.100.20")

    assert _client_key(request, "login") == "login:198.51.100.20"


def test_trusted_proxy_chain_is_walked_from_trusted_side(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_NETWORKS", TRUSTED_PROXY_NETWORKS)
    request = _request(
        "10.1.2.3",
        "203.0.113.99, 198.51.100.20, 10.2.3.4",
    )

    assert _client_key(request, "upload") == "upload:198.51.100.20"


@pytest.mark.parametrize(
    "forwarded",
    [
        "",
        "198.51.100.20,",
        "not-an-ip",
        "198.51.100.20, not-an-ip",
    ],
)
def test_malformed_forwarded_chain_falls_back_to_socket_peer(
    monkeypatch, forwarded
):
    monkeypatch.setattr(config, "TRUSTED_PROXY_NETWORKS", TRUSTED_PROXY_NETWORKS)
    request = _request("10.1.2.3", forwarded)

    assert _client_key(request, "login") == "login:10.1.2.3"


def test_rate_limit_keeps_namespace_and_limit_behavior(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_NETWORKS", TRUSTED_PROXY_NETWORKS)
    request = _request("10.1.2.3", "198.51.100.20")

    check_rate_limit(request, "auth_login", limit=1, window_seconds=60)
    assert list(_buckets) == ["auth_login:198.51.100.20"]

    with pytest.raises(HTTPException) as error:
        check_rate_limit(request, "auth_login", limit=1, window_seconds=60)
    assert error.value.status_code == 429

    check_rate_limit(request, "upload", limit=1, window_seconds=60)
    assert "upload:198.51.100.20" in _buckets
