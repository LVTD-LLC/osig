import base64
import io
import json

import pytest
from django.contrib.auth.models import User
from PIL import Image
from pydantic import ValidationError

from agent_images.services import ImageSpec, normalize_image_spec, render_image
from core.image_utils import load_font


def _tiny_png_buffer():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _canvas_spec(**overrides):
    spec = {
        "width": 800,
        "height": 450,
        "background": "#f8fafc",
        "layers": [
            {"kind": "rect", "x": 40, "y": 40, "width": 720, "height": 370, "color": "#2563eb", "radius": 28},
            {
                "kind": "text",
                "x": 80,
                "y": 120,
                "width": 620,
                "text": "Canvas renderer",
                "font": "helvetica",
                "font_size": 56,
                "color": "#ffffff",
            },
        ],
    }
    spec.update(overrides)
    return spec


@pytest.mark.django_db
def test_legacy_g_endpoint_is_removed(client):
    response = client.get("/g", data={"style": "base", "title": "Removed"})

    assert response.status_code == 404


@pytest.mark.django_db
def test_studio_render_api_returns_image_payload(client, monkeypatch):
    import agent_images.services as agent_services

    monkeypatch.setattr(agent_services, "render_canvas_image", lambda params: _tiny_png_buffer())

    response = client.post(
        "/api/studio/render",
        data=json.dumps({"spec": _canvas_spec()}),
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

    monkeypatch.setattr(agent_services, "render_canvas_image", lambda params: _tiny_png_buffer())
    user = User.objects.create_user(username="missing-profile", email="missing-profile@example.com", password="pass123")
    user.profile.delete()
    client.force_login(user)

    response = client.post(
        "/api/studio/render",
        data=json.dumps({"spec": _canvas_spec()}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["content_type"] == "image/png"


@pytest.mark.django_db
class TestAgentImageService:
    def test_normalize_image_spec_supports_custom_dimensions_and_layers(self):
        user = User.objects.create_user(username="normalizer", email="normalizer@example.com", password="pass123")

        normalized = normalize_image_spec(
            ImageSpec.model_validate(
                _canvas_spec(
                    key=user.profile.key,
                    width=640,
                    height=360,
                    layers=[{"kind": "text", "x": 24, "y": 40, "text": "Exact pixels", "font_size": 40}],
                )
            )
        )

        assert normalized.spec["width"] == 640
        assert normalized.spec["height"] == 360
        assert normalized.spec["layers"][0]["kind"] == "text"
        assert normalized.spec["key"] == user.profile.key
        assert normalized.safe_render_params["layers"][0]["x"] == 24
        assert "profile_id" not in normalized.safe_render_params

    def test_normalize_image_spec_defaults_to_x_preset_when_dimensions_are_omitted(self):
        normalized = normalize_image_spec(
            ImageSpec.model_validate(
                {"background": "#ffffff", "layers": [{"kind": "text", "x": 10, "y": 20, "text": "Default"}]}
            )
        )

        assert normalized.width == 800
        assert normalized.height == 450
        assert normalized.spec["width"] == 800
        assert normalized.spec["height"] == 450

    def test_normalize_image_spec_supports_google_font_provider(self):
        normalized = normalize_image_spec(
            ImageSpec.model_validate(
                {
                    "layers": [
                        {
                            "kind": "text",
                            "x": 40,
                            "y": 40,
                            "text": "Provider fonts",
                            "font": "google:Playfair Display",
                        }
                    ]
                }
            )
        )

        assert normalized.spec["layers"][0]["font"] == "google:playfair-display"
        assert normalized.safe_render_params["layers"][0]["font"] == "google:playfair-display"
        assert normalized.warnings == [
            "Provider fonts are fetched from the third-party provider on first render and cached locally."
        ]

    def test_image_spec_rejects_unknown_font_provider(self):
        with pytest.raises(ValidationError) as exc:
            ImageSpec.model_validate(
                {
                    "layers": [
                        {"kind": "text", "x": 10, "y": 20, "text": "Unknown provider", "font": "adobe:source-sans-3"}
                    ]
                }
            )

        assert "Unsupported font provider 'adobe'" in str(exc.value)

    def test_image_spec_rejects_unknown_google_font_family(self):
        with pytest.raises(ValidationError) as exc:
            ImageSpec.model_validate(
                {
                    "layers": [
                        {"kind": "text", "x": 10, "y": 20, "text": "Unknown family", "font": "google:noto-color-emoji"}
                    ]
                }
            )

        assert "Unknown Google Font family 'noto-color-emoji'" in str(exc.value)

    def test_image_spec_rejects_malformed_google_font_slug(self):
        with pytest.raises(ValidationError) as exc:
            ImageSpec.model_validate(
                {"layers": [{"kind": "text", "x": 10, "y": 20, "text": "Malformed family", "font": "google:inter-"}]}
            )

        assert "Provider font families may contain only lowercase letters" in str(exc.value)

    def test_image_spec_rejects_invalid_color(self):
        with pytest.raises(ValidationError) as exc:
            ImageSpec.model_validate({"background": "not-a-color", "layers": []})

        assert "Invalid color value" in str(exc.value)

    def test_render_image_supports_png_and_jpeg_content_types(self):
        png_payload = render_image(ImageSpec.model_validate({**_canvas_spec(), "format": "png"}))
        jpeg_payload = render_image(ImageSpec.model_validate({**_canvas_spec(), "format": "jpeg", "quality": 70}))

        assert png_payload["content_type"] == "image/png"
        assert base64.b64decode(png_payload["image_base64"]).startswith(b"\x89PNG")
        assert jpeg_payload["content_type"] == "image/jpeg"
        assert base64.b64decode(jpeg_payload["image_base64"]).startswith(b"\xff\xd8")

    def test_jpeg_quality_output_is_deterministic(self):
        spec = ImageSpec.model_validate({**_canvas_spec(), "format": "jpeg", "quality": 62})

        first = render_image(spec)
        second = render_image(spec)
        lower_quality = render_image(spec.model_copy(update={"quality": 20}))

        assert first["image_base64"] == second["image_base64"]
        assert first["image_base64"] != lower_quality["image_base64"]

    def test_canvas_image_layer_supports_remote_assets(self, monkeypatch):
        import core.image_styles as image_styles

        image_buffer = io.BytesIO()
        Image.new("RGB", (8, 8), color="red").save(image_buffer, format="PNG")

        class FakeResponse:
            content = image_buffer.getvalue()

            def raise_for_status(self):
                return None

        monkeypatch.setattr(image_styles.requests, "get", lambda *args, **kwargs: FakeResponse())

        payload = render_image(
            ImageSpec.model_validate(
                {
                    "width": 300,
                    "height": 220,
                    "layers": [
                        {
                            "kind": "image",
                            "x": 20,
                            "y": 20,
                            "width": 120,
                            "height": 80,
                            "url": "https://example.com/red.png",
                        }
                    ],
                }
            )
        )

        assert payload["content_type"] == "image/png"
        assert payload["byte_size"] > 0


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
