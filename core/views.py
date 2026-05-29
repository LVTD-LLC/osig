import io
from datetime import timedelta
from time import perf_counter
from urllib.parse import urlencode

import stripe
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView, TemplateView, UpdateView
from django_q.tasks import async_task
from djstripe import models as djstripe_models, settings as djstripe_settings
from PIL import Image

from core.forms import ProfileUpdateForm
from core.image_styles import generate_image_router
from core.models import BlogPost, Image as ImageModel, Profile
from core.render_observability import classify_render_error, is_transient_error, record_render_attempt
from core.signing import ExpiredSignatureError, InvalidSignatureError, verify_signed_params
from core.tasks import regenerate_and_update_image, save_generated_image
from core.usage import track_profile_usage
from core.utils import check_if_profile_has_pro_subscription
from osig.utils import get_osig_logger

logger = get_osig_logger(__name__)

stripe.api_key = djstripe_settings.djstripe_settings.STRIPE_SECRET_KEY


class HomeView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_choices"] = [("x", "X (Twitter)"), ("meta", "meta")]
        context["style_choices"] = [
            ("base", "Base"),
            ("logo", "Logo"),
            ("job_classic", "Job Classic"),
            ("job_logo", "Job Logo"),
            ("job_clean", "Job Clean"),
        ]
        context["font_choices"] = [("helvetica", "Helvetica"), ("markerfelt", "Marker Felt"), ("papyrus", "Papyrus")]

        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                context["user_key"] = profile.key
            except Profile.DoesNotExist:
                context["user_key"] = None
        else:
            context["user_key"] = None

        payment_status = self.request.GET.get("payment")
        if payment_status == "success":
            messages.success(self.request, "Thanks for subscribing, I hope you enjoy the app!")
            context["show_confetti"] = True
        elif payment_status == "failed":
            messages.error(self.request, "Something went wrong with the payment.")

        return context


class PricingView(TemplateView):
    template_name = "pages/pricing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                context["has_pro_subscription"] = check_if_profile_has_pro_subscription(profile.id)
            except Profile.DoesNotExist:
                context["has_pro_subscription"] = False
        else:
            context["has_pro_subscription"] = False

        return context


class HowToView(TemplateView):
    template_name = "pages/how-to.html"


class OnboardingWizardView(TemplateView):
    template_name = "pages/onboarding-wizard.html"


class BlogView(ListView):
    model = BlogPost
    template_name = "blog/blog_posts.html"
    context_object_name = "blog_posts"
    ordering = ["-created_at"]

    def get_queryset(self):
        from core.choices import BlogPostStatus

        return BlogPost.objects.filter(status=BlogPostStatus.PUBLISHED).order_by("-created_at")


class BlogPostView(DetailView):
    model = BlogPost
    template_name = "blog/blog_post.html"
    context_object_name = "blog_post"

    def get_queryset(self):
        from core.choices import BlogPostStatus

        return BlogPost.objects.filter(status=BlogPostStatus.PUBLISHED)

    def get_object(self, queryset=None):
        queryset = queryset or self.get_queryset()
        blog_post = queryset.filter(slug=self.kwargs["slug"]).order_by("-updated_at", "-created_at").first()
        if blog_post is None:
            raise Http404("No published blog post found matching the query")
        return blog_post


class UserSettingsView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    login_url = "account_login"
    model = Profile
    form_class = ProfileUpdateForm
    success_message = "User Profile Updated"
    success_url = reverse_lazy("settings")
    template_name = "pages/user-settings.html"

    def get_object(self):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        email_address = EmailAddress.objects.get_for_user(user, user.email)

        context["email_verified"] = email_address.verified
        context["resend_confirmation_url"] = reverse("resend_confirmation")
        context["has_pro_subscription"] = user.profile.subscription is not None

        return context


@login_required
def create_checkout_session(request, pk, plan):
    user = request.user

    product = djstripe_models.Product.objects.get(name=plan)
    price = product.prices.filter(active=True).first()
    customer, _ = djstripe_models.Customer.get_or_create(subscriber=user)

    profile = user.profile
    profile.customer = customer
    profile.save(update_fields=["customer"])

    base_success_url = request.build_absolute_uri(reverse("home"))
    base_cancel_url = request.build_absolute_uri(reverse("home"))

    success_params = {"payment": "success"}
    success_url = f"{base_success_url}?{urlencode(success_params)}"

    cancel_params = {"payment": "failed"}
    cancel_url = f"{base_cancel_url}?{urlencode(cancel_params)}"

    checkout_session = stripe.checkout.Session.create(
        customer=customer.id,
        payment_method_types=["card"],
        allow_promotion_codes=True,
        automatic_tax={"enabled": True},
        line_items=[
            {
                "price": price.id,
                "quantity": 1,
            }
        ],
        mode="subscription" if plan != "one-time" else "payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_update={
            "address": "auto",
        },
        metadata={"user_id": user.id, "pk": pk, "price_id": price.id},
    )

    return redirect(checkout_session.url, code=303)


@login_required
def create_customer_portal_session(request):
    user = request.user
    customer = djstripe_models.Customer.objects.get(subscriber=user)

    session = stripe.billing_portal.Session.create(
        customer=customer.id,
        return_url=request.build_absolute_uri(reverse("home")),
    )

    return redirect(session.url, code=303)


@login_required
def resend_confirmation_email(request):
    user = request.user
    send_email_confirmation(request, user, EmailAddress.objects.get_for_user(user, user.email))

    return redirect("settings")


def blank_square_image(request):
    size = (200, 200)
    image = Image.new("RGB", size, color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_data = buffer.getvalue()
    response = HttpResponse(image_data, content_type="image/png")
    response["Content-Disposition"] = 'inline; filename="blank_square.png"'

    return response


def _normalize_output_format(raw_value: str | None) -> str:
    value = (raw_value or "png").lower().strip()
    return value if value in {"png", "jpeg"} else "png"


def _normalize_quality(raw_value: str | None, output_format: str) -> int | None:
    if raw_value in (None, ""):
        return 85 if output_format == "jpeg" else None

    try:
        parsed = int(raw_value)
    except ValueError:
        return 85 if output_format == "jpeg" else None

    return max(1, min(parsed, 100))


def _normalize_max_kb(raw_value: str | None) -> int | None:
    if raw_value in (None, ""):
        return None

    try:
        parsed = int(raw_value)
    except ValueError:
        return None

    return parsed if parsed > 0 else None


def _content_type_for_output_format(output_format: str) -> str:
    return "image/jpeg" if output_format == "jpeg" else "image/png"


def _attach_usage_headers(response, usage_state) -> HttpResponse:
    if usage_state is None:
        return response

    if usage_state.daily_limit:
        response["X-OSIG-Daily-Usage"] = f"{usage_state.daily_count}/{usage_state.daily_limit}"
    if usage_state.monthly_limit:
        response["X-OSIG-Monthly-Usage"] = f"{usage_state.monthly_count}/{usage_state.monthly_limit}"

    if usage_state.warnings:
        response["X-OSIG-Quota-Warning"] = ",".join(usage_state.warnings)

    return response


def _build_image_response(image_content, output_format: str, signed_expires_at=None, usage_state=None) -> HttpResponse:
    response = HttpResponse(image_content, content_type=_content_type_for_output_format(output_format))

    if signed_expires_at is not None:
        max_age = max(0, int((signed_expires_at - timezone.now()).total_seconds()))
        response["Cache-Control"] = f"public, max-age={max_age}"
    else:
        response["Cache-Control"] = "public, max-age=31536000, immutable"

    return _attach_usage_headers(response, usage_state)


@require_GET
def generate_image(request):
    try:
        signed_expires_at = verify_signed_params(request.GET)
    except (InvalidSignatureError, ExpiredSignatureError):
        return HttpResponseForbidden("Invalid or expired signature")

    output_format = _normalize_output_format(request.GET.get("format"))
    quality = _normalize_quality(request.GET.get("quality"), output_format)
    max_kb = _normalize_max_kb(request.GET.get("max_kb"))

    image_url = request.GET.get("image_url") or request.GET.get("image_or_logo")

    params = {
        "key": request.GET.get("key", ""),
        "style": request.GET.get("style", "base"),
        "site": request.GET.get("site", "x"),
        "font": request.GET.get("font"),
        "title": request.GET.get("title"),
        "subtitle": request.GET.get("subtitle"),
        "eyebrow": request.GET.get("eyebrow"),
        "image_url": image_url,
    }

    if output_format != "png":
        params["format"] = output_format
    if quality is not None:
        params["quality"] = quality
    if max_kb is not None:
        params["max_kb"] = max_kb

    cache_version = request.GET.get("v")
    if cache_version:
        params["v"] = cache_version

    usage_state = None
    profile = None
    if params["key"]:
        try:
            profile = Profile.objects.get(key=params["key"])
            params["profile_id"] = profile.id
            usage_state = track_profile_usage(profile)

            if usage_state.blocked:
                return HttpResponse(
                    f"Usage quota exceeded: {'/'.join(usage_state.blocked_reasons)}",
                    status=429,
                )
        except Profile.DoesNotExist:
            logger.error("Profile not found for key", key=params["key"])

    existing_image = ImageModel.objects.filter(image_data=params).first()
    if existing_image and existing_image.generated_image:
        two_days_ago = timezone.now() - timedelta(days=2)
        should_update = (
            settings.ENVIRONMENT == "prod" and existing_image.updated_at < two_days_ago
        ) or settings.ENVIRONMENT == "dev"

        if should_update:
            async_task(regenerate_and_update_image, existing_image.id, params)

        try:
            return _build_image_response(
                existing_image.generated_image, output_format, signed_expires_at, usage_state=usage_state
            )
        except FileNotFoundError:
            logger.error(f"Generated image file not found for image_id: {existing_image.id}")

    max_attempts = max(1, int(getattr(settings, "OSIG_RENDER_MAX_ATTEMPTS", 2)))

    for attempt_number in range(1, max_attempts + 1):
        attempt_started_at = perf_counter()

        try:
            image = generate_image_router(params)
            duration_ms = int((perf_counter() - attempt_started_at) * 1000)

            record_render_attempt(
                profile=profile,
                key=params.get("key", ""),
                style=params.get("style", "base"),
                success=True,
                duration_ms=duration_ms,
                attempt_number=attempt_number,
            )

            async_task(save_generated_image, image, params)
            return _build_image_response(image, output_format, signed_expires_at, usage_state=usage_state)
        except Exception as exc:
            duration_ms = int((perf_counter() - attempt_started_at) * 1000)
            error_type = classify_render_error(exc)

            record_render_attempt(
                profile=profile,
                key=params.get("key", ""),
                style=params.get("style", "base"),
                success=False,
                duration_ms=duration_ms,
                error_type=error_type,
                attempt_number=attempt_number,
            )

            should_retry = is_transient_error(error_type) and attempt_number < max_attempts
            logger.warning(
                "Render pipeline failed",
                error_type=error_type,
                attempt_number=attempt_number,
                max_attempts=max_attempts,
                should_retry=should_retry,
                error=str(exc),
            )

            if should_retry:
                continue

            return HttpResponse(f"Render failed: {error_type}", status=502)

    return HttpResponse("Render failed: unknown_error", status=502)
