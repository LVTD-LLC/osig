# Studio Usage

The old public `/g` URL generator has been removed. Humans can exercise the same structured image spec used by MCP tools through the Studio render API and account setup surfaces.

## Workflow

1. Compose a canvas with dimensions, background fill, format, and ordered text/image/rectangle layers.
2. Render a preview through `POST /api/studio/render`.
3. Inspect normalized spec metadata, warnings, quota/watermark state, hashes, and output dimensions.
4. Export through MCP when committing final image bytes into a target project.
5. Reference the committed asset in Open Graph and Twitter metadata.

Fonts can be bundled ids such as `helvetica`, or Google Fonts provider values such as `google:inter`, `google:open-sans`, and `google:playfair-display`. Provider fonts are fetched on first render and cached locally.

Rectangle layers support solid fills, linear gradients, borders, shadows, opacity, and radius. Image layers accept HTTPS URLs or bounded inline base64 sources through the same `src` object used by MCP.

## Output

Studio renders return:

- content type
- dimensions
- byte size
- SHA-256 hash
- base64 image bytes
- warnings
- optional quota state for keyed profiles

Use MCP for autonomous agent workflows and Studio for manual preview/debugging.
