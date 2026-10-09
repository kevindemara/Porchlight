"""Actual crypto/HTTP seam checks, enabled only after optional package approval."""

import importlib
import json
from typing import Any

import httpx
import pytest
from porchlight.push import NativePushSender, SafePushSession, b64url


@pytest.mark.skipif(
    not NativePushSender().available(), reason="Optional Web Push packages not approved/installed"
)
def test_native_encryption_round_trip_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    ec = importlib.import_module("cryptography.hazmat.primitives.asymmetric.ec")
    serialization = importlib.import_module("cryptography.hazmat.primitives.serialization")
    ece = importlib.import_module("http_ece")
    receiver = ec.generate_private_key(ec.SECP256R1())
    public = receiver.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    auth = b"synthetic-auth16"
    calls: list[dict[str, Any]] = []

    def post(
        _self: SafePushSession, url: str, timeout: float | None = None, **values: Any
    ) -> httpx.Response:
        calls.append(values)
        decoded = ece.decrypt(
            values["data"], private_key=receiver, auth_secret=auth, version="aes128gcm"
        )
        assert json.loads(decoded) == {"body": "Synthetic encrypted test"}
        assert b"Synthetic encrypted test" not in values["data"]
        assert values["headers"]["TTL"] == "60"
        assert values["headers"]["Topic"] == "synthetic-topic"
        assert values["headers"]["Urgency"] == "high"
        assert "Authorization" in values["headers"]
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(SafePushSession, "post", post)
    sender = NativePushSender()
    keys = sender.generate_keys()
    result = sender.send(
        {
            "endpoint": "https://fcm.googleapis.com/fcm/send/synthetic_token",
            "keys": {"auth": b64url(auth), "p256dh": b64url(public)},
        },
        json.dumps({"body": "Synthetic encrypted test"}),
        keys["private_key"],
        "https://porch.example.org",
        60,
        "synthetic-topic",
    )
    assert result.status == 201 and len(calls) == 1


def test_http_seam_checks_dns_and_never_follows_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    original_client = httpx.Client
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(307, headers={"Location": "http://127.0.0.1/private"})

    monkeypatch.setattr(
        "porchlight.push.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))],
    )
    monkeypatch.setattr(
        "porchlight.push.httpx.Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    response = SafePushSession().post(
        "https://fcm.googleapis.com/fcm/send/synthetic_token", data=b"generated"
    )
    assert response.status_code == 307 and len(requests) == 1
    monkeypatch.setattr(
        "porchlight.push.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="public addresses"):
        SafePushSession().post(
            "https://fcm.googleapis.com/fcm/send/synthetic_token", data=b"generated"
        )
    assert len(requests) == 1
