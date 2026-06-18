from django.conf import settings
from django.contrib import admin

from core.models import BlogPost, Profile, ProfileUsage, RenderAttempt


class ProfileUsageAdmin(admin.ModelAdmin):
    list_display = (
        "profile_key",
        "daily_count",
        "monthly_count",
        "daily_date",
        "monthly_date",
        "daily_limit",
        "monthly_limit",
        "_warned",
        "updated_at",
    )
    ordering = ("-monthly_count",)
    list_filter = ("daily_date", "monthly_date")
    search_fields = ("profile__key", "profile__user__username", "profile__user__email")

    @admin.display(ordering="profile__key", description="Profile key")
    def profile_key(self, obj):
        return obj.profile.key

    @admin.display(description="Daily limit")
    def daily_limit(self, obj):
        return settings.OSIG_DAILY_USAGE_LIMIT

    @admin.display(description="Monthly limit")
    def monthly_limit(self, obj):
        return settings.OSIG_MONTHLY_USAGE_LIMIT

    @admin.display(description="Warned")
    def _warned(self, obj):
        flags = []
        if obj.daily_warning_sent:
            flags.append("D")
        if obj.monthly_warning_sent:
            flags.append("M")
        return "".join(flags) if flags else ""


class RenderAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "profile_key",
        "renderer",
        "success",
        "error_type",
        "duration_ms",
        "attempt_number",
    )
    ordering = ("-created_at",)
    list_filter = ("success", "renderer", "error_type")
    search_fields = ("profile__key", "key", "renderer", "error_type")

    @admin.display(ordering="profile__key", description="Profile key")
    def profile_key(self, obj):
        if obj.profile:
            return obj.profile.key
        return obj.key


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    pass


@admin.register(ProfileUsage)
class ProfileUsageModelAdmin(ProfileUsageAdmin):
    pass


@admin.register(RenderAttempt)
class RenderAttemptModelAdmin(RenderAttemptAdmin):
    pass


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "key")
