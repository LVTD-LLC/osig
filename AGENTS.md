# OSIG Agent Guide

## Scope

This file is the vendor-neutral operating manual for AI coding agents working in this repository. Read it with `PRODUCT.md`, `VISION.md`, `TECH.md`, `STRUCTURE.md`, and `DESIGN.md` before making product or architectural changes.

## Project Summary

OSIG is the Open Source Social Image Generator. The long-term direction is AI-agent-first image infrastructure: agents should be able to discover supported image templates, provide structured text and asset inputs, render deterministic previews, and either save image bytes into a project or create signed public Open Graph image URLs.

The hosted cloud product should be paid by default for production use. The repository remains open source and self-hostable, but hosted MCP/API access should not become an unlimited free utility.

## Product Direction

- Treat MCP and API workflows as the primary product surface.
- Treat the web UI as a playground, docs, account, billing, and diagnostics surface.
- Treat `/g` as a rendering and backwards-compatibility endpoint, not the main product concept for future work.
- Prefer deterministic code-generated images over model-generated images. The value is cost, repeatability, speed, and easy repo integration for agents.
- Start with Open Graph and social preview images, but keep boundaries clean enough for future code-generated image types.

## Reliable Commands

Install and run through Docker when possible:

```bash
cp .env.example .env
make serve
```

Run the Django shell:

```bash
make shell
```

Run migrations:

```bash
make migrate
make makemigrations
```

Run tests:

```bash
make test
make test core/tests/test_mcp.py
make test core/tests/test_generate_image_features.py
```

Run the local stdio MCP server:

```bash
uv run python mcp_server.py
```

Inspect the local MCP tool contract:

```bash
uv run fastmcp list --command "uv run python mcp_server.py"
```

Build frontend assets:

```bash
npm run build
```

## Development Workflow

- Use `rg` for code search.
- Read the existing implementation before changing behavior. The most important files are listed in `STRUCTURE.md`.
- Keep changes close to existing module boundaries.
- Add or update tests for behavior changes, especially MCP tools, `/g`, signing, usage quota, auth, and render error handling.
- Prefer `make test <path>` for focused verification and `make test` before finishing larger work.
- Do not stage unrelated files or revert user changes.

## AI-Agent-First Rules

- Tool contracts should be typed, discoverable, and safe for autonomous use.
- MCP tools should return machine-readable metadata, warnings, hashes, content types, dimensions, and stable URLs where useful.
- When adding image inputs, make them model-friendly: named fields, explicit enum choices, bounded text lengths, and clear validation errors.
- Keep preview and publish flows separate. Agents should be able to iterate cheaply, then create a signed public URL only when ready.
- Do not add arbitrary filesystem, shell, database, or admin tools to hosted MCP.
- Hosted MCP requests must stay authenticated with profile keys via `X-API-Key` or `Authorization: Bearer <key>`.
- Public URL parameters should use `key`, not `profile_id`.

## Pricing And Access Rules

- Open source/self-hosted usage can be free.
- Hosted production usage should require an account and paid entitlement.
- Watermarking is the default unpaid/free enforcement mechanism for rendered images.
- Quotas should remain visible and enforceable through profile usage records and response headers.
- Do not introduce new unlimited free hosted paths around watermark, quota, signing, or MCP authentication.
- Any free trial or demo should be deliberately bounded by quota, watermark, expiration, or non-production scope.

## Risky Actions

Ask for explicit approval before:

- Removing or breaking current public `/g` behavior without a migration plan.
- Weakening signature verification, MCP auth, API key handling, quotas, or watermark rules.
- Exposing generated images, profile keys, customer data, or render history across profiles.
- Adding new paid-plan behavior without making entitlement and failure states clear.
- Replacing deterministic rendering with model image generation as the default path.
- Changing deployment roles, CapRover app names, storage backends, or Stripe/dj-stripe behavior.

## Review Expectations

Before finishing meaningful changes, verify:

- MCP/API contracts still support agent-first discovery, preview, and publish flows.
- `/g` compatibility is preserved or intentionally documented as changed.
- Generated image layouts handle long text, missing images, invalid image URLs, and both `x` and `meta` dimensions.
- Quota, watermark, and signed URL behavior match `PRODUCT.md` and `TECH.md`.
- Docs and steering files stay in sync with code.
