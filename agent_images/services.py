from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass
from time import perf_counter
from typing import Annotated, Any, Literal

from django.conf import settings
from django.db import close_old_connections
from PIL import Image as PILImage
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.font_providers import (
    BUNDLED_FONT_CHOICES,
    FONT_PROVIDER_CHOICES,
    GOOGLE_FONT_CHOICES,
    is_provider_font,
    normalize_font_name,
)
from core.image_styles import parse_color, render_canvas_image
from core.image_utils import get_image_dimensions
from core.models import Profile
from core.render_observability import classify_render_error, is_transient_error, record_render_attempt
from core.usage import UsageState, track_profile_usage
from osig.utils import get_osig_logger

SiteName = Literal["x", "meta"]
OutputFormat = Literal["png", "jpeg"]
ImageFit = Literal["cover", "contain", "stretch"]
TextAlign = Literal["left", "center", "right"]

SITE_CHOICES: tuple[SiteName, ...] = ("x", "meta")
FONT_CHOICES: tuple[str, ...] = (*BUNDLED_FONT_CHOICES, *GOOGLE_FONT_CHOICES)
FORMAT_CHOICES: tuple[OutputFormat, ...] = ("png", "jpeg")
IMAGE_FIT_CHOICES: tuple[ImageFit, ...] = ("cover", "contain", "stretch")
TEXT_ALIGN_CHOICES: tuple[TextAlign, ...] = ("left", "center", "right")

MIN_CANVAS_EDGE = 200
MAX_CANVAS_EDGE = 2000
MAX_LAYER_EDGE = 4000
MAX_LAYERS = 50

logger = get_osig_logger(__name__)


def _validate_color(value: str) -> str:
    try:
        parse_color(value)
    except ValueError as exc:
        raise ValueError(f"Invalid color value: {value}") from exc
    return value


class CanvasLayerBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    x: Annotated[int, Field(ge=-MAX_LAYER_EDGE, le=MAX_LAYER_EDGE, description="Left pixel position.")]
    y: Annotated[int, Field(ge=-MAX_LAYER_EDGE, le=MAX_LAYER_EDGE, description="Top pixel position.")]
    opacity: Annotated[float, Field(default=1.0, ge=0, le=1, description="Layer opacity from 0 to 1.")]


class RectLayer(CanvasLayerBase):
    kind: Literal["rect"]
    width: Annotated[int, Field(ge=1, le=MAX_LAYER_EDGE, description="Rectangle width in pixels.")]
    height: Annotated[int, Field(ge=1, le=MAX_LAYER_EDGE, description="Rectangle height in pixels.")]
    color: Annotated[str, Field(default="#000000", max_length=32, description="Fill color.")]
    radius: Annotated[int, Field(default=0, ge=0, le=MAX_LAYER_EDGE, description="Corner radius in pixels.")]

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        return _validate_color(value)


class TextLayer(CanvasLayerBase):
    kind: Literal["text"]
    text: Annotated[str, Field(min_length=1, max_length=4000, description="Text to draw.")]
    font: Annotated[
        str,
        Field(
            default="helvetica", max_length=120, description="Bundled font id or provider font such as google:inter."
        ),
    ]
    font_size: Annotated[int, Field(default=48, ge=1, le=300, description="Font size in pixels.")]
    color: Annotated[str, Field(default="#111111", max_length=32, description="Text color.")]
    width: Annotated[int | None, Field(default=None, ge=1, le=MAX_LAYER_EDGE, description="Optional wrap width.")]
    line_height: Annotated[int | None, Field(default=None, ge=1, le=500, description="Optional line height in pixels.")]
    align: Annotated[TextAlign, Field(default="left", description="Text alignment inside width.")]
    stroke_color: Annotated[str | None, Field(default=None, max_length=32, description="Optional text stroke color.")]
    stroke_width: Annotated[int, Field(default=0, ge=0, le=20, description="Optional text stroke width.")]

    @field_validator("font")
    @classmethod
    def normalize_font(cls, font: str) -> str:
        return normalize_font_name(font)

    @field_validator("color", "stroke_color")
    @classmethod
    def validate_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_color(value)


class ImageLayer(CanvasLayerBase):
    kind: Literal["image"]
    url: Annotated[str, Field(min_length=1, max_length=2000, description="Remote image URL.")]
    width: Annotated[int, Field(ge=1, le=MAX_LAYER_EDGE, description="Image box width in pixels.")]
    height: Annotated[int, Field(ge=1, le=MAX_LAYER_EDGE, description="Image box height in pixels.")]
    fit: Annotated[ImageFit, Field(default="cover", description="How the image should fit inside its box.")]


CanvasLayer = Annotated[RectLayer | TextLayer | ImageLayer, Field(discriminator="kind")]


class ImageSpec(BaseModel):
    """Canvas image input for agents and the Studio API."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    key: Annotated[
        str,
        Field(default="", max_length=64, description="Optional OSIG profile key for quota and paid watermark state."),
    ]
    site: Annotated[SiteName | None, Field(default=None, description="Optional social preview size preset.")]
    width: Annotated[
        int | None,
        Field(default=None, ge=MIN_CANVAS_EDGE, le=MAX_CANVAS_EDGE, description="Custom canvas width in pixels."),
    ]
    height: Annotated[
        int | None,
        Field(default=None, ge=MIN_CANVAS_EDGE, le=MAX_CANVAS_EDGE, description="Custom canvas height in pixels."),
    ]
    background: Annotated[str, Field(default="#ffffff", max_length=32, description="Canvas background color.")]
    layers: Annotated[list[CanvasLayer], Field(default_factory=list, max_length=MAX_LAYERS)]
    format: Annotated[OutputFormat, Field(default="png", description="Rendered image format.")]
    quality: Annotated[int | None, Field(default=None, ge=1, le=100, description="PNG/JPEG compression quality.")]
    max_kb: Annotated[int | None, Field(default=None, ge=1, le=10000, description="Best-effort target size in KB.")]
    v: Annotated[str, Field(default="", max_length=100, description="Optional version token for caller bookkeeping.")]

    @field_validator("background")
    @classmethod
    def validate_background(cls, value: str) -> str:
        return _validate_color(value)

    @model_validator(mode="after")
    def validate_dimensions(self) -> ImageSpec:
        if (self.width is None) != (self.height is None):
            raise ValueError("Provide both width and height for custom canvas dimensions.")
        return self


@dataclass(frozen=True)
class NormalizedImageSpec:
    spec: dict[str, Any]
    render_params: dict[str, Any]
    safe_render_params: dict[str, Any]
    warnings: list[str]
    width: int
    height: int
    content_type: str
    profile: Profile | None


class ImageUsageLimitExceeded(Exception):
    def __init__(self, usage_state: UsageState):
        self.usage_state = usage_state
        super().__init__("Usage quota exceeded")


class ImageRenderFailed(Exception):
    def __init__(self, error_type: str):
        self.error_type = error_type
        super().__init__(f"Render failed: {error_type}")


def _record_render_attempt_safely(**kwargs):
    try:
        record_render_attempt(**kwargs)
    except Exception as exc:
        logger.warning(
            "Failed to record agent image render attempt",
            success=kwargs.get("success"),
            attempt_number=kwargs.get("attempt_number"),
            error=str(exc),
        )


def _content_type_for_format(output_format: str) -> str:
    return "image/jpeg" if output_format == "jpeg" else "image/png"


def _extension_for_format(output_format: str) -> str:
    return "jpg" if output_format == "jpeg" else "png"


def _profile_for_key(key: str, warnings: list[str]) -> Profile | None:
    if not key:
        return None

    try:
        return Profile.objects.only("id", "key", "subscription").get(key=key)
    except Profile.DoesNotExist:
        warnings.append("No profile exists for the supplied key; the render will use the watermarked trial state.")
        return None


def _safe_render_params(render_params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in render_params.items() if key != "profile_id"}


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


def _dimensions_for_spec(spec: ImageSpec) -> tuple[int, int]:
    if spec.width is not None and spec.height is not None:
        return spec.width, spec.height

    return get_image_dimensions(spec.site or "x")


def _layer_dump(layer: CanvasLayer) -> dict[str, Any]:
    return layer.model_dump(exclude_none=True)


def _layer_bounds(layer: CanvasLayer) -> tuple[int, int, int, int] | None:
    if isinstance(layer, TextLayer):
        width = layer.width
        if width is None:
            return None
        height = layer.line_height or round(layer.font_size * 1.2)
    else:
        width = layer.width
        height = layer.height

    return layer.x, layer.y, layer.x + width, layer.y + height


def _canvas_warnings(spec: ImageSpec, width: int, height: int) -> list[str]:
    warnings: list[str] = []

    if not spec.layers:
        warnings.append("Spec has no layers; the renderer will return only the background and watermark state.")

    if any(isinstance(layer, TextLayer) and is_provider_font(layer.font) for layer in spec.layers):
        warnings.append("Provider fonts are fetched from the third-party provider on first render and cached locally.")

    for index, layer in enumerate(spec.layers):
        bounds = _layer_bounds(layer)
        if bounds is None:
            continue
        left, top, right, bottom = bounds
        if left < 0 or top < 0 or right > width or bottom > height:
            warnings.append(f"Layer {index} extends outside the {width}x{height} canvas and will be clipped.")

    return warnings


def image_contract() -> dict[str, Any]:
    dimensions = {
        site: {"width": get_image_dimensions(site)[0], "height": get_image_dimensions(site)[1]} for site in SITE_CHOICES
    }

    return {
        "product": "OSIG Agent Images",
        "purpose": "Deterministic canvas images for AI agents.",
        "canvas": {
            "default_site": "x",
            "presets": dimensions,
            "custom_dimensions": {
                "min_width": MIN_CANVAS_EDGE,
                "max_width": MAX_CANVAS_EDGE,
                "min_height": MIN_CANVAS_EDGE,
                "max_height": MAX_CANVAS_EDGE,
            },
            "max_layers": MAX_LAYERS,
            "coordinate_system": "Pixel coordinates with origin at the top-left corner.",
        },
        "layer_kinds": {
            "rect": {
                "required": ["kind", "x", "y", "width", "height"],
                "optional": ["color", "opacity", "radius"],
            },
            "text": {
                "required": ["kind", "x", "y", "text"],
                "optional": [
                    "font",
                    "font_size",
                    "color",
                    "width",
                    "line_height",
                    "align",
                    "opacity",
                    "stroke_color",
                    "stroke_width",
                ],
            },
            "image": {
                "required": ["kind", "x", "y", "url", "width", "height"],
                "optional": ["fit", "opacity"],
            },
        },
        "choices": {
            "site": list(SITE_CHOICES),
            "font": list(FONT_CHOICES),
            "font_provider": list(FONT_PROVIDER_CHOICES),
            "format": list(FORMAT_CHOICES),
            "image_fit": list(IMAGE_FIT_CHOICES),
            "text_align": list(TEXT_ALIGN_CHOICES),
        },
        "font_providers": {
            "google": {
                "font_value_format": "google:<family-slug>",
                "examples": list(GOOGLE_FONT_CHOICES),
                "notes": [
                    "Provider fonts are resolved through the Google Fonts CSS API at render time.",
                    "The renderer caches downloaded font files locally after the first successful render.",
                    "Use hyphenated family slugs, for example google:playfair-display or google:dm-sans.",
                ],
            }
        },
        "access": {
            "hosted_mcp_url": "https://osig.app/mcp/",
            "authentication_required": False,
            "trial_note": (
                "The hosted MCP endpoint is currently public for trial use. Contract discovery, normalization, "
                "preview rendering, and image export work without a profile key."
            ),
            "profile_key_note": "A profile key is optional unless the user wants quota and paid watermark state.",
            "future_auth_note": "Profile-key auth is expected before paid production MCP access.",
        },
        "workflow": [
            "Call get_image_contract to inspect canvas limits, layer kinds, choices, and output formats.",
            "Build an ImageSpec with dimensions, background, and ordered rect/text/image layers.",
            "Call normalize_image_spec to canonicalize input and surface warnings.",
            "Call render_image_preview while iterating.",
            "Call export_image when the asset is ready to save into a repository.",
        ],
        "example_spec": {
            "site": "x",
            "background": "#0f172a",
            "layers": [
                {"kind": "rect", "x": 40, "y": 40, "width": 720, "height": 370, "color": "#1d4ed8", "radius": 24},
                {
                    "kind": "text",
                    "x": 80,
                    "y": 110,
                    "width": 620,
                    "text": "Ship deterministic images from code.",
                    "font": "google:inter",
                    "font_size": 52,
                    "color": "#ffffff",
                    "line_height": 62,
                },
            ],
            "format": "png",
        },
    }


def normalize_image_spec(spec: ImageSpec, profile: Profile | None = None) -> NormalizedImageSpec:
    warnings: list[str] = []

    if profile is not None and spec.key and spec.key != profile.key:
        raise PermissionError("The supplied key does not match the authenticated profile.")

    if profile is not None and spec.key != profile.key:
        spec = spec.model_copy(update={"key": profile.key})

    resolved_profile = profile or _profile_for_key(spec.key, warnings)
    width, height = _dimensions_for_spec(spec)

    public_spec: dict[str, Any] = {
        "width": width,
        "height": height,
        "background": spec.background,
        "layers": [_layer_dump(layer) for layer in spec.layers],
        "format": spec.format,
    }

    if spec.site:
        public_spec["site"] = spec.site

    optional_values = {
        "key": spec.key,
        "quality": spec.quality,
        "max_kb": spec.max_kb,
        "v": spec.v,
    }
    for key, value in optional_values.items():
        if value not in (None, ""):
            public_spec[key] = value

    warnings.extend(_canvas_warnings(spec, width, height))

    render_params = dict(public_spec)
    if resolved_profile is not None:
        render_params["profile_id"] = resolved_profile.id

    return NormalizedImageSpec(
        spec=public_spec,
        render_params=render_params,
        safe_render_params=_safe_render_params(render_params),
        warnings=warnings,
        width=width,
        height=height,
        content_type=_content_type_for_format(spec.format),
        profile=resolved_profile,
    )


def _usage_payload(usage_state: UsageState | None) -> dict[str, Any] | None:
    if usage_state is None:
        return None

    return {
        "daily_count": usage_state.daily_count,
        "daily_limit": usage_state.daily_limit,
        "monthly_count": usage_state.monthly_count,
        "monthly_limit": usage_state.monthly_limit,
        "warnings": list(usage_state.warnings),
        "blocked": usage_state.blocked,
        "blocked_reasons": list(usage_state.blocked_reasons),
    }


def render_image(
    spec: ImageSpec,
    *,
    profile: Profile | None = None,
    include_image_base64: bool = True,
    track_usage: bool = True,
) -> dict[str, Any]:
    close_old_connections()
    started_at = perf_counter()
    normalized: NormalizedImageSpec | None = None
    usage_state: UsageState | None = None

    try:
        normalized = normalize_image_spec(spec, profile=profile)
        if track_usage and normalized.profile is not None:
            usage_state = track_profile_usage(normalized.profile)
            if usage_state.blocked:
                raise ImageUsageLimitExceeded(usage_state)

        max_attempts = max(1, int(getattr(settings, "OSIG_RENDER_MAX_ATTEMPTS", 2)))

        for attempt_number in range(1, max_attempts + 1):
            attempt_started_at = perf_counter()
            try:
                image_buffer = render_canvas_image(normalized.render_params)
                payload = image_buffer.getvalue()
                render_duration_ms = int((perf_counter() - attempt_started_at) * 1000)
            except Exception as exc:
                duration_ms = int((perf_counter() - attempt_started_at) * 1000)
                error_type = classify_render_error(exc)

                _record_render_attempt_safely(
                    profile=normalized.profile,
                    key=normalized.spec.get("key", ""),
                    renderer="canvas",
                    success=False,
                    duration_ms=duration_ms,
                    error_type=error_type,
                    attempt_number=attempt_number,
                )

                should_retry = is_transient_error(error_type) and attempt_number < max_attempts
                logger.warning(
                    "Agent image render failed",
                    error_type=error_type,
                    attempt_number=attempt_number,
                    max_attempts=max_attempts,
                    should_retry=should_retry,
                    error=str(exc),
                )
                if should_retry:
                    continue

                raise ImageRenderFailed(error_type) from exc
            else:
                metadata = _image_payload_metadata(payload)
                _record_render_attempt_safely(
                    profile=normalized.profile,
                    key=normalized.spec.get("key", ""),
                    renderer="canvas",
                    success=True,
                    duration_ms=render_duration_ms,
                    attempt_number=attempt_number,
                )

                response: dict[str, Any] = {
                    "spec": normalized.spec,
                    "render_params": normalized.safe_render_params,
                    "warnings": [*normalized.warnings, *(usage_state.warnings if usage_state else [])],
                    "content_type": normalized.content_type,
                    "extension": _extension_for_format(spec.format),
                    "render_ms": int((perf_counter() - started_at) * 1000),
                    "output": {
                        "width": normalized.width,
                        "height": normalized.height,
                        "content_type": normalized.content_type,
                    },
                    "usage": _usage_payload(usage_state),
                    **metadata,
                }

                if include_image_base64:
                    encoded_image = base64.b64encode(payload).decode("ascii")
                    response["image_base64"] = encoded_image
                    response["data_uri"] = f"data:{normalized.content_type};base64,{encoded_image}"

                return response
    finally:
        close_old_connections()
