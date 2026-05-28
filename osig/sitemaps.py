from django.contrib import sitemaps
from django.urls import reverse

from core.choices import BlogPostStatus
from core.models import BlogPost


class StaticViewSitemap(sitemaps.Sitemap):
    """Generate Sitemap for the site"""

    priority = 0.9
    protocol = "https"

    def items(self):
        """Identify items that will be in the Sitemap

        Returns:
            List: urlNames that will be in the Sitemap
        """
        return [
            "home",
            "blog_posts",
            "pricing",
            "how_to",
            "uses",
        ]

    def location(self, item):
        """Get location for each item in the Sitemap

        Args:
            item (str): Item from the items function

        Returns:
            str: Url for the sitemap item
        """
        return reverse(item)


class BlogPostSitemap(sitemaps.Sitemap):
    """Generate a canonical sitemap entry for each published blog slug."""

    priority = 0.85
    protocol = "https"

    def items(self):
        posts = BlogPost.objects.filter(status=BlogPostStatus.PUBLISHED).order_by("slug", "-updated_at", "-created_at")
        posts_by_slug = {}
        for post in posts:
            posts_by_slug.setdefault(post.slug, post)
        return list(posts_by_slug.values())

    def lastmod(self, item):
        return item.updated_at


sitemaps = {
    "static": StaticViewSitemap,
    "blog": BlogPostSitemap,
}
