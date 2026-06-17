"""PostgreSQL-backed order tools for eComBot."""

import logging
import re
from typing import Any

from google.adk.tools import ToolContext

from ..services.db import execute, query_one

log = logging.getLogger(__name__)

ORDER_ID_PATTERN = re.compile(r"^ORD-\d{3}$")


def _normalize_order_id(order_id: str) -> str:
    return order_id.strip().upper()


def _invalid_order_id(order_id: str) -> bool:
    return not bool(ORDER_ID_PATTERN.fullmatch(_normalize_order_id(order_id or "")))


def save_customer_name(name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Store the customer's name in ADK session state."""
    if not name or not name.strip():
        return {"saved": False, "error": "Name cannot be empty."}

    cleaned_name = name.strip()
    tool_context.state["current_customer_name"] = cleaned_name
    tool_context.state["last_intent"] = "save_customer_name"
    return {"saved": True, "customer_name": cleaned_name}


def get_order_status(order_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Look up an order in PostgreSQL and update session working memory.

    Args:
        order_id: Order ID in the format ORD-001.

    Returns:
        Structured order data, or a safe error dict.
    """
    if not order_id or not order_id.strip():
        return {"found": False, "error": "Order ID cannot be empty."}

    normalized_order_id = _normalize_order_id(order_id)
    if _invalid_order_id(normalized_order_id):
        return {"found": False, "error": "Invalid order ID format."}

    try:
        row = query_one(
            """
            SELECT order_id, customer_name, status, eta, carrier, product_id,
                   product_name, quantity, total_amount, currency,
                   last_updated::text AS last_updated
            FROM orders
            WHERE order_id = %s
            """,
            (normalized_order_id,),
        )
    except Exception as exc:
        log.error("Order lookup failed: %s", exc)
        return {
            "found": False,
            "error": "Order lookup is temporarily unavailable. Please try again shortly.",
        }

    if row is None:
        return {
            "found": False,
            "order_id": normalized_order_id,
            "error": f"Order {normalized_order_id} not found.",
        }

    tool_context.state["current_order_id"] = normalized_order_id
    tool_context.state["current_customer_name"] = row["customer_name"]
    tool_context.state["last_intent"] = "get_order_status"
    tool_context.state["last_lookup_key"] = normalized_order_id

    return {
        "found": True,
        "order_id": row["order_id"],
        "customer_name": row["customer_name"],
        "status": row["status"],
        "eta": row["eta"],
        "carrier": row["carrier"],
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "quantity": row["quantity"],
        "total_amount": float(row["total_amount"]),
        "currency": row["currency"],
        "last_updated": row["last_updated"],
    }


def cancel_order(order_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Cancel an order if it is cancellable.

    Use ``order_id="current"`` to cancel the order stored in session state.
    """
    if not order_id or order_id.strip().lower() in ("", "current", "same order"):
        order_id = tool_context.state.get("current_order_id", "")

    if not order_id:
        return {
            "cancelled": False,
            "error": "No order ID provided or found in this session.",
        }

    normalized_order_id = _normalize_order_id(order_id)
    if _invalid_order_id(normalized_order_id):
        return {"cancelled": False, "error": "Invalid order ID format."}

    try:
        row = query_one(
            """
            SELECT order_id, customer_name, status, product_name
            FROM orders
            WHERE order_id = %s
            """,
            (normalized_order_id,),
        )
    except Exception as exc:
        log.error("Order cancellation lookup failed: %s", exc)
        return {
            "cancelled": False,
            "error": "Cancellation service is temporarily unavailable. Please try again shortly.",
        }

    if row is None:
        return {
            "cancelled": False,
            "order_id": normalized_order_id,
            "error": f"Order {normalized_order_id} not found.",
        }

    if row["status"].lower() == "cancelled":
        return {
            "cancelled": False,
            "order_id": normalized_order_id,
            "error": f"Order {normalized_order_id} is already cancelled.",
        }

    if row["status"].lower() == "delivered":
        return {
            "cancelled": False,
            "order_id": normalized_order_id,
            "error": f"Order {normalized_order_id} is already delivered and cannot be cancelled.",
        }

    try:
        execute(
            """
            UPDATE orders
            SET status = 'Cancelled',
                eta = 'Not applicable',
                carrier = 'None',
                last_updated = now()
            WHERE order_id = %s
            """,
            (normalized_order_id,),
        )
    except Exception as exc:
        log.error("Order cancellation update failed: %s", exc)
        return {
            "cancelled": False,
            "error": "Cancellation could not be saved. Please try again shortly.",
        }

    tool_context.state["current_order_id"] = normalized_order_id
    tool_context.state["current_customer_name"] = row["customer_name"]
    tool_context.state["last_intent"] = "cancel_order"
    tool_context.state["last_lookup_key"] = normalized_order_id

    return {
        "cancelled": True,
        "order_id": normalized_order_id,
        "customer_name": row["customer_name"],
        "product_name": row["product_name"],
        "message": f"Order {normalized_order_id} has been cancelled.",
    }
