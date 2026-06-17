"""PostgreSQL-backed product tools for eComBot."""

import logging
import re
from typing import Any

from google.adk.tools import ToolContext

from ..services.db import query_one

log = logging.getLogger(__name__)

PRODUCT_ID_PATTERN = re.compile(r"^PRD-\d{3}$")


def lookup_product(product_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Look up a product by ID or name in PostgreSQL.

    Args:
        product_name: Product ID such as PRD-101, or a product name/search term.

    Returns:
        Structured product data [product_id, product_name, category, price, currency,stock_status, 
        active, description, warranty,updated_at], or a safe error dict.
    """
    if not product_name or not product_name.strip():
        return {"found": False, "error": "Product name or ID cannot be empty."}

    lookup_key = product_name.strip()
    product_id_search = PRODUCT_ID_PATTERN.fullmatch(lookup_key.upper()) is not None

    try:
        if product_id_search:
            row = query_one(
                """
                SELECT product_id, product_name, category, price, currency,
                       stock_status, active, description, warranty,
                       updated_at::text AS updated_at
                FROM products
                WHERE product_id = %s
                """,
                (lookup_key.upper(),),
            )
        else:
            row = query_one(
                """
                SELECT product_id, product_name, category, price, currency,
                       stock_status, active, description, warranty,
                       updated_at::text AS updated_at
                FROM products
                WHERE LOWER(product_name) LIKE LOWER(%s)
                   OR LOWER(category) LIKE LOWER(%s)
                ORDER BY active DESC, product_id ASC
                LIMIT 1
                """,
                (f"%{lookup_key}%", f"%{lookup_key}%"),
            )
    except Exception as exc:
        log.error("Product lookup failed: %s", exc)
        return {
            "found": False,
            "error": "Product lookup is temporarily unavailable. Please try again shortly.",
        }

    if row is None:
        return {
            "found": False,
            "lookup_key": lookup_key,
            "error": f"No product found for '{lookup_key}'.",
        }

    tool_context.state["current_product_id"] = row["product_id"]
    tool_context.state["last_intent"] = "lookup_product"
    tool_context.state["last_lookup_key"] = lookup_key

    return {
        "found": True,
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "category": row["category"],
        "price": float(row["price"]),
        "currency": row["currency"],
        "stock_status": row["stock_status"],
        "active": row["active"],
        "description": row["description"],
        "warranty": row["warranty"],
        "updated_at": row["updated_at"],
    }
