# Chainlit UI Manual Test

Run from `lab/demo/arun/ecombot`.

## Setup

Install dependencies:

```powershell
py -3.13 -m venv .venv-chainlit
.\.venv-chainlit\Scripts\Activate.ps1
pip install -r requirements.txt
```

Chainlit requires Python `>=3.10,<3.14`. Do not use the Python `3.14` backend
venv for this UI test.

Start the local UI with memory-backed ADK sessions:

```powershell
$env:SESSION_BACKEND="memory"
chainlit run src/ui/chainlit_app.py -w
```

For stock and variant checks, start the MCP backend in another terminal:

```powershell
$env:ECOMBOT_MCP_TRANSPORT="streamable-http"
python -m src.services.mcp_servers.ecom_backend_server
```

Then set:

```powershell
$env:ECOMBOT_ENABLE_MCP_TOOLS="true"
$env:ECOMBOT_MCP_URL="http://127.0.0.1:8775/mcp"
```

## Support Card

Prompt:

```text
Where is my order ORD-001?
```

Expected:

- Chainlit shows a `Route to Support specialist` step.
- A specialist tool step appears for order status.
- The final message includes an Order Card.
- The UI saves `ORD-001` as session context.

## Product Card

Prompt:

```text
Show me PRD-101.
```

Expected:

- Chainlit shows a delegation step.
- A specialist tool step appears for product lookup.
- The final message includes a Product Card.
- The UI saves `PRD-101` as session context.

## Sales Actions

Prompt:

```text
Recommend a phone for gaming.
```

Expected:

- The response can include budget action buttons.
- Clicking `Under INR 30000` saves the budget preference.
- A follow-up recommendation prompt runs automatically.

## Mixed Flow

Prompt:

```text
My phone order ORD-001 was delayed. Check the order status and suggest an alternative phone that is currently in stock.
```

Expected:

- Support delegation appears before Sales delegation.
- Order and product/inventory specialist steps are visible.
- Cards appear when matching structured tool responses are returned.

## Explainability

Prompt:

```text
Show me how you made this answer.
```

Expected:

- The UI explains the last Orchestrator tools.
- The UI lists specialist tools.
- The UI reports cards, actions, and stored session context.
