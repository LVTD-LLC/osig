from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass
from time import perf_counter
from typing import Annotated, Any, Literal
from urllib.parse import urlencode, urlparse

from django.db import close_old_connections
from django.db.models import Q
from django.urls import reverse
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from PIL import Image as PILImage
from pydantic import BaseModel, ConfigDict, Field

from core.image_styles import generate_image_router
from core.image_utils import get_image_dimensions
from core.mcp_auth import authenticate_mcp_headers
from core.models import Image as ImageModel, Profile
from core.signing import build_signed_params
from osig.utils import get_osig_logger

StyleName = Literal["base", "logo", "job_classic", "job_logo", "job_clean"]
SiteName = Literal["x", "meta"]
FontName = Literal["helvetica", "markerfelt", "papyrus"]
OutputFormat = Literal["png", "jpeg"]

DEFAULT_PUBLIC_BASE_URL = "https://osig.app"
STYLE_CHOICES: tuple[StyleName, ...] = ("base", "logo", "job_classic", "job_logo", "job_clean")
SITE_CHOICES: tuple[SiteName, ...] = ("x", "meta")
FONT_CHOICES: tuple[FontName, ...] = ("helvetica", "markerfelt", "papyrus")
FORMAT_CHOICES: tuple[OutputFormat, ...] = ("png", "jpeg")

logger = get_osig_logger(__name__)


class ImageParams(BaseModel):
    """Parameters accepted by the OSIG renderer and public `/g` endpoint."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    key: str = Field(default="", max_length=64, description="Optional OSIG profile key used by the public renderer.")
    style: StyleName = Field(default="base", description="Image template to render.")
    site: SiteName = Field(default="x", description="Target social network size preset.")
    font: FontName = Field(default="helvetica", description="Bundled font family.")
    title: str = Field(default="", max_length=500, description="Main image copy.")
    subtitle: str = Field(default="", max_length=1000, description="Secondary image copy.")
    eyebrow: str = Field(default="", max_length=240, description="Small label text above the title.")
    image_url: str = Field(default="", max_length=2000, description="Remote background image or logo URL.")
    image_or_logo: str = Field(
        default="",
        max_length=2000,
        description="Alias for image_url, useful for job templates where the asset can be a logo.",
    )
    format: OutputFormat = Field(default="png", description="Rendered image format.")
    quality: int | None = Field(default=None, ge=1, le=100, description="PNG/JPEG compression quality.")
    max_kb: int | None = Field(default=None, ge=1, le=10000, description="Best-effort output size target in KB.")
    v: str = Field(default="", max_length=100, description="Cache-busting version token for social preview refreshes.")


@dataclass(frozen=True)
class NormalizedImageParams:
    public_params: dict[str, Any]
    render_params: dict[str, Any]
    warnings: list[str]
    width: int
    height: int
    content_type: str


def _content_type_for_format(output_format: str) -> str:
    return "image/jpeg" if output_format == "jpeg" else "image/png"


def _shorten(value: Any, max_chars: int = 140) -> str:
    text = "" if value is None else " ".join(str(value).split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _profile_id_for_key(key: str, warnings: list[str]) -> int | None:
    if not key:
        return None

    try:
        return Profile.objects.only("id").get(key=key).id
    except Profile.DoesNotExist:
        warnings.append("No profile exists for the supplied key; the render will use the free watermark state.")
        return None


def _normalize_image_params(params: ImageParams) -> NormalizedImageParams:
    warnings: list[str] = []
    image_url = params.image_url or params.image_or_logo

    if params.image_url and params.image_or_logo and params.image_url != params.image_or_logo:
        warnings.append("Both image_url and image_or_logo were provided; image_url was used.")

    public_params: dict[str, Any] = {
        "style": params.style,
        "site": params.site,
        "font": params.font,
    }

    optional_values = {
        "key": params.key,
        "title": params.title,
        "subtitle": params.subtitle,
        "eyebrow": params.eyebrow,
        "image_url": image_url,
        "format": params.format,
        "quality": params.quality,
        "max_kb": params.max_kb,
        "v": params.v,
    }
    for key, value in optional_values.items():
        if value not in (None, ""):
            public_params[key] = value

    render_params = dict(public_params)
    profile_id = _profile_id_for_key(params.key, warnings)
    if profile_id is not None:
        render_params["profile_id"] = profile_id

    width, height = get_image_dimensions(params.site)
    return NormalizedImageParams(
        public_params=public_params,
        render_params=render_params,
        warnings=warnings,
        width=width,
        height=height,
        content_type=_content_type_for_format(params.format),
    )


def _image_payload_metadata(payload: bytes) -> dict[str, Any]:
    with PILImage.open(io.BytesIO(payload)) as image:
        width, height = image.size
        detected_format = (image.format or "").lower()

    return {
        "width": width,
        "height": height,
        "detected_format": detected_format,
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _normalize_base_url(base_url: str) -> str:
    normalized_base_url = base_url.strip().rstrip("/")
    parsed = urlparse(normalized_base_url)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"base_url must be an absolute http:// or https:// origin with no path, got: {base_url!r}")

    return normalized_base_url


def _safe_render_params(render_params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in render_params.items() if key != "profile_id"}


def _profile_for_key(key: str) -> Profile:
    try:
        return Profile.objects.only("id", "key").get(key=key)
    except Profile.DoesNotExist as exc:
        raise ValueError("No profile exists for the supplied key.") from exc


def _get_http_profile() -> Profile | None:
    try:
        request = get_http_request()
    except RuntimeError:
        return None

    return authenticate_mcp_headers(request.headers)


def _params_for_request(params: ImageParams) -> ImageParams:
    profile = _get_http_profile()
    if profile is None:
        return params

    if params.key and params.key != profile.key:
        raise PermissionError("The supplied key does not match the authenticated MCP profile.")

    return params.model_copy(update={"key": profile.key})


def _summarize_image(image: ImageModel) -> dict[str, Any]:
    image_data = image.image_data or {}

    try:
        generated_image_url = image.generated_image.url if image.generated_image else ""
    except Exception as exc:
        logger.warning("Failed to resolve generated image URL", image_id=image.id, error=str(exc))
        generated_image_url = ""

    return {
        "id": image.id,
        "created_at": image.created_at.isoformat(),
        "updated_at": image.updated_at.isoformat(),
        "generated_image": {
            "name": image.generated_image.name if image.generated_image else "",
            "url": generated_image_url,
        },
        "params": {
            "style": image_data.get("style", "base"),
            "site": image_data.get("site", "x"),
            "font": image_data.get("font", ""),
            "title": _shorten(image_data.get("title")),
            "subtitle": _shorten(image_data.get("subtitle")),
            "eyebrow": _shorten(image_data.get("eyebrow"), max_chars=80),
            "image_url": _shorten(image_data.get("image_url") or image_data.get("image_or_logo"), max_chars=180),
            "format": image_data.get("format", "png"),
            "v": image_data.get("v", ""),
        },
    }


def create_mcp() -> FastMCP:
    mcp = FastMCP(
        "OSIG Image Iteration MCP",
        instructions=(
            "Use these tools to inspect OSIG image capabilities, normalize render parameters, "
            "generate previews, and create signed public image URLs."
        ),
        on_duplicate="error",
    )

    @mcp.tool(timeout=5)
    def get_image_generation_contract() -> dict[str, Any]:
        """Return the OSIG image styles, fields, defaults, and recommended iteration workflow."""
        dimensions = {
            site: {"width": get_image_dimensions(site)[0], "height": get_image_dimensions(site)[1]}
            for site in SITE_CHOICES
        }

        return {
            "styles": {
                "base": "Full-bleed background with dark overlay and left-aligned article-style copy.",
                "logo": "Centered logo/avatar with centered project or company copy.",
                "job_classic": "High-contrast job card over a full-bleed image.",
                "job_logo": "Dark role-focused job card with a circular logo slot.",
                "job_clean": "Minimal light job card with an accent bar and logo slot.",
            },
            "choices": {
                "style": list(STYLE_CHOICES),
                "site": list(SITE_CHOICES),
                "font": list(FONT_CHOICES),
                "format": list(FORMAT_CHOICES),
            },
            "dimensions": dimensions,
            "fields": {
                "title": "Main copy. Long text is truncated inside templates.",
                "subtitle": "Supporting copy. Keep it concise for social previews.",
                "eyebrow": "Small label text, especially useful for categories or location hints.",
                "image_url": "Remote background image or logo. image_or_logo is accepted as an alias.",
                "v": "Cache-busting token. Change it when social previews need to refresh.",
                "key": "Optional profile key. Public URLs should use key, not profile_id.",
            },
            "workflow": [
                "Call normalize_image_params to get canonical parameters and warnings.",
                "Call render_image_preview while varying one or two fields at a time.",
                "Call build_signed_image_url once the preview parameters are ready to publish.",
            ],
        }

    @mcp.tool(timeout=5)
    def normalize_image_params(params: ImageParams) -> dict[str, Any]:
        """Normalize OSIG image parameters into public URL params and internal render params."""
        close_old_connections()
        try:
            params = _params_for_request(params)
            normalized = _normalize_image_params(params)
            return {
                "public_params": normalized.public_params,
                "render_params": _safe_render_params(normalized.render_params),
                "warnings": normalized.warnings,
                "output": {
                    "content_type": normalized.content_type,
                    "width": normalized.width,
                    "height": normalized.height,
                },
            }
        finally:
            close_old_connections()

    @mcp.tool(timeout=20)
    def render_image_preview(params: ImageParams, include_image_base64: bool = True) -> dict[str, Any]:
        """Render a local image preview and return metadata plus optional base64 image bytes."""
        close_old_connections()
        started_at = perf_counter()
        try:
            params = _params_for_request(params)
            normalized = _normalize_image_params(params)
            image_buffer = generate_image_router(normalized.render_params)
            payload = image_buffer.getvalue()
            metadata = _image_payload_metadata(payload)
            encoded_image = base64.b64encode(payload).decode("ascii") if include_image_base64 else ""

            response: dict[str, Any] = {
                "params": normalized.public_params,
                "warnings": normalized.warnings,
                "content_type": normalized.content_type,
                "render_ms": int((perf_counter() - started_at) * 1000),
                **metadata,
            }
            if include_image_base64:
                response["image_base64"] = encoded_image
                response["data_uri"] = f"data:{normalized.content_type};base64,{encoded_image}"
            return response
        finally:
            close_old_connections()

    @mcp.tool(timeout=5)
    def build_signed_image_url(
        params: ImageParams,
        base_url: Annotated[
            str,
            Field(description="Public scheme and host, for example https://osig.app or http://localhost:8000."),
        ] = DEFAULT_PUBLIC_BASE_URL,
        expires_in_seconds: Annotated[int, Field(ge=1, le=60 * 60 * 24 * 30)] = 3600,
    ) -> dict[str, Any]:
        """Build a tamper-proof public `/g` image URL from normalized parameters."""
        normalized_base_url = _normalize_base_url(base_url)
        close_old_connections()
        try:
            params = _params_for_request(params)
            normalized = _normalize_image_params(params)
            signed_params, expires_at = build_signed_params(
                params=normalized.public_params,
                expires_in_seconds=expires_in_seconds,
            )
            signed_url = f"{normalized_base_url}{reverse('generate_image')}?{urlencode(signed_params)}"

            return {
                "signed_url": signed_url,
                "expires_at": expires_at.isoformat(),
                "signed_params": signed_params,
                "warnings": normalized.warnings,
            }
        finally:
            close_old_connections()

    @mcp.tool(timeout=10)
    def list_recent_generated_images(
        key: Annotated[
            str,
            Field(
                min_length=1,
                max_length=64,
                description="Required OSIG profile key used to scope image results.",
            ),
        ],
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
        style: StyleName | None = None,
    ) -> dict[str, Any]:
        """Return capped summaries of generated images scoped to one profile key."""
        close_old_connections()
        try:
            authenticated_profile = _get_http_profile()
            if authenticated_profile is not None and key != authenticated_profile.key:
                raise PermissionError("The supplied key does not match the authenticated MCP profile.")

            profile = authenticated_profile or _profile_for_key(key)
            queryset = ImageModel.objects.filter(Q(profile=profile) | Q(image_data__key=profile.key)).order_by(
                "-updated_at"
            )
            if style:
                queryset = queryset.filter(image_data__style=style)

            images = [_summarize_image(image) for image in queryset[:limit]]
            return {"count": len(images), "images": images}
        finally:
            close_old_connections()

    return mcp


mcp = create_mcp()
