# Self-Hosting OSIG

Self-hosting is the open source path for teams that want to run the renderer without relying on OSIG cloud. Hosted production usage remains account, quota, watermark, and entitlement based.

## Local Docker Setup

```bash
cp .env.example .env
make serve
```

Run migrations and tests:

```bash
make migrate
make test
```

## Environment

Required local values come from `.env.example`:

- `ENVIRONMENT`
- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

S3-compatible storage values are required when generated media should persist outside the local filesystem:

- `AWS_S3_ENDPOINT_URL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Stripe and dj-stripe values are optional unless you sell hosted access from your deployment.

## MCP Usage

Local stdio:

```bash
sh scripts/mcp-dev stdio
```

Local HTTP:

```bash
sh scripts/mcp-dev http
```

Default local endpoint:

```text
http://127.0.0.1:8765/mcp
```

Inspect and test tools:

```bash
sh scripts/mcp-dev list
sh scripts/mcp-dev call get_image_contract --json
sh scripts/mcp-dev test
```

## Quotas And Watermarks

Self-hosters can configure limits with:

- `OSIG_DAILY_USAGE_LIMIT`
- `OSIG_MONTHLY_USAGE_LIMIT`
- `OSIG_USAGE_WARNING_PERCENT`

Profile-key renders are metered through `ProfileUsage`. Watermark removal is tied to the profile subscription state in the default app, but self-hosters can adapt that entitlement logic for private deployments.

## Extension Points

- Add canvas primitives in `core/image_styles.py`, `agent_images/services.py`, MCP contract docs, and tests together.
- Add template starters in `agent_images/templates.py` when they can compile to ordinary canvas specs.
- Keep provider fonts namespaced and bounded. Do not accept arbitrary font URLs from public callers.
- Keep hosted/public MCP scope narrow: no filesystem, shell, database, billing, admin, or render-history tools.
