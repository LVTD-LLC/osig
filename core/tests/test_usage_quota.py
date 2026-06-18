import io

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import override_settings
from PIL import Image

from agent_images.services import ImageSpec, ImageUsageLimitExceeded, render_image
from core.admin import ProfileUsageModelAdmin
from core.models import ProfileUsage


def _canvas_spec(**overrides):
    spec = {
        "width": 800,
        "height": 450,
        "layers": [{"kind": "text", "x": 40, "y": 40, "text": "Quota"}],
    }
    spec.update(overrides)
    return spec


@pytest.fixture
def disable_async_and_image_router(monkeypatch):
    import agent_images.services as agent_services

    def tiny_png():
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    monkeypatch.setattr(agent_services, "render_canvas_image", lambda params: tiny_png())


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=5, OSIG_MONTHLY_USAGE_LIMIT=50, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_warns_at_80_percent_daily_limit(client, disable_async_and_image_router):
    user = User.objects.create_user(username="quota-user", email="quota@example.com", password="pass123")
    key = user.profile.key

    responses = []
    for _ in range(4):
        response = render_image(ImageSpec.model_validate(_canvas_spec(key=key)))
        responses.append(response)

    assert all(response["content_type"] == "image/png" for response in responses)
    assert responses[-1]["usage"]["warnings"] == ["daily"]
    assert responses[-1]["usage"]["daily_count"] == 4
    assert responses[-1]["usage"]["daily_limit"] == 5


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=3, OSIG_MONTHLY_USAGE_LIMIT=50, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_blocks_when_daily_limit_reaches_100_percent(client, disable_async_and_image_router):
    user = User.objects.create_user(username="blocked-user", email="blocked@example.com", password="pass123")
    key = user.profile.key

    ok_1 = render_image(ImageSpec.model_validate(_canvas_spec(key=key)))
    ok_2 = render_image(ImageSpec.model_validate(_canvas_spec(key=key)))

    with pytest.raises(ImageUsageLimitExceeded) as exc_info:
        render_image(ImageSpec.model_validate(_canvas_spec(key=key)))

    assert ok_1["content_type"] == "image/png"
    assert ok_2["content_type"] == "image/png"
    assert exc_info.value.usage_state.blocked_reasons == ("daily",)


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=100, OSIG_MONTHLY_USAGE_LIMIT=2, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_blocks_when_monthly_limit_reaches_100_percent(client, disable_async_and_image_router):
    user = User.objects.create_user(username="monthly-user", email="monthly@example.com", password="pass123")
    key = user.profile.key

    ok = render_image(ImageSpec.model_validate(_canvas_spec(key=key)))

    with pytest.raises(ImageUsageLimitExceeded) as exc_info:
        render_image(ImageSpec.model_validate(_canvas_spec(key=key)))

    assert ok["content_type"] == "image/png"
    assert exc_info.value.usage_state.blocked_reasons == ("monthly",)


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=1, OSIG_MONTHLY_USAGE_LIMIT=1, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_unsigned_or_no_key_requests_remain_backward_compatible(client, disable_async_and_image_router):
    response = render_image(ImageSpec.model_validate(_canvas_spec()))

    assert response["content_type"] == "image/png"
    assert response["usage"] is None


def test_admin_visibility_is_sorted_for_top_keys():
    admin = ProfileUsageModelAdmin(ProfileUsage, AdminSite())
    assert admin.ordering == ("-monthly_count",)
    assert "profile_key" in admin.list_display
