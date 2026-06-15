import json

import pytest


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/g"),
        ("post", "/api/sign"),
        ("post", "/api/onboarding/meta"),
        ("post", "/api/integrations/wordpress"),
        ("get", "/onboarding"),
    ],
)
def test_legacy_url_generation_endpoints_are_removed(client, method, path):
    request = getattr(client, method)
    kwargs = {}
    if method == "post":
        kwargs = {"data": json.dumps({}), "content_type": "application/json"}

    response = request(path, **kwargs)

    assert response.status_code == 404
