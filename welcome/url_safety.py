"""SSRF-resistant helpers for downloading bounded public HTTP resources."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import aiohttp

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class URLSafetyError(ValueError):
    """Raised when a URL is unsafe or a bounded download cannot be completed."""


class RemoteHTTPError(URLSafetyError):
    """Raised when a remote server returns a non-success status."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"The URL returned HTTP {status}.")


def _public_ip(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def validate_public_http_url(url: str) -> str:
    """Return a normalized HTTP(S) URL that cannot directly name a private host."""
    try:
        parsed = urlparse(str(url).strip())
        hostname = parsed.hostname
        # Accessing ``port`` also validates malformed and out-of-range values.
        parsed.port
    except (UnicodeError, ValueError) as exc:
        raise URLSafetyError("The provided URL is invalid.") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLSafetyError("Only public HTTP(S) links are supported.")
    if not hostname:
        raise URLSafetyError("The URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise URLSafetyError("URLs containing credentials are not supported.")

    hostname = hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise URLSafetyError("Local and private-network URLs are not supported.")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise URLSafetyError("Local and private-network URLs are not supported.")
    return parsed.geturl()


class PublicNetworkResolver(aiohttp.abc.AbstractResolver):
    """Resolve DNS through aiohttp while rejecting every non-global address."""

    def __init__(self) -> None:
        self._resolver = aiohttp.resolver.DefaultResolver()

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[dict[str, object]]:
        records = await self._resolver.resolve(host, port, family)
        if not records or any(not _public_ip(str(record.get("host", ""))) for record in records):
            raise OSError("The hostname resolves to a local or private-network address.")
        return records

    async def close(self) -> None:
        await self._resolver.close()


def public_client_session() -> aiohttp.ClientSession:
    """Create a session whose actual connection resolver rejects private networks."""
    connector = aiohttp.TCPConnector(
        resolver=PublicNetworkResolver(),
        ttl_dns_cache=0,
    )
    return aiohttp.ClientSession(connector=connector)


async def fetch_public_bytes(
    session: aiohttp.ClientSession,
    url: str,
    *,
    max_bytes: int,
    timeout: aiohttp.ClientTimeout,
    required_content_type_prefix: str | None = None,
    max_redirects: int = 5,
) -> tuple[bytes, str, str]:
    """Fetch a public URL with redirect validation and a streaming byte ceiling."""
    current_url = validate_public_http_url(url)

    for redirect_count in range(max_redirects + 1):
        try:
            async with session.get(
                current_url,
                timeout=timeout,
                allow_redirects=False,
            ) as response:
                if response.status in _REDIRECT_STATUSES:
                    location = response.headers.get("Location")
                    if not location:
                        raise URLSafetyError("The remote server returned an invalid redirect.")
                    if redirect_count >= max_redirects:
                        raise URLSafetyError("The URL redirected too many times.")
                    current_url = validate_public_http_url(urljoin(current_url, location))
                    continue

                if response.status != 200:
                    raise RemoteHTTPError(response.status)

                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if required_content_type_prefix and not content_type.startswith(
                    required_content_type_prefix,
                ):
                    raise URLSafetyError(
                        f"The provided URL did not return {required_content_type_prefix.rstrip('/')} data.",
                    )

                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        declared_size = int(content_length)
                    except ValueError as exc:
                        raise URLSafetyError("The remote server returned an invalid content length.") from exc
                    if declared_size > max_bytes:
                        raise URLSafetyError(
                            f"The remote resource is larger than {max_bytes:,} bytes.",
                        )

                data = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise URLSafetyError(
                            f"The remote resource is larger than {max_bytes:,} bytes.",
                        )
                return bytes(data), content_type, current_url
        except (aiohttp.InvalidURL, UnicodeError) as exc:
            raise URLSafetyError("The provided URL is invalid.") from exc

    raise URLSafetyError("The URL redirected too many times.")
