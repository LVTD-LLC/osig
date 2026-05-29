import io

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import override_settings
from PIL import Image

from core.admin import ProfileUsageModelAdmin
from core.models import ProfileUsage


@pytest.fixture
def disable_async_and_image_router(monkeypatch):
    import core.views as core_views

    def tiny_png():
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    monkeypatch.setattr(core_views, "async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(core_views, "generate_image_router", lambda params: tiny_png())


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=5, OSIG_MONTHLY_USAGE_LIMIT=50, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_warns_at_80_percent_daily_limit(client, disable_async_and_image_router):
    user = User.objects.create_user(username="quota-user", email="quota@example.com", password="pass123")
    key = user.profile.key

    responses = []
    for _ in range(4):
        response = client.get("/g", data={"style": "base", "title": "Quota", "key": key})
        responses.append(response)

    assert all(response.status_code == 200 for response in responses)
    assert responses[-1]["X-OSIG-Quota-Warning"] == "daily"
    assert responses[-1]["X-OSIG-Daily-Usage"] == "4/5"


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=3, OSIG_MONTHLY_USAGE_LIMIT=50, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_blocks_when_daily_limit_reaches_100_percent(client, disable_async_and_image_router):
    user = User.objects.create_user(username="blocked-user", email="blocked@example.com", password="pass123")
    key = user.profile.key

    ok_1 = client.get("/g", data={"style": "base", "title": "Quota", "key": key})
    ok_2 = client.get("/g", data={"style": "base", "title": "Quota", "key": key})
    blocked = client.get("/g", data={"style": "base", "title": "Quota", "key": key})

    assert ok_1.status_code == 200
    assert ok_2.status_code == 200
    assert blocked.status_code == 429
    assert "daily" in blocked.content.decode("utf-8")


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=100, OSIG_MONTHLY_USAGE_LIMIT=2, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_blocks_when_monthly_limit_reaches_100_percent(client, disable_async_and_image_router):
    user = User.objects.create_user(username="monthly-user", email="monthly@example.com", password="pass123")
    key = user.profile.key

    ok = client.get("/g", data={"style": "base", "title": "Quota", "key": key})
    blocked = client.get("/g", data={"style": "base", "title": "Quota", "key": key})

    assert ok.status_code == 200
    assert blocked.status_code == 429
    assert "monthly" in blocked.content.decode("utf-8")


@pytest.mark.django_db
@override_settings(OSIG_DAILY_USAGE_LIMIT=1, OSIG_MONTHLY_USAGE_LIMIT=1, OSIG_USAGE_WARNING_PERCENT=0.8)
def test_unsigned_or_no_key_requests_remain_backward_compatible(client, disable_async_and_image_router):
    response = client.get("/g", data={"style": "base", "title": "No key flow"})

    assert response.status_code == 200
    assert "X-OSIG-Daily-Usage" not in response
    assert "X-OSIG-Monthly-Usage" not in response


def test_admin_visibility_is_sorted_for_top_keys():
    admin = ProfileUsageModelAdmin(ProfileUsage, AdminSite())
    assert admin.ordering == ("-monthly_count",)
    assert "profile_key" in admin.list_display
