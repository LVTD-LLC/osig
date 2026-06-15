# ruff: noqa: E402

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "osig.settings")

import django

django.setup()

from agent_images.mcp import mcp

if __name__ == "__main__":
    mcp.run()
