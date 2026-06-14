# Vision

## Long-Term Direction

OSIG should become the cheapest reliable way for personal AI agents to create social preview images and related code-generated visuals. The agent should not need a design model for every Open Graph image. It should call a tool, pass structured content, inspect a deterministic result, and commit or publish the asset.

The product exists in a future where each person has an AI agent that builds apps, edits repos, and performs publishing work. OSIG gives those agents a narrow, useful capability: generate good-looking images with code instead of spending model tokens and image-generation credits.

## Product Shape

The primary interface is a hosted MCP/API service. The web app supports that service with account setup, API keys, billing, docs, examples, diagnostics, and a playground. The old direct `/g` endpoint can remain as a compatibility and rendering surface, but new product thinking should not revolve around users hand-building query strings.

## What Should Never Drift

- OSIG is deterministic image generation infrastructure, not an AI image model.
- Agents are first-class users.
- Structured inputs beat prompt-only inputs.
- The hosted cloud service is paid by default for production use.
- Open source self-hosting remains valid.
- Tool contracts stay explicit, typed, inspectable, and safe.
- Generated images must be useful in real social metadata, not just impressive in demos.

## Strategic Bets

- AI agents will choose cheaper deterministic tools when they produce good enough output.
- Open Graph images are an ideal first wedge because they are repetitive, structured, and expensive to generate manually at scale.
- MCP makes image generation available inside coding workflows where the resulting asset or metadata can be committed immediately.
- Watermarking plus quotas is a practical boundary between open/demo usage and paid hosted production usage.

## Non-Goals

- Do not become a Canva clone.
- Do not become a generic image-generation model wrapper.
- Do not optimize first for anonymous web traffic.
- Do not expose broad infrastructure controls through MCP.
- Do not make the hosted service free by accident through compatibility paths.

## Outcome-Level Success

- An agent can add polished OG images to a repo faster and cheaper than using a model.
- A developer can trust OSIG's signed URLs in production metadata.
- A self-hoster can adapt the open source renderer without relying on OSIG cloud.
- Paid hosted users understand what they are paying for: no watermark, higher quotas, reliable hosted generation, signed URLs, and agent-friendly tooling.
