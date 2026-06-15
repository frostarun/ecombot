"""Primary eComBot support agent used by ADK Web and the console runner."""

from pathlib import Path

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm

from ..config.settings import (
    AGENT_DIR,
    DEEP_ROUTE_NAME,
    DEFAULT_INSTRUCTION_VERSION,
    FAST_ROUTE_NAME,
    ROOT_DIR,
)
from ..gateway.litellm_gateway import model_for_route, normalize_route
from ..rag.retriever import format_retrieved_context, retrieve
from ..tools.mcp_backend_tools import get_mcp_toolsets
from ..tools.order_tools import cancel_order, get_order_status, save_customer_name
from ..tools.product_tools import lookup_product

litellm.suppress_debug_info = True

# Prefer the ecombot-local .env, while still allowing shell environment values.
load_dotenv(ROOT_DIR / ".env")

INSTRUCTION_FILES = {
    "v1": AGENT_DIR / "support_instructions_v1.txt",
    "v2": AGENT_DIR / "support_instructions_v2.txt",
    "v3": AGENT_DIR / "support_instructions_v3.txt",
}


def load_instruction(version: str = DEFAULT_INSTRUCTION_VERSION) -> str:
    """Load one prompt variant by version name."""
    try:
        instruction_path = INSTRUCTION_FILES[version]
    except KeyError as exc:
        available = ", ".join(sorted(INSTRUCTION_FILES))
        raise ValueError(
            f"Unknown instruction version '{version}'. Use one of: {available}."
        ) from exc

    return Path(instruction_path).read_text(encoding="utf-8").strip()


GROUNDING_RULES = """
Grounding rules:
- For factual product, shipping, return, refund, warranty, and support-policy
  answers, use only the retrieved knowledge section below plus tool outputs.
- If retrieved knowledge says nothing relevant was found, do not invent a
  policy, specification, warranty decision, price, stock level, or deadline.
- If a tool returns live order or catalog data, that tool output is trusted
  for that specific order/product lookup.
- For factual answers based on retrieved knowledge, include a short Sources
  line using the citation metadata when it is available.
- Greetings, name capture, order lookup, order cancellation, and basic
  clarification questions do not require retrieved knowledge.
- When knowledge is missing, say that the current eComBot knowledge base does
  not contain enough information and ask for the most useful next detail.
""".strip()


MCP_TOOL_RULES = """
External backend tools:
- MCP order tools are external-style backend integrations. Use them for
  item-level order details, external order status checks, and external
  cancellation previews when the user gives a specific order ID.
- MCP inventory tools are the source for stock counts, warehouse availability,
  and product variants.
- Tool responses are structured data. Summarise only the relevant fields in
  plain language; do not dump raw JSON.
- If an MCP tool returns found=false or error_type=not_found, tell the user the
  identifier was not found and ask them to verify the order ID, product ID, or
  SKU.
- If an MCP tool returns error_type=timeout or an error field, say the external
  backend is temporarily unavailable and suggest trying again shortly. Do not
  invent order, stock, or variant data.
- For cancellations, never cancel multiple orders. Preview the single order and
  ask for explicit confirmation before calling a cancellation tool with
  confirm=True.
""".strip()


def _latest_user_text(ctx: ReadonlyContext) -> str:
    if not ctx.user_content or not ctx.user_content.parts:
        return ""
    return "".join(part.text or "" for part in ctx.user_content.parts if part.text)


def build_grounded_instruction(base_instruction: str):
    """Return an ADK instruction provider that injects retrieved context."""

    def _instruction(ctx: ReadonlyContext) -> str:
        query = _latest_user_text(ctx)
        results = retrieve(query, n_results=3) if query.strip() else []
        retrieved_context = format_retrieved_context(results)
        return f"{base_instruction}\n\n{GROUNDING_RULES}\n\n{MCP_TOOL_RULES}\n\n{retrieved_context}"

    return _instruction


_AGENT_CACHE: dict[str, LlmAgent] = {}


def build_support_agent(
    instruction_version: str = DEFAULT_INSTRUCTION_VERSION,
    route_hint: str | None = None,
) -> LlmAgent:
    """Build the support agent with the selected instruction variant."""
    base_instruction = load_instruction(instruction_version)
    route = normalize_route(route_hint)
    gateway_model = model_for_route(route)
    tools = [
        get_order_status,
        cancel_order,
        lookup_product,
        save_customer_name,
        *get_mcp_toolsets(ROOT_DIR),
    ]
    return LlmAgent(
        name=f"ecombot_support_{route.replace('-', '_')}",
        model=LiteLlm(model=gateway_model.model),
        instruction=build_grounded_instruction(base_instruction),
        description=(
            "Electronics e-commerce support agent with database-backed tools "
            f"and knowledge-grounded responses on the {route} route."
        ),
        tools=tools,
    )


def get_agent_for_route(route_hint: str | None = None) -> LlmAgent:
    """Return a cached support agent for a logical model route."""
    route = normalize_route(route_hint)
    if route not in _AGENT_CACHE:
        _AGENT_CACHE[route] = build_support_agent(route_hint=route)
    return _AGENT_CACHE[route]


root_agent = get_agent_for_route(DEEP_ROUTE_NAME)
fast_support_agent = get_agent_for_route(FAST_ROUTE_NAME)
deep_support_agent = get_agent_for_route(DEEP_ROUTE_NAME)
