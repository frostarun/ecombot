# eComBot Chainlit UI

This UI wraps the existing eComBot ADK backend. It does not replace ADK Web or
`runner.py`; it adds a richer browser interface for demos and manual testing.

## Try These Prompts

| Flow | Prompt |
|---|---|
| Support card | `Where is my order ORD-001?` |
| Product card | `Show me PRD-101.` |
| Sales comparison | `Compare Galaxy A55 and Redmi Note 13 Pro for battery and camera.` |
| Mixed orchestration | `My phone order ORD-001 was delayed. Check the order status and suggest an alternative phone that is currently in stock.` |
| Explainability | `Show me how you made this answer.` |

## What To Observe

- Orchestrator delegation appears as Chainlit steps.
- Specialist tool results appear as additional steps.
- Order, product, and inventory responses are rendered as structured cards.
- Sales-style prompts can show budget action buttons.
- Chainlit session state remembers order ID, product ID, and budget preference
  for follow-up turns.

## Run

```powershell
py -3.13 -m venv .venv-chainlit
.\.venv-chainlit\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SESSION_BACKEND="memory"
chainlit run src/ui/chainlit_app.py -w
```

For inventory and variant checks, start the MCP backend first:

```powershell
$env:ECOMBOT_MCP_TRANSPORT="streamable-http"
python -m src.services.mcp_servers.ecom_backend_server
```
