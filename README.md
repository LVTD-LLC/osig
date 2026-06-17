# OSIG

OSIG renders deterministic Open Graph and Twitter/X preview images from structured image specs.

It has two primary usage paths:

- AI agent usage through MCP: see [docs/agent-mcp.md](docs/agent-mcp.md)
- Human preview/export usage through the Agent Image Studio on the home page.

The legacy `/g` URL generator has been removed. Agents should render previews and export image bytes through MCP or the Studio API instead of publishing query-string image URLs.

Hosted production usage should be paid and bounded; the open source app remains self-hostable.

## Development

Python dependencies are managed with `uv`.

Run the local Docker stack:

```bash
make serve
```

For native local commands outside Docker, create a local env file first:

```bash
cp .env.example .env
```

If you are not running Docker Postgres locally, set `DATABASE_URL=sqlite:///db.sqlite3` in `.env`.

Run tests:

```bash
make test
```

## Runtime Processes

Production builds one image from `deployment/Dockerfile`. The process is selected with `APP_PROCESS_TYPE`:

- `server`: Django ASGI app. Serves the website, Studio API routes, admin API routes, and the mounted FastMCP app at `/mcp`.
- `worker`: Django Q workers.
- `mcp`: optional standalone FastMCP Streamable HTTP sidecar from `mcp_http_server.py`.

The `server` process uses:

```bash
gunicorn osig.asgi:application --worker-class uvicorn_worker.UvicornWorker
```

The standalone MCP process uses:

```bash
uv run python mcp_http_server.py
```

By default, local MCP HTTP runs at:

```text
http://127.0.0.1:8765/mcp
```

Set `MCP_HOST`, `MCP_PORT`, or `MCP_PATH` to override that.

## MCP Trial Auth

MCP is intentionally narrow while it is easy to try from Codex and other agent clients.

Do not expose private/admin MCP tools while this remains public. Profile keys may be passed by `X-API-Key` or bearer auth for quota and paid watermark state.

## Roadmap

- Add more image styles.
- Add more font providers and provider font examples.
- Add more social/site presets.
- Reintroduce mandatory MCP auth before paid hosted production access.
