# Structure

## Directory Map

- `agent_images/`: agent-first image app with FastMCP tools, Studio render API, image specs, and shared render services.
- `core/`: Django app for accounts, billing hooks, blog/content, shared models, renderer internals, usage, observability, and tests.
- `core/api/`: Django Ninja API schemas, views, and auth helpers.
- `core/tests/`: pytest coverage for renderer behavior, MCP, auth, quotas, views, reliability, Studio API, and removed legacy endpoints.
- `frontend/src/`: JavaScript controllers and CSS entrypoint.
- `frontend/templates/`: Django templates for pages, account flows, components, blog, and base layout.
- `frontend/vendors/images/`: static product/logo/example images.
- `fonts/`: bundled fonts used by the Pillow renderer.
- `docs/`: project and feature documentation.
- `osig/`: Django project settings, URLs, ASGI/WSGI, sitemap, and logging utilities.
- `deployment/`: production Dockerfile and entrypoint.
- `.github/workflows/`: deployment workflow.
- `mcp_server.py`: local stdio MCP entrypoint.
- `mcp_http_server.py`: standalone FastMCP Streamable HTTP sidecar entrypoint.

## Important Files

- `agent_images/mcp.py`: MCP contract and tool implementation.
- `agent_images/services.py`: image spec validation, normalization, rendering, metadata, quota, and retry/observability.
- `agent_images/views.py`: Studio render API.
- `core/mcp.py`: compatibility import for the new MCP module.
- `core/mcp_auth.py`: profile-key MCP auth helpers; not currently mounted on the public trial MCP surface.
- `core/image_styles.py`: deterministic canvas layer renderer.
- `core/image_utils.py`: dimensions, font loading, image fetching, output encoding, watermark helper.
- `core/views.py`: public pages, account settings, billing redirects, and utility image views.
- `core/api/views.py`: blog submission and render metrics.
- `core/models.py`: profiles, usage, generated images, render attempts, blog posts.
- `core/usage.py`: per-profile usage metering and quota enforcement.
- `core/render_observability.py`: render error taxonomy, retry classification, aggregate metrics.
- `core/signing.py`: legacy signing helpers retained for now, not used by the current agent-first flow.
- `frontend/src/controllers/agent_studio_controller.js`: Studio render/export interactions.
- `frontend/src/styles/index.css`: product UI tokens and component classes.
- `deployment/entrypoint.sh`: production server/worker role selection.

## Ownership Boundaries

- MCP changes belong in `agent_images/mcp.py` unless they require shared render/auth behavior.
- Public JSON API changes belong in `core/api/`.
- Canvas renderer changes belong in `core/image_styles.py`; shared image mechanics belong in `core/image_utils.py`.
- Studio render API behavior belongs in `agent_images/views.py`; shared image behavior belongs in `agent_images/services.py`.
- New persisted state belongs in `core/models.py` with migrations and admin/test updates.
- Human UI changes should use Django templates, Stimulus controllers, and CSS tokens already present in `frontend/src/styles/index.css`.
- Product direction belongs in root steering files, not scattered only through feature docs.

## Placement Rules

- Add new tests beside related existing tests under `core/tests/`.
- Add new canvas primitives to the renderer, `agent_images` contract, README/docs, and test coverage in one change.
- Add new public API request/response shapes to `core/api/schemas.py`.
- Add new API endpoints to `core/api/views.py` and route through the existing Ninja API.
- Add new CSS component primitives in `frontend/src/styles/index.css` only when repeated across pages.
- Add generated/static example assets to `frontend/vendors/images/` only when they are durable docs/product assets.
- Add operational docs to `docs/`, but keep durable AI-agent steering at the repository root.

## Import And Naming Patterns

- Prefer explicit imports from local modules.
- Keep Django settings access through `django.conf.settings`.
- Use existing public canvas parameter names: `site`, `width`, `height`, `background`, `layers`, `kind`, `x`, `y`, `format`, `quality`, `max_kb`, `v`, and `key`.
- Use `profile_id` only internally after authenticating or resolving a `Profile`.
- Keep public enum values stable unless there is a migration plan.

## Cross-Cutting Checks

When touching renderer, MCP, API, billing, or quota behavior, check these paths together:

- `agent_images/mcp.py`
- `agent_images/services.py`
- `agent_images/views.py`
- `core/api/views.py`
- `core/image_styles.py`
- `core/image_utils.py`
- `core/tests/`
- `README.md`
- `docs/agent-mcp.md`
- `PRODUCT.md`
- `TECH.md`

## Current Product Surfaces

The Agent Image Studio is the human playground for the same services agents use. Future structure should keep MCP/API flows primary while humans use the web app for configuration, billing, docs, previews, and diagnostics.
