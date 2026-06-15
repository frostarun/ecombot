# eComBot LiteLLM Gateway Knowledgebase

This note explains the gateway layer added after the PDF RAG implementation.

## Goal

The application now separates "which model should answer this?" from the
support-agent business logic. Tools, sessions, RAG, and prompts stay in their
existing modules. Model routing lives under `src/gateway/`.

## New Pieces

- `src/gateway/routing.py` classifies a prompt into a logical route.
- `src/gateway/litellm_gateway.py` resolves that logical route into the model
  string ADK should send to LiteLLM.
- `litellm_config.yaml` defines the same logical routes for a LiteLLM proxy.
- `litellm_config.fallback_demo.yaml` intentionally breaks `fast-faq` so
  fallback behavior can be tested.
- `runner.py --route-check` prints routing decisions without calling a model.
- `runner.py --route auto` routes each prompt to the correct support-agent
  instance while preserving the same ADK session.

## Routes

`fast-faq` is for simple, low-risk requests:

- Order status or cancellation.
- Product lookup.
- Short FAQ questions.
- Simple warranty, shipping, return, and refund questions.

`deep-support` is for higher-complexity requests:

- Product comparisons.
- Multi-part complaints.
- Troubleshooting.
- Ambiguous support cases.
- Requests that need careful tradeoff reasoning.

Both routes default to Gemini 2.5 Flash in `.env.example` to keep the model
choice consistent with the rest of this project. You can change
`ECOMBOT_DEEP_MODEL` or the proxy config later if you want the deep route to use
a stronger model.

## Direct Mode

Direct mode is the default:

```powershell
$env:LLM_GATEWAY_MODE="direct"
python runner.py --route auto "Where is my order ORD-001?"
```

In direct mode, `fast-faq` resolves to `ECOMBOT_FAST_MODEL` and `deep-support`
resolves to `ECOMBOT_DEEP_MODEL`.

## Proxy Mode

Proxy mode sends chat-generation calls through a local LiteLLM proxy:

```powershell
$env:OPENROUTER_API_KEY="your key"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
litellm --config litellm_config.yaml --host 127.0.0.1 --port 4000
```

Then run eComBot:

```powershell
$env:LLM_GATEWAY_MODE="proxy"
$env:LITELLM_PROXY_BASE_URL="http://127.0.0.1:4000"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
python runner.py --route auto "Where is my order ORD-001?"
```

In proxy mode, the ADK model strings become:

- `openai/fast-faq`
- `openai/deep-support`

LiteLLM treats those as OpenAI-compatible calls to the proxy at
`LITELLM_PROXY_BASE_URL/v1`. The proxy then maps the logical model group to the
real OpenRouter model configured in `litellm_config.yaml`.

## Fallback

Fallback is configured in the LiteLLM proxy, not in the support agent.

The normal config has:

- `fast-faq` fallback to `deep-support`.
- `deep-support` fallback to `fast-faq`.

The fallback demo config intentionally points `fast-faq` to a bad model name.
When a `fast-faq` request fails, the proxy retries according to its router
settings and then calls `deep-support`.

## Runtime Flow

1. `runner.py` receives a prompt.
2. `classify_route()` returns `fast-faq` or `deep-support`.
3. `get_agent_for_route()` returns a cached support agent for that route.
4. The route-specific agent uses the same tools, instruction files, and RAG
   instruction builder as before.
5. `model_for_route()` decides whether the model string is a direct OpenRouter
   model or an OpenAI-compatible proxy route.
6. ADK runs the selected agent against the same ADK session service.
7. The model response still has access to the same order tools, product tools,
   retrieved knowledge, and durable history behavior.

## What Did Not Change

- PostgreSQL tool data.
- Redis/session behavior.
- ChromaDB retrieval.
- PDF ingestion.
- Support prompt variants.
- ADK Web entrypoint.

The new layer controls model selection only.
