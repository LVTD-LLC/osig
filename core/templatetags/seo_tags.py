from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


def _fallback_host():
    for host in getattr(settings, "ALLOWED_HOSTS", []):
        if host and host != "*":
            return host.lstrip(".")
    return "localhost:8000"


def _origin(context):
    request = context.get("request")
    if request:
        return request.build_absolute_uri("/").rstrip("/")
    scheme = "https" if getattr(settings, "SECURE_SSL_REDIRECT", False) else "http"
    return f"{scheme}://{_fallback_host()}"


@register.simple_tag(takes_context=True)
def site_url(context, path="/"):
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{_origin(context)}{path}"


@register.simple_tag(takes_context=True)
def absolute_static(context, path):
    return site_url(context, static(path))


@register.simple_tag(takes_context=True)
def og_image_url(
    context,
    title,
    subtitle="",
    style="logo",
    font="markerfelt",
    site="x",
    image_url="",
    eyebrow="",
):
    return image_url or absolute_static(context, "vendors/images/logo-square.png")
