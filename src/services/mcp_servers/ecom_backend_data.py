"""Mock external order and inventory backend used by the MCP server."""

from __future__ import annotations

import asyncio

ORDERS: dict[str, dict] = {
    "ORD-001": {
        "order_id": "ORD-001",
        "customer_name": "Priya Sharma",
        "status": "Shipped",
        "eta": "5 Jun 2026",
        "carrier": "BlueDart",
        "product_id": "PRD-101",
        "product_name": "Galaxy A55 5G",
        "quantity": 1,
        "total_amount": 38999.00,
        "currency": "INR",
        "items": [
            {"product_id": "PRD-101", "product_name": "Galaxy A55 5G", "quantity": 1}
        ],
    },
    "ORD-002": {
        "order_id": "ORD-002",
        "customer_name": "Priya Sharma",
        "status": "Processing",
        "eta": "7 Jun 2026",
        "carrier": "DTDC",
        "product_id": "PRD-104",
        "product_name": "BassPro Wireless Earbuds",
        "quantity": 2,
        "total_amount": 5998.00,
        "currency": "INR",
        "items": [
            {"product_id": "PRD-104", "product_name": "BassPro Wireless Earbuds", "quantity": 2}
        ],
    },
    "ORD-003": {
        "order_id": "ORD-003",
        "customer_name": "Ravi Patel",
        "status": "Delivered",
        "eta": "Already delivered",
        "carrier": "FedEx",
        "product_id": "PRD-102",
        "product_name": "Redmi Note 13 Pro",
        "quantity": 1,
        "total_amount": 24999.00,
        "currency": "INR",
        "items": [
            {"product_id": "PRD-102", "product_name": "Redmi Note 13 Pro", "quantity": 1}
        ],
    },
    "ORD-004": {
        "order_id": "ORD-004",
        "customer_name": "Aisha Mehta",
        "status": "Cancelled",
        "eta": "Not applicable",
        "carrier": "None",
        "product_id": "PRD-103",
        "product_name": "StreamMax 4K TV Decoder",
        "quantity": 1,
        "total_amount": 4999.00,
        "currency": "INR",
        "items": [
            {"product_id": "PRD-103", "product_name": "StreamMax 4K TV Decoder", "quantity": 1}
        ],
    },
}

INVENTORY: dict[str, dict] = {
    "PRD-101": {
        "product_id": "PRD-101",
        "sku": "GALAXY-A55-128-BLACK",
        "product_name": "Galaxy A55 5G",
        "available": True,
        "stock_count": 18,
        "warehouse": "BLR-01",
        "variants": ["Awesome Navy 128 GB", "Awesome Iceblue 128 GB"],
    },
    "PRD-102": {
        "product_id": "PRD-102",
        "sku": "REDMI-N13PRO-256-BLACK",
        "product_name": "Redmi Note 13 Pro",
        "available": True,
        "stock_count": 7,
        "warehouse": "BOM-02",
        "variants": ["Midnight Black 256 GB", "Arctic White 256 GB"],
    },
    "PRD-103": {
        "product_id": "PRD-103",
        "sku": "STREAMMAX-4K-DECODER",
        "product_name": "StreamMax 4K TV Decoder",
        "available": False,
        "stock_count": 0,
        "warehouse": "BLR-01",
        "variants": ["4K Decoder with Voice Remote"],
    },
    "PRD-104": {
        "product_id": "PRD-104",
        "sku": "BASSPRO-EARBUDS-BLACK",
        "product_name": "BassPro Wireless Earbuds",
        "available": True,
        "stock_count": 42,
        "warehouse": "DEL-03",
        "variants": ["Matte Black", "Pearl White", "Ocean Blue"],
    },
}


def _normalize(value: str) -> str:
    return (value or "").strip().upper()


def order_not_found(order_id: str) -> dict:
    normalized = _normalize(order_id)
    return {
        "found": False,
        "order_id": normalized,
        "error_type": "not_found",
        "message": f"No order found for {normalized}. Ask the customer to check the order ID.",
    }


def product_not_found(product_id_or_sku: str) -> dict:
    lookup = _normalize(product_id_or_sku)
    return {
        "found": False,
        "lookup_key": lookup,
        "error_type": "not_found",
        "message": f"No inventory record found for {lookup}. Ask for a valid product ID or SKU.",
    }


def get_order_status_data(order_id: str) -> dict:
    normalized = _normalize(order_id)
    if normalized == "ORD-TIMEOUT":
        return {
            "found": False,
            "order_id": normalized,
            "error_type": "timeout",
            "message": "The external order backend timed out. Ask the customer to try again shortly.",
        }

    order = ORDERS.get(normalized)
    if order is None:
        return order_not_found(order_id)

    return {
        "found": True,
        "order_id": order["order_id"],
        "status": order["status"],
        "eta": order["eta"],
        "carrier": order["carrier"],
        "product_id": order["product_id"],
        "product_name": order["product_name"],
    }


def get_order_details_data(order_id: str) -> dict:
    normalized = _normalize(order_id)
    order = ORDERS.get(normalized)
    if order is None:
        return order_not_found(order_id)
    return {"found": True, **order}


def cancel_order_data(order_id: str, confirm: bool = False) -> dict:
    normalized = _normalize(order_id)
    order = ORDERS.get(normalized)
    if order is None:
        return order_not_found(order_id)

    if order["status"].lower() == "delivered":
        return {
            "cancelled": False,
            "order_id": normalized,
            "error_type": "not_allowed",
            "message": f"Order {normalized} has already been delivered and cannot be cancelled.",
        }

    if order["status"].lower() == "cancelled":
        return {
            "cancelled": False,
            "order_id": normalized,
            "error_type": "not_allowed",
            "message": f"Order {normalized} is already cancelled.",
        }

    if not confirm:
        return {
            "cancelled": False,
            "order_id": normalized,
            "requires_confirmation": True,
            "message": f"Confirm before cancelling order {normalized}.",
        }

    order["status"] = "Cancelled"
    return {
        "cancelled": True,
        "order_id": normalized,
        "message": f"Order {normalized} has been cancelled in the external order backend.",
    }


def check_stock_data(product_id_or_sku: str) -> dict:
    lookup = _normalize(product_id_or_sku)
    product = INVENTORY.get(lookup)
    if product is None:
        product = next(
            (
                value
                for value in INVENTORY.values()
                if value["sku"].upper() == lookup or lookup in value["product_name"].upper()
            ),
            None,
        )

    if product is None:
        return product_not_found(product_id_or_sku)

    return {"found": True, **product}


def list_variants_data(product_id_or_name: str) -> dict:
    stock = check_stock_data(product_id_or_name)
    if not stock.get("found"):
        return stock
    return {
        "found": True,
        "product_id": stock["product_id"],
        "product_name": stock["product_name"],
        "variants": stock["variants"],
    }


async def simulated_slow_stock_data(product_id_or_sku: str, delay_seconds: float = 5.0) -> dict:
    await asyncio.sleep(delay_seconds)
    return check_stock_data(product_id_or_sku)
