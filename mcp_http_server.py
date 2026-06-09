import os


def _port() -> int:
    return int(os.getenv("MCP_PORT", "8765"))


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "osig.settings")

    import django

    django.setup()

    from core.mcp import mcp

    mcp.run(
        transport="http",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=_port(),
        path=os.getenv("MCP_PATH", "/mcp"),
    )


if __name__ == "__main__":
    main()
