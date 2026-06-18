# Reliability + Observability for Render Pipeline

Wave 1 task [7/8] adds structured reliability handling and render observability.

## Error taxonomy

Render failures are now classified into explicit categories:

- `transient_upstream_fetch`
- `upstream_fetch_5xx`
- `upstream_fetch_4xx`
- `image_decode_error`
- `validation_error`
- `render_error`
- `unknown_error`

## Retry policy

The shared `agent_images.services.render_image` pipeline retries transient failures.

Config:

- `OSIG_RENDER_MAX_ATTEMPTS` (default: `2`)
- `OSIG_IMAGE_FETCH_TIMEOUT_SECONDS` (default: `8`)

Behavior:

- retries only transient categories (`transient_upstream_fetch`, `upstream_fetch_5xx`)
- non-transient errors fail fast
- final Studio API failure returns `502` with the classified error type; MCP calls surface the same render failure through the tool error path

## Observability model

New model: `RenderAttempt`

Each render attempt tracks:

- profile/key
- renderer
- success/failure
- error type
- duration in ms
- attempt number

## Dashboard endpoint

Admin-only endpoint:

`GET /api/admin/render-metrics?api_key=<superuser_key>&hours=24`

Returns:

- `total_attempts`
- `failed_attempts`
- `fail_rate_percent`
- `p95_render_ms`
- `error_counts`

## Admin visibility

`RenderAttempt` is registered in Django admin for pipeline debugging.
