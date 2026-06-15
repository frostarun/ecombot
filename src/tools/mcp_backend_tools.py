"""ADK MCP toolset factory for eComBot external backend integrations."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def mcp_tools_enabled() -> bool:
    return os.getenv("ECOMBOT_ENABLE_MCP_TOOLS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def mcp_server_url() -> str:
    """Return the Streamable HTTP MCP endpoint."""
    configured_url = os.getenv("ECOMBOT_MCP_URL")
    if configured_url:
        return configured_url.rstrip("/")

    host = os.getenv("ECOMBOT_MCP_HOST", "127.0.0.1")
    port = os.getenv("ECOMBOT_MCP_PORT", "8775")
    return f"http://{host}:{port}/mcp"


def get_mcp_toolsets(root_dir: Path) -> list[Any]:
    """Return MCP toolsets when ADK's MCP extra is installed."""
    if not mcp_tools_enabled():
        return []

    try:
        from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
    except (ImportError, AttributeError) as exc:
        log.warning(
            "MCP tools are enabled but unavailable. Install requirements with "
            "`pip install -r requirements.txt`. Detail: %s",
            exc,
        )
        return []

    timeout = float(os.getenv("ECOMBOT_MCP_TIMEOUT_SECONDS", "8"))
    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=mcp_server_url(),
                timeout=timeout,
            ),
        )
    ]
