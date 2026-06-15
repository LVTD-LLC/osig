# Job-board Template Pack v1

Wave 1 task [4/8] introduces three templates tuned for job board listings and role previews.

## Styles

- `job_classic`: image-first, dark overlay, high-contrast text
- `job_logo`: text + circular logo emphasis
- `job_clean`: minimal white layout with accent bar

## Supported fields

All templates accept:

- `title`
- `subtitle`
- `eyebrow`
- `image_or_logo` (alias for `image_url`)

The templates are available through MCP tools and the Agent Image Studio.

## Safe truncation

Long text is normalized and truncated before render:

- title: 110 chars
- subtitle: 180 chars
- eyebrow: 55 chars

This prevents overflow while keeping output deterministic for caching.

## Example spec

```json
{
  "style": "job_logo",
  "site": "x",
  "title": "Senior Django Engineer",
  "subtitle": "Ship production systems",
  "eyebrow": "Remote",
  "image_or_logo": "https://example.com/logo.png"
}
```
