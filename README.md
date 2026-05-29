# OG Image Generator Documentation

## Development

Python dependencies are managed with `uv`. For the Dockerized local stack, run:

```
make serve
```

The local backend and worker services use `Dockerfile-python`, and production deploys build one shared image from `deployment/Dockerfile`. At runtime, `APP_PROCESS_TYPE=server` starts Gunicorn and `APP_PROCESS_TYPE=worker` starts Django Q workers. For CapRover, set `APP_PROCESS_TYPE=server` on the `osig` app, `APP_PROCESS_TYPE=worker` on the `osig-workers` app, and the GitHub repository variable `WORKERS_APP_PROCESS_TYPE=worker`.

For local AI-agent iteration on generated images, OSIG also exposes a FastMCP stdio server:

```
uv run python mcp_server.py
```

See [docs/agent-mcp.md](docs/agent-mcp.md) for the tool contract and transport notes.

## How to use?

The OG Image Generator allows you to create custom Open Graph images for your website. You can specify various parameters to customize the image according to your needs.

### URL

The url for all images will be the same:

`https://osig.app/g/`

### Parameters

Parameters will vary depending on the style. All of them are optional, but if you don't pass anything it will look like sh\*t.

![OG Image Generator Parameters](https://osig.app/static/vendors/images/no-params-example.0b515a8143fb.png)

Below is a list of all parameters we currently support:

*   **key**: Your API key. Can be found in your [settings](/settings) page, if you are registered.
*   **style**: Image style (default: "base")
    *   \- [base](#base)
    *   \- [logo](#logo)
    *   \- [job_classic](#job-board-template-pack-v1)
    *   \- [job_logo](#job-board-template-pack-v1)
    *   \- [job_clean](#job-board-template-pack-v1)
*   **site**: This dictates the size of the image (default: "x")
    *   \- x (1600 by 900)
    *   \- meta (1200 by 630)
*   **font**: Font to use for text (more will be added)
    *   \- [helvetica](#Helvetica)
    *   \- [markerfelt](#Markerfelt)
    *   \- [papyrus](#Papyrus)
*   **title**: Main title text
*   **subtitle**: Subtitle text
*   **eyebrow**: Eyebrow text
*   **image\_url**: URL of the background image
*   **image\_or\_logo**: Alias for `image_url`, recommended for job-board templates where the asset can be either a hero image or company logo.
*   **format**: Output format (`png` or `jpeg`, default: `png`)
*   **quality**: Compression quality (`1-100`).
    * For `jpeg`: defaults to `85` if omitted.
    * For `png`: optional, controls compression level when provided.
*   **max_kb**: Optional target size in KB (best-effort, currently tuned for `jpeg`).
*   **v**: Optional cache-busting version token. Change this when you want social previews to refresh.
*   **exp** + **sig**: Optional expiry/signature pair for tamper-proof signed URLs (generated via `POST /api/sign`).

### Usage

The url for all images will be the same:

```
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:image" content="{ generated_image_url }"/>
```

### Examples

#### Base Style

This is useful for general pages like Articles, Tutorial, News pages. Pro tip, you can generate the background image using AI. Those work super well.

Here is what gets generated for my site's articles:

![Base OG Image Example](https://osig.app/static/vendors/images/base-example.73fce7ac82c5.png)

This is the that I use to generate the image:

```
https://osig.app/g?
  site=x
  &style=base
  &font=helvetica
  &title=10 Years of Great Books
  &subtitle=I'm starting a 10 Year Reading Plan proposed in the 1st Volume (The Great Conversation) of the "Great Books of the Western World" series.
  &eyebrow=Article
  &image_url=https://www.rasulkireev.com/_astro/a_smiling_boy_from_Pixars_Coco.DrP3G0Ol.png
```

#### Logo Style

Logo style is super useful if you are trying to highlight a company or a project, advertize job postings or anything like. Super minimalistic.

Here is how I use it for one of my job boards:

![Logo OG Image Example](https://osig.app/static/vendors/images/logo-example.818309c1b90d.png)

This is the that I use to generate the image:

```
https://osig.app/g?
  site=x
  &style=logo
  &font=markerfelt
  &title=Narrative
  &subtitle=Founding Senior Software Engineer
  &image_url=http://res.cloudinary.com/built-with-django/image/upload/v1728024021/user-profile-image-prod/hhxfplsthiaytuttoamc.jpg
```

#### Job-board template pack v1

Wave 1 ships three production-ready job-board styles:

- `job_classic`: full-bleed background + high-contrast copy
- `job_logo`: role-focused copy with circular logo slot
- `job_clean`: minimal white layout with accent bar and logo slot

All three templates support the same core fields:

- `title`
- `subtitle`
- `eyebrow`
- `image_or_logo` (alias for `image_url`)

Copy is safely truncated to keep layouts stable for long job titles/descriptions.

Example:

```
https://osig.app/g?
  site=x
  &style=job_logo
  &font=helvetica
  &title=Senior Django Engineer
  &subtitle=Build reliable product features and own the roadmap.
  &eyebrow=Remote · Full-time
  &image_or_logo=https://example.com/company-logo.png
```

### Fonts

*   Helvetica ![Helvetica Font Example](https://osig.app/static/vendors/images/helvetica-example.9d748f0e4cd3.png)
*   Markerfelt ![Markerfelt Font Example](https://osig.app/static/vendors/images/markerfelt-example.f0edc54d9ba4.png)
*   Papyrus ![Papyrus Font Example](https://osig.app/static/vendors/images/papyrus-example.03867e8bc712.png)

### Precautions

Once you insert this link on your site, make sure to test it before sharing links online. I like to use [this Twitter Card Validator](https://threadcreator.com/tools/twitter-card-validator)

### Notes

*   Subtitle text is truncated to 150 characters if longer.
*   You can remove the watermark by subscribing to the [PRO version](/pricing).

### Integrating into your Site

As people use this, I will start adding more specific instructions on how to add these to your specific site that might use different technologies:

*   Wordpress
*   Django
*   Astro
*   Ruby on Rails
*   Next.js
*   etc.

### API

#### 1) Generate signed OG URLs

Use this endpoint when you need tamper-proof URLs with expiration.

`POST /api/sign`

Request body example:

```json
{
  "params": {
    "style": "logo",
    "site": "x",
    "title": "Narrative",
    "subtitle": "Founding Senior Software Engineer",
    "image_url": "https://example.com/logo.png",
    "format": "jpeg",
    "quality": 80,
    "v": "2026-02-26"
  },
  "expires_in_seconds": 3600
}
```

Response shape:

```json
{
  "signed_url": "https://osig.app/g?...&exp=...&sig=...",
  "expires_at": "2026-02-26T12:34:56+00:00"
}
```

Validation rules on `GET /g`:

- Tampered signed params -> `403`
- Expired signed links -> `403`
- Unsigned links still work for backwards compatibility

#### 2) Output controls

`GET /g` now supports:

- `format=png|jpeg`
- `quality=1..100`
- `max_kb=<int>` (best-effort size targeting for jpeg)

Content type is set explicitly:

- PNG -> `image/png`
- JPEG -> `image/jpeg`

#### 3) Cache/versioning workflow

`GET /g` responses now include explicit cache headers.

- Unsigned URLs: `Cache-Control: public, max-age=31536000, immutable`
- Signed URLs: `Cache-Control: public, max-age=<seconds until exp>`

Use `v` to force cache key rotation without changing title/subtitle payload:

1. Keep your normal OG params.
2. When image content changes, bump `v` (for example, `v=2026-03-01`).
3. Re-embed/re-publish URLs with the new `v` value.
4. If using signed URLs, regenerate via `POST /api/sign` so `sig` matches the new params.

Social preview refresh checklist:

- Bump `v`
- Regenerate signed URL (if signed)
- Re-deploy metadata with the new URL
- Re-validate on social debuggers (X Card Validator / LinkedIn Post Inspector / Facebook Sharing Debugger)

### 4) Onboarding wizard helper

`GET /onboarding` now exposes a 5-step guided wizard that outputs:

- signed OG image URL (reuses `POST /api/sign`)
- copy-ready OG/Twitter meta tags
- validation links (X/Twitter, Facebook, LinkedIn, Google rich results)

Backend helper endpoint used by the wizard:

`POST /api/onboarding/meta`

Example:

```json
{
  "page_url": "https://example.com/jobs/senior-engineer",
  "style": "job_logo",
  "site": "x",
  "font": "helvetica",
  "title": "Senior Engineer",
  "subtitle": "Ship reliable backend systems",
  "eyebrow": "Remote · Full-time",
  "image_url": "https://example.com/logo.png",
  "format": "jpeg",
  "quality": 80,
  "version": "v2026-02-26"
}
```

Response:

```json
{
  "signed_url": "https://osig.app/g?...&exp=...&sig=...",
  "expires_at": "2026-02-26T12:34:56+00:00",
  "meta_tags": "<meta ... />\n<meta ... />",
  "validation_links": {
    "Twitter/X Card Validator": "https://cards-dev.twitter.com/validator?url=..."
  }
}
```

### 5) Usage metering + quota enforcement

Keyed requests to `/g` now include per-key usage metering with configurable limits.

Config via environment:

- `OSIG_DAILY_USAGE_LIMIT` (default: `1000`)
- `OSIG_MONTHLY_USAGE_LIMIT` (default: `10000`)
- `OSIG_USAGE_WARNING_PERCENT` (default: `0.8`)

Behavior:

- warns when usage crosses warning threshold (`X-OSIG-Quota-Warning`)
- blocks at configured quota with `429`
- exposes counters via:
  - `X-OSIG-Daily-Usage`
  - `X-OSIG-Monthly-Usage`

Backward compatibility:

- existing no-key `/g` flows remain unchanged

Admin visibility:

- usage records are visible in Django admin (`ProfileUsage`) and sorted by monthly usage for top-key visibility.

### 6) Reliability + observability

Render pipeline now ships with:

- structured error taxonomy
- transient retry policy
- render-attempt metrics for fail-rate + p95 visibility

Config:

- `OSIG_RENDER_MAX_ATTEMPTS` (default `2`)
- `OSIG_IMAGE_FETCH_TIMEOUT_SECONDS` (default `8`)

Observability endpoint (superuser API key required):

`GET /api/admin/render-metrics?api_key=<key>&hours=24`

Example response:

```json
{
  "window_hours": 24,
  "total_attempts": 120,
  "failed_attempts": 6,
  "fail_rate_percent": 5.0,
  "p95_render_ms": 284,
  "error_counts": {
    "transient_upstream_fetch": 4,
    "validation_error": 2
  }
}
```

### 7) WordPress helper MVP

`POST /api/integrations/wordpress` maps common WordPress fields to OSIG params and returns a ready signed URL.

- maps `post_title`, `post_name`, `excerpt/description`, `featured_image_url/featured_image/logo`
- supports `quality`, `max_kb`, `version` and cache-friendly URL parameters
- applies image fallback chain:
  1. `featured_image_url`
  2. `featured_image`
  3. `logo_url`
  4. `fallback_image_url`
  5. no image fallback

Returns:

- `signed_url`
- `expires_at`
- `mapped_fields`
- `fallbacks`
- `snippet` (PHP helper sample)

## Roadmap

- Add instruction on how to self host.
- Add more styles.
- Add more fonts.
- Add more sites.
