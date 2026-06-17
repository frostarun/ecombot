"""Standalone sales guidance agent for future eComBot modules."""

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from ..config.settings import MODEL, ROOT_DIR

litellm.suppress_debug_info = True
load_dotenv(ROOT_DIR / ".env")

sales_agent = LlmAgent(
    name="ecombot_sales_agent",
    model=LiteLlm(model=MODEL),
    instruction="""
You are eComBot's sales assistant for electronics shoppers.

Ask about budget, preferred brands, must-have features, and use case before
making recommendations. Since we have no catalog tool,
do not invent current prices, availability, or promotions. Give general buying
guidance and make clear when live catalog confirmation is required.
""".strip(),
    description="Electronics sales assistant.",
)
