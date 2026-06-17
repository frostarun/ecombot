"""Orchestrator agent that delegates eComBot requests to specialists."""

from __future__ import annotations

import logging

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from ..config.settings import DEEP_ROUTE_NAME, FAST_ROUTE_NAME, ROOT_DIR
from ..gateway.litellm_gateway import model_for_route, normalize_route
from ..services.session_service import make_runner
from .sales_agent import get_sales_agent_for_route
from .support_agent import get_agent_for_route as get_support_agent_for_route

log = logging.getLogger(__name__)

litellm.suppress_debug_info = True
load_dotenv(ROOT_DIR / ".env")

delegation_trace: list[dict] = []


def _message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def _run_specialist(agent: LlmAgent, request: str) -> str:
    """Run one specialist in its own ADK runner/session and capture trace."""
    runner, user_id, session_id = await make_runner(agent)
    reply = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_message(request),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                function_call = getattr(part, "function_call", None)
                if function_call:
                    delegation_trace.append(
                        {
                            "agent": agent.name,
                            "type": "call",
                            "tool": function_call.name,
                            "args": dict(function_call.args or {}),
                        }
                    )

                function_response = getattr(part, "function_response", None)
                if function_response:
                    delegation_trace.append(
                        {
                            "agent": agent.name,
                            "type": "result",
                            "tool": function_response.name,
                            "response": dict(function_response.response or {}),
                        }
                    )

        if event.is_final_response() and event.content and event.content.parts:
            reply = event.content.parts[0].text or ""

    return reply.strip()


async def delegate_to_support_agent(request: str) -> str:
    """Delegate order, return, refund, warranty, delivery, or complaint work.

    Args:
        request: A self-contained support task. Include order IDs, product IDs,
            issue details, and any context needed by the Support specialist.

    Returns:
        The Support specialist's plain-language answer.
    """
    log.info("Delegating to support specialist: %s", request)
    return await _run_specialist(get_support_agent_for_route(FAST_ROUTE_NAME), request)


async def delegate_to_sales_agent(request: str) -> str:
    """Delegate product discovery, recommendation, comparison, or stock work.

    Args:
        request: A self-contained sales task. Include budget, use case,
            product IDs/names, and any support result that should influence
            the recommendation.

    Returns:
        The Sales specialist's plain-language answer.
    """
    log.info("Delegating to sales specialist: %s", request)
    return await _run_specialist(get_sales_agent_for_route(DEEP_ROUTE_NAME), request)


_ORCHESTRATOR_INSTRUCTION = """
You are eComBot's Orchestrator. You receive every customer message and decide
whether to answer directly or delegate to a specialist.

Specialists:
- Support specialist: order status, delivery, cancellation, returns, refunds,
  warranty claims, complaints, external order backend checks, and support
  policy questions.
- Sales specialist: product discovery, recommendations, comparisons, buying
  guidance, stock checks, variants, and alternatives.

Routing rules:
- For pure support requests, call delegate_to_support_agent.
- For pure sales/product-discovery requests, call delegate_to_sales_agent.
- For mixed requests, call delegate_to_support_agent first, then call
  delegate_to_sales_agent with the original sales task plus any useful support
  result. Combine both responses into one final answer.
- For greetings or capability questions, answer directly without delegation.
- Make every delegation request self-contained. Specialists do not know the
  full conversation unless you include the needed context.
- Do not call product/order/inventory tools yourself. Your tools are only the
  two delegation tools.
- Do not invent facts. Use specialist answers as the source of truth.
- If a specialist reports a backend error or missing data, tell the user
  plainly and continue with any other part of the request that can be handled.

Output style:
- Keep the final answer concise.
- When both specialists are used, structure the answer as Support update first,
  then Product options or next step.
""".strip()


_AGENT_CACHE: dict[str, LlmAgent] = {}


def build_orchestrator_agent(route_hint: str | None = None) -> LlmAgent:
    """Build the primary multi-agent orchestrator."""
    route = normalize_route(route_hint or DEEP_ROUTE_NAME)
    gateway_model = model_for_route(route)
    return LlmAgent(
        name=f"ecombot_orchestrator_{route.replace('-', '_')}",
        model=LiteLlm(model=gateway_model.model),
        instruction=_ORCHESTRATOR_INSTRUCTION,
        description=(
            "Primary eComBot orchestrator that delegates support and sales "
            "work to specialist agents."
        ),
        tools=[delegate_to_support_agent, delegate_to_sales_agent],
    )


def get_orchestrator_for_route(route_hint: str | None = None) -> LlmAgent:
    """Return a cached orchestrator for a logical model route."""
    route = normalize_route(route_hint or DEEP_ROUTE_NAME)
    if route not in _AGENT_CACHE:
        _AGENT_CACHE[route] = build_orchestrator_agent(route)
    return _AGENT_CACHE[route]


root_agent = get_orchestrator_for_route(DEEP_ROUTE_NAME)
