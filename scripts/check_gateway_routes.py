"""Check eComBot route classification and optional LiteLLM proxy calls."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.config.settings import ROOT_DIR as SETTINGS_ROOT_DIR  # noqa: E402
from src.gateway.litellm_gateway import model_for_route  # noqa: E402
from src.gateway.routing import classify_route  # noqa: E402

load_dotenv(SETTINGS_ROOT_DIR / ".env")
litellm.suppress_debug_info = True


async def _call_proxy(model: str, prompt: str) -> str:
    response = await litellm.acompletion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are eComBot. Answer in one short sentence.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Check eComBot gateway routes.")
    parser.add_argument(
        "prompts",
        nargs="*",
        default=[
            "Where is my order ORD-001?",
            "Compare Galaxy A55 and Redmi Note 13 Pro for battery, camera, and warranty.",
            "My refund was rejected and the replacement device is also not working. What should I do?",
        ],
    )
    parser.add_argument(
        "--call-proxy",
        action="store_true",
        help="Call the configured LiteLLM proxy for each route.",
    )
    args = parser.parse_args()

    for prompt in args.prompts:
        decision = classify_route(prompt)
        gateway_model = model_for_route(decision.route)
        print(f"prompt: {prompt}")
        print(f"route:  {decision.route}")
        print(f"reason: {decision.reason}")
        print(f"mode:   {gateway_model.mode}")
        print(f"model:  {gateway_model.model}")
        if gateway_model.base_url:
            print(f"proxy:  {gateway_model.base_url}")

        if args.call_proxy:
            if gateway_model.mode != "proxy":
                print("call:   skipped, set LLM_GATEWAY_MODE=proxy first")
            elif not os.getenv("OPENAI_API_KEY"):
                print("call:   skipped, LITELLM_PROXY_API_KEY is not set")
            else:
                reply = await _call_proxy(gateway_model.model, prompt)
                print(f"reply:  {reply}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
