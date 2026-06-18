import io
import os

import requests
from django.conf import settings
from PIL import Image, ImageFont

from core.font_providers import is_provider_font, normalize_font_name, provider_font_path
from osig.utils import get_osig_logger

logger = get_osig_logger(__name__)


def get_image_dimensions(site):
    if site.lower() == "meta":
        width, height = 1200, 630
    else:  # default to X (Twitter)
        width, height = 1600, 900

    return int(width / 2), int(height / 2)


def add_watermark(img, draw, width, height):
    watermark_text = "made with osig.app"
    watermark_font = ImageFont.load_default().font_variant(size=int(height * 0.05))
    watermark_color = (255, 255, 255, 128)  # White with 50% opacity

    # Get the size of the watermark text
    bbox = watermark_font.getbbox(watermark_text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Calculate position (bottom right corner)
    x = width - text_width - int(width * 0.02)
    y = height - text_height - int(height * 0.08)

    # Draw the watermark
    draw.text((x, y), watermark_text, font=watermark_font, fill=watermark_color)


def draw_wrapped_text(
    draw, text, font, max_width, y_position, text_spacing, text_color, width, align="left", is_title=False, height=None
):
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = font.getbbox(test_line)
        if bbox[2] <= max_width:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    for line in lines:
        bbox = font.getbbox(line)
        left_margin = (width - bbox[2]) // 2 if align == "center" else 0

        if is_title and height:
            bold_offset = int(height * 0.002)
            for offset_x in range(-bold_offset - 1, bold_offset + 1):
                for offset_y in range(-bold_offset, bold_offset + 1):
                    draw.text((left_margin + offset_x, y_position + offset_y), line, font=font, fill=text_color)
        else:
            draw.text((left_margin, y_position), line, font=font, fill=text_color)

        y_position += bbox[3] - bbox[1] + text_spacing

    return y_position


def load_font(font, size):
    provider_font_requested = is_provider_font(font)
    try:
        normalized_font = normalize_font_name(font)
        if is_provider_font(normalized_font):
            font_path = provider_font_path(normalized_font)
        else:
            font_path = os.path.join(settings.BASE_DIR, "fonts", f"{normalized_font}.ttc")
        return ImageFont.truetype(font_path, size)
    except Exception as e:
        logger.error("Error loading font", font=font, error=str(e))
        if provider_font_requested:
            raise
        return ImageFont.load_default().font_variant(size=size)


def _render_jpeg_buffer(img, quality):
    jpeg_buffer = io.BytesIO()
    img.convert("RGB").save(
        jpeg_buffer,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=False,
    )
    jpeg_buffer.seek(0)
    return jpeg_buffer


def create_image_buffer(img, output_format="png", quality=None, max_kb=None):
    output_format = (output_format or "png").lower()

    if output_format == "jpeg":
        jpeg_quality = 85 if quality is None else max(1, min(int(quality), 100))
        buffer = _render_jpeg_buffer(img, jpeg_quality)

        if max_kb:
            target_size = int(max_kb) * 1024
            while len(buffer.getvalue()) > target_size and jpeg_quality > 20:
                jpeg_quality = max(20, jpeg_quality - 5)
                buffer = _render_jpeg_buffer(img, jpeg_quality)

        return buffer

    buffer = io.BytesIO()
    img = img.convert("RGB")

    if quality is None:
        img.save(buffer, format="PNG")
    else:
        png_quality = max(1, min(int(quality), 100))
        compress_level = round((100 - png_quality) * 9 / 100)
        img.save(buffer, format="PNG", optimize=True, compress_level=compress_level)

    buffer.seek(0)
    return buffer


def load_and_resize_image(image_url, width, height):
    timeout_seconds = getattr(settings, "OSIG_IMAGE_FETCH_TIMEOUT_SECONDS", 8)
    response = requests.get(image_url, timeout=timeout_seconds)
    response.raise_for_status()
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    return img.resize((width, height), Image.LANCZOS)
