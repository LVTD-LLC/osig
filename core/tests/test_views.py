import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.sites.models import Site
from django.test import RequestFactory, override_settings
from django.urls import reverse

from core.templatetags.seo_tags import site_url
from core.views import MCP_AGENT_PROMPT


@pytest.mark.django_db
class TestHomeView:
    def test_home_view_status_code(self, client):
        url = reverse("home")
        response = client.get(url)
        assert response.status_code == 200

    def test_home_view_uses_correct_template(self, client):
        url = reverse("home")
        response = client.get(url)
        assert "pages/home.html" in [t.name for t in response.templates]

    def test_home_view_is_reduced_to_project_info_and_copy_prompt(self, client):
        response = client.get(reverse("home"))

        body = response.content.decode()
        assert "Repo-ready OG images." in body
        assert "OSIG is the Open Source Social Image Generator." in body
        assert "Discover the canvas contract. Render previews. Export PNG or JPEG assets into a repository." in body
        assert "A renderer shaped for agent work." in body
        assert "Open source renderer, paid hosted path." in body
        assert "https://osig.app/mcp/" in body
        assert "Start with MCP" in body
        assert "Copy MCP prompt" in body
        assert "Copy the setup prompt." in body
        assert "Paste it into your coding agent" in body
        assert 'id="agent-prompt-copy-description"' in body
        assert 'aria-describedby="agent-prompt-copy-description"' in body
        assert 'class="sr-only"' in body
        assert "MCP docs" not in body
        assert "Pricing" not in body
        assert "Back to guides" not in body
        assert 'data-controller="image-generator"' not in body
        assert 'data-controller="agent-studio"' not in body
        assert "#generator" not in body
        assert "#studio" not in body

    def test_mcp_agent_prompt_is_concise_setup_instruction(self):
        assert "https://osig.app/mcp/" in MCP_AGENT_PROMPT
        assert "deterministic Open Graph" in MCP_AGENT_PROMPT
        assert "typed canvas" in MCP_AGENT_PROMPT
        assert "get_image_contract" not in MCP_AGENT_PROMPT
        assert "normalize_image_spec" not in MCP_AGENT_PROMPT
        assert "render_image_preview" not in MCP_AGENT_PROMPT
        assert "export_image" not in MCP_AGENT_PROMPT


@pytest.mark.django_db
class TestSeoSurface:
    def test_robots_txt_points_to_sitemap_and_blocks_utility_paths(self, client):
        with override_settings(ALLOWED_HOSTS=["osig.app"]):
            response = client.get(reverse("robots_txt"), HTTP_HOST="osig.app")

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")

        body = response.content.decode()
        assert "Sitemap: https://osig.app/sitemap.xml" in body
        assert "Disallow: /accounts/" in body
        assert "Disallow: /api/" in body
        assert "Disallow: /create-checkout-session/" in body

    def test_auth_entry_pages_are_noindexed(self, client):
        for url_name in ["account_login", "account_signup"]:
            response = client.get(reverse(url_name))

            assert response.status_code == 200
            body = response.content.decode()
            assert '<meta name="robots" content="noindex, follow" />' in body
            assert '<script type="application/ld+json">' not in body
            assert "Back to OSIG" in body
            assert reverse("home") in body

    def test_logout_page_is_noindexed_for_authenticated_users(self, client, django_user_model):
        user = django_user_model.objects.create_user(
            username="test-user",
            email="test@example.com",
            password="password",
        )
        client.force_login(user)

        response = client.get(reverse("account_logout"))

        assert response.status_code == 200
        body = response.content.decode()
        assert '<meta name="robots" content="noindex, follow" />' in body
        assert '<script type="application/ld+json">' not in body

    def test_settings_page_keeps_account_actions_without_removed_page_links(self, client, django_user_model):
        user = django_user_model.objects.create_user(
            username="settings-user",
            email="settings@example.com",
            password="password",
        )
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        client.force_login(user)

        response = client.get(reverse("settings"))

        assert response.status_code == 200
        body = response.content.decode()
        assert "Back to OSIG" in body
        assert "Sign out" in body
        assert reverse("account_logout") in body
        assert "Compare plans" not in body
        assert reverse("pricing") not in body

    def test_removed_public_pages_redirect_home(self, client):
        removed_paths = [
            "/how-to",
            "/how-to/",
            "/pricing",
            "/pricing/",
            "/uses",
            "/uses/",
            "/blog/",
            "/blog/example-post",
            "/blog/example-post/",
        ]

        for path in removed_paths:
            response = client.get(path)

            assert response.status_code == 301
            assert response["Location"] == reverse("home")

    def test_site_url_uses_request_scheme_for_local_preview(self):
        request = RequestFactory().get("/how-to", HTTP_HOST="localhost:8000")

        assert site_url({"request": request}, "/how-to") == "http://localhost:8000/how-to"

    @override_settings(ALLOWED_HOSTS=["preview.example"], SECURE_SSL_REDIRECT=False)
    def test_site_url_without_request_uses_configured_non_production_origin(self):
        assert site_url({}, "/how-to") == "http://preview.example/how-to"

    @override_settings(ALLOWED_HOSTS=["osig.app"], SECURE_SSL_REDIRECT=True)
    def test_site_url_without_request_uses_https_when_ssl_redirect_is_enabled(self):
        assert site_url({}, "/how-to") == "https://osig.app/how-to"

    def test_sitemap_includes_landing_page_only(self, client):
        Site.objects.update_or_create(id=settings.SITE_ID, defaults={"domain": "osig.app", "name": "osig.app"})

        with override_settings(ALLOWED_HOSTS=["osig.app"]):
            response = client.get(reverse("django.contrib.sitemaps.views.sitemap"), HTTP_HOST="osig.app")

        assert response.status_code == 200
        body = response.content.decode()
        assert "https://osig.app/" in body
        assert "https://osig.app/blog/" not in body
        assert "https://osig.app/how-to" not in body
        assert "https://osig.app/pricing" not in body
        assert "https://osig.app/uses" not in body
