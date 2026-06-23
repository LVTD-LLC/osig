"""
ASGI config for osig project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

import os

from django.conf import settings
from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "osig.settings")

django_application = get_asgi_application()

from agent_images.mcp import mcp  # noqa: E402
from core.mcp_auth import McpAuthMiddleware  # noqa: E402

# OSIG's MCP tools are stateless request/response actions. Stateless HTTP avoids
# process-local session affinity failures when Gunicorn runs multiple workers.
mcp_transport_application = mcp.http_app(path="/", stateless_http=True)


def build_hosted_mcp_application(app):
    if settings.OSIG_MCP_REQUIRE_AUTH or not settings.OSIG_MCP_TRIAL_ENABLED:
        return McpAuthMiddleware(app)
    return app


mcp_application = build_hosted_mcp_application(mcp_transport_application)


def redirect_mcp(request: Request) -> RedirectResponse:
    return RedirectResponse(str(request.url.replace(path="/mcp/")), status_code=307)


application = Starlette(
    routes=[
        Route("/mcp", endpoint=redirect_mcp, methods=["GET", "POST", "DELETE"]),
        Mount("/mcp", app=mcp_application),
        Mount("/", app=django_application),
    ],
    lifespan=mcp_transport_application.lifespan,
)
