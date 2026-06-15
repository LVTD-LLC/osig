# Tech

## Canonical Stack

- Python/Django backend with Django 5.
- Django Ninja for JSON API endpoints.
- FastMCP for hosted and local MCP tooling.
- Pillow for deterministic image rendering.
- PostgreSQL for app data.
- Redis and Django Q2 for background jobs.
- dj-stripe and Stripe for subscription/customer state.
- django-allauth for account/auth flows.
- S3-compatible object storage for generated images.
- webpack, Tailwind CSS, Stimulus, and Django templates for frontend assets.
- PostHog, Plausible, Sentry, Logfire, structlog, and render-attempt records for analytics/observability.

## Runtime And Tooling

- Python version: project requires `>=3.10,<4.0`; production image currently uses Python 3.11.
- JavaScript runtime: deployment asset build uses Node 24.15.0.
- Python dependency manager: `uv`.
- Frontend package manager: npm with `package-lock.json`.

## Main Commands

```bash
cp .env.example .env
make serve
make test
make test core/tests/test_mcp.py
make shell
make migrate
npm run build
uv run python mcp_server.py
uv run fastmcp list --command "uv run python mcp_server.py"
```

## Primary Product Interfaces

- Hosted MCP trial: `/mcp/`, currently public/unauthenticated for agent experimentation.
- Standalone local MCP HTTP sidecar: `uv run python mcp_http_server.py`.
- Local MCP stdio: `uv run python mcp_server.py`.
- Public render endpoint: `/g`.
- Signed URL API: `POST /api/sign`.
- Onboarding metadata API: `POST /api/onboarding/meta`.
- WordPress helper API: `POST /api/integrations/wordpress`.
- Admin render metrics API: `GET /api/admin/render-metrics`.

## MCP Tool Contract

The MCP source of truth is `core/mcp.py`.

Current tools:

- `get_image_generation_contract`
- `normalize_image_params`
- `render_image_preview`
- `build_signed_image_url`
- `list_recent_generated_images`

Admin render metrics are REST-only at `GET /api/admin/render-metrics`; do not list them as MCP tools while hosted MCP remains public and unauthenticated.

Keep MCP tools narrow, typed, and deterministic. They should wrap existing renderer/signing behavior rather than becoming a separate product implementation.

## Rendering Model

Image rendering starts in `core/image_styles.py` and shared utilities live in `core/image_utils.py`. Supported output formats are PNG and JPEG. Supported size presets are `x` and `meta`; `get_image_dimensions` currently returns half-size dimensions for the named social targets.

Current style choices are:

- `base`
- `logo`
- `job_classic`
- `job_logo`
- `job_clean`

Current font choices are:

- `helvetica`
- `markerfelt`
- `papyrus`

Future styles should be added through the router, MCP contract, docs, and tests together.

## Auth, Billing, Quotas

- `Profile.key` is the public API/MCP key.
- Public URLs should use `key`; do not expose or accept `profile_id` from public callers.
- `core/mcp_auth.py` contains profile-key MCP auth helpers, but the current ASGI mount is intentionally unauthenticated for trial use.
- User-scoped MCP tools still require an explicit OSIG profile key as a tool argument.
- Re-enable hosted MCP auth before introducing paid production MCP access or private/admin tools.
- Quota tracking lives in `core/usage.py` and `ProfileUsage`.
- Subscription/customer state lives on `Profile` through dj-stripe models.
- Watermark removal is tied to subscription status through `check_if_profile_has_pro_subscription`.
- Free hosted behavior should stay bounded by watermark and quota.

## Reliability And Observability

- Render error classification and metrics live in `core/render_observability.py`.
- Render attempts are stored in `RenderAttempt`.
- `/g` retries transient upstream fetch failures and records attempt duration/error type.
- Admin metrics expose total attempts, failed attempts, fail rate, p95 render time, and error counts.

## Deployment

- Production deploys through GitHub Actions in `.github/workflows/deploy.yml`.
- The shared production image is built from `deployment/Dockerfile`.
- `APP_PROCESS_TYPE=server` starts Gunicorn with `uvicorn_worker.UvicornWorker` against `osig.asgi:application`.
- `APP_PROCESS_TYPE=worker` starts Django Q workers.
- `APP_PROCESS_TYPE=mcp` starts the standalone FastMCP HTTP sidecar from `mcp_http_server.py`.
- CapRover app names are `osig` and `osig-workers`.

## Technical Constraints

- Do not weaken signature verification in `core/signing.py`.
- Do not expose private/admin MCP tools while hosted MCP remains unauthenticated.
- Do not launch paid production MCP access until profile-key auth is re-enabled.
- Do not add broad admin/database/file access to MCP.
- Do not make rendering depend on external model image generation by default.
- Keep generated image outputs deterministic for the same normalized params.
- Preserve cache-busting with `v` and signed URL regeneration.
- When changing renderer inputs, update MCP schema, public docs, tests, and UI examples.
- Keep image fetch timeouts and retry taxonomy explicit.
