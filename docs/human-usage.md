# Studio Usage

The old public `/g` URL generator has been removed. Humans now use the Agent Image Studio on the home page to exercise the same structured image spec used by MCP tools.

## Workflow

1. Open the Studio.
2. Choose a template, dimensions, format, font, and copy fields.
3. Render a preview.
4. Copy the repository payload or download the generated image.
5. Commit the image into the target project and reference that asset in Open Graph and Twitter metadata.

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
