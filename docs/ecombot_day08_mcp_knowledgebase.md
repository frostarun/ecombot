# eComBot FastMCP Integration Knowledgebase

This note explains the FastMCP backend integration added after the LiteLLM
gateway layer.

## Goal

The project now has an external-style backend boundary for order and inventory
operations. The support agent can still use its existing in-process PostgreSQL
tools, but it also has access to MCP tools exposed by a FastMCP server.

This keeps the application structure intact:

- `src/agents/` still owns agent construction and prompt behavior.
- `src/tools/` still owns ADK tool registration.
- `src/services/` owns service integrations, including the MCP server.
- `src/rag/` still owns retrieval.
- `src/gateway/` still owns model routing.

## New Files

- `src/services/mcp_servers/ecom_backend_data.py`
  - Pure Python mock backend data and functions.
  - Used by tests and by the FastMCP server.
- `src/services/mcp_servers/ecom_backend_server.py`
  - FastMCP server entrypoint.
  - Exposes order and inventory tools.
- `src/tools/mcp_backend_tools.py`
  - Builds an ADK `McpToolset` using Streamable HTTP transport.
  - Handles missing MCP dependencies gracefully.
- `scripts/check_mcp_backend.py`
  - Offline check for backend behavior.
- `tests/test_mcp_backend_manual.md`
  - Manual verification runbook.

## MCP Tools

The server exposes:

- `mcp_get_order_status(order_id)`
- `mcp_get_order_details(order_id)`
- `mcp_cancel_order(order_id, confirm=False)`
- `mcp_check_stock(product_id_or_sku)`
- `mcp_list_variants(product_id_or_name)`
- `mcp_slow_stock_check(product_id_or_sku, delay_seconds=5.0)`

The `mcp_` prefix is intentional. It prevents name collisions with the existing
in-process tools such as `get_order_status`, `cancel_order`, and
`lookup_product`.

## Runtime Flow

1. `support_agent.py` builds the normal eComBot support agent.
2. `get_mcp_toolsets(ROOT_DIR)` checks whether MCP tools are enabled.
3. If the MCP dependency is installed, ADK receives an `McpToolset`.
4. The toolset connects to `http://127.0.0.1:8775/mcp` by default.
5. FastMCP exposes the backend functions as Streamable HTTP MCP tools.
6. ADK returns tool results to the model as structured tool output.
7. The grounding and MCP rules tell the model to summarize results, not invent
   unavailable order or inventory details.

## Error Behavior

The mock backend returns controlled structured errors:

- Unknown order/product:
  - `found=False`
  - `error_type=not_found`
  - User message should ask the user to verify the ID or SKU.
- Timeout simulation:
  - `error_type=timeout`
  - User message should say the external backend is temporarily unavailable.
- Cancellation safety:
  - Cancellation preview returns `requires_confirmation=True`.
  - Actual cancellation requires `confirm=True`.

## Commands

Install MCP support:

```powershell
pip install -r requirements.txt
```

Offline backend check:

```powershell
python scripts/check_mcp_backend.py
```

Manual server start:

```powershell
$env:ECOMBOT_MCP_TRANSPORT="streamable-http"
python -m src.services.mcp_servers.ecom_backend_server
```

Agent run:

```powershell
$env:SESSION_BACKEND="memory"
$env:ECOMBOT_ENABLE_MCP_TOOLS="true"
$env:ECOMBOT_MCP_URL="http://127.0.0.1:8775/mcp"
python runner.py --trace-tools --route auto "Do we have PRD-101 in stock and what variants are available?"
```

`--trace-tools` prints each ADK tool call and tool result. This is the simplest
local observability path for confirming whether a response used an MCP tool.

## Streamable HTTP vs Stdio

The current implementation uses Streamable HTTP:

```text
ADK Agent -> McpToolset -> http://127.0.0.1:8775/mcp -> FastMCP server
```

This is different from stdio mode, where ADK starts the server as a child
process and communicates over stdin/stdout. Streamable HTTP is better when the
MCP server should run as a separate backend service with its own host and port.

## Design Boundary

MCP tools are external backend integrations. They are best for live-style order
details, stock, variants, and backend failure handling.

RAG is still for policy and product knowledge. PostgreSQL tools still provide
the local application database flow. The gateway still controls model routing.
