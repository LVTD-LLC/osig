import asyncio
import base64
import io

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
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


def _canvas_spec(**overrides):
    spec = {
        "width": 800,
        "height": 450,
        "background": "#0f172a",
        "layers": [
            {"kind": "rect", "x": 40, "y": 40, "width": 720, "height": 370, "fill": "#1d4ed8", "radius": 24},
            {
                "kind": "text",
                "x": 80,
                "y": 120,
                "width": 620,
                "text": "Canvas MCP",
                "font": "helvetica",
                "font_size": 56,
                "color": "#ffffff",
            },
        ],
    }
    spec.update(overrides)
    return spec


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
        "normalize_image_spec",
        "render_image_preview",
        "export_image",
    }.issubset(tool_names)
    assert "build_og_image_spec" not in tool_names
    assert "list_image_templates" not in tool_names
    assert "build_signed_image_url" not in tool_names
    assert "list_recent_generated_images" not in tool_names


def test_get_image_contract_describes_canvas_workflow():
    result = _run(_call_tool("get_image_contract"))

    assert result.data["product"] == "OSIG Agent Images"
    assert result.data["purpose"] == "Deterministic canvas images for AI agents."
    assert result.data["canvas"]["default_site"] == "x"
    assert result.data["canvas"]["custom_dimensions"]["max_width"] == 2000
    assert result.data["canvas"]["custom_dimensions"]["max_pixels"] == 2500000
    assert set(result.data["layer_kinds"]) == {"rect", "text", "image"}
    assert {"fill", "border", "shadow"}.issubset(result.data["layer_kinds"]["rect"]["optional"])
    assert {"height", "valign", "overflow"}.issubset(result.data["layer_kinds"]["text"]["optional"])
    assert "src" in result.data["layer_kinds"]["image"]["required"]
    assert "base64" in result.data["image_sources"]
    assert result.data["fill_models"]["linear_gradient"]["required"] == ["type", "from", "to"]
    assert "style" not in result.data["choices"]
    assert {"cover", "contain", "fill", "none"} == set(result.data["choices"]["image_fit"])
    assert "stretch" not in result.data["choices"]["image_fit"]
    assert "google" in result.data["choices"]["font_provider"]
    assert "google:inter" in result.data["choices"]["font"]
    assert result.data["font_providers"]["google"]["font_value_format"] == "google:<family-slug>"
    assert result.data["contract_version"] == "canvas-v1"
    assert "image_spec" in result.data["schemas"]
    assert result.data["schemas"]["response_metadata"]["hashes"]["spec_sha256"]
    assert result.data["schemas"]["response_metadata"]["hashes"]["sha256"] == (
        "Deprecated compatibility alias for image_sha256."
    )
    assert result.data["access"]["accepted_profile_key_headers"] == [
        "Authorization: Bearer <profile_key>",
        "X-API-Key: <profile_key>",
    ]
    assert result.data["access"]["trial_boundaries"]["watermark_applied"] is True
    assert result.data["access"]["trial_boundaries"]["private_or_admin_tools_exposed"] is False
    assert {template["id"] for template in result.data["template_library"]} == {
        "repo_preview",
        "article_summary",
        "product_update",
    }
    assert set(result.data["template_library"][0]["example_specs"]) == {"x", "meta"}
    assert "export_image" in " ".join(result.data["workflow"])


@override_settings(OSIG_MCP_TRIAL_ENABLED=False, OSIG_MCP_REQUIRE_AUTH=False)
def test_get_image_contract_matches_disabled_trial_auth_enforcement():
    result = _run(_call_tool("get_image_contract"))

    assert result.data["access"]["authentication_required"] is True
    assert result.data["access"]["trial_enabled"] is False
    assert "OSIG_MCP_TRIAL_ENABLED is disabled" in result.data["access"]["trial_note"]


@pytest.mark.django_db(transaction=True)
def test_og_template_library_returns_valid_template_specs():
    from agent_images.services import ImageSpec, normalize_image_spec
    from agent_images.templates import OgTemplateContent, build_og_image_spec

    data = build_og_image_spec(
        OgTemplateContent(
            title="Launch agent-ready OG images",
            subtitle="Preview, export, and commit deterministic assets.",
            site_name="OSIG",
            logo={"type": "url", "url": "https://example.com/logo.png"},
            image={"type": "url", "url": "https://example.com/preview.png"},
            tags=["MCP", "Open Graph"],
        ),
        template="product_update",
        site="meta",
    )

    spec = data["spec"]
    normalized = normalize_image_spec(ImageSpec.model_validate(spec))

    assert data["template"]["id"] == "product_update"
    assert data["template"]["slots"] == ["title", "subtitle", "site_name", "logo", "image", "tags"]
    assert data["output"]["width"] == 600
    assert data["output"]["height"] == 315
    assert spec["site"] == "meta"
    assert spec["width"] == 600
    assert spec["height"] == 315
    assert any(layer.get("text") == "Launch agent-ready OG images" for layer in spec["layers"])
    assert any(layer.get("src") == {"type": "url", "url": "https://example.com/logo.png"} for layer in spec["layers"])
    assert any(
        layer.get("src") == {"type": "url", "url": "https://example.com/preview.png"} for layer in spec["layers"]
    )
    assert normalized.width == 600
    assert normalized.height == 315


def test_template_library_contract_returns_independent_copy():
    from agent_images.templates import template_library_contract

    first_contract = template_library_contract()
    first_contract[0]["slots"].append("mutated")
    first_contract[0]["example_specs"]["x"]["layers"].clear()

    second_contract = template_library_contract()

    assert "mutated" not in second_contract[0]["slots"]
    assert second_contract[0]["example_specs"]["x"]["layers"]


def test_og_template_content_validates_image_sources_early():
    from pydantic import ValidationError

    from agent_images.templates import OgTemplateContent

    with pytest.raises(ValidationError) as exc_info:
        OgTemplateContent(title="Launch", logo={"type": "url", "url": "http://internal-service/logo.png"})

    assert "Image URLs must use HTTPS" in str(exc_info.value)


@pytest.mark.django_db(transaction=True)
def test_trial_mcp_core_tools_work_without_authentication_or_key(monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "render_canvas_image", lambda params: _tiny_png_buffer())

    async def run_test():
        from agent_images.mcp import create_mcp

        async with Client(create_mcp()) as client:
            contract = await client.call_tool("get_image_contract", {})
            normalized = await client.call_tool("normalize_image_spec", {"spec": _canvas_spec()})
            preview = await client.call_tool(
                "render_image_preview",
                {
                    "spec": _canvas_spec(),
                    "include_image_base64": False,
                },
            )
            exported = await client.call_tool("export_image", {"spec": _canvas_spec()})

        return contract.data, normalized.data, preview.data, exported.data

    contract, normalized, preview, exported = _run(run_test())

    assert contract["access"]["hosted_mcp_url"] == "https://osig.app/mcp/"
    assert contract["access"]["authentication_required"] is False
    assert "key" not in normalized["spec"]
    assert normalized["spec_sha256"]
    assert "profile_id" not in normalized["render_params"]
    assert normalized["access"]["mode"] == "trial"
    assert normalized["access"]["watermark"]["applied"] is True
    assert normalized["output"]["width"] == 800
    assert normalized["output"]["height"] == 450
    assert preview["mode"] == "preview"
    assert preview["preview"]["final"] is False
    assert "export" not in preview
    assert preview["sha256"]
    assert preview["image_sha256"] == preview["sha256"]
    assert "image_base64" not in preview
    assert preview["content_type"] == "image/png"
    assert exported["mode"] == "export"
    assert exported["export"]["final"] is True
    assert exported["export"]["suggested_filename"].endswith(".png")
    assert exported["export"]["cache_key"]
    assert exported["image_base64"]


@pytest.mark.django_db(transaction=True)
def test_normalize_image_spec_supports_custom_canvas_and_profile_key():
    user = User.objects.create_user(username="normalizer", email="normalizer@example.com", password="pass123")

    result = _run(
        _call_tool(
            "normalize_image_spec",
            {
                "spec": _canvas_spec(
                    key=user.profile.key,
                    width=640,
                    height=360,
                    layers=[
                        {
                            "kind": "text",
                            "x": 24,
                            "y": 32,
                            "width": 500,
                            "text": "Precise placement",
                            "font_size": 42,
                            "color": "#111827",
                        }
                    ],
                )
            },
        )
    )

    assert result.data["spec"]["width"] == 640
    assert result.data["spec"]["height"] == 360
    assert result.data["spec"]["layers"][0]["kind"] == "text"
    assert result.data["spec"]["key"] == user.profile.key
    assert "profile_id" not in result.data["render_params"]
    assert result.data["access"]["mode"] == "keyed"
    assert result.data["access"]["profile_resolved"] is True
    assert result.data["output"]["width"] == 640
    assert result.data["output"]["height"] == 360


@pytest.mark.django_db(transaction=True)
def test_normalize_image_spec_uses_authenticated_profile_key(monkeypatch):
    import agent_images.mcp as agent_mcp

    user = User.objects.create_user(username="hosted", email="hosted@example.com", password="pass123")
    monkeypatch.setattr(agent_mcp, "_get_http_profile", lambda: user.profile)

    result = _run(_call_tool("normalize_image_spec", {"spec": _canvas_spec()}))

    assert result.data["spec"]["key"] == user.profile.key
    assert "profile_id" not in result.data["render_params"]


@pytest.mark.django_db(transaction=True)
def test_normalize_image_spec_rejects_mismatched_authenticated_key(monkeypatch):
    import agent_images.mcp as agent_mcp

    user = User.objects.create_user(username="hosted-mismatch", email="hosted-mismatch@example.com", password="pass123")
    monkeypatch.setattr(agent_mcp, "_get_http_profile", lambda: user.profile)

    with pytest.raises(ToolError):
        _run(_call_tool("normalize_image_spec", {"spec": _canvas_spec(key="other-key")}))


@pytest.mark.django_db(transaction=True)
def test_render_image_preview_returns_metadata_and_optional_image(monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "render_canvas_image", lambda params: _tiny_png_buffer())

    result = _run(
        _call_tool(
            "render_image_preview",
            {
                "spec": _canvas_spec(site="meta", width=None, height=None, format="png"),
                "include_image_base64": True,
            },
        )
    )

    data = result.data
    decoded = base64.b64decode(data["image_base64"])

    assert data["content_type"] == "image/png"
    assert data["width"] == 16
    assert data["height"] == 16
    assert data["output"]["width"] == 600
    assert data["output"]["height"] == 315
    assert decoded.startswith(b"\x89PNG")
    assert data["data_uri"].startswith("data:image/png;base64,")
    assert data["preview"]["export_required_for_publish"] is True


@pytest.mark.django_db(transaction=True)
def test_export_image_always_returns_base64_payload(monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "render_canvas_image", lambda params: _tiny_png_buffer())

    result = _run(_call_tool("export_image", {"spec": _canvas_spec()}))

    assert result.data["image_base64"]
    assert result.data["extension"] == "png"
    assert result.data["sha256"]
    assert result.data["image_sha256"] == result.data["sha256"]
    assert result.data["spec_sha256"]
    assert result.data["export"]["content_type"] == "image/png"
    assert result.data["export"]["image_sha256"] == result.data["sha256"]


@pytest.mark.django_db(transaction=True)
def test_render_image_preview_raises_render_errors(monkeypatch):
    import agent_images.services as agent_services

    def unavailable_renderer(params):
        raise ValueError("invalid render input")

    monkeypatch.setattr(agent_services, "render_canvas_image", unavailable_renderer)

    with pytest.raises(ToolError):
        _run(
            _call_tool(
                "render_image_preview",
                {
                    "spec": _canvas_spec(),
                    "include_image_base64": False,
                },
            )
        )
