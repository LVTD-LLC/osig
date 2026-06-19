# Studio Usage

The old public `/g` URL generator has been removed. Humans now use the Agent Image Studio on the home page to exercise the same structured image spec used by MCP tools.

## Workflow

1. Open the Studio.
2. Compose a canvas with dimensions, background fill, format, and ordered text/image/rectangle layers.
3. Render a preview.
4. Copy the repository payload or download the generated image.
5. Commit the image into the target project and reference that asset in Open Graph and Twitter metadata.

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
