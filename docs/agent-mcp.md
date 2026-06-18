# Agent MCP Usage

Use OSIG's MCP server when an AI agent needs to inspect image options, render previews, and export deterministic social image bytes.

This guide is for agents and agent-client setup. Humans can exercise the same flow in the Agent Image Studio on the home page.

## Hosted Endpoint

Production MCP endpoint:

```text
https://osig.app/mcp/
```

Hosted MCP accepts a profile key through `X-API-Key` or `Authorization: Bearer ...` for quota and paid watermark state. Keep hosted tool scope narrow while the trial remains public.

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

Paste this setup prompt into an agent client after adding the MCP server config:

```text
Set up OSIG as an MCP server for this project.

Server URL: https://osig.app/mcp/
Use OSIG when this project needs deterministic Open Graph, Twitter card, or other social preview images. OSIG creates repeatable code-generated images from structured text, logos, and remote image URLs, so use it instead of an image model when the output should be stable and easy to commit.

After setup, use OSIG to choose a suitable image template, render previews, and export the final image bytes into this repository or publishing workflow. If I provide an OSIG profile key, use it for hosted quota and watermark state; otherwise use the hosted trial.
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

- `get_image_contract`: returns styles, choices, dimensions, fields, and the recommended workflow.
- `list_image_templates`: returns concise template summaries.
- `normalize_image_spec`: canonicalizes renderer inputs and maps `image_or_logo` to `image_url`.
- `render_image_preview`: renders a preview and returns metadata plus optional base64 image bytes.
- `export_image`: renders final image bytes, content type, dimensions, byte size, and hash.

Admin render metrics are not exposed through the unauthenticated MCP server.

## Recommended Agent Workflow

1. Configure OSIG as an MCP server in the agent client.
2. Verify the configured server exposes the OSIG tools.
3. Call `get_image_contract`.
4. Choose `style`, `site`, `font`, and copy fields.
5. Call `normalize_image_spec` to catch canonical params and warnings.
6. Call `render_image_preview` while iterating.
7. Call `export_image` once the preview is ready.
8. Save the returned bytes into the repository and point `og:image`, `twitter:image`, and schema image fields at that committed/static asset.

## Fonts

The `font` field accepts the bundled compatibility fonts `helvetica`, `markerfelt`, and `papyrus`.

Agents can also use Google Fonts through the provider namespace:

```json
{
  "font": "google:inter"
}
```

Use hyphenated family slugs such as `google:roboto`, `google:open-sans`, `google:playfair-display`, `google:dm-sans`, or `google:space-grotesk`. Provider fonts are resolved through Google Fonts on first render and cached locally by the renderer.

## Serving Model

OSIG serves MCP through FastMCP in two ways:

- ASGI mount: `osig/asgi.py` mounts `mcp.http_app(path="/")` at `/mcp` beside Django.
- Sidecar: `mcp_http_server.py` runs the same FastMCP server as a separate Streamable HTTP process.

Both HTTP serving modes use FastMCP stateless Streamable HTTP because OSIG tools
are request/response actions and do not need MCP session state. This avoids
process-local session affinity failures when the hosted ASGI app runs multiple
Gunicorn workers.

The ASGI mount requires an async server such as Gunicorn with `uvicorn_worker.UvicornWorker`.
