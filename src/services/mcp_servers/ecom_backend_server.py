"""FastMCP server exposing eComBot order and inventory backend tools.

Run from the ecombot directory:

    python -m src.services.mcp_servers.ecom_backend_server

The default transport is Streamable HTTP. The ADK agent connects to
``http://<ECOMBOT_MCP_HOST>:<ECOMBOT_MCP_PORT>/mcp`` using ``McpToolset``.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

try:
    from .ecom_backend_data import (
        cancel_order_data,
        check_stock_data,
        get_order_details_data,
        get_order_status_data,
        list_variants_data,
        simulated_slow_stock_data,
    )
except ImportError:
    from ecom_backend_data import (  # type: ignore
        cancel_order_data,
        check_stock_data,
        get_order_details_data,
        get_order_status_data,
        list_variants_data,
        simulated_slow_stock_data,
    )


mcp = FastMCP(
    "ecombot-backend",
    log_level="WARNING",
    host=os.getenv("ECOMBOT_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("ECOMBOT_MCP_PORT", "8775")),
)


@mcp.tool()
def mcp_get_order_status(order_id: str) -> dict:
    """Get order status from the external order backend."""
    return get_order_status_data(order_id)


@mcp.tool()
def mcp_get_order_details(order_id: str) -> dict:
    """Get item-level order details from the external order backend."""
    return get_order_details_data(order_id)


@mcp.tool()
def mcp_cancel_order(order_id: str, confirm: bool = False) -> dict:
    """Cancel one order in the external order backend after confirmation."""
    return cancel_order_data(order_id, confirm=confirm)


@mcp.tool()
def mcp_check_stock(product_id_or_sku: str) -> dict:
    """Check product availability and stock from the external inventory backend."""
    return check_stock_data(product_id_or_sku)


@mcp.tool()
def mcp_list_variants(product_id_or_name: str) -> dict:
    """List available variants for a product from the external inventory backend."""
    return list_variants_data(product_id_or_name)


@mcp.tool()
async def mcp_slow_stock_check(product_id_or_sku: str, delay_seconds: float = 5.0) -> dict:
    """Simulate a slow inventory backend for timeout/error handling checks."""
    return await simulated_slow_stock_data(product_id_or_sku, delay_seconds)


if __name__ == "__main__":
    transport = os.getenv("ECOMBOT_MCP_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)
