from django.urls import path
from django.views.generic import RedirectView

from agent_images import views as agent_image_views
from core import views
from core.api.views import api

urlpatterns = [
    # pages
    path("", views.HomeView.as_view(), name="home"),
    path("settings", views.UserSettingsView.as_view(), name="settings"),
    path("how-to/", RedirectView.as_view(url="/", permanent=True), name="how_to_trailing_slash_redirect"),
    path("how-to", RedirectView.as_view(url="/", permanent=True), name="how_to"),
    # api
    path("api/", api.urls),
    path("api/studio/render", agent_image_views.render_studio_image, name="studio_render"),
    # blog
    path("blog/", RedirectView.as_view(url="/", permanent=True), name="blog_posts"),
    path(
        "blog/<slug:slug>/",
        RedirectView.as_view(url="/", permanent=True),
        name="blog_post_trailing_slash_redirect",
    ),
    path("blog/<slug:slug>", RedirectView.as_view(url="/", permanent=True), name="blog_post"),
    # utils
    path("resend-confirmation", views.resend_confirmation_email, name="resend_confirmation"),
    # payments
    path(
        "pricing/",
        RedirectView.as_view(url="/", permanent=True),
        name="pricing_trailing_slash_redirect",
    ),
    path("pricing", RedirectView.as_view(url="/", permanent=True), name="pricing"),
    path("create-customer-portal", views.create_customer_portal_session, name="create_customer_portal_session"),
    path(
        "create-checkout-session/<int:pk>/<str:plan>/",
        views.create_checkout_session,
        name="user_upgrade_checkout_session",
    ),
    # app
    path("blank-square.png", views.blank_square_image, name="blank_square_image"),
]
