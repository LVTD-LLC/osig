import asyncio
import base64
import io
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import User
from fastmcp import Client
from fastmcp.exceptions import ToolError
from PIL import Image

from core.models import Image as ImageModel, RenderAttempt
from core.render_observability import RenderErrorType


def _run(coro):
    return asyncio.run(coro)


def _tiny_png_buffer():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


async def _call_tool(name, arguments=None, raise_on_error=True):
    from core.mcp import create_mcp

    async with Client(create_mcp()) as client:
        return await client.call_tool(name, arguments or {}, raise_on_error=raise_on_error)


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
    user = User.objects.create_user(username="normalizer", email="normalizer@example.com", password="pass123")

    result = _run(
        _call_tool(
            "normalize_image_params",
            {
                "params": {
                    "key": user.profile.key,
                    "style": "job_logo",
                    "title": "Senior Django Engineer",
                    "image_or_logo": "https://example.com/logo.png",
                }
            },
        )
    )

    assert result.data["public_params"]["image_url"] == "https://example.com/logo.png"
    assert result.data["public_params"]["key"] == user.profile.key
    assert "profile_id" not in result.data["render_params"]
    assert result.data["output"]["width"] == 800
    assert result.data["output"]["height"] == 450


@pytest.mark.django_db(transaction=True)
def test_normalize_image_params_uses_authenticated_profile_key(monkeypatch):
    import core.mcp as core_mcp

    user = User.objects.create_user(username="hosted", email="hosted@example.com", password="pass123")
    monkeypatch.setattr(core_mcp, "_get_http_profile", lambda: user.profile)

    result = _run(
        _call_tool(
            "normalize_image_params",
            {
                "params": {
                    "style": "base",
                    "title": "Hosted MCP",
                }
            },
        )
    )

    assert result.data["public_params"]["key"] == user.profile.key
    assert "profile_id" not in result.data["render_params"]


@pytest.mark.django_db(transaction=True)
def test_normalize_image_params_rejects_mismatched_authenticated_key(monkeypatch):
    import core.mcp as core_mcp

    user = User.objects.create_user(username="hosted-mismatch", email="hosted-mismatch@example.com", password="pass123")
    monkeypatch.setattr(core_mcp, "_get_http_profile", lambda: user.profile)

    with pytest.raises(ToolError):
        _run(
            _call_tool(
                "normalize_image_params",
                {
                    "params": {
                        "key": "other-key",
                        "style": "base",
                        "title": "Hosted MCP",
                    }
                },
            )
        )


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

    assert data["content_type"] == "image/png"
    assert data["width"] == 16
    assert data["height"] == 16
    assert decoded.startswith(b"\x89PNG")
    assert data["data_uri"].startswith("data:image/png;base64,")


@pytest.mark.django_db(transaction=True)
def test_render_image_preview_raises_render_errors(monkeypatch):
    import core.mcp as core_mcp

    def unavailable_router(params):
        raise ValueError("invalid render input")

    monkeypatch.setattr(core_mcp, "generate_image_router", unavailable_router)

    with pytest.raises(ToolError):
        _run(
            _call_tool(
                "render_image_preview",
                {
                    "params": {
                        "style": "base",
                        "title": "Preview title",
                    },
                    "include_image_base64": False,
                },
            )
        )


@pytest.mark.django_db(transaction=True)
def test_render_image_preview_reraises_unexpected_code_errors(monkeypatch):
    import core.mcp as core_mcp

    def broken_router(params):
        raise TypeError("programming error")

    monkeypatch.setattr(core_mcp, "generate_image_router", broken_router)

    with pytest.raises(ToolError):
        _run(
            _call_tool(
                "render_image_preview",
                {
                    "params": {
                        "style": "base",
                        "title": "Preview title",
                    },
                    "include_image_base64": False,
                },
            )
        )


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
def test_build_signed_image_url_rejects_non_http_base_url():
    result = _run(
        _call_tool(
            "build_signed_image_url",
            {
                "params": {
                    "style": "logo",
                    "title": "Narrative",
                },
                "base_url": "ftp://example.com",
            },
            raise_on_error=False,
        )
    )

    assert result.is_error is True
    assert "base_url must be an absolute http:// or https:// origin with no path" in result.content[0].text


@pytest.mark.django_db(transaction=True)
def test_build_signed_image_url_rejects_base_url_paths():
    result = _run(
        _call_tool(
            "build_signed_image_url",
            {
                "params": {
                    "style": "logo",
                    "title": "Narrative",
                },
                "base_url": "https://example.com/nested",
            },
            raise_on_error=False,
        )
    )

    assert result.is_error is True
    assert "base_url must be an absolute http:// or https:// origin with no path" in result.content[0].text


@pytest.mark.django_db(transaction=True)
def test_list_recent_generated_images_requires_and_scopes_by_key():
    first_user = User.objects.create_user(username="first", email="first@example.com", password="pass123")
    second_user = User.objects.create_user(username="second", email="second@example.com", password="pass123")

    ImageModel.objects.create(
        profile=first_user.profile,
        image_data={"key": first_user.profile.key, "style": "base", "title": "First image"},
    )
    ImageModel.objects.create(
        profile=first_user.profile,
        image_data={"key": first_user.profile.key, "style": "logo", "title": "First logo image"},
    )
    ImageModel.objects.create(
        profile=second_user.profile,
        image_data={"key": second_user.profile.key, "style": "base", "title": "Second image"},
    )

    result = _run(_call_tool("list_recent_generated_images", {"key": first_user.profile.key, "style": "base"}))
    missing_key_result = _run(_call_tool("list_recent_generated_images", {}, raise_on_error=False))

    assert result.data["count"] == 1
    assert result.data["images"][0]["params"]["title"] == "First image"
    assert missing_key_result.is_error is True


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


@pytest.mark.django_db(transaction=True)
def test_get_recent_render_metrics_requires_superuser_for_hosted_auth(monkeypatch):
    import core.mcp as core_mcp

    user = User.objects.create_user(username="regular", email="regular@example.com", password="pass123")
    monkeypatch.setattr(core_mcp, "_get_http_profile", lambda: user.profile)

    with pytest.raises(ToolError):
        _run(_call_tool("get_recent_render_metrics", {"window_hours": 24}))
