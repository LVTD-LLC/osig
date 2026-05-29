from html import escape
from urllib.parse import quote_plus, urlencode

from django.http import HttpRequest
from django.urls import reverse
from ninja import NinjaAPI

from core.api.auth import superuser_api_auth
from core.api.schemas import (
    BlogPostIn,
    BlogPostOut,
    OnboardingWizardIn,
    OnboardingWizardOut,
    RenderMetricsOut,
    SignOgUrlIn,
    SignOgUrlOut,
    WordPressHelperIn,
    WordPressHelperOut,
)
from core.models import BlogPost
from core.render_observability import build_render_metrics
from core.signing import build_signed_params
from core.wordpress_helper import build_wordpress_render_params, wordpress_helper_snippet

api = NinjaAPI(docs_url=None)


@api.post("/blog-posts/submit", response=BlogPostOut, auth=[superuser_api_auth])
def submit_blog_post(request: HttpRequest, data: BlogPostIn):
    try:
        BlogPost.objects.create(
            title=data.title,
            description=data.description,
            slug=data.slug,
            tags=data.tags,
            content=data.content,
            status=data.status,
            # icon and image are ignored for now (file upload not handled)
        )
        return BlogPostOut(status="success", message="Blog post submitted successfully.")
    except Exception as e:
        return BlogPostOut(status="error", message=f"Failed to submit blog post: {str(e)}")


def _build_onboarding_cache_key(version: str) -> str:
    return version.strip()


def _to_int_if_valid(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_onboarding_params(data: OnboardingWizardIn) -> dict:
    params = {
        "style": data.style,
        "site": data.site,
        "font": data.font,
        "title": data.title,
        "subtitle": data.subtitle,
        "eyebrow": data.eyebrow,
        "format": data.format,
    }

    quality = _to_int_if_valid(data.quality)
    if quality is not None:
        params["quality"] = quality

    max_kb = _to_int_if_valid(data.max_kb)
    if max_kb is not None:
        params["max_kb"] = max_kb

    version = _build_onboarding_cache_key(data.version)
    if version:
        params["v"] = version

    if data.image_url:
        params["image_url"] = data.image_url

    return params


def _build_validation_links(page_url: str) -> dict[str, str]:
    encoded_url = quote_plus(page_url)
    return {
        "Twitter/X Card Validator": f"https://cards-dev.twitter.com/validator?url={encoded_url}",
        "Facebook Sharing Debugger": f"https://developers.facebook.com/tools/debug/?q={encoded_url}",
        "LinkedIn Post Inspector": f"https://www.linkedin.com/post-inspector/inspect/{encoded_url}",
        "Google Rich Results": f"https://search.google.com/test/rich-results?url={encoded_url}",
    }


def _build_meta_tags(signed_url: str, title: str, subtitle: str, page_url: str) -> str:
    escaped_title = escape(title, quote=True)
    escaped_subtitle = escape(subtitle, quote=True)
    escaped_page_url = escape(page_url, quote=True)
    escaped_image = escape(signed_url, quote=True)

    return "\n".join(
        [
            '<meta property="og:type" content="website" />',
            f'<meta property="og:title" content="{escaped_title}" />',
            f'<meta property="og:description" content="{escaped_subtitle}" />',
            f'<meta property="og:url" content="{escaped_page_url}" />',
            f'<meta property="og:image" content="{escaped_image}" />',
            '<meta name="twitter:card" content="summary_large_image" />',
            f'<meta name="twitter:title" content="{escaped_title}" />',
            f'<meta name="twitter:description" content="{escaped_subtitle}" />',
            f'<meta name="twitter:image" content="{escaped_image}" />',
            f'<meta property="og:image:alt" content="{escaped_title}" />',
        ]
    )


@api.post("/sign", response=SignOgUrlOut)
def sign_og_url(request: HttpRequest, data: SignOgUrlIn):
    base_url = request.build_absolute_uri(reverse("generate_image"))

    signed_params, expires_at = build_signed_params(
        params=data.params,
        expires_in_seconds=data.expires_in_seconds,
    )

    signed_url = f"{base_url}?{urlencode(signed_params)}"

    return SignOgUrlOut(
        signed_url=signed_url,
        expires_at=expires_at.isoformat(),
    )


@api.post("/onboarding/meta", response=OnboardingWizardOut)
def build_onboarding_meta_tags(request: HttpRequest, data: OnboardingWizardIn):
    base_url = request.build_absolute_uri(reverse("generate_image"))
    params = _build_onboarding_params(data)

    signed_params, expires_at = build_signed_params(params=params, expires_in_seconds=data.expires_in_seconds)
    signed_url = f"{base_url}?{urlencode(signed_params)}"

    return OnboardingWizardOut(
        signed_url=signed_url,
        expires_at=expires_at.isoformat(),
        meta_tags=_build_meta_tags(
            signed_url=signed_url, title=data.title, subtitle=data.subtitle, page_url=data.page_url
        ),
        validation_links=_build_validation_links(data.page_url),
    )


@api.post("/integrations/wordpress", response=WordPressHelperOut)
def build_wordpress_helper_payload(request: HttpRequest, data: WordPressHelperIn):
    base_url = request.build_absolute_uri(reverse("generate_image"))

    mapping = build_wordpress_render_params(
        page_url=data.page_url,
        post_title=data.post_title,
        post_name=data.post_name,
        seo_title=data.seo_title,
        title=data.title,
        subtitle=data.subtitle,
        excerpt=data.excerpt,
        description=data.description,
        featured_image=data.featured_image,
        featured_image_url=data.featured_image_url,
        logo_url=data.logo_url,
        fallback_image_url=data.fallback_image_url,
        eyebrow=data.eyebrow,
        style=data.style,
        site=data.site,
        font=data.font,
        key=data.key,
        format=data.format,
        quality=data.quality,
        max_kb=data.max_kb,
        version=data.version,
    )

    signed_params, expires_at = build_signed_params(
        params=mapping.params,
        expires_in_seconds=data.expires_in_seconds,
    )

    signed_url = f"{base_url}?{urlencode(signed_params)}"
    snippet = wordpress_helper_snippet(base_url=base_url)

    return WordPressHelperOut(
        signed_url=signed_url,
        expires_at=expires_at.isoformat(),
        mapped_fields=mapping.mapped_fields,
        fallbacks=mapping.fallbacks,
        snippet=snippet,
    )


@api.get("/admin/render-metrics", response=RenderMetricsOut, auth=[superuser_api_auth])
def get_render_metrics(request: HttpRequest, hours: int = 24):
    window_hours = max(1, min(int(hours), 24 * 30))
    metrics = build_render_metrics(window_hours=window_hours)

    return RenderMetricsOut(
        window_hours=metrics.window_hours,
        total_attempts=metrics.total_attempts,
        failed_attempts=metrics.failed_attempts,
        fail_rate_percent=metrics.fail_rate_percent,
        p95_render_ms=metrics.p95_render_ms,
        error_counts=metrics.error_counts,
    )
