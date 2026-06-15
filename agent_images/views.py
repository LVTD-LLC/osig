from __future__ import annotations

import json
from json import JSONDecodeError

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from .services import ImageRenderFailed, ImageSpec, ImageUsageLimitExceeded, render_image


def _profile_for_request(request: HttpRequest):
    if not request.user.is_authenticated:
        return None
    return request.user.profile


@require_POST
def render_studio_image(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, JSONDecodeError):
        return JsonResponse({"error": "invalid_json", "message": "Request body must be valid JSON."}, status=400)

    try:
        spec = ImageSpec.model_validate(payload.get("spec", payload))
        result = render_image(spec, profile=_profile_for_request(request), include_image_base64=True)
        return JsonResponse(result)
    except ValidationError as exc:
        return JsonResponse(
            {"error": "invalid_spec", "message": "Image spec is invalid.", "details": exc.errors()},
            status=400,
        )
    except PermissionError as exc:
        return JsonResponse({"error": "forbidden", "message": str(exc)}, status=403)
    except ImageUsageLimitExceeded as exc:
        return JsonResponse(
            {
                "error": "quota_exceeded",
                "message": "Usage quota exceeded.",
                "usage": {
                    "daily_count": exc.usage_state.daily_count,
                    "daily_limit": exc.usage_state.daily_limit,
                    "monthly_count": exc.usage_state.monthly_count,
                    "monthly_limit": exc.usage_state.monthly_limit,
                    "blocked_reasons": exc.usage_state.blocked_reasons,
                },
            },
            status=429,
        )
    except ImageRenderFailed as exc:
        return JsonResponse(
            {"error": "render_failed", "message": "The image could not be rendered.", "error_type": exc.error_type},
            status=502,
        )
