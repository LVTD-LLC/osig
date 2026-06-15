# Design

## Summary

OSIG uses a restrained technical UI system for agent-first image infrastructure. The product should feel like a reliable developer tool: clear contracts, visible examples, copyable code, predictable billing, and fast diagnostics.

The generated images are also part of the product design. They should look polished enough for production social previews while remaining deterministic, template-driven, and safe under long text or missing assets.

## Interface Priority

- Lead with the agent/MCP/API workflow over a human hand-tuned generator.
- Use the web UI for setup, API keys, docs, Studio previews, usage, billing, and render health.
- Keep the Agent Image Studio as a playground for the same structured specs MCP tools consume.
- Prefer tables, code blocks, parameter inspectors, previews, and status panels over marketing sections.
- Make paid/free state, watermark behavior, quota, and export metadata visible.

## Visual Theme

- Mood: clear technical workspace, calm publishing utility, direct copy.
- Surfaces: light neutral background, white working panels, soft secondary panels for supporting context.
- Shape: 8px radius for panels, controls, previews, and repeated items.
- Chrome: borders over shadows; use framing only where it helps identify a tool, form, preview, code sample, or plan.
- Density: practical and scannable. Avoid oversized marketing compositions unless redesigning the public homepage intentionally.

## Color

Tokens live in `frontend/src/styles/index.css` and use OKLCH values.

- `--osig-bg`: page background.
- `--osig-surface`: primary content surface.
- `--osig-surface-soft`: secondary surface.
- `--osig-surface-tint`: subtle inline code and inactive step backgrounds.
- `--osig-ink`: primary text.
- `--osig-muted`: body and helper text.
- `--osig-soft`: low-emphasis labels and status text.
- `--osig-line`: borders.
- `--osig-accent`: primary action blue.
- `--osig-accent-strong`: links, hover states, and strong actions.
- `--osig-accent-soft`: selected states and light callouts.
- `--osig-olive` and `--osig-amber`: logo-informed supporting colors.
- `--osig-danger`, `--osig-success`, `--osig-warning`: semantic states.
- `--osig-code`: code block background.

## Typography

Use the system sans stack for all product UI. Headings rely on weight and hierarchy, not decorative fonts. Body copy should stay direct and specific, with line lengths capped on documentation and article surfaces.

Do not use viewport-width font scaling. Keep letter spacing at `0` in new compact UI; existing display headings can keep their current styling unless being redesigned.

## Components

- Buttons: `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-ghost`.
- Forms: `.field-label`, `.field`, `.field-help`, `.copy-field`.
- Layout: `.site-container`, `.site-container-narrow`, `.panel`, `.panel-soft`.
- Content: `.page-kicker`, `.page-title`, `.section-title`, `.lede`, `.doc-prose`, `.code-block`.
- Workflow: `.step-pill`, `.wizard-step-indicator`.
- Preview: `.preview-frame`.

Add new component classes only when the pattern repeats across pages. For one-off layouts, prefer Tailwind utility classes in the template.

## Generated Image Design

- Templates should be text-safe first: clamp, wrap, or truncate deliberately.
- Always test both `x` and `meta` dimensions.
- Missing `image_url` should produce a deliberate fallback, not a broken layout.
- Invalid remote images should fail or degrade consistently according to renderer behavior.
- Watermarks should be legible but not destructive; paid output should remove them cleanly.
- Avoid visual styles that look like generic AI art. The product promise is code-generated reliability.
- New templates should document their intended content type, required/optional fields, and truncation behavior.

## Interaction

Motion is limited to short state transitions on navigation, buttons, dropdowns, Studio status, and toasts. Reduced motion users receive instant or near-instant transitions.

Preview, quota, billing, validation, and wizard states should always communicate what is happening in text, not color alone. Errors should name the failing input or system boundary.

## Accessibility

Target WCAG AA contrast, visible focus states, keyboard reachable controls, semantic sections, useful button labels, and non-color state indicators. Keep generated URLs and code blocks copyable and horizontally scrollable on small screens.

Agent-facing JSON and docs should be accessible in the practical sense: stable field names, concise descriptions, copyable examples, and machine-readable enum choices.
