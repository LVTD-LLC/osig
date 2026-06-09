# ruff: noqa: E402

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "osig.settings")

import django

django.setup()

from core.mcp import mcp


def _port() -> int:
    return int(os.getenv("MCP_PORT") or os.getenv("PORT") or "8765")


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=_port(),
        path=os.getenv("MCP_PATH", "/mcp"),
    )
