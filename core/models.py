from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.base_models import BaseModel
from core.choices import BlogPostStatus
from core.model_utils import generate_random_key
from osig.utils import get_osig_logger


def _first_of_month(d):
    return d.replace(day=1)


def _today():
    return timezone.now().date()


def _month_start():
    return _first_of_month(_today())


logger = get_osig_logger(__name__)


class Profile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=10, unique=True, default=generate_random_key)

    subscription = models.ForeignKey(
        "djstripe.Subscription",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
        help_text="The user's Stripe Subscription object, if it exists",
    )
    customer = models.ForeignKey(
        "djstripe.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
        help_text="The user's Stripe Customer object, if it exists",
    )

    def track_state_change(self, to_state, metadata=None):
        from_state = self.current_state

        if from_state != to_state:
            logger.info(
                "Tracking State Change", from_state=from_state, to_state=to_state, profile_id=self.id, metadata=metadata
            )
            ProfileStateTransition.objects.create(
                profile=self, from_state=from_state, to_state=to_state, backup_profile_id=self.id, metadata=metadata
            )

    @property
    def current_state(self):
        if not self.state_transitions.all().exists():
            return ProfileStates.STRANGER
        latest_transition = self.state_transitions.latest("created_at")
        return latest_transition.to_state


class ProfileUsage(BaseModel):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="usage")
    daily_count = models.PositiveIntegerField(default=0)
    monthly_count = models.PositiveIntegerField(default=0)
    daily_date = models.DateField(default=_today)
    monthly_date = models.DateField(default=_month_start)
    daily_warning_sent = models.BooleanField(default=False)
    monthly_warning_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"Usage for {self.profile.key}"


class ProfileStates(models.TextChoices):
    STRANGER = "stranger"
    SIGNED_UP = "signed_up"
    SUBSCRIBED = "subscribed"
    CANCELLED = "cancelled"
    CHURNED = "churned"
    ACCOUNT_DELETED = "account_deleted"


class ProfileStateTransition(BaseModel):
    profile = models.ForeignKey(Profile, null=True, on_delete=models.SET_NULL, related_name="state_transitions")
    from_state = models.CharField(max_length=255, choices=ProfileStates.choices)
    to_state = models.CharField(max_length=255, choices=ProfileStates.choices)
    backup_profile_id = models.IntegerField()
    metadata = models.JSONField(null=True, blank=True)


class Sites(models.TextChoices):
    X = "x"
    META = "meta"


class RenderAttempt(BaseModel):
    profile = models.ForeignKey(
        Profile, null=True, blank=True, on_delete=models.SET_NULL, related_name="render_attempts"
    )
    key = models.CharField(max_length=12, blank=True)
    renderer = models.CharField(max_length=64, blank=True)
    success = models.BooleanField(default=False)
    error_type = models.CharField(max_length=64, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    attempt_number = models.PositiveSmallIntegerField(default=1)


class BlogPost(BaseModel):
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=250)
    tags = models.TextField()
    content = models.TextField()
    icon = models.ImageField(upload_to="blog_post_icons/", blank=True)
    image = models.ImageField(upload_to="blog_post_images/", blank=True)

    status = models.CharField(
        max_length=20,
        choices=BlogPostStatus.choices,
        default=BlogPostStatus.DRAFT,
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog_post", kwargs={"slug": self.slug})
