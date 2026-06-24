# Product Guardrails

Use this checklist when proposing or reviewing new OSIG features.

## Proposal Checklist

Every new feature proposal should state:

- How it preserves structured inputs over prompt-only inputs.
- How output remains deterministic for the same normalized spec.
- Whether it affects MCP, Studio API, docs, renderer, quota, watermark, or export behavior.
- Whether hosted cloud use remains bounded by account, quota, watermark, expiration, or paid entitlement.
- Why it does not make OSIG a Canva-style design editor.
- Why it does not make model image generation the default path.

## Allowed Direction

- MCP and API workflows are the primary product surface.
- The web UI supports setup, docs, billing, examples, diagnostics, and Studio debugging.
- Templates should compile to bounded canvas specs.
- New primitives should be typed, documented, validated, and tested.

## Stop Conditions

Ask for a product decision before:

- Reintroducing public `/g` query-string generation.
- Adding unauthenticated hosted production rendering paths.
- Exposing private, billing, admin, cross-profile, filesystem, shell, or database capabilities through MCP.
- Making generated images depend on a model image provider by default.
