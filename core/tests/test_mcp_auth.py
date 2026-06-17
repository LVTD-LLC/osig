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


def test_asgi_application_mounts_mcp_without_auth_middleware():
    from starlette.routing import Mount

    from osig.asgi import application

    mcp_mounts = [route for route in application.routes if isinstance(route, Mount) and route.path == "/mcp"]

    assert len(mcp_mounts) == 1
    assert not isinstance(mcp_mounts[0].app, McpAuthMiddleware)


def test_asgi_mcp_stateless_http_does_not_require_session_affinity():
    from osig.asgi import mcp_application

    initialize_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    with TestClient(mcp_application) as client:
        initialized = client.post("/", headers=headers, json=initialize_payload)
        stale_session = client.post(
            "/",
            headers={**headers, "mcp-session-id": "missing"},
            json=initialize_payload,
        )

    assert initialized.status_code == 200
    assert "mcp-session-id" not in initialized.headers
    assert stale_session.status_code == 200
    assert "Session not found" not in stale_session.text


def test_standalone_mcp_http_server_uses_stateless_transport(monkeypatch):
    import agent_images.mcp as agent_mcp
    import mcp_http_server

    run_kwargs = {}

    def fake_run(**kwargs):
        run_kwargs.update(kwargs)

    monkeypatch.setattr(agent_mcp.mcp, "run", fake_run)

    mcp_http_server.main()

    assert run_kwargs["transport"] == "http"
    assert run_kwargs["stateless_http"] is True
