# Agent Image Studio Design

## Decision

Rebuild OSIG around the agent-first workflow instead of the legacy `/g` URL generator. The primary product surface becomes a dedicated MCP server and a compact web studio that exercises the same render services agents use.

## Scope

- Remove the public `/g` rendering endpoint and the URL-generator UI.
- Create a separate Django app for agent image capabilities, including FastMCP registration, typed image schemas, render services, and tests.
- Keep deterministic code-generated images as the core value. Do not introduce model image generation.
- Replace signed `/g` URL creation with agent outputs that are useful inside repositories: image bytes/base64, metadata, dimensions, content type, warnings, and hashes.
- Simplify the web UI into a technical workspace for humans to configure MCP access, edit image specs, preview output, and export assets.

## Architecture

The new Django app, `agent_images`, owns the agent-facing image contract. It exposes a small FastMCP server built with `fastmcp.FastMCP`, and keeps tool functions thin by calling shared service functions.

The existing renderer remains deterministic and reusable, but it is called through service boundaries that normalize input, render images, calculate metadata, and package export responses. Browser views and MCP tools consume those services instead of constructing `/g` URLs.

The MCP entrypoints (`mcp_server.py`, `mcp_http_server.py`, and `osig/asgi.py`) import from `agent_images.mcp`. Hosted HTTP MCP remains intentionally narrow while unauthenticated/public access exists.

## MCP Contract

Initial tools:

- `get_image_contract`: return templates, fields, defaults, dimensions, formats, and workflow guidance.
- `list_image_templates`: return concise template cards for agent selection.
- `normalize_image_spec`: validate and normalize model-friendly structured input.
- `render_image_preview`: return a bounded base64 data URL plus metadata for iteration.
- `export_image`: return base64 image content, content type, dimensions, byte size, and hash for saving into a repository.

Tools use typed fields, bounded text lengths, enum choices, safe errors, and JSON-serializable responses. They do not expose arbitrary filesystem, shell, database, or admin access.

## Web UI

The home page becomes an Agent Image Studio:

- Left column: MCP setup, endpoint, local stdio command, and account/API key state.
- Main column: structured image spec editor with template, dimensions, format, title, subtitle, eyebrow, font, and asset URL fields.
- Right column: rendered preview, metadata, warnings, copy/download actions, and empty/error states.

The interface should feel like a quiet developer tool: restrained colors, system typography, 8px radii, visible focus states, practical density, and no decorative card grids or marketing sections.

## Removals

The implementation removes `/g` routing and updates code that depended on it, including SEO helpers, docs, tests, signing examples, and old generator JavaScript. Site-level Open Graph images should use static assets or the new service path, not the removed URL API.

## Testing

Verification should cover:

- FastMCP tool discovery and core tool calls through an in-memory `fastmcp.Client`.
- Invalid specs, long text bounds, missing/invalid asset URLs, formats, and dimensions.
- The new studio render API.
- `/g` no longer being available.
- Frontend build and focused Django tests.
