# Agent Repository Publishing Workflow

Use this flow when an agent needs to generate an Open Graph or Twitter/X image, save it into a project, and update metadata in the same commit.

## Workflow

1. Call `get_image_contract` to confirm dimensions, layer kinds, limits, formats, and template specs.
2. Build a canvas spec directly or adapt a `template_library` example spec from `get_image_contract`.
3. Call `normalize_image_spec` and fix any validation errors or warnings before rendering.
4. Call `render_image_preview` with `include_image_base64=false` while iterating.
5. Call `export_image` only when the preview metadata and warnings are acceptable.
6. Save the returned bytes into the repository under a public/static asset path.
7. Point `og:image`, `twitter:image`, and schema image fields at the committed asset.

## Cache-Busting Asset Names

Use deterministic names so social platforms and CDNs can refresh when the image changes:

```text
public/og/<slug>-<image_sha256_prefix>.png
public/og/osig-agent-images-9f3a21c2.png
```

Prefer `sha256` from `export_image` for the suffix. If your framework fingerprints static assets during build, keep the source filename readable and let the framework add the final hash.

## Static HTML Metadata

```html
<meta property="og:image" content="https://example.com/og/osig-agent-images-9f3a21c2.png">
<meta property="og:image:width" content="800">
<meta property="og:image:height" content="450">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://example.com/og/osig-agent-images-9f3a21c2.png">
```

## Next.js Metadata

```ts
export const metadata = {
  openGraph: {
    images: [
      {
        url: "/og/osig-agent-images-9f3a21c2.png",
        width: 800,
        height: 450,
        alt: "OSIG agent image workflow",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og/osig-agent-images-9f3a21c2.png"],
  },
}
```

## Preview Validation Checklist

- `warnings` is empty or every warning is intentional.
- `output.width` and `output.height` match the target platform.
- `content_type` and `extension` match the file you plan to commit.
- `sha256` changes only when the rendered bytes change.
- Trial/watermark state is acceptable for the target environment.

Do not publish a preview response as a production asset. Use `export_image` for final bytes.
