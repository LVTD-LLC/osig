from urllib.parse import urlencode

from django import template
from django.templatetags.static import static

register = template.Library()


def _origin(context):
    request = context.get("request")
    host = request.get_host() if request else "osig.app"
    return f"https://{host}"


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
    params = {
        "site": site,
        "style": style,
        "font": font,
        "title": title,
    }
    if subtitle:
        params["subtitle"] = subtitle
    if eyebrow:
        params["eyebrow"] = eyebrow
    if image_url:
        params["image_url"] = image_url

    return f"{_origin(context)}/g?{urlencode(params)}"
