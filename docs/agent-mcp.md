# Agent MCP Usage

Use OSIG's MCP server when an AI agent needs to inspect image options, render previews, and publish a stable `/g` image URL.

This guide is for agents and agent-client setup. Human website usage is in [human-usage.md](human-usage.md).

## Hosted Endpoint

Production MCP endpoint:

```text
https://osig.app/mcp/
```

No authentication headers are required during the current trial.

Example MCP client config:

```json
{
  "mcpServers": {
    "osig": {
      "url": "https://osig.app/mcp/"
    }
  }
}
```

## Local HTTP Server

Local commands expect the normal Django environment. If you do not already have `.env`, start from the example:

```bash
cp .env.example .env
```

For native local runs without Docker Postgres, set `DATABASE_URL=sqlite:///db.sqlite3` in `.env`.

Run the standalone FastMCP Streamable HTTP server:

```bash
uv run python mcp_http_server.py
```

Default local endpoint:

```text
http://127.0.0.1:8765/mcp
```

Override host, port, or path with:

```bash
MCP_HOST=0.0.0.0 MCP_PORT=8765 MCP_PATH=/mcp uv run python mcp_http_server.py
```

## Local Stdio Server

For stdio-based clients:

```bash
uv run python mcp_server.py
```

Inspect the tool list:

```bash
uv run fastmcp list --command "uv run python mcp_server.py"
```

If you are passing ad hoc environment values instead of using `.env`, put them inside the spawned command string:

```bash
uv run fastmcp list --command "sh -c 'set -a; . ./.env.example; set +a; uv run python mcp_server.py'"
```

## Tools

- `get_image_generation_contract`: returns styles, choices, dimensions, fields, and the recommended workflow.
- `normalize_image_params`: canonicalizes renderer inputs and maps `image_or_logo` to `image_url`.
- `render_image_preview`: renders a preview and returns metadata plus optional base64 image bytes.
- `build_signed_image_url`: creates a signed public `/g` URL.
- `list_recent_generated_images`: returns recent persisted images for an explicit OSIG profile key.

Admin render metrics are not exposed through the unauthenticated MCP server.

## Recommended Agent Workflow

1. Call `get_image_generation_contract`.
2. Choose `style`, `site`, `font`, and copy fields.
3. Call `normalize_image_params` to catch canonical params and warnings.
4. Call `render_image_preview` while iterating.
5. Call `build_signed_image_url` once the preview is ready to publish.
6. Put the returned URL in `og:image`, `twitter:image`, and schema image fields.

## Serving Model

OSIG serves MCP through FastMCP in two ways:

- ASGI mount: `osig/asgi.py` mounts `mcp.http_app(path="/")` at `/mcp` beside Django.
- Sidecar: `mcp_http_server.py` runs the same FastMCP server as a separate Streamable HTTP process.

The ASGI mount requires an async server such as Gunicorn with `uvicorn_worker.UvicornWorker`.
