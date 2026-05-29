import pytest
from django.contrib.auth.models import User
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from core.mcp_auth import McpAuthMiddleware, authenticate_mcp_headers


async def _ok_app(scope, receive, send):
    response = JSONResponse({"ok": True})
    await response(scope, receive, send)


@pytest.mark.django_db(transaction=True)
def test_authenticate_mcp_headers_accepts_profile_key_headers():
    user = User.objects.create_user(username="mcp-auth", email="mcp-auth@example.com", password="pass123")

    assert authenticate_mcp_headers({"x-api-key": user.profile.key}) == user.profile
    assert authenticate_mcp_headers({"authorization": f"Bearer {user.profile.key}"}) == user.profile
    assert authenticate_mcp_headers({"x-api-key": "invalid"}) is None


@pytest.mark.django_db(transaction=True)
def test_mcp_auth_middleware_rejects_missing_credentials():
    client = TestClient(McpAuthMiddleware(_ok_app))

    response = client.post("/mcp/")

    assert response.status_code == 401
    assert response.json() == {"detail": "MCP authentication required."}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.django_db(transaction=True)
def test_mcp_auth_middleware_allows_profile_key_header():
    user = User.objects.create_user(username="mcp-client", email="mcp-client@example.com", password="pass123")
    client = TestClient(McpAuthMiddleware(_ok_app))

    response = client.post("/mcp/", headers={"X-API-Key": user.profile.key})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_asgi_application_mounts_hosted_mcp():
    from osig.asgi import application

    route_paths = {getattr(route, "path", "") for route in application.routes}

    assert "/mcp" in route_paths
    assert "" in route_paths
