# Human Usage

Use OSIG when you want a stable social preview image URL for a website page.

## Image URL

All generated images use:

```text
https://osig.app/g
```

Add query parameters to control the rendered image:

```text
https://osig.app/g?site=x&style=base&font=helvetica&title=Hello&subtitle=Short%20description
```

## Common Parameters

- `title`: main text.
- `subtitle`: supporting text.
- `eyebrow`: small label above the title.
- `image_url`: background image or logo URL.
- `image_or_logo`: alias for `image_url`, useful for job-board templates.
- `style`: `base`, `logo`, `job_classic`, `job_logo`, or `job_clean`.
- `site`: `x` or `meta`.
- `font`: `helvetica`, `markerfelt`, or `papyrus`.
- `format`: `png` or `jpeg`.
- `quality`: `1` to `100`, mostly useful for JPEG.
- `max_kb`: best-effort JPEG size target.
- `v`: cache-busting version token.

## Meta Tags

Use the generated URL in Open Graph and Twitter/X tags:

```html
<meta property="og:image" content="https://osig.app/g?site=x&style=base&title=Hello" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:image" content="https://osig.app/g?site=x&style=base&title=Hello" />
```

## Examples

Article preview:

```text
https://osig.app/g?site=x&style=base&font=helvetica&title=10%20Years%20of%20Great%20Books&subtitle=A%20reading%20plan&eyebrow=Article&image_url=https://example.com/cover.png
```

Job preview:

```text
https://osig.app/g?site=x&style=job_logo&font=helvetica&title=Senior%20Django%20Engineer&subtitle=Build%20reliable%20product%20features&eyebrow=Remote%20Full-time&image_or_logo=https://example.com/company-logo.png
```

## Cache Refresh

Social platforms cache images aggressively. When the image should change, update the `v` parameter:

```text
https://osig.app/g?title=Hello&v=2026-06-09
```

Unsigned `/g` URLs remain supported so existing templates keep working.
