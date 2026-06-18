import base64
import io
import json

import pytest
from django.contrib.auth.models import User
from PIL import Image
from pydantic import ValidationError

from agent_images.services import ImageSpec, normalize_image_spec, render_image
from core.image_styles import _safe_truncate, generate_job_clean_image
from core.image_utils import load_font


def _tiny_png_buffer():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


@pytest.mark.django_db
def test_legacy_g_endpoint_is_removed(client):
    response = client.get("/g", data={"style": "base", "title": "Removed"})

    assert response.status_code == 404


@pytest.mark.django_db
def test_studio_render_api_returns_image_payload(client, monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "generate_image_router", lambda params: _tiny_png_buffer())

    response = client.post(
        "/api/studio/render",
        data=json.dumps(
            {
                "spec": {
                    "style": "base",
                    "site": "x",
                    "title": "Studio render",
                }
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    decoded = base64.b64decode(payload["image_base64"])

    assert payload["content_type"] == "image/png"
    assert payload["data_uri"].startswith("data:image/png;base64,")
    assert decoded.startswith(b"\x89PNG")


@pytest.mark.django_db
def test_studio_render_api_rejects_invalid_specs(client):
    response = client.post(
        "/api/studio/render",
        data=json.dumps({"spec": {"style": "unknown", "title": "Invalid"}}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_spec"


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [None, [], 42, "string"])
def test_studio_render_api_rejects_non_object_json(client, payload):
    response = client.post(
        "/api/studio/render",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"


@pytest.mark.django_db
def test_studio_render_api_handles_authenticated_user_without_profile(client, monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "generate_image_router", lambda params: _tiny_png_buffer())
    user = User.objects.create_user(username="missing-profile", email="missing-profile@example.com", password="pass123")
    user.profile.delete()
    client.force_login(user)

    response = client.post(
        "/api/studio/render",
        data=json.dumps({"spec": {"style": "base", "site": "x", "title": "Missing profile"}}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["content_type"] == "image/png"


@pytest.mark.django_db
class TestAgentImageService:
    def test_normalize_image_spec_maps_logo_alias(self):
        user = User.objects.create_user(username="normalizer", email="normalizer@example.com", password="pass123")

        normalized = normalize_image_spec(
            ImageSpec(
                key=user.profile.key,
                style="job_logo",
                title="Senior Django Engineer",
                image_or_logo="https://example.com/logo.png",
            )
        )

        assert normalized.spec["image_url"] == "https://example.com/logo.png"
        assert normalized.spec["key"] == user.profile.key
        assert normalized.safe_render_params["image_url"] == "https://example.com/logo.png"
        assert "profile_id" not in normalized.safe_render_params

    def test_normalize_image_spec_supports_google_font_provider(self):
        normalized = normalize_image_spec(
            ImageSpec(
                style="base",
                font="google:Playfair Display",
                title="Provider fonts",
            )
        )

        assert normalized.spec["font"] == "google:playfair-display"
        assert normalized.safe_render_params["font"] == "google:playfair-display"
        assert normalized.warnings == [
            "Provider fonts are fetched from the third-party provider on first render and cached locally."
        ]

    def test_image_spec_rejects_unknown_font_provider(self):
        with pytest.raises(ValidationError) as exc:
            ImageSpec(style="base", font="adobe:source-sans-3", title="Unknown provider")

        assert "Unsupported font provider 'adobe'" in str(exc.value)

    def test_image_spec_rejects_unknown_google_font_family(self):
        with pytest.raises(ValidationError) as exc:
            ImageSpec(style="base", font="google:noto-color-emoji", title="Unknown family")

        assert "Unknown Google Font family 'noto-color-emoji'" in str(exc.value)

    def test_image_spec_rejects_malformed_google_font_slug(self):
        with pytest.raises(ValidationError) as exc:
            ImageSpec(style="base", font="google:inter-", title="Malformed family")

        assert "Provider font families may contain only lowercase letters" in str(exc.value)

    def test_render_image_supports_png_and_jpeg_content_types(self):
        png_payload = render_image(
            ImageSpec(style="base", site="x", title="Format Test", subtitle="Content types", format="png")
        )
        jpeg_payload = render_image(
            ImageSpec(style="base", site="x", title="Format Test", subtitle="Content types", format="jpeg", quality=70)
        )

        assert png_payload["content_type"] == "image/png"
        assert base64.b64decode(png_payload["image_base64"]).startswith(b"\x89PNG")
        assert jpeg_payload["content_type"] == "image/jpeg"
        assert base64.b64decode(jpeg_payload["image_base64"]).startswith(b"\xff\xd8")

    def test_jpeg_quality_output_is_deterministic(self):
        spec = ImageSpec(
            style="base",
            site="x",
            title="Deterministic",
            subtitle="JPEG quality",
            format="jpeg",
            quality=62,
        )

        first = render_image(spec)
        second = render_image(spec)
        lower_quality = render_image(spec.model_copy(update={"quality": 20}))

        assert first["image_base64"] == second["image_base64"]
        assert first["image_base64"] != lower_quality["image_base64"]

    @pytest.mark.parametrize("style", ["job_classic", "job_logo", "job_clean"])
    def test_render_image_supports_job_board_styles(self, style):
        payload = render_image(
            ImageSpec(
                style=style,
                site="x",
                title="Senior Django Engineer",
                subtitle="Ship production systems for real users",
                eyebrow="Remote",
            )
        )

        assert payload["content_type"] == "image/png"
        assert payload["byte_size"] > 0


def test_safe_truncation_limits_copy_length():
    long_text = "A" * 500
    truncated = _safe_truncate(long_text, 64)

    assert len(truncated) <= 64
    assert truncated.endswith("...")


def test_job_clean_template_handles_long_copy_without_errors():
    image = generate_job_clean_image(
        profile_id=None,
        site="x",
        font="helvetica",
        title="Senior Python Engineer " * 30,
        subtitle="Build reliable systems and own customer outcomes. " * 40,
        eyebrow="Hiring now " * 20,
        image_url=None,
    )

    assert image.getbuffer().nbytes > 0


def test_google_font_provider_loader_downloads_and_caches_font(settings, tmp_path, monkeypatch):
    import core.font_providers as font_providers

    settings.OSIG_FONT_CACHE_DIR = str(tmp_path)
    font_bytes = (settings.BASE_DIR / "fonts" / "markerfelt.ttc").read_bytes()
    requested_urls = []

    class FakeResponse:
        def __init__(self, *, text="", content=b""):
            self.text = text
            self.content = content

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=65536):
            for index in range(0, len(self.content), chunk_size):
                yield self.content[index : index + chunk_size]

    def fake_get(url, *args, **kwargs):
        requested_urls.append(url)
        if url.startswith("https://fonts.googleapis.com/"):
            return FakeResponse(
                text=(
                    "@font-face {"
                    "font-family: 'Inter';"
                    "src: url(https://fonts.gstatic.com/s/inter/v1/inter.ttf) format('truetype');"
                    "unicode-range: U+0000-00FF;"
                    "}"
                )
            )
        if url.startswith("https://fonts.gstatic.com/"):
            return FakeResponse(content=font_bytes)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(font_providers.requests, "get", fake_get)

    first = load_font("google:Inter", 24)
    second = load_font("google:inter", 28)

    assert first.getbbox("OSIG")
    assert second.getbbox("OSIG")
    assert (tmp_path / "google-inter.ttf").exists()
    assert requested_urls == [
        "https://fonts.googleapis.com/css2?family=Inter:wght@400&display=swap",
        "https://fonts.gstatic.com/s/inter/v1/inter.ttf",
    ]


def test_google_font_provider_requires_basic_latin_font_url():
    from core.font_providers import FontProviderError, _extract_font_url

    css = (
        "@font-face {"
        "font-family: 'Inter';"
        "src: url(https://fonts.gstatic.com/s/inter/v1/inter-cyrillic.ttf) format('truetype');"
        "unicode-range: U+0400-04FF;"
        "}"
    )

    with pytest.raises(FontProviderError) as exc:
        _extract_font_url(css)

    assert "Basic Latin" in str(exc.value)


def test_provider_font_load_errors_are_not_silently_swallowed(monkeypatch):
    import core.image_utils as image_utils
    from core.font_providers import FontProviderError

    def unavailable_provider_font_path(font):
        raise FontProviderError("Google Fonts unavailable")

    monkeypatch.setattr(image_utils, "provider_font_path", unavailable_provider_font_path)

    with pytest.raises(FontProviderError) as exc:
        image_utils.load_font("google:inter", 24)

    assert "Google Fonts unavailable" in str(exc.value)
