import json
import tempfile
from pathlib import Path

from django.conf import settings


def pytest_configure(config):
    settings.STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
    manifest_path = Path(tempfile.gettempdir()) / "osig-test-webpack-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "css/index.css": "/static/css/index.css",
                "js/index.js": "/static/js/index.js",
                "entrypoints": {
                    "index": {
                        "assets": {
                            "css": ["/static/css/index.css"],
                            "js": ["/static/js/index.js"],
                        }
                    }
                },
            }
        )
    )
    settings.WEBPACK_LOADER["MANIFEST_FILE"] = manifest_path
