from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTNAMES = {"localhost"}


def validate_remote_image_url(url: str, *, resolve: bool = True) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Image URLs must use HTTPS.")
    if parsed.username or parsed.password:
        raise ValueError("Image URLs must not include credentials.")
    if not parsed.hostname:
        raise ValueError("Image URLs must include a host.")

    host = parsed.hostname.rstrip(".").lower()
    if host in BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise ValueError("Image URL host must be public.")

    _validate_public_ip_literal(host)
    if resolve:
        _validate_public_dns_addresses(host)

    return url


def _validate_public_ip_literal(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return

    _validate_public_address(address)


def _validate_public_dns_addresses(host: str) -> None:
    try:
        results = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Image URL host could not be resolved.") from exc

    addresses = {result[4][0] for result in results}
    if not addresses:
        raise ValueError("Image URL host could not be resolved.")

    for address in addresses:
        _validate_public_address(ipaddress.ip_address(address))


def _validate_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if not address.is_global or address.is_multicast:
        raise ValueError("Image URL host must resolve to public IP addresses.")
