# eComBot Gateway Routing Manual Tests

These checks validate model routing and LiteLLM proxy fallback.

## Offline Route Classification

```powershell
python runner.py --route-check "Where is my order ORD-001?"
python runner.py --route-check "Compare Galaxy A55 and Redmi Note 13 Pro for camera and warranty."
python scripts/check_gateway_routes.py
```

Expected:

- Simple order or FAQ prompts route to `fast-faq`.
- Comparison, complaint, troubleshooting, or multi-step prompts route to
  `deep-support`.
- No model call is made for `--route-check`.

## Run Through the LiteLLM Proxy

Terminal 1:

```powershell
$env:OPENROUTER_API_KEY="your key"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
litellm --config litellm_config.yaml --host 127.0.0.1 --port 4000
```

Terminal 2:

```powershell
$env:LLM_GATEWAY_MODE="proxy"
$env:LITELLM_PROXY_BASE_URL="http://127.0.0.1:4000"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
python runner.py --route auto "Where is my order ORD-001?" "Compare Galaxy A55 and Redmi Note 13 Pro."
```

Expected:

- Runner prints the selected route before each prompt.
- LiteLLM proxy logs show calls to `fast-faq` and `deep-support`.
- eComBot tools, RAG, and session state still work.

## Fallback Demo

Terminal 1:

```powershell
$env:OPENROUTER_API_KEY="your key"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
litellm --config litellm_config.fallback_demo.yaml --host 127.0.0.1 --port 4000
```

Terminal 2:

```powershell
$env:LLM_GATEWAY_MODE="proxy"
$env:LITELLM_PROXY_BASE_URL="http://127.0.0.1:4000"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
python runner.py --route fast-faq "What is the return policy?"
```

Expected:

- `fast-faq` primary fails because the demo config uses a bad model.
- LiteLLM falls back to `deep-support`.
- eComBot still returns a useful answer.
