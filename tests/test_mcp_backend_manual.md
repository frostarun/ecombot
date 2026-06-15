# eComBot FastMCP Backend Manual Tests

## Dependency Check

Install the MCP extra first:

```powershell
pip install -r requirements.txt
```

Then verify the imports:

```powershell
python -c "from google.adk.tools.mcp_tool import McpToolset; from mcp.server.fastmcp import FastMCP; print('mcp ok')"
```

## Offline Backend Checks

```powershell
python scripts/check_mcp_backend.py
```

Expected:

- `ORD-001` returns status data.
- `ORD-999` returns `found=False` with `error_type=not_found`.
- `ORD-TIMEOUT` returns a controlled timeout-style result.
- `PRD-101` returns inventory stock data.
- `BassPro` returns variants.

## Start the FastMCP Server Manually

From the ecombot directory:

```powershell
$env:ECOMBOT_MCP_TRANSPORT="streamable-http"
python -m src.services.mcp_servers.ecom_backend_server
```

Expected:

- The server starts in Streamable HTTP mode.
- It listens on `http://127.0.0.1:8775/mcp` by default.
- Stop it with `Ctrl+C`.

## Agent Checks

Use memory session mode for a lightweight local run:

```powershell
$env:SESSION_BACKEND="memory"
$env:ECOMBOT_ENABLE_MCP_TOOLS="true"
$env:ECOMBOT_MCP_URL="http://127.0.0.1:8775/mcp"
python runner.py --route auto "Check external backend details for order ORD-001."
python runner.py --trace-tools --route auto "Do we have PRD-101 in stock and what variants are available?"
python runner.py --route auto "Check external backend status for order ORD-999."
```

Expected:

- Order detail/status questions can call MCP order tools.
- Inventory questions can call MCP inventory tools.
- Not-found responses are explained plainly.
- Existing PostgreSQL tools and RAG continue to work.
- `--trace-tools` prints ADK tool calls and tool results.
