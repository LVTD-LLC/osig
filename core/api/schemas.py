from ninja import Schema

from core.choices import BlogPostStatus


class BlogPostIn(Schema):
    title: str
    description: str = ""
    slug: str
    tags: str = ""
    content: str
    icon: str | None = None  # URL or base64 string
    image: str | None = None  # URL or base64 string
    status: BlogPostStatus = BlogPostStatus.DRAFT


class BlogPostOut(Schema):
    status: str
    message: str


class RecentRenderFailureOut(Schema):
    created_at: str
    renderer: str
    error_type: str
    duration_ms: int
    attempt_number: int


class RenderMetricsOut(Schema):
    window_hours: int
    total_attempts: int
    failed_attempts: int
    fail_rate_percent: float
    p95_render_ms: int | None
    error_counts: dict[str, int]
    recent_failures: list[RecentRenderFailureOut]
    troubleshooting_hints: list[str]
