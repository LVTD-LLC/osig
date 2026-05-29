import json
from urllib.parse import parse_qs, urlparse

import pytest


def _endpoint_payload():
    return {
        "page_url": "https://example.com/jobs/senior-engineer",
        "post_title": "Senior PHP Engineer",
        "post_name": "senior-php-engineer",
        "subtitle": "Build backend services",
        "excerpt": "",
        "description": "",
        "featured_image_url": "https://example.com/logo.png",
        "logo_url": "",
        "fallback_image_url": "https://example.com/fallback.png",
        "style": "job_logo",
        "site": "x",
        "font": "helvetica",
        "format": "jpeg",
        "quality": 88,
        "version": "v2026-02-26",
        "eyebrow": "Remote · Full-time",
        "key": "abc",
    }


@pytest.mark.django_db
class TestWordPressHelper:
    def test_wordpress_helper_maps_post_fields_and_signs_url(self, client):
        response = client.post(
            "/api/integrations/wordpress",
            data=json.dumps(_endpoint_payload()),
            content_type="application/json",
        )

        assert response.status_code == 200
        payload = response.json()

        assert payload["mapped_fields"]["title"] == "Senior PHP Engineer"
        assert payload["mapped_fields"]["subtitle"] == "Build backend services"
        assert payload["mapped_fields"]["image_url"] == "https://example.com/logo.png"
        assert payload["mapped_fields"]["style"] == "job_logo"

        parsed = parse_qs(urlparse(payload["signed_url"]).query)
        assert parsed["title"] == ["Senior PHP Engineer"]
        assert parsed["subtitle"] == ["Build backend services"]
        assert parsed["style"] == ["job_logo"]
        assert parsed["format"] == ["jpeg"]
        assert parsed["quality"] == ["88"]
        assert parsed["v"] == ["v2026-02-26"]
        assert "sig" in parsed
        assert "exp" in parsed

        assert payload["snippet"].startswith("<?php")

    def test_wordpress_helper_fallback_to_logo_when_no_featured_image(self, client):
        payload = _endpoint_payload()
        payload["featured_image_url"] = ""
        payload["logo_url"] = "https://example.com/company-logo.png"

        response = client.post(
            "/api/integrations/wordpress",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()

        assert data["mapped_fields"]["image_url"] == "https://example.com/company-logo.png"
        assert "image_fallback" not in data["fallbacks"]

    def test_wordpress_helper_uses_fallback_image_when_no_logo_or_featured(self, client):
        payload = _endpoint_payload()
        payload["featured_image_url"] = ""
        payload["logo_url"] = ""

        response = client.post(
            "/api/integrations/wordpress",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()

        assert data["mapped_fields"]["image_url"] == payload["fallback_image_url"]
        assert data["fallbacks"] == ["image_fallback"]

    def test_wordpress_helper_uses_slug_title_when_title_missing(self, client):
        payload = {
            "page_url": "https://example.com/jobs/senior-data-scientist",
            "post_name": "senior-data-scientist",
            "description": "Build ML systems",
            "fallback_image_url": "https://example.com/fallback.png",
            "style": "job_clean",
        }

        response = client.post(
            "/api/integrations/wordpress",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mapped_fields"]["title"] == "Senior Data Scientist"
        assert data["mapped_fields"]["subtitle"] == "Build ML systems"
        assert data["mapped_fields"]["image_url"] == payload["fallback_image_url"]
