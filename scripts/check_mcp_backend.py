"""Offline checks for the eComBot external backend functions.

This does not require the MCP runtime. It validates the same data functions
that the FastMCP server exposes as tools.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.services.mcp_servers.ecom_backend_data import (  # noqa: E402
    cancel_order_data,
    check_stock_data,
    get_order_details_data,
    get_order_status_data,
    list_variants_data,
)


def _print_case(title: str, result: dict) -> None:
    print(f"## {title}")
    for key, value in result.items():
        print(f"{key}: {value}")
    print()


def main() -> None:
    _print_case("order status success", get_order_status_data("ORD-001"))
    _print_case("order details success", get_order_details_data("ORD-002"))
    _print_case("order not found", get_order_status_data("ORD-999"))
    _print_case("order timeout simulation", get_order_status_data("ORD-TIMEOUT"))
    _print_case("stock success", check_stock_data("PRD-101"))
    _print_case("variants success", list_variants_data("BassPro"))
    _print_case("cancel preview", cancel_order_data("ORD-002", confirm=False))


if __name__ == "__main__":
    main()
