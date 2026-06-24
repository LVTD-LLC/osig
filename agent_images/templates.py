from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from core.image_utils import get_image_dimensions
from osig.utils import get_osig_logger

TemplateId = Literal["repo_preview", "article_summary", "product_update"]
TemplateSite = Literal["x", "meta"]
TemplateFormat = Literal["png", "jpeg"]
TemplateTag = Annotated[str, Field(min_length=1, max_length=32)]

logger = get_osig_logger(__name__)
_IMAGE_SOURCE_ADAPTER: TypeAdapter[Any] | None = None


def _image_source_adapter() -> TypeAdapter[Any]:
    global _IMAGE_SOURCE_ADAPTER

    if _IMAGE_SOURCE_ADAPTER is None:
        from agent_images.services import ImageSource

        _IMAGE_SOURCE_ADAPTER = TypeAdapter(ImageSource)
    return _IMAGE_SOURCE_ADAPTER


class OgTemplateContent(BaseModel):
    """Structured content slots for deterministic Open Graph template specs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: Annotated[str, Field(min_length=1, max_length=140, description="Primary social image headline.")]
    subtitle: Annotated[str, Field(default="", max_length=260, description="Optional supporting copy.")]
    site_name: Annotated[str, Field(default="", max_length=80, description="Publisher, product, or site label.")]
    logo: Annotated[dict[str, Any] | None, Field(default=None, description="Optional OSIG image source for a logo.")]
    image: Annotated[
        dict[str, Any] | None, Field(default=None, description="Optional OSIG image source for a hero image.")
    ]
    tags: Annotated[list[TemplateTag], Field(default_factory=list, max_length=4, description="Optional short tags.")]

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        return [tag.strip() for tag in tags if tag.strip()]

    @field_validator("logo", "image")
    @classmethod
    def validate_image_source(cls, source: dict[str, Any] | None) -> dict[str, Any] | None:
        if source is None:
            return None

        validated_source = _image_source_adapter().validate_python(source)
        return validated_source.model_dump()


TEMPLATE_LIBRARY: dict[str, dict[str, Any]] = {
    "repo_preview": {
        "name": "Repo Preview",
        "description": "Technical repo or launch card with strong headline, site label, tags, and optional logo.",
        "slots": ["title", "subtitle", "site_name", "logo", "tags"],
    },
    "article_summary": {
        "name": "Article Summary",
        "description": "Editorial social card for posts, essays, docs, or changelogs with optional hero image.",
        "slots": ["title", "subtitle", "site_name", "image", "tags"],
    },
    "product_update": {
        "name": "Product Update",
        "description": "Product or feature announcement card with logo, image, headline, and tag chips.",
        "slots": ["title", "subtitle", "site_name", "logo", "image", "tags"],
    },
}


def _scaled(value: int, ratio: float) -> int:
    return max(1, round(value * ratio))


def _font_size(value: int, ratio: float) -> int:
    return max(12, round(value * ratio))


def _base_layout(site: TemplateSite) -> tuple[int, int, float, float]:
    width, height = get_image_dimensions(site)
    reference_width, reference_height = get_image_dimensions("x")
    return width, height, width / reference_width, height / reference_height


def _tag_layers(tags: list[str], *, x: int, y: int, scale_x: float, scale_y: float) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    current_x = x
    for tag in tags[:4]:
        chip_width = min(_scaled(150, scale_x), _scaled(30 + len(tag) * 10, scale_x))
        chip_height = _scaled(34, scale_y)
        layers.extend(
            [
                {
                    "kind": "rect",
                    "x": current_x,
                    "y": y,
                    "width": chip_width,
                    "height": chip_height,
                    "fill": "rgba(15,23,42,0.08)",
                    "radius": _scaled(17, scale_y),
                },
                {
                    "kind": "text",
                    "x": current_x + _scaled(14, scale_x),
                    "y": y + _scaled(8, scale_y),
                    "width": chip_width - _scaled(28, scale_x),
                    "height": _scaled(18, scale_y),
                    "text": tag,
                    "font_size": _font_size(15, scale_y),
                    "color": "#334155",
                    "overflow": "clamp",
                },
            ]
        )
        current_x += chip_width + _scaled(10, scale_x)
    return layers


def _logo_or_mark(content: OgTemplateContent, *, x: int, y: int, size: int) -> list[dict[str, Any]]:
    if content.logo:
        return [
            {
                "kind": "image",
                "x": x,
                "y": y,
                "width": size,
                "height": size,
                "src": content.logo,
                "fit": "contain",
                "radius": max(4, round(size * 0.18)),
            }
        ]

    return [
        {
            "kind": "rect",
            "x": x,
            "y": y,
            "width": size,
            "height": size,
            "fill": {"type": "linear_gradient", "from": "#2563eb", "to": "#0f766e", "angle": 135},
            "radius": max(4, round(size * 0.22)),
        }
    ]


def _repo_preview_spec(
    content: OgTemplateContent, *, site: TemplateSite, output_format: TemplateFormat
) -> dict[str, Any]:
    width, height, scale_x, scale_y = _base_layout(site)
    margin_x = _scaled(48, scale_x)
    margin_y = _scaled(42, scale_y)
    logo_size = _scaled(52, scale_y)

    layers: list[dict[str, Any]] = [
        {
            "kind": "rect",
            "x": margin_x,
            "y": margin_y,
            "width": width - margin_x * 2,
            "height": height - margin_y * 2,
            "fill": "#ffffff",
            "radius": _scaled(26, scale_y),
            "border": {"color": "rgba(15,23,42,0.12)", "width": max(1, _scaled(2, scale_x))},
            "shadow": {"x": 0, "y": _scaled(16, scale_y), "blur": _scaled(32, scale_y), "color": "rgba(15,23,42,0.16)"},
        },
        *_logo_or_mark(content, x=margin_x + _scaled(30, scale_x), y=margin_y + _scaled(28, scale_y), size=logo_size),
        {
            "kind": "text",
            "x": margin_x + _scaled(96, scale_x),
            "y": margin_y + _scaled(36, scale_y),
            "width": width - margin_x * 2 - _scaled(140, scale_x),
            "height": _scaled(28, scale_y),
            "text": content.site_name or "OSIG",
            "font_size": _font_size(20, scale_y),
            "color": "#475569",
            "overflow": "clamp",
        },
        {
            "kind": "text",
            "x": margin_x + _scaled(30, scale_x),
            "y": margin_y + _scaled(118, scale_y),
            "width": width - margin_x * 2 - _scaled(60, scale_x),
            "height": _scaled(135, scale_y),
            "text": content.title,
            "font": "google:inter",
            "font_size": _font_size(56, scale_y),
            "line_height": _scaled(64, scale_y),
            "color": "#0f172a",
            "overflow": "clamp",
        },
        {
            "kind": "text",
            "x": margin_x + _scaled(32, scale_x),
            "y": margin_y + _scaled(262, scale_y),
            "width": width - margin_x * 2 - _scaled(64, scale_x),
            "height": _scaled(54, scale_y),
            "text": content.subtitle or "Deterministic social image output, ready for repository workflows.",
            "font_size": _font_size(25, scale_y),
            "line_height": _scaled(31, scale_y),
            "color": "#475569",
            "overflow": "clamp",
        },
    ]
    layers.extend(
        _tag_layers(
            content.tags,
            x=margin_x + _scaled(30, scale_x),
            y=height - margin_y - _scaled(62, scale_y),
            scale_x=scale_x,
            scale_y=scale_y,
        )
    )

    return {
        "site": site,
        "width": width,
        "height": height,
        "background": "#f8fafc",
        "layers": layers,
        "format": output_format,
    }


def _article_summary_spec(
    content: OgTemplateContent, *, site: TemplateSite, output_format: TemplateFormat
) -> dict[str, Any]:
    width, height, scale_x, scale_y = _base_layout(site)
    text_width = _scaled(470, scale_x) if content.image else width - _scaled(96, scale_x)
    layers: list[dict[str, Any]] = [
        {"kind": "rect", "x": 0, "y": 0, "width": width, "height": height, "fill": "#fff7ed"},
        {
            "kind": "rect",
            "x": _scaled(42, scale_x),
            "y": _scaled(38, scale_y),
            "width": width - _scaled(84, scale_x),
            "height": height - _scaled(76, scale_y),
            "fill": "#ffffff",
            "radius": _scaled(20, scale_y),
            "border": {"color": "rgba(124,45,18,0.16)", "width": max(1, _scaled(2, scale_x))},
        },
        {
            "kind": "text",
            "x": _scaled(72, scale_x),
            "y": _scaled(70, scale_y),
            "width": text_width,
            "height": _scaled(28, scale_y),
            "text": content.site_name or "Publication",
            "font_size": _font_size(19, scale_y),
            "color": "#9a3412",
            "overflow": "clamp",
        },
        {
            "kind": "text",
            "x": _scaled(72, scale_x),
            "y": _scaled(120, scale_y),
            "width": text_width,
            "height": _scaled(164, scale_y),
            "text": content.title,
            "font": "google:playfair-display",
            "font_size": _font_size(54, scale_y),
            "line_height": _scaled(62, scale_y),
            "color": "#1c1917",
            "overflow": "clamp",
        },
        {
            "kind": "text",
            "x": _scaled(74, scale_x),
            "y": _scaled(292, scale_y),
            "width": text_width,
            "height": _scaled(58, scale_y),
            "text": content.subtitle or "A concise summary for social preview cards.",
            "font_size": _font_size(24, scale_y),
            "line_height": _scaled(30, scale_y),
            "color": "#57534e",
            "overflow": "clamp",
        },
    ]

    if content.image:
        layers.append(
            {
                "kind": "image",
                "x": _scaled(566, scale_x),
                "y": _scaled(76, scale_y),
                "width": _scaled(172, scale_x),
                "height": _scaled(286, scale_y),
                "src": content.image,
                "fit": "cover",
                "radius": _scaled(18, scale_y),
            }
        )

    layers.extend(
        _tag_layers(
            content.tags, x=_scaled(72, scale_x), y=height - _scaled(74, scale_y), scale_x=scale_x, scale_y=scale_y
        )
    )

    return {
        "site": site,
        "width": width,
        "height": height,
        "background": "#fff7ed",
        "layers": layers,
        "format": output_format,
    }


def _product_update_spec(
    content: OgTemplateContent, *, site: TemplateSite, output_format: TemplateFormat
) -> dict[str, Any]:
    width, height, scale_x, scale_y = _base_layout(site)
    layers: list[dict[str, Any]] = [
        {
            "kind": "rect",
            "x": 0,
            "y": 0,
            "width": width,
            "height": height,
            "fill": {"type": "linear_gradient", "from": "#0f172a", "to": "#164e63", "angle": 135},
        },
        {
            "kind": "rect",
            "x": _scaled(44, scale_x),
            "y": _scaled(40, scale_y),
            "width": width - _scaled(88, scale_x),
            "height": height - _scaled(80, scale_y),
            "fill": "rgba(255,255,255,0.10)",
            "radius": _scaled(24, scale_y),
            "border": {"color": "rgba(255,255,255,0.22)", "width": max(1, _scaled(2, scale_x))},
        },
        *_logo_or_mark(content, x=_scaled(76, scale_x), y=_scaled(74, scale_y), size=_scaled(48, scale_y)),
        {
            "kind": "text",
            "x": _scaled(138, scale_x),
            "y": _scaled(83, scale_y),
            "width": _scaled(340, scale_x),
            "height": _scaled(28, scale_y),
            "text": content.site_name or "Product update",
            "font_size": _font_size(20, scale_y),
            "color": "#bae6fd",
            "overflow": "clamp",
        },
        {
            "kind": "text",
            "x": _scaled(76, scale_x),
            "y": _scaled(146, scale_y),
            "width": _scaled(438, scale_x),
            "height": _scaled(146, scale_y),
            "text": content.title,
            "font": "google:inter",
            "font_size": _font_size(53, scale_y),
            "line_height": _scaled(61, scale_y),
            "color": "#ffffff",
            "overflow": "clamp",
        },
        {
            "kind": "text",
            "x": _scaled(78, scale_x),
            "y": _scaled(304, scale_y),
            "width": _scaled(430, scale_x),
            "height": _scaled(56, scale_y),
            "text": content.subtitle or "A deterministic announcement card generated from structured content.",
            "font_size": _font_size(23, scale_y),
            "line_height": _scaled(29, scale_y),
            "color": "#dbeafe",
            "overflow": "clamp",
        },
    ]

    if content.image:
        layers.append(
            {
                "kind": "image",
                "x": _scaled(552, scale_x),
                "y": _scaled(110, scale_y),
                "width": _scaled(174, scale_x),
                "height": _scaled(214, scale_y),
                "src": content.image,
                "fit": "cover",
                "radius": _scaled(22, scale_y),
                "opacity": 0.96,
            }
        )
    else:
        layers.append(
            {
                "kind": "rect",
                "x": _scaled(552, scale_x),
                "y": _scaled(110, scale_y),
                "width": _scaled(174, scale_x),
                "height": _scaled(214, scale_y),
                "fill": {"type": "linear_gradient", "from": "#38bdf8", "to": "#a7f3d0", "angle": 90},
                "radius": _scaled(22, scale_y),
                "opacity": 0.88,
            }
        )

    layers.extend(
        _tag_layers(
            content.tags, x=_scaled(76, scale_x), y=height - _scaled(74, scale_y), scale_x=scale_x, scale_y=scale_y
        )
    )

    return {
        "site": site,
        "width": width,
        "height": height,
        "background": "#0f172a",
        "layers": layers,
        "format": output_format,
    }


def _template_spec(
    template: TemplateId, content: OgTemplateContent, *, site: TemplateSite, output_format: TemplateFormat
) -> dict[str, Any]:
    builders = {
        "repo_preview": _repo_preview_spec,
        "article_summary": _article_summary_spec,
        "product_update": _product_update_spec,
    }
    return builders[template](content, site=site, output_format=output_format)


def build_og_image_spec(
    content: OgTemplateContent,
    template: TemplateId = "repo_preview",
    site: TemplateSite = "x",
    output_format: TemplateFormat = "png",
) -> dict[str, Any]:
    spec = _template_spec(template, content, site=site, output_format=output_format)

    from .services import ImageSpec

    ImageSpec.model_validate(spec)
    width, height = get_image_dimensions(site)

    return {
        "template": {
            "id": template,
            "name": TEMPLATE_LIBRARY[template]["name"],
            "slots": TEMPLATE_LIBRARY[template]["slots"],
        },
        "spec": spec,
        "warnings": [],
        "output": {
            "width": width,
            "height": height,
            "content_type": "image/jpeg" if output_format == "jpeg" else "image/png",
        },
    }


@lru_cache(maxsize=1)
def _cached_template_library_contract() -> tuple[dict[str, Any], ...]:
    example_content = OgTemplateContent(
        title="Ship repo-ready social images",
        subtitle="Generate deterministic Open Graph assets from structured content.",
        site_name="OSIG",
        tags=["MCP", "OG image"],
    )

    templates: list[dict[str, Any]] = []
    for template_id, definition in TEMPLATE_LIBRARY.items():
        try:
            example_specs = {
                "x": build_og_image_spec(example_content, template=template_id, site="x", output_format="png")["spec"],
                "meta": build_og_image_spec(example_content, template=template_id, site="meta", output_format="png")[
                    "spec"
                ],
            }
        except ValidationError as exc:
            logger.warning("Skipping invalid OG template contract example", template_id=template_id, error=str(exc))
            continue

        templates.append(
            {
                "id": template_id,
                "name": definition["name"],
                "description": definition["description"],
                "slots": definition["slots"],
                "supported_sites": ["x", "meta"],
                "output_formats": ["png", "jpeg"],
                "example_specs": example_specs,
            }
        )

    return tuple(templates)


def template_library_contract() -> list[dict[str, Any]]:
    return [deepcopy(template) for template in _cached_template_library_contract()]
