import io

import pytest
import requests
from django.contrib.auth.models import User
from django.test import override_settings
from PIL import Image

from agent_images.services import ImageRenderFailed, ImageSpec, render_image
from core.models import RenderAttempt
from core.render_observability import RenderErrorType


def _tiny_png_buffer():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


@pytest.mark.django_db
@override_settings(OSIG_RENDER_MAX_ATTEMPTS=2)
def test_retries_transient_render_failures(client, monkeypatch):
    import agent_images.services as agent_services

    call_count = {"value": 0}

    def flaky_router(params):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise requests.exceptions.Timeout("network timeout")
        return _tiny_png_buffer()

    monkeypatch.setattr(agent_services, "generate_image_router", flaky_router)

    payload = render_image(ImageSpec(style="base", title="Retry test"))

    assert payload["content_type"] == "image/png"
    assert call_count["value"] == 2

    attempts = list(RenderAttempt.objects.order_by("created_at"))
    assert len(attempts) == 2
    assert attempts[0].success is False
    assert attempts[0].error_type == RenderErrorType.TRANSIENT_UPSTREAM_FETCH
    assert attempts[1].success is True


@pytest.mark.django_db
@override_settings(OSIG_RENDER_MAX_ATTEMPTS=3)
def test_does_not_retry_non_transient_errors(client, monkeypatch):
    import agent_images.services as agent_services

    call_count = {"value": 0}

    def invalid_router(params):
        call_count["value"] += 1
        raise ValueError("invalid payload")

    monkeypatch.setattr(agent_services, "generate_image_router", invalid_router)

    with pytest.raises(ImageRenderFailed) as exc_info:
        render_image(ImageSpec(style="base", title="Validation failure"))

    assert exc_info.value.error_type == RenderErrorType.VALIDATION_ERROR
    assert call_count["value"] == 1

    attempts = list(RenderAttempt.objects.all())
    assert len(attempts) == 1
    assert attempts[0].error_type == RenderErrorType.VALIDATION_ERROR


@pytest.mark.django_db
def test_render_metrics_dashboard_returns_fail_rate_and_p95(client):
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass123")
    profile = admin_user.profile

    RenderAttempt.objects.create(profile=profile, key=profile.key, style="base", success=True, duration_ms=100)
    RenderAttempt.objects.create(profile=profile, key=profile.key, style="base", success=True, duration_ms=200)
    RenderAttempt.objects.create(profile=profile, key=profile.key, style="base", success=True, duration_ms=300)
    RenderAttempt.objects.create(
        profile=profile,
        key=profile.key,
        style="base",
        success=False,
        duration_ms=150,
        error_type=RenderErrorType.TRANSIENT_UPSTREAM_FETCH,
    )

    response = client.get("/api/admin/render-metrics", data={"api_key": profile.key, "hours": 24})

    assert response.status_code == 200
    payload = response.json()

    assert payload["total_attempts"] == 4
    assert payload["failed_attempts"] == 1
    assert payload["fail_rate_percent"] == 25.0
    assert payload["p95_render_ms"] == 300
    assert payload["error_counts"][RenderErrorType.TRANSIENT_UPSTREAM_FETCH] == 1
