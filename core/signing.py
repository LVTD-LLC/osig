from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Mapping
from urllib.parse import urlencode

from django.core import signing
from django.utils import timezone
from django.utils.crypto import constant_time_compare

SIGNATURE_PARAM = "sig"
EXPIRES_AT_PARAM = "exp"
SIGNING_SALT = "core.og-url-signature"

DEFAULT_SIGNED_URL_TTL_SECONDS = 60 * 60
MAX_SIGNED_URL_TTL_SECONDS = 60 * 60 * 24 * 30


class SignedUrlError(ValueError):
    pass


class InvalidSignatureError(SignedUrlError):
    pass


class ExpiredSignatureError(SignedUrlError):
    pass


def _canonical_items(params: Mapping[str, Any]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for key in sorted(params.keys()):
        if key == SIGNATURE_PARAM:
            continue

        value = params[key]
        if value is None:
            continue

        if isinstance(value, (list, tuple)):
            for item in value:
                items.append((key, str(item)))
        else:
            items.append((key, str(value)))

    return items


def build_signature_payload(params: Mapping[str, Any]) -> str:
    return urlencode(_canonical_items(params), doseq=True)


def _clamp_ttl(expires_in_seconds: int) -> int:
    return max(1, min(int(expires_in_seconds), MAX_SIGNED_URL_TTL_SECONDS))


def build_signed_params(
    params: Mapping[str, Any],
    expires_in_seconds: int = DEFAULT_SIGNED_URL_TTL_SECONDS,
    now: datetime | None = None,
) -> tuple[dict[str, str], datetime]:
    current_time = now or timezone.now()
    ttl_seconds = _clamp_ttl(expires_in_seconds)
    expires_at = current_time + timedelta(seconds=ttl_seconds)

    normalized_params: dict[str, str] = {
        key: str(value)
        for key, value in params.items()
        if value is not None and key not in {SIGNATURE_PARAM, EXPIRES_AT_PARAM}
    }
    normalized_params[EXPIRES_AT_PARAM] = str(int(expires_at.timestamp()))

    signer = signing.Signer(salt=SIGNING_SALT)
    payload = build_signature_payload(normalized_params)
    signature = signer.signature(payload)

    signed_params = dict(normalized_params)
    signed_params[SIGNATURE_PARAM] = signature

    return signed_params, expires_at


def verify_signed_params(params: Mapping[str, Any], now: datetime | None = None) -> datetime | None:
    signature = params.get(SIGNATURE_PARAM)
    if not signature:
        return None

    expires_at_raw = params.get(EXPIRES_AT_PARAM)
    if not expires_at_raw:
        raise InvalidSignatureError("Missing exp parameter")

    try:
        expires_at_ts = int(str(expires_at_raw))
    except ValueError as exc:
        raise InvalidSignatureError("Invalid exp parameter") from exc

    expires_at = datetime.fromtimestamp(expires_at_ts, tz=dt_timezone.utc)
    current_time = now or timezone.now()
    if current_time > expires_at:
        raise ExpiredSignatureError("Signed URL has expired")

    signer = signing.Signer(salt=SIGNING_SALT)

    normalized_params: dict[str, str] = {
        key: str(value) for key, value in params.items() if value is not None and key != SIGNATURE_PARAM
    }

    payload = build_signature_payload(normalized_params)
    expected_signature = signer.signature(payload)

    if not constant_time_compare(str(signature), expected_signature):
        raise InvalidSignatureError("Signature mismatch")

    return expires_at
