import asyncio
import base64
import io

import pytest
from django.contrib.auth.models import User
from fastmcp import Client
from fastmcp.exceptions import ToolError
from PIL import Image


def _run(coro):
    return asyncio.run(coro)


def _tiny_png_buffer():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


async def _call_tool(name, arguments=None, raise_on_error=True):
    from agent_images.mcp import create_mcp

    async with Client(create_mcp()) as client:
        return await client.call_tool(name, arguments or {}, raise_on_error=raise_on_error)


def test_mcp_lists_agent_image_tools():
    async def run_test():
        from agent_images.mcp import create_mcp

        async with Client(create_mcp()) as client:
            tools = await client.list_tools()

        return {tool.name for tool in tools}

    tool_names = _run(run_test())

    assert {
        "get_image_contract",
        "list_image_templates",
        "normalize_image_spec",
        "render_image_preview",
        "export_image",
    }.issubset(tool_names)
    assert "build_signed_image_url" not in tool_names
    assert "list_recent_generated_images" not in tool_names


def test_get_image_contract_describes_agent_workflow():
    result = _run(_call_tool("get_image_contract"))

    assert result.data["product"] == "OSIG Agent Images"
    assert "export_image" in " ".join(result.data["workflow"])
    assert result.data["choices"]["style"] == ["base", "logo", "job_classic", "job_logo", "job_clean"]


@pytest.mark.django_db(transaction=True)
def test_trial_mcp_core_tools_work_without_authentication_or_key(monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "generate_image_router", lambda params: _tiny_png_buffer())

    async def run_test():
        from agent_images.mcp import create_mcp

        async with Client(create_mcp()) as client:
            contract = await client.call_tool("get_image_contract", {})
            normalized = await client.call_tool(
                "normalize_image_spec",
                {"spec": {"style": "base", "title": "Unauthed trial"}},
            )
            preview = await client.call_tool(
                "render_image_preview",
                {
                    "spec": {"style": "base", "title": "Unauthed trial"},
                    "include_image_base64": False,
                },
            )
            exported = await client.call_tool(
                "export_image",
                {"spec": {"style": "base", "title": "Unauthed trial"}},
            )

        return contract.data, normalized.data, preview.data, exported.data

    contract, normalized, preview, exported = _run(run_test())

    assert contract["access"]["hosted_mcp_url"] == "https://osig.app/mcp/"
    assert contract["access"]["authentication_required"] is False
    assert "key" not in normalized["spec"]
    assert "profile_id" not in normalized["render_params"]
    assert preview["sha256"]
    assert preview["content_type"] == "image/png"
    assert exported["image_base64"]


@pytest.mark.django_db(transaction=True)
def test_normalize_image_spec_maps_logo_alias_to_render_params():
    user = User.objects.create_user(username="normalizer", email="normalizer@example.com", password="pass123")

    result = _run(
        _call_tool(
            "normalize_image_spec",
            {
                "spec": {
                    "key": user.profile.key,
                    "style": "job_logo",
                    "title": "Senior Django Engineer",
                    "image_or_logo": "https://example.com/logo.png",
                }
            },
        )
    )

    assert result.data["spec"]["image_url"] == "https://example.com/logo.png"
    assert result.data["spec"]["key"] == user.profile.key
    assert "profile_id" not in result.data["render_params"]
    assert result.data["output"]["width"] == 800
    assert result.data["output"]["height"] == 450


@pytest.mark.django_db(transaction=True)
def test_normalize_image_spec_uses_authenticated_profile_key(monkeypatch):
    import agent_images.mcp as agent_mcp

    user = User.objects.create_user(username="hosted", email="hosted@example.com", password="pass123")
    monkeypatch.setattr(agent_mcp, "_get_http_profile", lambda: user.profile)

    result = _run(
        _call_tool(
            "normalize_image_spec",
            {
                "spec": {
                    "style": "base",
                    "title": "Hosted MCP",
                }
            },
        )
    )

    assert result.data["spec"]["key"] == user.profile.key
    assert "profile_id" not in result.data["render_params"]


@pytest.mark.django_db(transaction=True)
def test_normalize_image_spec_rejects_mismatched_authenticated_key(monkeypatch):
    import agent_images.mcp as agent_mcp

    user = User.objects.create_user(username="hosted-mismatch", email="hosted-mismatch@example.com", password="pass123")
    monkeypatch.setattr(agent_mcp, "_get_http_profile", lambda: user.profile)

    with pytest.raises(ToolError):
        _run(
            _call_tool(
                "normalize_image_spec",
                {
                    "spec": {
                        "key": "other-key",
                        "style": "base",
                        "title": "Hosted MCP",
                    }
                },
            )
        )


@pytest.mark.django_db(transaction=True)
def test_render_image_preview_returns_metadata_and_optional_image(monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "generate_image_router", lambda params: _tiny_png_buffer())

    result = _run(
        _call_tool(
            "render_image_preview",
            {
                "spec": {
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
def test_export_image_always_returns_base64_payload(monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "generate_image_router", lambda params: _tiny_png_buffer())

    result = _run(
        _call_tool(
            "export_image",
            {
                "spec": {
                    "style": "logo",
                    "title": "Narrative",
                    "subtitle": "Founding Engineer",
                },
            },
        )
    )

    assert result.data["image_base64"]
    assert result.data["extension"] == "png"
    assert result.data["sha256"]


@pytest.mark.django_db(transaction=True)
def test_render_image_preview_raises_render_errors(monkeypatch):
    import agent_images.services as agent_services

    def unavailable_router(params):
        raise ValueError("invalid render input")

    monkeypatch.setattr(agent_services, "generate_image_router", unavailable_router)

    with pytest.raises(ToolError):
        _run(
            _call_tool(
                "render_image_preview",
                {
                    "spec": {
                        "style": "base",
                        "title": "Preview title",
                    },
                    "include_image_base64": False,
                },
            )
        )
