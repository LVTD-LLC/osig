from __future__ import annotations

from typing import Any

from django.db import close_old_connections
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

from core.mcp_auth import authenticate_mcp_headers
from core.models import Profile

from .services import (
    ImageSpec,
    image_contract,
    list_templates,
    normalize_image_spec as normalize_image_spec_service,
    render_image,
)


def _get_http_profile() -> Profile | None:
    try:
        request = get_http_request()
    except RuntimeError:
        return None

    return authenticate_mcp_headers(request.headers)


def create_mcp() -> FastMCP:
    mcp = FastMCP(
        "OSIG Agent Images MCP",
        instructions=(
            "Use these tools to discover deterministic social image templates, validate structured image specs, "
            "render previews, and export image bytes for repository updates. The hosted OSIG MCP endpoint is "
            "currently an unauthenticated trial; use a profile key only when the user provides one."
        ),
        on_duplicate="error",
    )

    @mcp.tool(timeout=5)
    def get_image_contract() -> dict[str, Any]:
        """Return available templates, fields, choices, dimensions, and the agent workflow."""
        return image_contract()

    @mcp.tool(timeout=5)
    def list_image_templates() -> dict[str, Any]:
        """Return concise template summaries for choosing the right image layout."""
        return {"templates": list_templates()}

    @mcp.tool(timeout=5)
    def normalize_image_spec(spec: ImageSpec) -> dict[str, Any]:
        """Validate and normalize a structured OSIG image spec without rendering it."""
        close_old_connections()
        try:
            normalized = normalize_image_spec_service(spec, profile=_get_http_profile())
            return {
                "spec": normalized.spec,
                "render_params": normalized.safe_render_params,
                "warnings": normalized.warnings,
                "output": {
                    "width": normalized.width,
                    "height": normalized.height,
                    "content_type": normalized.content_type,
                },
            }
        finally:
            close_old_connections()

    @mcp.tool(timeout=20)
    def render_image_preview(spec: ImageSpec, include_image_base64: bool = True) -> dict[str, Any]:
        """Render an image preview for iteration and return metadata plus optional base64 bytes."""
        return render_image(spec, profile=_get_http_profile(), include_image_base64=include_image_base64)

    @mcp.tool(timeout=20)
    def export_image(spec: ImageSpec) -> dict[str, Any]:
        """Render final image bytes for saving into a repository or publishing workflow."""
        return render_image(spec, profile=_get_http_profile(), include_image_base64=True)

    return mcp


mcp = create_mcp()
