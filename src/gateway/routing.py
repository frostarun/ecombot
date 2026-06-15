"""Route eComBot prompts to logical LiteLLM model groups."""

from __future__ import annotations

from dataclasses import dataclass

from ..config.settings import DEEP_ROUTE_NAME, FAST_ROUTE_NAME
from .litellm_gateway import normalize_route

_DEEP_SIGNALS = {
    "compare",
    "comparison",
    "recommend",
    "which is better",
    "tradeoff",
    "trade-off",
    "diagnose",
    "troubleshoot",
    "not working",
    "multiple",
    "several",
    "complaint",
    "escalate",
    "refund rejected",
    "warranty denied",
    "explain why",
    "step by step",
    "best option",
    "options",
}

_FAST_SIGNALS = {
    "where is my order",
    "track order",
    "cancel",
    "return policy",
    "replacement window",
    "standard delivery",
    "express delivery",
    "warranty",
    "show me",
    "price",
    "hi",
    "hello",
}


@dataclass(frozen=True)
class RouteDecision:
    """Application-level route hint sent by selecting a LiteLLM model group."""

    route: str
    reason: str


def classify_route(prompt: str, explicit_route: str | None = None) -> RouteDecision:
    """Classify one user prompt as a fast FAQ or deeper support request."""
    if explicit_route and explicit_route != "auto":
        route = normalize_route(explicit_route)
        return RouteDecision(route=route, reason="explicit route override")

    text = (prompt or "").strip().lower()
    if not text:
        return RouteDecision(route=FAST_ROUTE_NAME, reason="empty prompt")

    if len(text.split()) >= 35:
        return RouteDecision(route=DEEP_ROUTE_NAME, reason="long multi-part prompt")

    for signal in _DEEP_SIGNALS:
        if signal in text:
            return RouteDecision(route=DEEP_ROUTE_NAME, reason=f"matched '{signal}'")

    for signal in _FAST_SIGNALS:
        if signal in text:
            return RouteDecision(route=FAST_ROUTE_NAME, reason=f"matched '{signal}'")

    return RouteDecision(route=FAST_ROUTE_NAME, reason="default low-risk support route")
