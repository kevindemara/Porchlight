"""Bounded IMMIS transport using blinkpy's protocol helpers, never its unverified TLS path."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
import ssl
from contextlib import suppress
from typing import Any
from urllib.parse import parse_qs, urlsplit

from blinkpy import api
from blinkpy.livestream import BlinkLiveStream

from porchlight.api.contracts import ApiError, RelayTrustRequired


def blink_dns(name: str) -> bool:
    return name in {"blink.com", "immedia-semi.com"} or name.endswith(
        (".blink.com", ".immedia-semi.com")
    )


def relay_target(server: str) -> tuple[str, int, bool]:
    try:
        url = urlsplit(server)
        host = url.hostname or ""
        if url.scheme != "immis" or url.port != 443 or url.username or url.password or url.fragment:
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                raise ValueError()
            numeric = True
        except ValueError:
            if not blink_dns(host) or len(host) > 253:
                raise ValueError() from None
            numeric = False
        client = parse_qs(url.query).get("client_id", [])
        if len(client) != 1 or not 0 <= int(client[0]) <= 0xFFFFFFFF:
            raise ValueError()
        connection_id = url.path.rsplit("/", 1)[-1].split("__", 1)[0]
        if not connection_id or len(connection_id) > 64:
            raise ValueError()
        return host, 443, numeric
    except (ValueError, TypeError) as exc:
        raise ApiError(
            409, "LIVE_RELAY_REJECTED", "Blink returned an unsupported live relay."
        ) from exc


class VerifiedStream(BlinkLiveStream):  # type: ignore[misc]
    def __init__(self, camera: Any, response: dict[str, Any], certificates: dict[str, str]):
        super().__init__(camera, response)
        self.certificates = certificates

    async def auth(self) -> None:
        host, port, numeric = relay_target(self.target.geturl())
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ApiError(409, "LIVE_RELAY_REJECTED", "The live relay address was rejected.")
        context = ssl.create_default_context()
        # IP relays must still have a trusted certificate with a Blink-owned DNS identity.
        # Certificate-chain validation remains CERT_REQUIRED; nothing is sent before the SAN check.
        context.check_hostname = not numeric
        address = str(addresses[0][4][0])
        approved_fingerprint: str | None = None
        try:
            self.target_reader, self.target_writer = await asyncio.open_connection(
                address, port, ssl=context, server_hostname=None if numeric else host
            )
        except ssl.SSLCertVerificationError as error:
            if error.verify_code not in {18, 19}:
                raise
            # Certificate inspection only: no protocol/auth bytes, media, or trust change.
            inspection = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            inspection.check_hostname = False
            inspection.verify_mode = ssl.CERT_NONE
            _, writer = await asyncio.open_connection(
                address, port, ssl=inspection, server_hostname=None if numeric else host
            )
            try:
                der = writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
                if not der or len(der) > 64 * 1024:
                    raise ApiError(409, "LIVE_TLS_REJECTED", "The relay certificate was rejected.")
                fingerprint = hashlib.sha256(der).hexdigest()
                pem = ssl.DER_cert_to_PEM_cert(der)
            finally:
                writer.close()
                with suppress(Exception):
                    await asyncio.wait_for(writer.wait_closed(), 2)
            if self.certificates.get(fingerprint) != pem:
                raise RelayTrustRequired(fingerprint, pem) from error
            approved_fingerprint = fingerprint
            pinned = ssl.create_default_context(cadata=pem)
            pinned.check_hostname = False  # Exact owner-approved certificate replaces DNS identity.
            pinned.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
            self.target_reader, self.target_writer = await asyncio.open_connection(
                address, port, ssl=pinned, server_hostname=None if numeric else host
            )
            actual = self.target_writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
            if hashlib.sha256(actual).hexdigest() != fingerprint:
                self.target_writer.close()
                raise ApiError(
                    409, "LIVE_CERT_CHANGED", "The relay certificate changed. Review it again."
                ) from error
        if numeric and not approved_fingerprint:
            certificate = self.target_writer.get_extra_info("ssl_object").getpeercert()
            identities = [
                value for kind, value in certificate.get("subjectAltName", []) if kind == "DNS"
            ]
            if not any(blink_dns(name.removeprefix("*.")) for name in identities):
                self.target_writer.close()
                raise ApiError(
                    409, "LIVE_TLS_REJECTED", "The relay certificate identity was rejected."
                )
        self.target_writer.write(self.get_auth_header())
        await self.target_writer.drain()


class BlinkLiveInput:
    def __init__(
        self,
        camera: Any,
        response: dict[str, Any],
        lock: asyncio.Lock,
        certificates: dict[str, str] | None = None,
    ):
        self.stream = VerifiedStream(camera, response, certificates or {})
        self.lock = lock
        self.tasks: list[asyncio.Task[None]] = []
        self.closed = False
        self.bytes_read = 0

    async def start(self) -> None:
        try:
            async with asyncio.timeout(12):
                await self.stream.auth()
            self.tasks = [asyncio.create_task(self.stream.send()), asyncio.create_task(self.poll())]
        except ssl.SSLCertVerificationError as exc:
            await self.close()
            reason = {
                18: "The Blink live relay uses a self-signed certificate.",
                19: "The Blink live relay certificate chain is self-signed.",
                20: "The Blink live relay certificate issuer is not trusted.",
                10: "The Blink live relay certificate has expired.",
                62: "The Blink live relay certificate hostname did not match.",
            }.get(exc.verify_code, "The Blink live relay certificate could not be verified.")
            raise ApiError(409, "LIVE_TLS_REJECTED", reason) from exc
        except ssl.SSLError as exc:
            await self.close()
            raise ApiError(
                409, "LIVE_TLS_REJECTED", "The Blink live relay could not be securely verified."
            ) from exc
        except BaseException:
            await self.close()
            raise

    async def poll(self) -> None:
        try:
            while not self.closed:
                await asyncio.sleep(max(2, min(10, self.stream.polling_interval)))
                async with self.lock, asyncio.timeout(10):
                    response = await api.request_command_status(
                        self.stream.camera.sync.blink,
                        self.stream.camera.network_id,
                        self.stream.command_id,
                    )
                commands = response.get("commands", []) if isinstance(response, dict) else []
                command = next((c for c in commands if c.get("id") == self.stream.command_id), None)
                if not command or command.get("state_condition") not in {"new", "running"}:
                    break
        except Exception:
            pass
        finally:
            if self.stream.target_writer:
                self.stream.target_writer.close()

    async def read(self) -> bytes:
        while not self.closed:
            try:
                async with asyncio.timeout(10):
                    header = await self.stream.target_reader.readexactly(9)
                    length = int.from_bytes(header[5:9], "big")
                    if not 0 <= length <= 1024 * 1024:
                        raise ApiError(
                            409, "LIVE_PACKET_REJECTED", "The live stream packet was rejected."
                        )
                    payload = await self.stream.target_reader.readexactly(length)
                if header[0] == 0 and payload:
                    if len(payload) % 188 or any(
                        payload[i] != 0x47 for i in range(0, len(payload), 188)
                    ):
                        raise ApiError(
                            409, "LIVE_PACKET_REJECTED", "The live stream format is unsupported."
                        )
                    self.bytes_read += len(payload)
                    if self.bytes_read > 256 * 1024**2:
                        raise ApiError(
                            409, "LIVE_LIMIT", "The live stream exceeded its byte limit."
                        )
                    return bytes(payload)
            except asyncio.IncompleteReadError:
                return b""
        return b""

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.stream.stop()
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with suppress(asyncio.CancelledError, Exception):
                await task
        with suppress(Exception):
            async with asyncio.timeout(3), self.lock:
                await api.request_command_done(
                    self.stream.camera.sync.blink,
                    self.stream.camera.network_id,
                    self.stream.command_id,
                )
