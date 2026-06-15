"""Model-name and proxy configuration helpers for LiteLLM-backed agents."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..config.settings import (
    DEEP_MODEL,
    DEEP_ROUTE_NAME,
    FAST_MODEL,
    FAST_ROUTE_NAME,
    LITELLM_PROXY_API_KEY_ENV,
)

DIRECT_MODE = "direct"
PROXY_MODE = "proxy"


@dataclass(frozen=True)
class GatewayModel:
    """Resolved model settings for one eComBot route."""

    route: str
    model: str
    mode: str
    base_url: str | None


def gateway_mode() -> str:
    """Return ``direct`` or ``proxy`` from environment configuration."""
    mode = os.getenv("LLM_GATEWAY_MODE", DIRECT_MODE).strip().lower()
    if mode not in {DIRECT_MODE, PROXY_MODE}:
        return DIRECT_MODE
    return mode


def proxy_base_url() -> str:
    """Return the LiteLLM proxy base URL without the OpenAI ``/v1`` suffix."""
    return os.getenv("LITELLM_PROXY_BASE_URL", "http://127.0.0.1:4000").rstrip("/")


def _proxy_openai_base_url() -> str:
    return f"{proxy_base_url()}/v1"


def configure_proxy_environment() -> None:
    """Configure LiteLLM's OpenAI-compatible client for the local proxy."""
    if gateway_mode() != PROXY_MODE:
        return

    os.environ["OPENAI_API_BASE"] = _proxy_openai_base_url()
    os.environ["OPENAI_BASE_URL"] = _proxy_openai_base_url()

    proxy_key = os.getenv(LITELLM_PROXY_API_KEY_ENV, "sk-ecombot-local")
    os.environ["OPENAI_API_KEY"] = proxy_key


def normalize_route(route: str | None) -> str:
    """Return a supported logical route name."""
    candidate = (route or FAST_ROUTE_NAME).strip().lower()
    if candidate in {FAST_ROUTE_NAME, DEEP_ROUTE_NAME}:
        return candidate
    if candidate in {"fast", "faq", "simple"}:
        return FAST_ROUTE_NAME
    if candidate in {"deep", "support", "complex"}:
        return DEEP_ROUTE_NAME
    return FAST_ROUTE_NAME


def model_for_route(route: str | None) -> GatewayModel:
    """Resolve the LiteLLM model string used by ADK for a route."""
    normalized = normalize_route(route)
    mode = gateway_mode()

    if mode == PROXY_MODE:
        configure_proxy_environment()
        return GatewayModel(
            route=normalized,
            model=f"openai/{normalized}",
            mode=mode,
            base_url=_proxy_openai_base_url(),
        )

    direct_model = DEEP_MODEL if normalized == DEEP_ROUTE_NAME else FAST_MODEL
    return GatewayModel(
        route=normalized,
        model=direct_model,
        mode=mode,
        base_url=None,
    )
