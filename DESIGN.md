# Design

## Summary

OSIG uses a restrained product UI system for a public utility site. The interface should make the generator, documentation, onboarding wizard, pricing, and account settings feel like one practical workflow.

## Visual Theme

- Mood: clear technical workspace, calm publishing utility, direct copy.
- Surfaces: light neutral background, white working panels, soft secondary panels for supporting context.
- Shape: 8px radius for panels, controls, previews, and repeated items.
- Chrome: borders over shadows; use framing only where it helps identify a tool, form, preview, or plan.

## Color

Tokens live in `frontend/src/styles/index.css` and use OKLCH values.

- `--osig-bg`: page background.
- `--osig-surface`: primary content surface.
- `--osig-surface-soft`: secondary surface.
- `--osig-ink`: primary text.
- `--osig-muted`: body and helper text.
- `--osig-accent`: primary action blue.
- `--osig-olive` and `--osig-amber`: logo-informed supporting colors.
- `--osig-danger`, `--osig-success`, `--osig-warning`: semantic states.

## Typography

Use the system sans stack for all product UI. Headings rely on weight and compact tracking, not decorative fonts. Body copy should stay direct and specific, with line lengths capped on documentation and article surfaces.

## Components

- Buttons: `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-ghost`.
- Forms: `.field-label`, `.field`, `.field-help`, `.copy-field`.
- Layout: `.site-container`, `.site-container-narrow`, `.panel`, `.panel-soft`.
- Content: `.page-kicker`, `.page-title`, `.section-title`, `.lede`, `.doc-prose`, `.code-block`.
- Workflow: `.step-pill`, `.wizard-step-indicator`.

## Interaction

Motion is limited to short state transitions on navigation, buttons, dropdowns, wizard progress, generator status, and toasts. Reduced motion users receive instant or near-instant transitions. Generated preview and wizard states should always communicate what is happening in text, not color alone.

## Accessibility

Target WCAG AA contrast, visible focus states, keyboard reachable controls, semantic sections, useful button labels, and non-color state indicators. Keep generated URLs and code blocks copyable and horizontally scrollable on small screens.
