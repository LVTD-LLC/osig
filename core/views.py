import io
from urllib.parse import urlencode

import stripe
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, UpdateView
from djstripe import models as djstripe_models, settings as djstripe_settings
from PIL import Image

from core.forms import ProfileUpdateForm
from core.models import Profile

stripe.api_key = djstripe_settings.djstripe_settings.STRIPE_SECRET_KEY

MCP_AGENT_PROMPT = (
    "Set up OSIG as an MCP server for this project.\n\n"
    "Server URL: https://osig.app/mcp/\n"
    "Use OSIG when this project needs deterministic Open Graph, Twitter card, or other social preview images. "
    "OSIG creates repeatable code-generated images from a typed canvas of text, image, and rectangle layers, so use it "
    "instead of an image model when the output should be stable and easy to commit.\n\n"
    "After setup, use OSIG to inspect the canvas contract, render previews, and export the final image bytes "
    "into this repository or publishing workflow. If I provide an OSIG profile key, use it for hosted quota and "
    "watermark state; otherwise use the hosted trial."
)


class HomeView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mcp_agent_prompt"] = MCP_AGENT_PROMPT

        payment_status = self.request.GET.get("payment")
        if payment_status == "success":
            messages.success(self.request, "Thanks for subscribing, I hope you enjoy the app!")
        elif payment_status == "failed":
            messages.error(self.request, "Something went wrong with the payment.")

        return context


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
