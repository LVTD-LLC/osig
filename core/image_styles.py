from __future__ import annotations

import io
from typing import Any

import requests
from django.conf import settings
from PIL import Image, ImageColor, ImageDraw

from core.image_utils import add_watermark, create_image_buffer, load_font
from core.utils import check_if_profile_has_pro_subscription
from osig.utils import get_osig_logger

logger = get_osig_logger(__name__)


def parse_color(color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    rgba = ImageColor.getcolor(color, "RGBA")
    alpha = max(0, min(255, round(rgba[3] * opacity)))
    return rgba[0], rgba[1], rgba[2], alpha


def _apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 1:
        return image

    faded = image.copy()
    alpha = faded.getchannel("A").point(lambda value: round(value * max(0, opacity)))
    faded.putalpha(alpha)
    return faded


def _composite_clipped(base: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + overlay.width, base.width)
    bottom = min(y + overlay.height, base.height)

    if right <= left or bottom <= top:
        return

    crop_box = (left - x, top - y, right - x, bottom - y)
    base.alpha_composite(overlay.crop(crop_box), (left, top))


def _load_remote_image(url: str) -> Image.Image:
    timeout_seconds = getattr(settings, "OSIG_IMAGE_FETCH_TIMEOUT_SECONDS", 8)
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).convert("RGBA")


def _resize_image(image: Image.Image, width: int, height: int, fit: str) -> Image.Image:
    if fit == "stretch":
        return image.resize((width, height), Image.LANCZOS)

    scale = (
        min(width / image.width, height / image.height)
        if fit == "contain"
        else max(width / image.width, height / image.height)
    )
    resized_width = max(1, round(image.width * scale))
    resized_height = max(1, round(image.height * scale))
    resized = image.resize((resized_width, resized_height), Image.LANCZOS)

    if fit == "contain":
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        layer.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
        return layer

    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _draw_rect(img: Image.Image, layer: dict[str, Any]) -> None:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x = int(layer["x"])
    y = int(layer["y"])
    width = int(layer["width"])
    height = int(layer["height"])
    radius = int(layer.get("radius") or 0)
    fill = parse_color(layer["color"], float(layer.get("opacity", 1)))
    box = [x, y, x + width, y + height]

    if radius:
        draw.rounded_rectangle(box, radius=radius, fill=fill)
    else:
        draw.rectangle(box, fill=fill)

    img.alpha_composite(overlay)


def _line_width(font, text: str) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _wrap_paragraph(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join([*current, word])
        if not current or _line_width(font, candidate) <= max_width:
            current.append(word)
            continue

        lines.append(" ".join(current))
        current = [word]

    if current:
        lines.append(" ".join(current))

    return lines


def _wrap_text(text: str, font, max_width: int | None) -> list[str]:
    if not max_width:
        return text.splitlines() or [text]

    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        lines.extend(_wrap_paragraph(paragraph, font, max_width))
    return lines


def _draw_text(img: Image.Image, layer: dict[str, Any]) -> None:
    font_size = int(layer["font_size"])
    font = load_font(layer["font"], font_size)
    x = int(layer["x"])
    y = int(layer["y"])
    block_width = layer.get("width")
    max_width = int(block_width) if block_width else None
    line_height = int(layer.get("line_height") or round(font_size * 1.2))
    align = layer.get("align", "left")
    fill = parse_color(layer["color"], float(layer.get("opacity", 1)))
    stroke_color = layer.get("stroke_color")
    stroke_fill = parse_color(stroke_color, float(layer.get("opacity", 1))) if stroke_color else None
    stroke_width = int(layer.get("stroke_width") or 0)

    draw = ImageDraw.Draw(img)
    current_y = y
    for line in _wrap_text(layer["text"], font, max_width):
        line_x = x
        if max_width and align != "left":
            line_width = _line_width(font, line)
            if align == "center":
                line_x = x + max(0, (max_width - line_width) // 2)
            elif align == "right":
                line_x = x + max(0, max_width - line_width)

        draw.text(
            (line_x, current_y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        current_y += line_height


def _draw_image(img: Image.Image, layer: dict[str, Any]) -> None:
    remote = _load_remote_image(layer["url"])
    resized = _resize_image(remote, int(layer["width"]), int(layer["height"]), layer.get("fit", "cover"))
    resized = _apply_opacity(resized, float(layer.get("opacity", 1)))
    _composite_clipped(img, resized, int(layer["x"]), int(layer["y"]))


def render_canvas_image(image_data: dict[str, Any]):
    width = int(image_data["width"])
    height = int(image_data["height"])
    img = Image.new("RGBA", (width, height), parse_color(image_data.get("background", "#ffffff")))

    logger.info(
        "Generating canvas image",
        profile_id=image_data.get("profile_id"),
        width=width,
        height=height,
        layer_count=len(image_data.get("layers", [])),
    )

    for layer in image_data.get("layers", []):
        kind = layer["kind"]
        if kind == "rect":
            _draw_rect(img, layer)
        elif kind == "text":
            _draw_text(img, layer)
        elif kind == "image":
            _draw_image(img, layer)
        else:
            raise ValueError(f"Unsupported layer kind: {kind}")

    if not check_if_profile_has_pro_subscription(image_data.get("profile_id")):
        add_watermark(img, ImageDraw.Draw(img), width, height)

    return create_image_buffer(
        img,
        output_format=image_data.get("format", "png"),
        quality=image_data.get("quality"),
        max_kb=image_data.get("max_kb"),
    )
