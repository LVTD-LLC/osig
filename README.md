# OSIG

OSIG renders Open Graph and Twitter/X preview images from URL parameters.

It has two separate usage paths:

- Human website usage: see [docs/human-usage.md](docs/human-usage.md)
- AI agent usage through MCP: see [docs/agent-mcp.md](docs/agent-mcp.md)

The public image endpoint remains:

```text
https://osig.app/g
```

Existing unsigned `/g` image URLs keep working for backwards compatibility.

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

- `server`: Django ASGI app. Serves the website, `/g`, API routes, and the mounted FastMCP app at `/mcp`.
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

MCP is intentionally unauthenticated for now so it is easy to try from Codex and other agent clients.

Do not expose private/admin MCP tools while this remains public. User-scoped history tools still require an explicit OSIG profile key as a tool argument.

## Roadmap

- Add more image styles.
- Add more fonts.
- Add more social/site presets.
- Reintroduce MCP auth once the agent workflow is proven.
