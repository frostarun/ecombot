"""ADK Web entrypoint for eComBot.

Run from ``lab/demo/arun`` with:
    adk web ecombot
"""

from .src.agents.orchestrator_agent import root_agent

__all__ = ["root_agent"]
