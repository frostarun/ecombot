"""Chainlit UI adapter for the eComBot orchestrator."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import chainlit as cl
import litellm
from dotenv import load_dotenv
from google.genai import types

from src.agents.orchestrator_agent import delegation_trace, root_agent
from src.config.settings import ROOT_DIR
from src.services.redis_client import save_session_state
from src.services.session_service import make_runner

load_dotenv(ROOT_DIR / ".env")

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
os.environ.setdefault("LITELLM_LOG", "ERROR")
for _name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    _logger = logging.getLogger(_name)
    _logger.setLevel(logging.CRITICAL)
    _logger.propagate = False
litellm.suppress_debug_info = True

ORDER_ID_RE = re.compile(r"\bORD-\d{3}\b", re.IGNORECASE)
PRODUCT_ID_RE = re.compile(r"\bPRD-\d{3}\b", re.IGNORECASE)
BUDGET_RE = re.compile(
    r"(?:under|below|less than|upto|up to)\s*(?:inr|rs\.?)?\s*([\d,]+)",
    re.IGNORECASE,
)

EXPLAIN_TRIGGERS = (
    "show me how",
    "how did you",
    "how was this",
    "explain how",
    "walk me through",
)

SALES_HINTS = (
    "recommend",
    "suggest",
    "compare",
    "buy",
    "phone",
    "product",
    "alternative",
    "stock",
)

TOOL_LABELS = {
    "delegate_to_support_agent": "Route to Support specialist",
    "delegate_to_sales_agent": "Route to Sales specialist",
    "get_order_status": "Check order status",
    "cancel_order": "Cancel order",
    "save_customer_name": "Save customer name",
    "lookup_product": "Fetch product details",
    "mcp_get_order_status": "External order status",
    "mcp_get_order_details": "External order details",
    "mcp_cancel_order": "External cancellation",
    "mcp_check_stock": "Check inventory",
    "mcp_list_variants": "List variants",
    "mcp_slow_stock_check": "Slow inventory check",
}


def _message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _latest_id(pattern: re.Pattern[str], text: str) -> str | None:
    matches = pattern.findall(text or "")
    return matches[-1].upper() if matches else None


def _is_explainability_query(text: str) -> bool:
    lower = text.lower()
    return any(trigger in lower for trigger in EXPLAIN_TRIGGERS)


def _looks_like_sales_prompt(text: str) -> bool:
    lower = text.lower()
    return any(hint in lower for hint in SALES_HINTS)


def _budget_from_text(text: str) -> str | None:
    match = BUDGET_RE.search(text or "")
    if not match:
        return None
    return match.group(1).replace(",", "")


def _unwrap_response(response: Any) -> Any:
    if isinstance(response, dict) and "result" in response and len(response) == 1:
        return _unwrap_response(response["result"])

    if isinstance(response, dict) and "content" in response:
        content = response.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                try:
                    return json.loads(first["text"])
                except json.JSONDecodeError:
                    return response

    return response


def _to_json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def _record_response(
    responses: dict[str, list[dict[str, Any]]],
    tool_name: str,
    response: Any,
) -> None:
    payload = _unwrap_response(response)
    if isinstance(payload, dict):
        responses.setdefault(tool_name, []).append(payload)


def _tool_label(tool_name: str) -> str:
    return TOOL_LABELS.get(tool_name, tool_name.replace("_", " ").title())


def _contextual_prompt(prompt: str) -> str:
    context = []
    order_id = cl.user_session.get("current_order_id")
    product_id = cl.user_session.get("current_product_id")
    budget_band = cl.user_session.get("budget_band")
    budget_limit = cl.user_session.get("budget_limit")

    if order_id:
        context.append(f"Current order ID: {order_id}")
    if product_id:
        context.append(f"Current product ID: {product_id}")
    if budget_band:
        context.append(f"Preferred budget band: {budget_band}")
    if budget_limit:
        context.append(f"Budget limit: INR {budget_limit}")

    if not context:
        return prompt

    return (
        f"{prompt}\n\n"
        "Chainlit session context. Use only when relevant:\n"
        + "\n".join(f"- {item}" for item in context)
    )


def _update_session_context_from_prompt(prompt: str) -> dict[str, str]:
    updates = {}
    order_id = _latest_id(ORDER_ID_RE, prompt)
    product_id = _latest_id(PRODUCT_ID_RE, prompt)
    budget_limit = _budget_from_text(prompt)

    if order_id:
        cl.user_session.set("current_order_id", order_id)
        updates["Order"] = order_id
    if product_id:
        cl.user_session.set("current_product_id", product_id)
        updates["Product"] = product_id
    if budget_limit:
        cl.user_session.set("budget_limit", budget_limit)
        updates["Budget"] = f"INR {budget_limit}"

    return updates


def _update_session_context_from_tool(tool_name: str, payload: dict[str, Any]) -> None:
    if payload.get("order_id"):
        cl.user_session.set("current_order_id", str(payload["order_id"]).upper())
    if payload.get("product_id"):
        cl.user_session.set("current_product_id", str(payload["product_id"]).upper())
    if tool_name == "lookup_product" and payload.get("product_name"):
        cl.user_session.set("current_product_name", payload["product_name"])


def _order_card(order: dict[str, Any]) -> str:
    order_id = order.get("order_id")
    if not order_id:
        return ""

    fields = [
        ("Order ID", order_id),
        ("Status", order.get("status")),
        ("ETA", order.get("eta")),
        ("Carrier", order.get("carrier")),
        ("Product", order.get("product_name")),
        ("Quantity", order.get("quantity")),
    ]
    if order.get("total_amount") is not None:
        fields.append(("Total", f"{order.get('currency', 'INR')} {order['total_amount']}"))

    return _field_table("Order Card", fields)


def _product_card(product: dict[str, Any]) -> str:
    product_id = product.get("product_id")
    if not product_id:
        return ""

    price = ""
    if product.get("price") is not None:
        price = f"{product.get('currency', 'INR')} {product['price']}"

    return _field_table(
        "Product Card",
        [
            ("Product ID", product_id),
            ("Name", product.get("product_name")),
            ("Category", product.get("category")),
            ("Price", price),
            ("Stock", product.get("stock_status")),
            ("Warranty", product.get("warranty")),
        ],
    )


def _inventory_card(stock: dict[str, Any]) -> str:
    product_id = stock.get("product_id")
    if not product_id:
        return ""

    variants = stock.get("variants") or []
    if isinstance(variants, list):
        variants_text = ", ".join(str(item) for item in variants)
    else:
        variants_text = str(variants)

    return _field_table(
        "Inventory Card",
        [
            ("Product ID", product_id),
            ("Name", stock.get("product_name")),
            ("Available", stock.get("available")),
            ("Stock Count", stock.get("stock_count")),
            ("Warehouse", stock.get("warehouse")),
            ("Variants", variants_text),
        ],
    )


def _field_table(title: str, fields: list[tuple[str, Any]]) -> str:
    rows = []
    for key, value in fields:
        if value is None or value == "":
            continue
        rows.append(f"| {key} | {value} |")

    if not rows:
        return ""

    return "\n".join([f"### {title}", "", "| Field | Value |", "|---|---|", *rows])


def _build_cards(tool_responses: dict[str, list[dict[str, Any]]]) -> list[str]:
    cards = []

    for tool_name in ("get_order_status", "mcp_get_order_status", "mcp_get_order_details"):
        for payload in tool_responses.get(tool_name, []):
            card = _order_card(payload)
            if card:
                cards.append(card)

    for payload in tool_responses.get("lookup_product", []):
        card = _product_card(payload)
        if card:
            cards.append(card)

    for tool_name in ("mcp_check_stock", "mcp_list_variants"):
        for payload in tool_responses.get(tool_name, []):
            card = _inventory_card(payload)
            if card:
                cards.append(card)

    return cards


async def _show_context_note(updates: dict[str, str]) -> None:
    if not updates:
        return

    pairs = " | ".join(f"{key}: {value}" for key, value in updates.items())
    await cl.Message(
        content=f"Session context saved: {pairs}",
        author="eComBot UI",
    ).send()


async def _run_turn(prompt: str) -> dict[str, Any]:
    runner = cl.user_session.get("runner")
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")

    delegation_trace.clear()
    open_steps: dict[str, list[cl.Step]] = {}
    tool_responses: dict[str, list[dict[str, Any]]] = {}
    top_level_trace: list[dict[str, Any]] = []
    final_text = ""
    final_author = ""
    has_error = False

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_message(_contextual_prompt(prompt)),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                function_call = getattr(part, "function_call", None)
                if function_call:
                    args = dict(function_call.args or {})
                    step = cl.Step(name=_tool_label(function_call.name), type="tool")
                    step.input = _to_json(args)
                    await step.send()
                    open_steps.setdefault(function_call.name, []).append(step)
                    top_level_trace.append(
                        {"type": "call", "tool": function_call.name, "args": args}
                    )

                function_response = getattr(part, "function_response", None)
                if function_response:
                    response = dict(function_response.response or {})
                    _record_response(tool_responses, function_response.name, response)
                    top_level_trace.append(
                        {
                            "type": "result",
                            "tool": function_response.name,
                            "response": _unwrap_response(response),
                        }
                    )

                    steps = open_steps.get(function_response.name) or []
                    if steps:
                        step = steps.pop()
                        payload = _unwrap_response(response)
                        step.output = f"```json\n{_to_json(payload)}\n```"
                        step.is_error = isinstance(payload, dict) and (
                            "error" in payload or payload.get("error_type") == "timeout"
                        )
                        has_error = has_error or step.is_error
                        await step.update()

        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""
            final_author = event.author

    specialist_trace = list(delegation_trace)
    delegation_trace.clear()

    for step_info in specialist_trace:
        if step_info.get("type") != "result":
            continue

        payload = _unwrap_response(step_info.get("response") or {})
        tool_name = step_info.get("tool", "")
        _record_response(tool_responses, tool_name, payload)
        if isinstance(payload, dict):
            _update_session_context_from_tool(tool_name, payload)

        async with cl.Step(
            name=f"{step_info.get('agent', 'specialist')}: {_tool_label(tool_name)}",
            type="tool",
        ) as step:
            matching_call = next(
                (
                    item
                    for item in reversed(specialist_trace)
                    if item.get("type") == "call"
                    and item.get("tool") == tool_name
                    and item.get("agent") == step_info.get("agent")
                ),
                None,
            )
            if matching_call:
                step.input = _to_json(matching_call.get("args") or {})
            step.output = f"```json\n{_to_json(payload)}\n```"
            step.is_error = isinstance(payload, dict) and (
                "error" in payload or payload.get("error_type") == "timeout"
            )
            has_error = has_error or step.is_error

    return {
        "text": final_text.strip(),
        "author": final_author,
        "tool_responses": tool_responses,
        "top_level_trace": top_level_trace,
        "specialist_trace": specialist_trace,
        "has_error": has_error,
    }


async def _handle_prompt(prompt: str) -> None:
    updates = _update_session_context_from_prompt(prompt)
    result = await _run_turn(prompt)

    if not result["text"]:
        await cl.Message(
            content="I could not produce a response for that request. Please try again.",
            author="eComBot",
        ).send()
        return

    cards = _build_cards(result["tool_responses"])
    content = result["text"]
    if cards:
        content += "\n\n---\n\n" + "\n\n---\n\n".join(cards)

    actions = _budget_actions(prompt)
    await cl.Message(content=content, actions=actions, author="eComBot").send()
    await _show_context_note(updates)
    await _store_turn_log(prompt, result, bool(cards), bool(actions))
    await _snapshot_state()


def _budget_actions(prompt: str) -> list[cl.Action]:
    if not _looks_like_sales_prompt(prompt):
        return []

    if cl.user_session.get("budget_band") or _budget_from_text(prompt):
        return []

    return [
        cl.Action(
            name="choose_budget",
            label="Under INR 15000",
            payload={"label": "budget", "limit": "15000"},
            tooltip="Save budget preference and ask for budget recommendations.",
        ),
        cl.Action(
            name="choose_budget",
            label="Under INR 30000",
            payload={"label": "mid-range", "limit": "30000"},
            tooltip="Save mid-range preference and refine recommendations.",
        ),
        cl.Action(
            name="choose_budget",
            label="Premium",
            payload={"label": "premium", "limit": "60000"},
            tooltip="Save premium preference and refine recommendations.",
        ),
    ]


async def _store_turn_log(
    prompt: str,
    result: dict[str, Any],
    has_cards: bool,
    has_actions: bool,
) -> None:
    turn_log = cl.user_session.get("turn_log", [])
    turn_log.append(
        {
            "query": prompt[:90],
            "author": result["author"],
            "top_tools": [
                item["tool"]
                for item in result["top_level_trace"]
                if item.get("type") == "call"
            ],
            "specialist_tools": [
                item["tool"]
                for item in result["specialist_trace"]
                if item.get("type") == "call"
            ],
            "has_cards": has_cards,
            "has_actions": has_actions,
            "has_error": result["has_error"],
        }
    )
    cl.user_session.set("turn_log", turn_log)


async def _snapshot_state() -> None:
    runner = cl.user_session.get("runner")
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")
    if not runner or not user_id or not session_id:
        return

    try:
        session = await runner.session_service.get_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if session and session.state:
            save_session_state(session_id, dict(session.state))
    except Exception as exc:
        logging.getLogger(__name__).warning("State snapshot skipped: %s", exc)


async def _send_explainability() -> None:
    turn_log = cl.user_session.get("turn_log", [])
    if not turn_log:
        await cl.Message(
            content="No previous eComBot turn is recorded in this Chainlit session yet.",
            author="eComBot UI",
        ).send()
        return

    last = turn_log[-1]
    lines = [
        "## How eComBot built the last response",
        "",
        f"**Question:** {last['query']}",
        f"**Final ADK author:** `{last['author'] or 'unknown'}`",
        "",
    ]

    if last["top_tools"]:
        lines.append(
            "**Orchestrator tools:** "
            + ", ".join(f"`{tool}`" for tool in last["top_tools"])
        )
    else:
        lines.append("**Orchestrator tools:** none")

    if last["specialist_tools"]:
        lines.append(
            "**Specialist tools:** "
            + ", ".join(f"`{tool}`" for tool in last["specialist_tools"])
        )
    else:
        lines.append("**Specialist tools:** none")

    ui_bits = []
    if last["has_cards"]:
        ui_bits.append("structured cards")
    if last["has_actions"]:
        ui_bits.append("budget action buttons")
    if last["has_error"]:
        ui_bits.append("error-marked tool step")
    lines.append("**UI additions:** " + (", ".join(ui_bits) if ui_bits else "plain response"))

    context = []
    for key in ("current_order_id", "current_product_id", "budget_band", "budget_limit"):
        value = cl.user_session.get(key)
        if value:
            context.append(f"- {key}: {value}")
    if context:
        lines += ["", "**Chainlit session context:**", *context]

    await cl.Message(content="\n".join(lines), author="eComBot UI").send()


@cl.on_chat_start
async def on_chat_start() -> None:
    runner, user_id, session_id = await make_runner(root_agent)

    cl.user_session.set("runner", runner)
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("current_order_id", None)
    cl.user_session.set("current_product_id", None)
    cl.user_session.set("current_product_name", None)
    cl.user_session.set("budget_band", None)
    cl.user_session.set("budget_limit", None)
    cl.user_session.set("turn_log", [])

    await cl.Message(
        content=(
            "Welcome to eComBot.\n\n"
            "I can help with order support, returns and warranty questions, "
            "product comparisons, recommendations, and stock checks.\n\n"
            "Try `Where is my order ORD-001?`, `Show me PRD-101`, or "
            "`Compare Galaxy A55 and Redmi Note 13 Pro`."
        ),
        actions=[
            cl.Action(
                name="demo_prompt",
                label="Check ORD-001",
                payload={"prompt": "Where is my order ORD-001?"},
                tooltip="Run a support flow.",
            ),
            cl.Action(
                name="demo_prompt",
                label="Compare phones",
                payload={
                    "prompt": "Compare Galaxy A55 and Redmi Note 13 Pro for battery and camera."
                },
                tooltip="Run a sales comparison flow.",
            ),
        ],
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    prompt = message.content.strip()
    if not prompt:
        return

    if _is_explainability_query(prompt):
        await _send_explainability()
        return

    await _handle_prompt(prompt)


@cl.action_callback("choose_budget")
async def on_choose_budget(action: cl.Action) -> None:
    label = action.payload.get("label", "mid-range")
    limit = action.payload.get("limit", "30000")
    cl.user_session.set("budget_band", label)
    cl.user_session.set("budget_limit", limit)

    await cl.Message(
        content=f"Budget preference saved: {label}, up to INR {limit}.",
        author="eComBot UI",
    ).send()

    prompt = (
        "Recommend the best phone options for my saved budget. "
        f"My budget is under INR {limit}."
    )
    await _handle_prompt(prompt)


@cl.action_callback("demo_prompt")
async def on_demo_prompt(action: cl.Action) -> None:
    prompt = action.payload.get("prompt", "")
    if prompt:
        await _handle_prompt(prompt)
