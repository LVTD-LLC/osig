import asyncio
import base64
import io
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import User
from fastmcp import Client
from PIL import Image

from core.models import RenderAttempt
from core.render_observability import RenderErrorType


def _run(coro):
    return asyncio.run(coro)


def _tiny_png_buffer():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


async def _call_tool(name, arguments=None):
    from core.mcp import create_mcp

    async with Client(create_mcp()) as client:
        return await client.call_tool(name, arguments or {})


def test_mcp_lists_image_iteration_tools():
    async def run_test():
        from core.mcp import create_mcp

        async with Client(create_mcp()) as client:
            tools = await client.list_tools()

        return {tool.name for tool in tools}

    tool_names = _run(run_test())

    assert {
        "get_image_generation_contract",
        "normalize_image_params",
        "render_image_preview",
        "build_signed_image_url",
        "list_recent_generated_images",
        "get_recent_render_metrics",
    }.issubset(tool_names)


@pytest.mark.django_db(transaction=True)
def test_normalize_image_params_maps_logo_alias_to_public_params():
    result = _run(
        _call_tool(
            "normalize_image_params",
            {
                "params": {
                    "style": "job_logo",
                    "title": "Senior Django Engineer",
                    "image_or_logo": "https://example.com/logo.png",
                }
            },
        )
    )

    assert result.data["public_params"]["image_url"] == "https://example.com/logo.png"
    assert result.data["output"]["width"] == 800
    assert result.data["output"]["height"] == 450


@pytest.mark.django_db(transaction=True)
def test_render_image_preview_returns_metadata_and_optional_image(monkeypatch):
    import core.mcp as core_mcp

    monkeypatch.setattr(core_mcp, "generate_image_router", lambda params: _tiny_png_buffer())

    result = _run(
        _call_tool(
            "render_image_preview",
            {
                "params": {
                    "style": "base",
                    "site": "meta",
                    "title": "Preview title",
                    "format": "png",
                },
                "include_image_base64": True,
            },
        )
    )

    data = result.data
    decoded = base64.b64decode(data["image_base64"])

    assert data["ok"] is True
    assert data["content_type"] == "image/png"
    assert data["width"] == 16
    assert data["height"] == 16
    assert decoded.startswith(b"\x89PNG")
    assert data["data_uri"].startswith("data:image/png;base64,")


@pytest.mark.django_db(transaction=True)
def test_build_signed_image_url_returns_signed_g_endpoint():
    result = _run(
        _call_tool(
            "build_signed_image_url",
            {
                "params": {
                    "style": "logo",
                    "site": "x",
                    "title": "Narrative",
                    "subtitle": "Founding Engineer",
                },
                "base_url": "https://example.com",
                "expires_in_seconds": 300,
            },
        )
    )

    signed_url = result.data["signed_url"]
    parsed = urlparse(signed_url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "example.com"
    assert parsed.path == "/g"
    assert query["title"] == ["Narrative"]
    assert "sig" in query
    assert "exp" in query
    assert "profile_id" not in query


@pytest.mark.django_db(transaction=True)
def test_get_recent_render_metrics_reports_existing_attempts():
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass123")
    profile = admin_user.profile

    RenderAttempt.objects.create(profile=profile, key=profile.key, style="base", success=True, duration_ms=100)
    RenderAttempt.objects.create(
        profile=profile,
        key=profile.key,
        style="base",
        success=False,
        duration_ms=125,
        error_type=RenderErrorType.TRANSIENT_UPSTREAM_FETCH,
    )

    result = _run(_call_tool("get_recent_render_metrics", {"window_hours": 24}))

    assert result.data["total_attempts"] == 2
    assert result.data["failed_attempts"] == 1
    assert result.data["fail_rate_percent"] == 50.0
    assert result.data["error_counts"][RenderErrorType.TRANSIENT_UPSTREAM_FETCH] == 1
