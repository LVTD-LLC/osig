import base64
import io
import json

import pytest
from django.contrib.auth.models import User
from PIL import Image

from agent_images.services import ImageSpec, normalize_image_spec, render_image
from core.image_styles import _safe_truncate, generate_job_clean_image


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
