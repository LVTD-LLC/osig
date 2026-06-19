# Agent Canvas Renderer

## Context

OSIG currently exposes deterministic agent image generation through a template-shaped contract. Agents choose a fixed style and fill known fields such as title, subtitle, eyebrow, font, and image URL. That is useful for constrained social previews, but it keeps layout authority inside OSIG instead of giving agents direct composition primitives.

The next version should replace the template contract with a deterministic canvas contract. There are no current external users to preserve compatibility for, so the product can remove obsolete template code and documentation rather than keep a parallel compatibility surface.

## Product Goal

Give AI agents a typed canvas they can control directly: place text, images, and visual shape/color layers at explicit coordinates, render deterministic previews, inspect metadata, and export final PNG/JPEG bytes.

The renderer should remain code-generated, repeatable, cheap, bounded, and safe for hosted MCP/API use.

## Non-Goals

- Do not build a general-purpose human design editor.
- Do not accept arbitrary local file paths from public MCP/API callers.
- Do not make rendering depend on model-generated images.
- Do not preserve the old template/style API after the replacement lands.
- Do not expose private, admin, filesystem, shell, database, or render-history MCP tools.

## Decisions

- Replace the current template model rather than adding canvas as an advanced mode.
- Render a structured JSON canvas spec with Pillow.
- Support `x` and `meta` social presets plus bounded custom dimensions.
- Let agents manually place text boxes while OSIG wraps and clamps text within the requested box.
- Let image layers use HTTPS URLs or bounded inline base64 image payloads.
- Support background color, shape layers, gradients, borders, shadows, and opacity.
- Keep quota, watermark, profile-key, retry, observability, output metadata, and export behavior attached to the shared render path.

## Canvas Spec Requirements

The public image spec should contain:

- `site`: optional social preset, currently `x` or `meta`.
- `width` and `height`: optional custom dimensions. If omitted, dimensions come from `site`.
- `background`: optional canvas fill. Solid color is required; gradients are allowed if represented by the same fill model as shape layers.
- `layers`: ordered drawing operations. Later layers render above earlier layers.
- `format`: `png` or `jpeg`.
- `quality`, `max_kb`, `v`, and `key`: keep the existing export, caller bookkeeping, and profile/quota semantics.

Custom dimensions should be bounded. The first version should support dimensions from `200px` to `2000px` on each side, with a maximum pixel area cap to protect hosted rendering.

Layer counts, text lengths, inline image byte sizes, remote image response sizes, shadow blur, border width, radius, opacity, and font sizes should all have explicit validation limits.

## Layer Requirements

### Text

Text layers should support:

- `kind: "text"`.
- `x`, `y`, `width`, and optional `height`.
- `text`.
- `font`, including existing bundled fonts and approved provider-backed font values such as `google:inter`.
- `font_size`.
- `color`.
- Optional `line_height`.
- Optional `align`: `left`, `center`, or `right`.
- Optional `valign`: `top`, `middle`, or `bottom`.
- Optional `opacity`.
- `overflow: "clamp"` as the default behavior.

Renderer behavior:

- Wrap words within `width`.
- Clamp text when it exceeds the provided height or canvas bounds.
- Return warnings when text is clamped.
- Keep output deterministic for the same normalized spec.

### Image

Image layers should support:

- `kind: "image"`.
- `x`, `y`, `width`, `height`.
- `src` as either an HTTPS URL or bounded inline base64.
- `fit`: `cover`, `contain`, `fill`, or `none`.
- Optional `opacity`.
- Optional `radius`.

Renderer behavior:

- Fetch remote images with the existing timeout/retry/error taxonomy.
- Reject non-HTTPS public URLs.
- Decode base64 only up to the configured size limit.
- Return warnings or structured errors for unsupported image input.

### Shape

Shape layers should support:

- `kind: "rect"` for the first version.
- `x`, `y`, `width`, `height`.
- `fill` as a solid color or linear gradient.
- Optional `opacity`.
- Optional `radius`.
- Optional `border` with color and width.
- Optional `shadow` with x/y offset, blur, and color.

Renderer behavior:

- Draw rounded rectangles deterministically.
- Clip borders, shadows, and fills consistently within the canvas.
- Keep gradient inputs bounded and explicit.

## MCP/API Requirements

The MCP source of truth remains `agent_images/mcp.py`.

Required MCP tools:

- `get_image_contract`: returns canvas schema, supported dimensions, layer kinds, fill models, font choices, image source rules, limits, output formats, access notes, and workflow.
- `normalize_image_spec`: validates and canonicalizes a canvas spec without rendering.
- `render_image_preview`: renders a preview and returns metadata plus optional base64 bytes.
- `export_image`: renders final image bytes for repository updates or publishing workflows.

Removed MCP tool:

- `list_image_templates`.

Studio render API should consume the same canvas spec as MCP. It should not maintain a separate template-only path.

## Documentation Requirements

Update these docs and steering files with the canvas-first model:

- `PRODUCT.md`
- `TECH.md`
- `STRUCTURE.md`
- `DESIGN.md`
- `AGENTS.md`
- `docs/agent-mcp.md`
- `docs/human-usage.md` if Studio examples change

Remove or rewrite references to choosing fixed templates/styles. Keep wording explicit that OSIG is still not a general-purpose design editor; it is a deterministic bounded canvas renderer for agent-generated social images.

## Deletion Requirements

Remove unused code once the replacement lands:

- Template style definitions and template listing.
- Old `StyleName` and `STYLE_CHOICES`.
- Old template-specific render functions if they are no longer reachable.
- Old tests that assert template behavior.
- Documentation examples that pass `style`, `title`, `subtitle`, `eyebrow`, `image_url`, or `image_or_logo` as top-level template fields.

Keep shared pieces that still serve the canvas renderer:

- Font loading and provider-font normalization.
- Image dimension presets.
- Remote image fetching where reused by image layers.
- Output encoding.
- Watermarking.
- Usage quota tracking.
- Render observability and retry classification.
- Profile-key authentication helpers.

## Acceptance Criteria

- Agents can discover the full canvas contract from MCP without reading docs.
- Agents can render an image with only a background and one text layer.
- Agents can render ordered combinations of text, image, and rectangle layers.
- Agents can use `x`, `meta`, or bounded custom dimensions.
- Long text wraps and clamps with a warning rather than corrupting the image.
- Invalid layer input fails validation with specific field-level errors.
- HTTPS and inline base64 image inputs work within configured limits.
- Non-HTTPS remote image URLs and oversized inline images are rejected.
- Preview and export responses include width, height, content type, extension, byte size, hash, render time, warnings, and usage metadata.
- Free/unpaid hosted renders remain watermarked and quota-tracked.
- Old template MCP tool and unreachable template renderer code are removed.
- Focused MCP, service, renderer, quota, and Studio API tests pass.
