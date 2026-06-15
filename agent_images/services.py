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
from pydantic import BaseModel, ConfigDict, Field

from core.image_styles import generate_image_router
from core.image_utils import get_image_dimensions
from core.models import Profile
from core.render_observability import classify_render_error, is_transient_error, record_render_attempt
from core.usage import UsageState, track_profile_usage
from osig.utils import get_osig_logger

StyleName = Literal["base", "logo", "job_classic", "job_logo", "job_clean"]
SiteName = Literal["x", "meta"]
FontName = Literal["helvetica", "markerfelt", "papyrus"]
OutputFormat = Literal["png", "jpeg"]

STYLE_CHOICES: tuple[StyleName, ...] = ("base", "logo", "job_classic", "job_logo", "job_clean")
SITE_CHOICES: tuple[SiteName, ...] = ("x", "meta")
FONT_CHOICES: tuple[FontName, ...] = ("helvetica", "markerfelt", "papyrus")
FORMAT_CHOICES: tuple[OutputFormat, ...] = ("png", "jpeg")

TEMPLATE_DEFINITIONS: dict[str, dict[str, str]] = {
    "base": {
        "name": "Article",
        "description": "Full-bleed background with left-aligned editorial copy.",
        "best_for": "Posts, guides, essays, launches, and pages with a strong cover image.",
    },
    "logo": {
        "name": "Logo",
        "description": "Centered logo or avatar with centered project copy.",
        "best_for": "Projects, products, company pages, and simple brand cards.",
    },
    "job_classic": {
        "name": "Job Classic",
        "description": "High-contrast hiring card over a full-bleed image.",
        "best_for": "Job posts with a background image and strong role headline.",
    },
    "job_logo": {
        "name": "Job Logo",
        "description": "Dark role-focused card with a circular logo slot.",
        "best_for": "Hiring pages where the company mark is the main visual asset.",
    },
    "job_clean": {
        "name": "Job Clean",
        "description": "Minimal light hiring card with an accent bar and logo slot.",
        "best_for": "Job posts that need a calmer, text-first preview.",
    },
}

logger = get_osig_logger(__name__)


class ImageSpec(BaseModel):
    """Structured image input for agents and the Studio UI."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    key: Annotated[
        str,
        Field(default="", max_length=64, description="Optional OSIG profile key for quota and paid watermark state."),
    ]
    style: Annotated[StyleName, Field(default="base", description="Image template to render.")]
    site: Annotated[SiteName, Field(default="x", description="Target social preview size preset.")]
    font: Annotated[FontName, Field(default="helvetica", description="Bundled font family.")]
    title: Annotated[str, Field(default="", max_length=500, description="Main image copy.")]
    subtitle: Annotated[str, Field(default="", max_length=1000, description="Secondary image copy.")]
    eyebrow: Annotated[str, Field(default="", max_length=240, description="Small context label.")]
    image_url: Annotated[str, Field(default="", max_length=2000, description="Remote background image or logo URL.")]
    image_or_logo: Annotated[
        str,
        Field(default="", max_length=2000, description="Alias for image_url, useful for job templates."),
    ]
    format: Annotated[OutputFormat, Field(default="png", description="Rendered image format.")]
    quality: Annotated[int | None, Field(default=None, ge=1, le=100, description="PNG/JPEG compression quality.")]
    max_kb: Annotated[int | None, Field(default=None, ge=1, le=10000, description="Best-effort target size in KB.")]
    v: Annotated[str, Field(default="", max_length=100, description="Optional version token for caller bookkeeping.")]


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


def list_templates() -> list[dict[str, str]]:
    return [{"id": style, **TEMPLATE_DEFINITIONS[style]} for style in STYLE_CHOICES]


def image_contract() -> dict[str, Any]:
    dimensions = {
        site: {"width": get_image_dimensions(site)[0], "height": get_image_dimensions(site)[1]} for site in SITE_CHOICES
    }

    return {
        "product": "OSIG Agent Images",
        "purpose": "Deterministic Open Graph and social preview images for AI agents.",
        "templates": list_templates(),
        "choices": {
            "style": list(STYLE_CHOICES),
            "site": list(SITE_CHOICES),
            "font": list(FONT_CHOICES),
            "format": list(FORMAT_CHOICES),
        },
        "dimensions": dimensions,
        "fields": {
            "title": "Main copy. Templates clamp or truncate long text.",
            "subtitle": "Supporting copy. Keep it short for social previews.",
            "eyebrow": "Small context label such as category, role type, or launch status.",
            "image_url": "Remote background image or logo URL. image_or_logo is accepted as an alias.",
            "key": "Optional profile key for quota and paid watermark state. Omit for self-hosted/local trials.",
        },
        "workflow": [
            "Call get_image_contract or list_image_templates to choose a template.",
            "Call normalize_image_spec to canonicalize input and surface warnings.",
            "Call render_image_preview while iterating.",
            "Call export_image when the asset is ready to save into a repository.",
        ],
    }


def normalize_image_spec(spec: ImageSpec, profile: Profile | None = None) -> NormalizedImageSpec:
    warnings: list[str] = []

    if profile is not None and spec.key and spec.key != profile.key:
        raise PermissionError("The supplied key does not match the authenticated profile.")

    if profile is not None and spec.key != profile.key:
        spec = spec.model_copy(update={"key": profile.key})

    image_url = spec.image_url or spec.image_or_logo
    if spec.image_url and spec.image_or_logo and spec.image_url != spec.image_or_logo:
        warnings.append("Both image_url and image_or_logo were provided; image_url was used.")

    resolved_profile = profile or _profile_for_key(spec.key, warnings)

    public_spec: dict[str, Any] = {
        "style": spec.style,
        "site": spec.site,
        "font": spec.font,
        "format": spec.format,
    }
    optional_values = {
        "key": spec.key,
        "title": spec.title,
        "subtitle": spec.subtitle,
        "eyebrow": spec.eyebrow,
        "image_url": image_url,
        "quality": spec.quality,
        "max_kb": spec.max_kb,
        "v": spec.v,
    }
    for key, value in optional_values.items():
        if value not in (None, ""):
            public_spec[key] = value

    render_params = dict(public_spec)
    if resolved_profile is not None:
        render_params["profile_id"] = resolved_profile.id

    width, height = get_image_dimensions(spec.site)
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
                image_buffer = generate_image_router(normalized.render_params)
                payload = image_buffer.getvalue()
                render_duration_ms = int((perf_counter() - attempt_started_at) * 1000)
            except Exception as exc:
                duration_ms = int((perf_counter() - attempt_started_at) * 1000)
                error_type = classify_render_error(exc)

                _record_render_attempt_safely(
                    profile=normalized.profile,
                    key=normalized.spec.get("key", ""),
                    style=normalized.spec.get("style", "base"),
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
                    style=normalized.spec.get("style", "base"),
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
