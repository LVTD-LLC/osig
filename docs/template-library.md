# OG Template Library

OSIG templates are deterministic canvas spec starters returned by `get_image_contract`. They do not replace the canvas renderer and do not create public image URLs. Agents can inspect a template `example_specs` entry, adapt its ordinary canvas layers, then preview and export through the normal render flow.

## Contract Shape

```json
{
  "template_library": [
    {
      "id": "product_update",
      "supported_sites": ["x", "meta"],
      "output_formats": ["png", "jpeg"],
      "example_specs": {
        "x": { "site": "x", "layers": [] },
        "meta": { "site": "meta", "layers": [] }
      }
    }
  ]
}
```

Template example specs include layers for:

```json
{
  "title": "Launch agent-ready OG images",
  "subtitle": "Preview, export, and commit deterministic assets.",
  "site_name": "OSIG",
  "logo": { "type": "url", "url": "https://example.com/logo.png" },
  "image": { "type": "url", "url": "https://example.com/preview.png" },
  "tags": ["MCP", "Open Graph"]
}
```

Agents should replace these slots in the returned canvas layers, then call `normalize_image_spec`.

## Templates

| ID | Use | Slots |
| --- | --- | --- |
| `repo_preview` | Technical repo, launch, or docs card | `title`, `subtitle`, `site_name`, `logo`, `tags` |
| `article_summary` | Post, essay, docs, or changelog card | `title`, `subtitle`, `site_name`, `image`, `tags` |
| `product_update` | Feature or product announcement | `title`, `subtitle`, `site_name`, `logo`, `image`, `tags` |

Each template supports both `x` and `meta` dimensions and returns ordinary canvas layers. Optional images use the same `src` object as image layers, so HTTPS and inline base64 validation stays consistent with the renderer.

## Slot Bounds

- `title`: 1 to 140 characters.
- `subtitle`: up to 260 characters.
- `site_name`: up to 80 characters.
- `tags`: up to 4 tags, each up to 32 characters.
- `logo` and `image`: optional OSIG image sources.

Long text is clamped by the returned canvas spec so layouts remain deterministic.
