# Usage Metering + Quota Enforcement

Per-key metering and configurable quota enforcement apply to agent image renders that resolve a valid profile key.

## What is tracked

For requests that include a valid `key`:

- daily usage count
- monthly usage count
- warning sent flags (daily/monthly)

Storage model: `ProfileUsage` (one row per API key/profile).

## Enforcement rules

- warning threshold: `OSIG_USAGE_WARNING_PERCENT` (default `0.8`)
- hard block: at 100% of configured limit
- blocked requests return `429`

Configurable limits:

- `OSIG_DAILY_USAGE_LIMIT` (default `1000`)
- `OSIG_MONTHLY_USAGE_LIMIT` (default `10000`)

## API response metadata

When a keyed Studio request is accepted, quota state is returned in the JSON payload:

- `daily_count`
- `daily_limit`
- `monthly_count`
- `monthly_limit`
- `warnings`
- `blocked`

MCP tool responses include the same quota metadata when a render is accepted.

Render responses also include an `access` object for agents:

- `mode`: `trial` or `keyed`
- `profile_key_supplied`
- `profile_resolved`
- `paid_entitlement`
- `entitlement_reason`
- `watermark.applied`
- `watermark.reason`
- `quota.tracked`
- `quota.state`

The account settings page shows the same hosted access posture: plan, watermark state, daily quota, and monthly quota.

## Trial behavior

No-key trial renders remain watermarked and do not resolve paid watermark state. Invalid keys also fall back to watermarked trial output and return a warning plus `access.entitlement_reason=invalid_profile_key`.

## Admin visibility

`ProfileUsage` is registered in Django admin and sorted by `monthly_count` descending for quick top-key visibility.
