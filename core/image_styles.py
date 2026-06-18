from __future__ import annotations

import io
import re
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings
from PIL import Image, ImageColor, ImageDraw, ImageFilter

from core.image_url_safety import validate_remote_image_url
from core.image_utils import add_watermark, create_image_buffer, load_font
from core.utils import check_if_profile_has_pro_subscription
from osig.utils import get_osig_logger

logger = get_osig_logger(__name__)

RGBA_RE = re.compile(
    r"^rgba?\(\s*(?P<red>\d{1,3})\s*,\s*(?P<green>\d{1,3})\s*,\s*(?P<blue>\d{1,3})(?:\s*,\s*(?P<alpha>[0-9.]+)\s*)?\)$",
    re.IGNORECASE,
)


def parse_color(color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    match = RGBA_RE.match(color)
    if match:
        red = max(0, min(255, int(match.group("red"))))
        green = max(0, min(255, int(match.group("green"))))
        blue = max(0, min(255, int(match.group("blue"))))
        alpha_value = match.group("alpha")
        if alpha_value is None:
            alpha = 255
        else:
            alpha_float = float(alpha_value)
            alpha = round((alpha_float if alpha_float <= 1 else alpha_float / 255) * 255)
        rgba = (red, green, blue, max(0, min(255, alpha)))
    else:
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
    current_url = validate_remote_image_url(url, resolve=True)
    timeout_seconds = getattr(settings, "OSIG_IMAGE_FETCH_TIMEOUT_SECONDS", 8)
    max_redirects = getattr(settings, "OSIG_IMAGE_FETCH_MAX_REDIRECTS", 3)

    for _ in range(max_redirects + 1):
        response = requests.get(current_url, timeout=timeout_seconds, allow_redirects=False)
        if response.is_redirect:
            redirect_url = response.headers.get("Location")
            if not redirect_url:
                raise ValueError("Image URL redirect is missing a Location header.")
            current_url = validate_remote_image_url(urljoin(current_url, redirect_url), resolve=True)
            continue

        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGBA")

    raise ValueError("Image URL redirected too many times.")


def _load_inline_image(source: dict[str, Any]) -> Image.Image:
    import base64

    payload = base64.b64decode(source["data"], validate=True)
    return Image.open(io.BytesIO(payload)).convert("RGBA")


def _load_source_image(source: dict[str, Any]) -> Image.Image:
    if source["type"] == "url":
        return _load_remote_image(source["url"])
    if source["type"] == "base64":
        return _load_inline_image(source)
    raise ValueError(f"Unsupported image source type: {source['type']}")


def _resize_image(image: Image.Image, width: int, height: int, fit: str) -> Image.Image:
    if fit == "fill":
        return image.resize((width, height), Image.LANCZOS)

    if fit == "none":
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        layer.alpha_composite(image.crop((0, 0, min(width, image.width), min(height, image.height))), (0, 0))
        return layer

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


def _rounded_mask(width: int, height: int, radius: int) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    box = (0, 0, width, height)
    if radius:
        draw.rounded_rectangle(box, radius=radius, fill=255)
    else:
        draw.rectangle(box, fill=255)
    return mask


def _apply_radius(image: Image.Image, radius: int) -> Image.Image:
    if not radius:
        return image
    rounded = image.copy()
    rounded.putalpha(
        Image.composite(rounded.getchannel("A"), Image.new("L", image.size, 0), _rounded_mask(*image.size, radius))
    )
    return rounded


def _linear_gradient(size: tuple[int, int], fill: dict[str, Any], opacity: float) -> Image.Image:
    width, height = size
    start = parse_color(fill["from"], opacity)
    end = parse_color(fill["to"], opacity)

    if width == 1:
        mask = Image.linear_gradient("L").resize((1, height))
    else:
        mask = Image.linear_gradient("L").rotate(90, expand=True).resize((width, height))

    angle = int(fill.get("angle", 0)) % 360
    if angle:
        rotated = mask.resize((max(width, height) * 2, max(width, height) * 2))
        rotated = rotated.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=False)
        left = (rotated.width - width) // 2
        top = (rotated.height - height) // 2
        mask = rotated.crop((left, top, left + width, top + height))

    return Image.composite(Image.new("RGBA", size, end), Image.new("RGBA", size, start), mask)


def _fill_image(size: tuple[int, int], fill: str | dict[str, Any], opacity: float = 1.0) -> Image.Image:
    if isinstance(fill, dict):
        if fill.get("type") == "linear_gradient":
            return _linear_gradient(size, fill, opacity)
        raise ValueError(f"Unsupported fill type: {fill.get('type')}")

    return Image.new("RGBA", size, parse_color(fill, opacity))


def _draw_shadow(img: Image.Image, layer: dict[str, Any], radius: int) -> None:
    shadow = layer.get("shadow")
    if not shadow:
        return

    x = int(layer["x"]) + int(shadow.get("x", 0))
    y = int(layer["y"]) + int(shadow.get("y", 0))
    width = int(layer["width"])
    height = int(layer["height"])
    blur = int(shadow.get("blur", 0))
    color = parse_color(shadow.get("color", "rgba(0,0,0,0.35)"), float(layer.get("opacity", 1)))
    padding = blur * 2
    shadow_layer = Image.new("RGBA", (width + padding * 2, height + padding * 2), (0, 0, 0, 0))
    shape = Image.new("RGBA", (width, height), color)
    shape.putalpha(_rounded_mask(width, height, radius).point(lambda value: round(value * (color[3] / 255))))
    shadow_layer.alpha_composite(shape, (padding, padding))
    if blur:
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
    _composite_clipped(img, shadow_layer, x - padding, y - padding)


def _draw_rect(img: Image.Image, layer: dict[str, Any]) -> None:
    x = int(layer["x"])
    y = int(layer["y"])
    width = int(layer["width"])
    height = int(layer["height"])
    radius = int(layer.get("radius") or 0)
    opacity = float(layer.get("opacity", 1))

    _draw_shadow(img, layer, radius)

    rect = _fill_image((width, height), layer.get("fill", "#000000"), opacity)
    if radius:
        rect.putalpha(
            Image.composite(rect.getchannel("A"), Image.new("L", rect.size, 0), _rounded_mask(width, height, radius))
        )

    _composite_clipped(img, rect, x, y)

    border = layer.get("border")
    if border:
        border_width = int(border.get("width", 1))
        border_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(border_layer)
        inset = max(0, border_width // 2)
        box = [inset, inset, max(inset, width - inset - 1), max(inset, height - inset - 1)]
        outline = parse_color(border.get("color", "#000000"), opacity)
        if radius:
            draw.rounded_rectangle(box, radius=max(0, radius - inset), outline=outline, width=border_width)
        else:
            draw.rectangle(box, outline=outline, width=border_width)
        _composite_clipped(img, border_layer, x, y)


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
    block_height = int(layer["height"]) if layer.get("height") else None
    line_height = int(layer.get("line_height") or round(font_size * 1.2))
    align = layer.get("align", "left")
    valign = layer.get("valign", "top")
    fill = parse_color(layer["color"], float(layer.get("opacity", 1)))
    stroke_color = layer.get("stroke_color")
    stroke_fill = parse_color(stroke_color, float(layer.get("opacity", 1))) if stroke_color else None
    stroke_width = int(layer.get("stroke_width") or 0)

    draw = ImageDraw.Draw(img)
    lines = _wrap_text(layer["text"], font, max_width)
    if block_height:
        max_lines = max(1, block_height // line_height)
        lines = lines[:max_lines]
        total_height = len(lines) * line_height
        if valign == "middle":
            current_y = y + max(0, (block_height - total_height) // 2)
        elif valign == "bottom":
            current_y = y + max(0, block_height - total_height)
        else:
            current_y = y
    else:
        current_y = y

    for line in lines:
        if block_height and current_y + line_height > y + block_height:
            break
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
    source = layer.get("src")
    if source is None:
        raise ValueError("Image layer requires src.")

    remote = _load_source_image(source)
    resized = _resize_image(remote, int(layer["width"]), int(layer["height"]), layer.get("fit", "cover"))
    resized = _apply_radius(resized, int(layer.get("radius") or 0))
    resized = _apply_opacity(resized, float(layer.get("opacity", 1)))
    _composite_clipped(img, resized, int(layer["x"]), int(layer["y"]))


def render_canvas_image(image_data: dict[str, Any]):
    width = int(image_data["width"])
    height = int(image_data["height"])
    img = _fill_image((width, height), image_data.get("background", "#ffffff"))

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
