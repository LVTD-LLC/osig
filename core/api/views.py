from django.http import HttpRequest
from ninja import NinjaAPI

from core.api.auth import superuser_api_auth
from core.api.schemas import BlogPostIn, BlogPostOut, RenderMetricsOut
from core.models import BlogPost
from core.render_observability import build_render_metrics

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
        recent_failures=metrics.recent_failures,
        troubleshooting_hints=metrics.troubleshooting_hints,
    )
