# Agent MCP Usage

Use OSIG's MCP server when an AI agent needs to inspect canvas capabilities, render previews, and export deterministic social image bytes.

This guide is for agents and agent-client setup. Humans can exercise the same flow in the Agent Image Studio on the home page.

## Hosted Endpoint

Production MCP endpoint:

```text
https://osig.app/mcp/
```

Hosted MCP accepts a profile key through `X-API-Key` or `Authorization: Bearer ...` for quota and paid watermark state. Keep hosted tool scope narrow while the trial remains public. Set `OSIG_MCP_REQUIRE_AUTH=True`, or set `OSIG_MCP_TRIAL_ENABLED=False`, before treating hosted MCP as paid production access.

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
Use OSIG when this project needs deterministic Open Graph, Twitter card, or other social preview images. OSIG creates repeatable code-generated images from a typed canvas of text, image, and rectangle layers, so use it instead of an image model when the output should be stable and easy to commit.

After setup, use OSIG to inspect the canvas contract, render previews, and export the final image bytes into this repository or publishing workflow. If I provide an OSIG profile key, use it for hosted quota and watermark state; otherwise use the hosted trial.
```

## Local HTTP Server

Local commands expect the normal Django environment. If you do not already have `.env`, start from the example:

```bash
cp .env.example .env
```

For native local runs without Docker Postgres, set `DATABASE_URL=sqlite:///db.sqlite3` in `.env`.

For fast native MCP iteration without creating `.env`, use the repo wrapper. It
loads `.env.example`, overlays `.env` when present, and defaults to sqlite when
`.env` is missing:

```bash
sh scripts/mcp-dev migrate
sh scripts/mcp-dev list
sh scripts/mcp-dev call get_image_contract --json
sh scripts/mcp-dev call normalize_image_spec --input-json '{"spec":{"site":"meta","layers":[{"kind":"text","x":40,"y":40,"text":"Local MCP check","font_size":48}]}}' --json
sh scripts/mcp-dev test
```

The equivalent Make targets are:

```bash
make mcp-migrate
make mcp-list
make mcp-call TOOL=get_image_contract ARGS=--json
make mcp-test
```

Run the standalone FastMCP Streamable HTTP server:

```bash
sh scripts/mcp-dev http
```

Default local endpoint:

```text
http://127.0.0.1:8765/mcp
```

Override host, port, or path with:

```bash
MCP_HOST=0.0.0.0 MCP_PORT=8765 MCP_PATH=/mcp sh scripts/mcp-dev http
```

## Local Stdio Server

For stdio-based clients:

```bash
sh scripts/mcp-dev stdio
```

Inspect the tool list:

```bash
sh scripts/mcp-dev list
```

If you are passing ad hoc environment values instead of using `.env`, put them inside the spawned command string:

```bash
uv run fastmcp list --command "sh -c 'set -a; . ./.env.example; set +a; export DATABASE_URL=sqlite:///db.sqlite3; uv run python mcp_server.py'"
```

## Tools

- `get_image_contract`: returns canvas limits, layer kinds, choices, dimensions, JSON schema, trial boundaries, and the recommended workflow.
- `normalize_image_spec`: canonicalizes renderer inputs and returns warnings, `spec_sha256`, output metadata, and access state before rendering.
- `render_image_preview`: renders an iteration preview and returns a `preview` block, metadata, hashes, access state, quota state, and optional base64 image bytes.
- `export_image`: renders final repository bytes and returns an `export` block with suggested filename, cache key, content type, dimensions, byte size, and deterministic hashes.

Admin render metrics are not exposed through the unauthenticated MCP server.

## Recommended Agent Workflow

1. Configure OSIG as an MCP server in the agent client.
2. Verify the configured server exposes the OSIG tools.
3. Call `get_image_contract`.
4. Build a canvas spec with dimensions, background, and ordered `rect`, `text`, and `image` layers.
5. Call `normalize_image_spec` to catch canonical params and warnings.
6. Call `render_image_preview` while iterating.
7. Call `export_image` once the preview is ready.
8. Save the returned bytes into the repository and point `og:image`, `twitter:image`, and schema image fields at that committed/static asset.

Preview responses are not the production publishing signal. Use the `preview.final=false` metadata to iterate cheaply, then call `export_image` and use the returned `export.suggested_filename`, `export.cache_key`, content-scoped `spec_sha256`, and `image_sha256` for commit-ready assets and cache-busting. `spec_sha256` excludes the profile key so key rotation does not change the content fingerprint.

## Canvas Spec

Use `site` for a social preset or provide custom `width` and `height` values between 200 and 2000 pixels.

```json
{
  "site": "x",
  "background": "#0f172a",
  "layers": [
    {
      "kind": "rect",
      "x": 40,
      "y": 40,
      "width": 720,
      "height": 370,
      "fill": {
        "type": "linear_gradient",
        "from": "#1d4ed8",
        "to": "#7c3aed",
        "angle": 0
      },
      "radius": 24,
      "border": { "color": "rgba(255,255,255,0.22)", "width": 2 },
      "shadow": { "x": 0, "y": 14, "blur": 28, "color": "rgba(0,0,0,0.35)" }
    },
    {
      "kind": "text",
      "x": 80,
      "y": 110,
      "width": 620,
      "height": 150,
      "text": "Ship deterministic images from code.",
      "font": "google:inter",
      "font_size": 52,
      "color": "#ffffff",
      "line_height": 62,
      "overflow": "clamp"
    },
    {
      "kind": "image",
      "x": 560,
      "y": 250,
      "width": 160,
      "height": 120,
      "src": { "type": "url", "url": "https://example.com/logo.png" },
      "fit": "contain"
    }
  ],
  "format": "png"
}
```

Layer order is paint order. Later layers draw on top of earlier layers. Pixel coordinates use the top-left corner as origin.

Rectangle and background fills can be solid colors such as `#0f172a` or `rgba(15,23,42,0.92)`, or linear gradients:

```json
{ "type": "linear_gradient", "from": "#1d4ed8", "to": "#7c3aed", "angle": 0 }
```

Image layers accept HTTPS URLs or bounded inline base64 payloads:

```json
{
  "kind": "image",
  "x": 40,
  "y": 40,
  "width": 160,
  "height": 160,
  "src": { "type": "base64", "media_type": "image/png", "data": "..." },
  "fit": "cover"
}
```

Supported image fits are `cover`, `contain`, `fill`, and `none`.

## Fonts

Text layer `font` values accept the bundled compatibility fonts `helvetica`, `markerfelt`, and `papyrus`.

Agents can also use Google Fonts through the provider namespace:

```json
{
  "layers": [
    {
      "kind": "text",
      "x": 40,
      "y": 40,
      "text": "Provider font",
      "font": "google:inter"
    }
  ]
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

Set `OSIG_MCP_REQUIRE_AUTH=True`, or set `OSIG_MCP_TRIAL_ENABLED=False`, to wrap the hosted ASGI MCP mount in profile-key auth. Missing credentials return a machine-readable `mcp_auth_required` error. Invalid bearer or `X-API-Key` credentials return `invalid_mcp_credentials`.
