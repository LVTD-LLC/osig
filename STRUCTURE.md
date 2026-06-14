# Structure

## Directory Map

- `core/`: main Django app for product logic, API endpoints, rendering, MCP, usage, billing hooks, and tests.
- `core/api/`: Django Ninja API schemas, views, and auth helpers.
- `core/tests/`: pytest coverage for renderer behavior, MCP, auth, onboarding, quotas, views, reliability, and integrations.
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

- `core/mcp.py`: MCP contract and tool implementation.
- `core/mcp_auth.py`: profile-key MCP auth helpers; not currently mounted on the public trial MCP surface.
- `core/image_styles.py`: image style router and template renderers.
- `core/image_utils.py`: dimensions, font loading, image fetching, output encoding, watermark helper.
- `core/views.py`: public pages and `/g` renderer endpoint.
- `core/api/views.py`: signed URL, onboarding metadata, WordPress helper, blog submission, render metrics.
- `core/models.py`: profiles, usage, generated images, render attempts, blog posts.
- `core/usage.py`: per-profile usage metering and quota enforcement.
- `core/render_observability.py`: render error taxonomy, retry classification, aggregate metrics.
- `core/signing.py`: signed public URL creation and verification.
- `frontend/src/controllers/image_generator_controller.js`: current human web generator.
- `frontend/src/controllers/onboarding_wizard_controller.js`: guided human metadata workflow.
- `frontend/src/styles/index.css`: product UI tokens and component classes.
- `deployment/entrypoint.sh`: production server/worker role selection.

## Ownership Boundaries

- MCP changes belong in `core/mcp.py` unless they require shared auth/render/signing behavior.
- Public JSON API changes belong in `core/api/`.
- Render template changes belong in `core/image_styles.py`; shared image mechanics belong in `core/image_utils.py`.
- `/g` request parsing and response/cache behavior belong in `core/views.py`.
- New persisted state belongs in `core/models.py` with migrations and admin/test updates.
- Human UI changes should use Django templates, Stimulus controllers, and CSS tokens already present in `frontend/src/styles/index.css`.
- Product direction belongs in root steering files, not scattered only through feature docs.

## Placement Rules

- Add new tests beside related existing tests under `core/tests/`.
- Add new image styles to the router, MCP contract, README/docs, and test coverage in one change.
- Add new public API request/response shapes to `core/api/schemas.py`.
- Add new API endpoints to `core/api/views.py` and route through the existing Ninja API.
- Add new CSS component primitives in `frontend/src/styles/index.css` only when repeated across pages.
- Add generated/static example assets to `frontend/vendors/images/` only when they are durable docs/product assets.
- Add operational docs to `docs/`, but keep durable AI-agent steering at the repository root.

## Import And Naming Patterns

- Prefer explicit imports from local modules.
- Keep Django settings access through `django.conf.settings`.
- Use existing helper names and public parameter names: `style`, `site`, `font`, `title`, `subtitle`, `eyebrow`, `image_url`, `image_or_logo`, `format`, `quality`, `max_kb`, `v`, `key`.
- Use `profile_id` only internally after authenticating or resolving a `Profile`.
- Keep public enum values stable unless there is a migration plan.

## Cross-Cutting Checks

When touching renderer, MCP, API, billing, or quota behavior, check these paths together:

- `core/mcp.py`
- `core/views.py`
- `core/api/views.py`
- `core/image_styles.py`
- `core/image_utils.py`
- `core/tests/`
- `README.md`
- `docs/agent-mcp.md`
- `PRODUCT.md`
- `TECH.md`

## Current Product Surfaces

The web generator and onboarding wizard are useful, but they are not the long-term center of the product. Future structure should make it easy for agents to call MCP/API flows directly while humans use the web app for configuration, billing, docs, and diagnostics.
