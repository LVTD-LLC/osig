# OSIG Agent MCP

OSIG exposes a local FastMCP server for agents that need to iterate on generated Open Graph images.

The server is intentionally small and explicit. It does not expose generic database access or arbitrary file access. The tools wrap the existing image renderer, signing helpers, and render metrics so future improvements stay close to the Django source of truth.

## Run Locally

```bash
uv run python mcp_server.py
```

For clients that inspect a server before connecting:

```bash
uv run fastmcp list --command "uv run python mcp_server.py"
```

The stdio entrypoint uses `DJANGO_SETTINGS_MODULE=osig.settings` and calls `django.setup()` before loading `core.mcp`. It expects the same environment as the Django app, either through `.env` or exported shell variables.

When using `fastmcp list --command` with ad hoc local settings instead of a `.env` file, put those environment variables inside the command string so the spawned stdio server receives them.

## Tools

- `get_image_generation_contract`: styles, valid choices, dimensions, fields, and the recommended iteration workflow.
- `normalize_image_params`: canonicalizes renderer inputs and maps `image_or_logo` to `image_url`.
- `render_image_preview`: renders a preview and returns metadata plus optional base64 image bytes.
- `build_signed_image_url`: creates a tamper-proof public `/g` URL.
- `list_recent_generated_images`: returns capped summaries of persisted images scoped to a required profile key.
- `get_recent_render_metrics`: returns recent render attempt health metrics.

## Transport Notes

The default entrypoint is stdio because this is meant for local/editor agents. If this becomes a remote service, run it as a private HTTP sidecar rather than mounting it into the current WSGI deployment, then add authentication before exposing it beyond trusted infrastructure.
