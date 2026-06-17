# eComBot Chainlit UI Knowledgebase

## Goal

The Chainlit UI gives eComBot a richer browser interface without replacing the
existing ADK Web or `runner.py` paths. It is a UI adapter over the current
Orchestrator, Support specialist, Sales specialist, RAG, PostgreSQL tools, and
MCP backend tools.

## Entry Point

| File | Purpose |
|---|---|
| `src/ui/chainlit_app.py` | Chainlit app, ADK event mapper, cards, actions, UI session state. |
| `chainlit.md` | Chainlit landing/help content shown by the UI. |
| `requirements.txt` | Adds `chainlit>=2.11.1,<3` for Python `<3.14`, while keeping the existing LiteLLM security floor. |

Run from `lab/demo/arun/ecombot`:

```powershell
py -3.13 -m venv .venv-chainlit
.\.venv-chainlit\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SESSION_BACKEND="memory"
chainlit run src/ui/chainlit_app.py -w
```

The current repo venv is Python `3.14`. Chainlit does not install there, so
use a Python `3.10` to `3.13` environment for this UI.

For inventory and variant flows, start the MCP backend first:

```powershell
$env:ECOMBOT_MCP_TRANSPORT="streamable-http"
python -m src.services.mcp_servers.ecom_backend_server
```

## Runtime Flow

```text
Browser
  -> Chainlit on_message
  -> existing ADK Runner for orchestrator_agent.root_agent
  -> Orchestrator delegates to Support or Sales specialist
  -> Chainlit maps ADK events to UI steps
  -> Chainlit builds cards from structured tool responses
  -> Chainlit stores UI context in cl.user_session
```

The backend agent structure from the previous implementation is unchanged:

- `agent.py` still exposes the Orchestrator for ADK Web.
- `runner.py` still supports scripted and trace-based local checks.
- `src/ui/chainlit_app.py` is only the browser UI layer.

## UI Features

### Messages

Final ADK text is sent as the main `cl.Message` content.

### Steps

Top-level Orchestrator delegation appears as Chainlit steps:

```text
Route to Support specialist
Route to Sales specialist
```

Specialist tool results are also shown as steps after the delegated specialist
finishes:

```text
ecombot_support_fast_faq: Check order status
ecombot_sales_deep_support: Fetch product details
ecombot_sales_deep_support: Check inventory
```

### Cards

Cards are built from structured tool responses, not from model text.

| Card | Source tools |
|---|---|
| Order Card | `get_order_status`, `mcp_get_order_status`, `mcp_get_order_details` |
| Product Card | `lookup_product` |
| Inventory Card | `mcp_check_stock`, `mcp_list_variants` |

### Actions

Sales-style prompts can show budget action buttons:

```text
Under INR 15000
Under INR 30000
Premium
```

Clicking a button stores the budget preference in Chainlit session state and
runs a follow-up recommendation prompt through the same Orchestrator.

### Session Context

Chainlit stores UI-level context with `cl.user_session`:

| Key | Purpose |
|---|---|
| `current_order_id` | Remembered order ID such as `ORD-001`. |
| `current_product_id` | Remembered product ID such as `PRD-101`. |
| `budget_band` | User-selected budget band. |
| `budget_limit` | User-selected numeric budget limit. |
| `turn_log` | Short explainability history for the current UI session. |

The app appends this UI context to later prompts only as relevant context. ADK
session state remains owned by ADK and the existing tool layer.

### Explainability

The prompt:

```text
Show me how you made this answer.
```

returns a short explanation of:

- Which Orchestrator tools ran.
- Which specialist tools ran.
- Whether cards or action buttons were added.
- Which Chainlit session values are currently remembered.

## Manual Flow

1. Start Chainlit.
2. Ask `Where is my order ORD-001?`.
3. Expand the delegation and order-status steps.
4. Confirm an Order Card appears.
5. Ask `Show me PRD-101.`.
6. Confirm a Product Card appears.
7. Ask `Compare Galaxy A55 and Redmi Note 13 Pro for battery and camera.`.
8. Confirm budget buttons appear if no budget was already selected.
9. Click a budget button.
10. Ask `Show me how you made this answer.`.

## Design Boundary

The UI adapter does not directly query PostgreSQL or MCP. It reads structured
responses from ADK events and the existing Day09 `delegation_trace`. This keeps
business behavior in agents/tools and visual behavior in Chainlit.
