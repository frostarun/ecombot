"""Standalone product-discovery agent for future eComBot modules."""

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from ..config.settings import MODEL, ROOT_DIR

litellm.suppress_debug_info = True
load_dotenv(ROOT_DIR / ".env")

product_agent = LlmAgent(
    name="ecombot_product_agent",
    model=LiteLlm(model=MODEL),
    instruction="""
You are eComBot's product-discovery assistant for an electronics e-commerce
store that sells phones, TV decoders, and accessories.

Help customers clarify their needs, compare product categories, and choose
reasonable next steps. Do not invent live prices, stock levels, discounts, or
product specifications. If exact catalog data is needed, say that current
catalog lookup is not available yet and ask the customer to verify on the store
site or with support.
""".strip(),
    description="Electronics product-discovery assistant.",
)
