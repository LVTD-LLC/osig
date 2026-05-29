from __future__ import annotations

from asgiref.sync import sync_to_async
from django.db import close_old_connections
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from core.models import Profile
from osig.utils import get_osig_logger

logger = get_osig_logger(__name__)


def _bearer_token(headers) -> str:
    authorization = headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return ""


def _profile_for_key(key: str) -> Profile | None:
    if not key:
        return None

    try:
        return Profile.objects.select_related("user").get(key=key)
    except Profile.DoesNotExist:
        return None


def authenticate_mcp_headers(headers) -> Profile | None:
    """Authenticate hosted MCP requests with an OSIG profile API key."""
    close_old_connections()
    try:
        bearer_profile = _profile_for_key(_bearer_token(headers))
        if bearer_profile is not None:
            logger.info("[MCP] Authenticated with bearer API key", profile_id=bearer_profile.id)
            return bearer_profile

        header_profile = _profile_for_key(headers.get("x-api-key", "").strip())
        if header_profile is not None:
            logger.info("[MCP] Authenticated with X-API-Key", profile_id=header_profile.id)
            return header_profile

        return None
    finally:
        close_old_connections()


class McpAuthMiddleware:
    """Require an OSIG profile key for hosted MCP HTTP transport."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        profile = await sync_to_async(authenticate_mcp_headers, thread_sensitive=True)(headers)
        if profile is not None:
            await self.app(scope, receive, send)
            return

        has_credentials = bool(_bearer_token(headers) or headers.get("x-api-key", "").strip())
        response = JSONResponse(
            {"detail": "MCP authentication required."},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"' if has_credentials else "Bearer"},
        )
        await response(scope, receive, send)
