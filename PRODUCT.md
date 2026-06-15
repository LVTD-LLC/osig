# Product

## Summary

OSIG is AI-agent-first infrastructure for generating deterministic social preview images from structured text, remote assets, and reusable code templates. The product lets an AI agent avoid expensive model image generation when the needed output is a clean Open Graph or Twitter card image.

The current app supports a hosted FastMCP server, a local stdio MCP entrypoint, a Studio render API, usage metering, quotas, Stripe subscriptions, and render observability. Future product work should make the MCP/API workflow the primary experience and keep the web UI focused on setup, docs, billing, examples, and diagnostics.

## Users

Primary users are AI agents working on behalf of developers, founders, publishers, indie hackers, marketers, and small teams. The agent needs to generate an image asset, embed an OG URL, or update repository metadata without asking a human to open a design tool.

Secondary users are humans configuring accounts, API keys, billing, self-hosting, templates, and validation. They need confidence that the generated image will be stable, cheap, and social-platform-ready.

## Problem

Agents can ask image models to generate social preview images, but that is often expensive, slow, inconsistent, and hard to revise precisely. Most OG images need layout, typography, background/logo placement, dimensions, and text handling more than they need generative art.

OSIG should give agents a cheaper path: provide text and parameters, render with code, inspect the result, and publish the output as image bytes saved into the target project.

## Core Workflows

- Agent discovers the image contract with MCP, chooses a template, normalizes parameters, renders previews, then saves a PNG/JPEG or creates a signed public URL.
- Agent updates a website repository by generating OG metadata, preview images, cache-busting versions, and validation links.
- Human signs up, retrieves an API key, checks usage/quota, manages billing, and reads integration docs.
- Self-hoster runs the open source app and adapts templates for private use.
- Admin investigates render failure rate, p95 render time, and recent generated images.

## What Good Looks Like

- An agent can generate a useful image without browsing the web UI.
- The available styles, dimensions, fields, defaults, warnings, and publish steps are machine-readable.
- Preview generation is cheap and repeatable.
- Final output is deterministic, cacheable, and safe to embed in production metadata.
- The hosted product makes paid access, watermark behavior, quotas, and entitlement states obvious.
- The codebase stays self-hostable and open source without making hosted cloud usage unlimited or free by default.

## Pricing Posture

OSIG cloud should be paid for production use. The open source code can remain free to run independently, but hosted MCP/API rendering should require an account and should be bounded by quota, watermark, expiration, or subscription state.

The default unpaid behavior is watermarking. Paid plans should remove watermarks and raise hosted usage limits. Free/demo access, if offered, should exist only to prove the workflow and should not become an unmetered production image CDN.

## In Scope

- MCP tools for image contract discovery, template listing, normalization, preview rendering, and final image export.
- API endpoints for render metrics and integration helpers that should not be exposed as unauthenticated MCP tools.
- Open Graph and social preview templates, starting with article, logo, and job-board styles.
- Deterministic code-rendered PNG/JPEG output.
- Usage metering, quota enforcement, paid access, watermarking, and deterministic export workflows.
- Human-facing setup, docs, playground, billing, account, validation, and observability screens.
- CMS/helper integrations when they map common content fields into OSIG's structured parameters.

## Out Of Scope

- Defaulting to model-generated images.
- A general-purpose design editor.
- A free unlimited hosted image rendering/CDN service.
- Arbitrary remote control through MCP, such as database browsing, shell execution, or file access.
- Complex brand-management suites until the agent-first OG workflow is clearly working.

## Brand Personality

Clear, practical, technical, and reliable. OSIG should sound like a tool an agent can use safely: specific inputs, explicit constraints, predictable results, and no vague marketing language.

## Success Criteria

- Agents can complete the discover, preview, publish loop with MCP alone.
- Hosted usage converts to paid plans because it is cheaper than model generation and easier than custom image code.
- Render failures are observable and actionable.
- New templates are easy to test against long text, missing images, invalid remote assets, and both supported dimensions.
- Human users understand the difference between open source self-hosting and paid hosted cloud access.
