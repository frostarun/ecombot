"""Sales specialist agent for eComBot product discovery and recommendations."""

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm

from ..config.settings import DEEP_ROUTE_NAME, ROOT_DIR
from ..gateway.litellm_gateway import model_for_route, normalize_route
from ..rag.retriever import format_retrieved_context, retrieve
from ..tools.mcp_backend_tools import get_mcp_toolsets
from ..tools.product_tools import lookup_product

litellm.suppress_debug_info = True
load_dotenv(ROOT_DIR / ".env")

_SALES_BASE_INSTRUCTION = """
You are eComBot's Sales specialist for electronics shoppers.

Scope:
- Product recommendations, product comparisons, buying guidance, bundles,
  alternatives, and availability-oriented shopping questions.
- Phones, TV decoders, and accessories sold by this store.

Use the available product/RAG/inventory evidence before giving factual
recommendations. Ask one concise clarifying question when budget, use case, or
must-have features are missing and the answer would otherwise be too broad.

Rules:
- Use lookup_product when the user provides a product ID, product name, or
  category that needs catalog confirmation.
- Use MCP inventory tools when the user asks about stock counts, warehouse
  availability, or variants.
- Use retrieved knowledge for product facts, warranty, shipping, returns, and
  policy claims.
- Do not invent prices, live stock, promotions, specifications, or warranty
  terms.
- If evidence is missing, say what cannot be verified and suggest the next
  useful detail to check.
- Keep recommendations concise and explain the reason for each option.
""".strip()


def _latest_user_text(ctx: ReadonlyContext) -> str:
    if not ctx.user_content or not ctx.user_content.parts:
        return ""
    return "".join(part.text or "" for part in ctx.user_content.parts if part.text)


def build_sales_instruction(base_instruction: str):
    """Return an instruction provider that injects retrieved product context."""

    def _instruction(ctx: ReadonlyContext) -> str:
        query = _latest_user_text(ctx)
        results = retrieve(query, n_results=4) if query.strip() else []
        retrieved_context = format_retrieved_context(results)
        return f"{base_instruction}\n\n{retrieved_context}"

    return _instruction


_AGENT_CACHE: dict[str, LlmAgent] = {}


def build_sales_agent(route_hint: str | None = None) -> LlmAgent:
    """Build the sales specialist for the selected model route."""
    route = normalize_route(route_hint or DEEP_ROUTE_NAME)
    gateway_model = model_for_route(route)
    return LlmAgent(
        name=f"ecombot_sales_{route.replace('-', '_')}",
        model=LiteLlm(model=gateway_model.model),
        instruction=build_sales_instruction(_SALES_BASE_INSTRUCTION),
        description=(
            "Electronics sales specialist for recommendations, comparisons, "
            "product discovery, and inventory-aware buying guidance."
        ),
        tools=[lookup_product, *get_mcp_toolsets(ROOT_DIR)],
    )


def get_sales_agent_for_route(route_hint: str | None = None) -> LlmAgent:
    """Return a cached sales specialist for a logical model route."""
    route = normalize_route(route_hint or DEEP_ROUTE_NAME)
    if route not in _AGENT_CACHE:
        _AGENT_CACHE[route] = build_sales_agent(route)
    return _AGENT_CACHE[route]


sales_agent = get_sales_agent_for_route(DEEP_ROUTE_NAME)
