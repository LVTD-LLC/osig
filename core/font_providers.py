from __future__ import annotations

import re
import uuid
from pathlib import Path
from urllib.parse import quote_plus, unquote_plus, urlparse

import requests
from django.conf import settings

from osig.utils import get_osig_logger

logger = get_osig_logger(__name__)

BUNDLED_FONT_CHOICES: tuple[str, ...] = ("helvetica", "markerfelt", "papyrus")
FONT_PROVIDER_CHOICES: tuple[str, ...] = ("google",)
GOOGLE_FONT_CHOICES: tuple[str, ...] = (
    "google:inter",
    "google:roboto",
    "google:open-sans",
    "google:lato",
    "google:montserrat",
    "google:playfair-display",
    "google:source-serif-4",
    "google:dm-sans",
    "google:ibm-plex-sans",
    "google:oswald",
    "google:merriweather",
    "google:space-grotesk",
)
SUPPORTED_GOOGLE_FONT_SLUGS = tuple(choice.split(":", 1)[1] for choice in GOOGLE_FONT_CHOICES)

GOOGLE_FONT_FAMILY_NAMES: dict[str, str] = {
    "dm-sans": "DM Sans",
    "ibm-plex-sans": "IBM Plex Sans",
    "inter": "Inter",
    "lato": "Lato",
    "merriweather": "Merriweather",
    "montserrat": "Montserrat",
    "noto-sans": "Noto Sans",
    "noto-serif": "Noto Serif",
    "open-sans": "Open Sans",
    "oswald": "Oswald",
    "playfair-display": "Playfair Display",
    "pt-serif": "PT Serif",
    "roboto": "Roboto",
    "roboto-slab": "Roboto Slab",
    "source-serif-4": "Source Serif 4",
    "space-grotesk": "Space Grotesk",
}

GOOGLE_FONTS_CSS_URL = "https://fonts.googleapis.com/css2"
GOOGLE_FONTS_STATIC_HOST = "fonts.gstatic.com"
FONT_URL_RE = re.compile(r"url\((?P<quote>['\"]?)(?P<url>https://[^)'\"\s]+)(?P=quote)\)")
FONT_FACE_BLOCK_RE = re.compile(r"@font-face\s*{.*?}", re.DOTALL)
FONT_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,94}[a-z0-9])?$")
LATIN_UNICODE_RANGE_RE = re.compile(r"unicode-range\s*:\s*U\+0000-00FF", re.IGNORECASE)
FONT_FILE_MAX_BYTES = 2_000_000


class FontProviderError(ValueError):
    """Raised when a provider font cannot be resolved safely."""


def normalize_font_name(font: str | None) -> str:
    raw_font = (font or "helvetica").strip()
    if not raw_font:
        return "helvetica"

    bundled_font = raw_font.lower()
    if bundled_font in BUNDLED_FONT_CHOICES:
        return bundled_font

    if ":" not in raw_font:
        raise ValueError("Unsupported font. Use a bundled font or a provider font such as 'google:inter'.")

    provider, family = raw_font.split(":", 1)
    provider = provider.strip().lower()
    if provider not in FONT_PROVIDER_CHOICES:
        raise ValueError(f"Unsupported font provider '{provider}'. Supported providers: google.")

    family_slug = _family_slug(family)
    if not family_slug:
        raise ValueError("Provider fonts must include a family, for example 'google:inter'.")

    if not FONT_SLUG_RE.match(family_slug):
        raise ValueError(
            "Provider font families may contain only lowercase letters, digits, and hyphens "
            "(e.g. 'playfair-display')."
        )

    if provider == "google" and family_slug not in SUPPORTED_GOOGLE_FONT_SLUGS:
        raise ValueError(
            f"Unknown Google Font family '{family_slug}'. "
            "Use a supported family such as 'google:inter' or 'google:playfair-display'."
        )

    return f"{provider}:{family_slug}"


def is_provider_font(font: str | None) -> bool:
    return bool(font) and ":" in font and font.split(":", 1)[0].lower() in FONT_PROVIDER_CHOICES


def provider_font_path(font: str) -> Path:
    normalized_font = normalize_font_name(font)
    provider, family_slug = normalized_font.split(":", 1)
    if provider != "google":
        raise FontProviderError(f"Unsupported font provider '{provider}'.")

    cache_path = _cached_font_path(provider=provider, family_slug=family_slug)
    if cache_path.exists():
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    font_bytes = _download_google_font(family_slug)
    temp_path = cache_path.with_name(f"{cache_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_bytes(font_bytes)
        temp_path.replace(cache_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return cache_path


def _family_slug(family: str) -> str:
    decoded_family = unquote_plus(family).strip()
    decoded_family = decoded_family.replace("_", " ").replace("+", " ").replace("-", " ")
    decoded_family = re.sub(r"\s+", " ", decoded_family)
    return decoded_family.lower().replace(" ", "-")


def _google_family_name(family_slug: str) -> str:
    if family_slug in SUPPORTED_GOOGLE_FONT_SLUGS:
        return GOOGLE_FONT_FAMILY_NAMES[family_slug]

    raise FontProviderError(f"Unsupported Google Font family '{family_slug}'.")


def _font_cache_dir() -> Path:
    configured_cache_dir = getattr(settings, "OSIG_FONT_CACHE_DIR", "")
    if configured_cache_dir:
        return Path(configured_cache_dir)
    return Path(settings.MEDIA_ROOT) / "font-cache"


def _cached_font_path(*, provider: str, family_slug: str) -> Path:
    return _font_cache_dir() / f"{provider}-{family_slug}.ttf"


def _font_fetch_timeout() -> int:
    return int(getattr(settings, "OSIG_FONT_FETCH_TIMEOUT_SECONDS", settings.OSIG_IMAGE_FETCH_TIMEOUT_SECONDS))


def _font_fetch_max_bytes() -> int:
    return int(getattr(settings, "OSIG_FONT_FETCH_MAX_BYTES", FONT_FILE_MAX_BYTES))


def _download_google_font(family_slug: str) -> bytes:
    family_name = _google_family_name(family_slug)
    css_url = f"{GOOGLE_FONTS_CSS_URL}?family={quote_plus(family_name)}:wght@400&display=swap"
    timeout_seconds = _font_fetch_timeout()
    response = requests.get(
        css_url,
        headers={"User-Agent": "OSIG font resolver (https://osig.app)"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    font_url = _extract_font_url(response.text)
    parsed_url = urlparse(font_url)
    if parsed_url.scheme != "https" or parsed_url.netloc != GOOGLE_FONTS_STATIC_HOST:
        raise FontProviderError("Google Fonts CSS returned an unsupported font URL.")

    max_bytes = _font_fetch_max_bytes()
    font_response = requests.get(font_url, timeout=timeout_seconds, stream=True)
    font_response.raise_for_status()
    chunks: list[bytes] = []
    total_bytes = 0
    for chunk in font_response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise FontProviderError("Google Fonts returned a font file larger than the allowed limit.")
        chunks.append(chunk)

    font_bytes = b"".join(chunks)

    if not font_bytes:
        raise FontProviderError("Google Fonts returned an empty font file.")

    logger.info("Cached Google font", family=family_name, bytes=len(font_bytes))
    return font_bytes


def _extract_font_url(css: str) -> str:
    for block in FONT_FACE_BLOCK_RE.findall(css):
        if not LATIN_UNICODE_RANGE_RE.search(block):
            continue
        match = FONT_URL_RE.search(block)
        if match:
            return match.group("url")

    raise FontProviderError("Google Fonts CSS did not contain a Basic Latin font file URL.")
