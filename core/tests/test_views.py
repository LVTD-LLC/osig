import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.test import RequestFactory, override_settings
from django.urls import reverse

from core.choices import BlogPostStatus
from core.models import BlogPost
from core.templatetags.seo_tags import site_url


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

    def test_trailing_slash_variants_redirect_to_canonical_urls(self, client):
        expected_redirects = {
            "/how-to/": reverse("how_to"),
            "/pricing/": reverse("pricing"),
            "/uses/": reverse("uses"),
        }

        for path, canonical_path in expected_redirects.items():
            response = client.get(path)

            assert response.status_code == 301
            assert response["Location"].endswith(canonical_path)

    def test_public_marketing_pages_render_indexable_metadata(self, client):
        for url_name in ["how_to", "pricing", "uses", "blog_posts"]:
            response = client.get(reverse(url_name), secure=True)

            assert response.status_code == 200
            body = response.content.decode()
            assert '<meta name="robots" content="index, follow" />' in body
            assert '<link rel="canonical" href="https://testserver' in body
            assert '<script type="application/ld+json">' in body

    def test_how_to_page_documents_mcp_not_legacy_g(self, client):
        response = client.get(reverse("how_to"))

        assert response.status_code == 200
        body = response.content.decode()
        assert "MCP docs" in body
        assert "https://osig.app/mcp/" in body
        assert "get_image_contract" in body
        assert "export_image" in body
        assert "https://osig.app/g" not in body

    def test_site_url_uses_request_scheme_for_local_preview(self):
        request = RequestFactory().get("/how-to", HTTP_HOST="localhost:8000")

        assert site_url({"request": request}, "/how-to") == "http://localhost:8000/how-to"

    @override_settings(ALLOWED_HOSTS=["preview.example"], SECURE_SSL_REDIRECT=False)
    def test_site_url_without_request_uses_configured_non_production_origin(self):
        assert site_url({}, "/how-to") == "http://preview.example/how-to"

    @override_settings(ALLOWED_HOSTS=["osig.app"], SECURE_SSL_REDIRECT=True)
    def test_site_url_without_request_uses_https_when_ssl_redirect_is_enabled(self):
        assert site_url({}, "/how-to") == "https://osig.app/how-to"

    def test_sitemap_includes_published_blog_slugs_once(self, client):
        Site.objects.update_or_create(id=settings.SITE_ID, defaults={"domain": "osig.app", "name": "osig.app"})
        BlogPost.objects.create(
            title="Published one",
            description="Published description",
            slug="duplicate-slug",
            tags="og images",
            content="Published content",
            status=BlogPostStatus.PUBLISHED,
        )
        BlogPost.objects.create(
            title="Published duplicate",
            description="Published duplicate description",
            slug="duplicate-slug",
            tags="og images",
            content="Published duplicate content",
            status=BlogPostStatus.PUBLISHED,
        )
        BlogPost.objects.create(
            title="Draft post",
            description="Draft description",
            slug="draft-slug",
            tags="og images",
            content="Draft content",
            status=BlogPostStatus.DRAFT,
        )

        with override_settings(ALLOWED_HOSTS=["osig.app"]):
            response = client.get(reverse("django.contrib.sitemaps.views.sitemap"), HTTP_HOST="osig.app")

        assert response.status_code == 200
        body = response.content.decode()
        assert body.count("https://osig.app/blog/duplicate-slug") == 1
        assert "https://osig.app/blog/draft-slug" not in body
        assert "https://osig.app/uses" in body

    def test_blog_detail_only_serves_published_posts_and_handles_duplicate_slugs(self, client):
        BlogPost.objects.create(
            title="Older duplicate",
            description="Older duplicate description",
            slug="duplicate-slug",
            tags="og images",
            content="Older duplicate content",
            status=BlogPostStatus.PUBLISHED,
        )
        BlogPost.objects.create(
            title="Newer duplicate",
            description="Newer duplicate description",
            slug="duplicate-slug",
            tags="og images",
            content="Newer duplicate content",
            status=BlogPostStatus.PUBLISHED,
        )
        draft = BlogPost.objects.create(
            title="Draft post",
            description="Draft description",
            slug="draft-slug",
            tags="og images",
            content="Draft content",
            status=BlogPostStatus.DRAFT,
        )

        duplicate_response = client.get(reverse("blog_post", kwargs={"slug": "duplicate-slug"}))
        draft_response = client.get(draft.get_absolute_url())

        assert duplicate_response.status_code == 200
        assert draft_response.status_code == 404
