from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta

import requests
from django.db.models import Count
from django.utils import timezone
from PIL import UnidentifiedImageError

from core.models import Profile, RenderAttempt


class RenderErrorType:
    TRANSIENT_UPSTREAM_FETCH = "transient_upstream_fetch"
    UPSTREAM_FETCH_4XX = "upstream_fetch_4xx"
    UPSTREAM_FETCH_5XX = "upstream_fetch_5xx"
    IMAGE_DECODE_ERROR = "image_decode_error"
    VALIDATION_ERROR = "validation_error"
    RENDER_ERROR = "render_error"
    UNKNOWN_ERROR = "unknown_error"


TRANSIENT_ERROR_TYPES = {
    RenderErrorType.TRANSIENT_UPSTREAM_FETCH,
    RenderErrorType.UPSTREAM_FETCH_5XX,
}


@dataclass(frozen=True)
class RenderMetrics:
    window_hours: int
    total_attempts: int
    failed_attempts: int
    fail_rate_percent: float
    p95_render_ms: int | None
    error_counts: dict[str, int]


def classify_render_error(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.Timeout | requests.exceptions.ConnectionError):
        return RenderErrorType.TRANSIENT_UPSTREAM_FETCH

    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = exc.response.status_code if exc.response else None
        if status_code is not None and 500 <= status_code <= 599:
            return RenderErrorType.UPSTREAM_FETCH_5XX
        if status_code is not None and 400 <= status_code <= 499:
            return RenderErrorType.UPSTREAM_FETCH_4XX

    if isinstance(exc, UnidentifiedImageError):
        return RenderErrorType.IMAGE_DECODE_ERROR

    if isinstance(exc, ValueError):
        return RenderErrorType.VALIDATION_ERROR

    if isinstance(exc, OSError):
        return RenderErrorType.RENDER_ERROR

    return RenderErrorType.UNKNOWN_ERROR


def is_transient_error(error_type: str) -> bool:
    return error_type in TRANSIENT_ERROR_TYPES


def record_render_attempt(
    *,
    profile: Profile | None,
    key: str,
    renderer: str,
    success: bool,
    duration_ms: int,
    error_type: str = "",
    attempt_number: int = 1,
):
    RenderAttempt.objects.create(
        profile=profile,
        key=key,
        renderer=renderer,
        success=success,
        duration_ms=max(0, int(duration_ms)),
        error_type=error_type,
        attempt_number=max(1, int(attempt_number)),
    )


def _p95(values: list[int]) -> int | None:
    if not values:
        return None

    sorted_values = sorted(values)
    index = max(0, math.ceil(len(sorted_values) * 0.95) - 1)
    return sorted_values[index]


def build_render_metrics(*, window_hours: int = 24) -> RenderMetrics:
    cutoff = timezone.now() - timedelta(hours=window_hours)
    queryset = RenderAttempt.objects.filter(created_at__gte=cutoff)

    total_attempts = queryset.count()
    failed_attempts = queryset.filter(success=False).count()

    fail_rate_percent = round((failed_attempts / total_attempts) * 100, 2) if total_attempts else 0.0
    durations = list(queryset.filter(success=True).values_list("duration_ms", flat=True))

    error_counts = {
        item["error_type"]: item["count"]
        for item in queryset.filter(success=False).values("error_type").annotate(count=Count("id")).order_by("-count")
    }

    return RenderMetrics(
        window_hours=window_hours,
        total_attempts=total_attempts,
        failed_attempts=failed_attempts,
        fail_rate_percent=fail_rate_percent,
        p95_render_ms=_p95(durations),
        error_counts=error_counts,
    )
