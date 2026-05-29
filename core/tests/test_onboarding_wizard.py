import json
from urllib.parse import parse_qs, urlparse

import pytest


@pytest.mark.django_db
class TestOnboardingWizardAPI:
    def test_onboarding_api_generates_signed_og_meta_and_checks(self, client):
        payload = {
            "page_url": "https://example.com/jobs/senior-engineer",
            "style": "job_logo",
            "site": "x",
            "font": "helvetica",
            "title": "Senior Engineering Lead",
            "subtitle": "Build and ship resilient systems",
            "eyebrow": "Remote",
            "image_url": "https://example.com/logo.png",
            "format": "jpeg",
            "quality": 80,
            "version": "v2026",
            "expires_in_seconds": 600,
        }

        response = client.post(
            "/api/onboarding/meta",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()

        assert data["signed_url"].startswith("http")
        parsed = parse_qs(urlparse(data["signed_url"]).query)

        assert parsed["style"] == ["job_logo"]
        assert parsed["site"] == ["x"]
        assert parsed["format"] == ["jpeg"]
        assert parsed["quality"] == ["80"]
        assert parsed["v"] == ["v2026"]
        assert "sig" in parsed
        assert "exp" in parsed

        assert '<meta property="og:title"' in data["meta_tags"]
        assert "twitter:image" in data["meta_tags"]
        assert data["validation_links"]["Facebook Sharing Debugger"].startswith(
            "https://developers.facebook.com/tools/debug/"
        )
