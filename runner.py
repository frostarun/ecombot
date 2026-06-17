"""Console runner for the eComBot support agent.

Run from this directory:
    python runner.py --scenario
    python runner.py --repl
    python runner.py "Where is my order ORD-001?"
"""

import argparse
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from google.genai import types

from src.config.settings import ROOT_DIR
from src.gateway.litellm_gateway import model_for_route
from src.gateway.routing import classify_route
from src.services.history_service import get_history, record_turn
from src.services.redis_client import load_session_state, save_session_state
from src.services.session_service import get_session_service, make_runner

load_dotenv(ROOT_DIR / ".env")
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

DAY04_SCENARIO = [
    "Hi, my name is Priya.",
    "Where is my order ORD-001?",
    "What about that same order?",
    "Show me PRD-101.",
    "What is the price again?",
    "Cancel ORD-004.",
    "Track order XYZ-100.",
]

KNOWLEDGE_RAG_SCENARIO = [
    "What is the replacement window for electronics?",
    "What warranty does the Galaxy A55 5G have?",
    "What documents are needed to claim warranty?",
    "Can I return opened earbuds because I changed my mind?",
    "Do you sell refrigerator compressors?",
]

BLOCKED_PROXY_VALUES = {"http://127.0.0.1:9", "https://127.0.0.1:9"}


def _load_root_agent():
    """Import the agent only after environment preflight checks pass."""
    from src.agents.support_agent import root_agent

    return root_agent


def _load_agent_for_route(route: str):
    """Import the route-specific support agent after preflight checks pass."""
    from src.agents.support_agent import get_agent_for_route

    return get_agent_for_route(route)


def _message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def ask(
    runner,
    user_id: str,
    session_id: str,
    question: str,
    *,
    trace_tools: bool = False,
) -> str:
    """Send one prompt, persist history, and snapshot session state."""
    response_text = ""
    tool_calls: list[dict] = []
    tool_results: list[dict] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=_message(question),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                function_call = getattr(part, "function_call", None)
                if function_call:
                    tool_calls.append(
                        {
                            "name": function_call.name,
                            "args": dict(function_call.args or {}),
                        }
                    )
                function_response = getattr(part, "function_response", None)
                if function_response:
                    tool_results.append(
                        {
                            "name": function_response.name,
                            "response": dict(function_response.response or {}),
                        }
                    )

        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text or ""

    response_text = response_text.strip()

    record_turn(session_id, user_id, "user", question)
    record_turn(
        session_id,
        user_id,
        "model",
        response_text,
        tool_calls=tool_calls or None,
    )

    if trace_tools:
        for call in tool_calls:
            print(f"Tool call:   {call['name']}({call['args']})")
        for result in tool_results:
            print(f"Tool result: {result['name']} -> {result['response']}")
        if tool_calls or tool_results:
            print()

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

    return response_text


async def run_prompts(
    prompts: list[str],
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    route_mode: str = "auto",
    trace_tools: bool = False,
) -> tuple[str, str]:
    session_service = get_session_service()
    route_runners = {}

    async def _runner_for_prompt(prompt: str):
        nonlocal user_id, session_id

        decision = classify_route(prompt, route_mode)
        if decision.route not in route_runners:
            agent = _load_agent_for_route(decision.route)
            runner, user_id, session_id = await make_runner(
                agent,
                user_id=user_id,
                session_id=session_id,
                session_service=session_service,
            )
            route_runners[decision.route] = runner
        return route_runners[decision.route], decision

    first_runner, first_decision = await _runner_for_prompt(prompts[0])
    gateway_model = model_for_route(first_decision.route)

    print(f"user_id:    {user_id}")
    print(f"session_id: {session_id}")
    print(
        f"gateway:    mode={gateway_model.mode} "
        f"route_mode={route_mode} first_route={first_decision.route}"
    )
    if gateway_model.base_url:
        print(f"proxy:      {gateway_model.base_url}")
    print()

    cached_state = load_session_state(session_id)
    if cached_state:
        print(f"Redis cached state: {cached_state}\n")

    for question in prompts:
        runner, decision = await _runner_for_prompt(question)
        resolved_model = model_for_route(decision.route)
        print(
            f"Route: {decision.route} "
            f"({decision.reason}; model={resolved_model.model})"
        )
        print(f"User : {question}\n")
        reply = await ask(
            runner,
            user_id,
            session_id,
            question,
            trace_tools=trace_tools,
        )
        print(f"Agent: {reply}\n")

    return user_id, session_id


async def run_repl(
    user_id: str | None,
    session_id: str | None,
    *,
    trace_tools: bool = False,
) -> tuple[str, str]:
    session_service = get_session_service()
    route_runners = {}

    async def _runner_for_prompt(prompt: str):
        nonlocal user_id, session_id

        decision = classify_route(prompt, "auto")
        if decision.route not in route_runners:
            agent = _load_agent_for_route(decision.route)
            runner, user_id, session_id = await make_runner(
                agent,
                user_id=user_id,
                session_id=session_id,
                session_service=session_service,
            )
            route_runners[decision.route] = runner
        return route_runners[decision.route], decision

    runner, decision = await _runner_for_prompt("hello")
    print(f"user_id:    {user_id}")
    print(f"session_id: {session_id}")
    print(f"gateway:    mode={model_for_route(decision.route).mode} route_mode=auto")
    print("Type q to quit.\n")

    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if prompt.lower() == "q":
            break
        if not prompt:
            continue

        runner, decision = await _runner_for_prompt(prompt)
        resolved_model = model_for_route(decision.route)
        print(
            f"\nRoute: {decision.route} "
            f"({decision.reason}; model={resolved_model.model})"
        )
        reply = await ask(
            runner,
            user_id,
            session_id,
            prompt,
            trace_tools=trace_tools,
        )
        print(f"\nAgent: {reply}\n")

    return user_id, session_id


def print_history(session_id: str) -> None:
    history = get_history(session_id)
    if not history:
        print(f"No history found for session {session_id}.")
        return

    for turn in history:
        timestamp = str(turn["created_at"])[:19]
        tools_note = ""
        if turn.get("tool_calls"):
            calls = turn["tool_calls"]
            if isinstance(calls, str):
                calls = json.loads(calls)
            names = ", ".join(call.get("name", "?") for call in calls)
            tools_note = f" [tools: {names}]"
        print(f"{timestamp} {turn['role']:5s}: {turn['content']}{tools_note}")


def print_retrieval(query: str) -> None:
    from src.rag.retriever import retrieve

    results = retrieve(query, n_results=3)
    if not results:
        print(f"No grounded chunks found for: {query}")
        return

    print(f"Retrieved chunks for: {query}\n")
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        title = metadata.get("title") or result["id"]
        source = metadata.get("source_file") or metadata.get("source")
        page = metadata.get("page")
        section = metadata.get("section")
        source_note = ""
        if source and page:
            source_note = f" source={source} page={page}"
            if section:
                source_note += f" section={section}"
        print(
            f"{index}. score={result['score']:.3f} "
            f"id={result['id']} title={title}{source_note}"
        )
        print(f"   {result['text']}\n")


def _has_blocked_proxy() -> list[str]:
    """Return proxy env vars pointing at the local blackhole proxy."""
    blocked = []
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        value = os.environ.get(key)
        if value and value.lower() in BLOCKED_PROXY_VALUES:
            blocked.append(key)
    return blocked


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run eComBot locally.")
    parser.add_argument("prompts", nargs="*", help="Prompts to run in one session.")
    parser.add_argument("--scenario", action="store_true", help="Run Day 04 scenario.")
    parser.add_argument(
        "--rag-scenario",
        action="store_true",
        help="Run a knowledge-grounding scenario.",
    )
    parser.add_argument("--repl", action="store_true", help="Start an interactive REPL.")
    parser.add_argument("--user-id", help="Reuse a specific ADK user_id.")
    parser.add_argument("--session-id", help="Reuse a specific ADK session_id.")
    parser.add_argument("--history", help="Print durable history for a session_id.")
    parser.add_argument("--retrieve", help="Print top retrieved RAG chunks for a query.")
    parser.add_argument(
        "--trace-tools",
        action="store_true",
        help="Print ADK tool calls and tool results for each prompt.",
    )
    parser.add_argument(
        "--route",
        choices=("auto", "fast-faq", "deep-support"),
        default="auto",
        help="Route prompts to a logical LiteLLM model group.",
    )
    parser.add_argument(
        "--route-check",
        help="Classify one prompt and print the resolved model without calling the agent.",
    )
    args = parser.parse_args()

    if args.history:
        print_history(args.history)
        return

    if args.route_check:
        decision = classify_route(args.route_check, args.route)
        gateway_model = model_for_route(decision.route)
        print(f"prompt:     {args.route_check}")
        print(f"route:      {decision.route}")
        print(f"reason:     {decision.reason}")
        print(f"mode:       {gateway_model.mode}")
        print(f"model:      {gateway_model.model}")
        if gateway_model.base_url:
            print(f"proxy:      {gateway_model.base_url}")
        return

    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "\n[ERROR] OPENROUTER_API_KEY is not set.\n"
            "Copy .env.example to .env and fill in the key.\n"
        )
        return

    blocked_proxy_vars = _has_blocked_proxy()
    if blocked_proxy_vars:
        joined = ", ".join(blocked_proxy_vars)
        print(
            "\n[ERROR] Model calls are blocked by proxy environment variables: "
            f"{joined}.\n"
            "Clear them in this PowerShell session before running the agent:\n"
            "Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY -ErrorAction SilentlyContinue\n"
        )
        return

    if args.retrieve:
        print_retrieval(args.retrieve)
        return

    try:
        if args.repl:
            await run_repl(
                args.user_id,
                args.session_id,
                trace_tools=args.trace_tools,
            )
        elif args.rag_scenario:
            await run_prompts(
                KNOWLEDGE_RAG_SCENARIO,
                user_id=args.user_id,
                session_id=args.session_id,
                route_mode=args.route,
                trace_tools=args.trace_tools,
            )
        elif args.scenario:
            await run_prompts(
                DAY04_SCENARIO,
                user_id=args.user_id,
                session_id=args.session_id,
                route_mode=args.route,
                trace_tools=args.trace_tools,
            )
        else:
            prompts = args.prompts or ["Hi, can you help me with my order?"]
            await run_prompts(
                prompts,
                user_id=args.user_id,
                session_id=args.session_id,
                route_mode=args.route,
                trace_tools=args.trace_tools,
            )
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}\n")
    except Exception as exc:
        print(f"\n[ERROR] Agent run failed: {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())
