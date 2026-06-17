# Multi-Agent Orchestration Manual Test

Run from `lab/demo/arun/ecombot`.

## Setup

```powershell
$env:SESSION_BACKEND="memory"
python -m src.rag.embed_catalog
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

## Support Routing

```powershell
python runner.py --trace-tools --route auto "Where is my order ORD-001?"
```

Expected:

- Top-level trace calls `delegate_to_support_agent`.
- Specialist trace shows support tools such as `get_order_status` or MCP order
  tools.
- No `delegate_to_sales_agent` call is needed.

## Sales Routing

```powershell
python runner.py --trace-tools --route auto "Compare Galaxy A55 and Redmi Note 13 Pro for battery and camera."
```

Expected:

- Top-level trace calls `delegate_to_sales_agent`.
- Specialist answer focuses on product comparison and buying guidance.
- No order-status support tool is needed.

## Mixed Planner-Executor Routing

```powershell
python runner.py --trace-tools --route auto "My phone order ORD-001 was delayed. Check the order status and suggest an alternative phone that is currently in stock."
```

Expected:

- Top-level trace calls `delegate_to_support_agent` first.
- Top-level trace calls `delegate_to_sales_agent` second.
- Final answer gives the support update first and product option second.
- Sales request includes useful support context from the first specialist.

## Direct Orchestrator Answer

```powershell
python runner.py --trace-tools --route auto "What can you help me with as a shopping assistant?"
```

Expected:

- The Orchestrator may answer directly.
- No specialist delegation is required.

## Bundled Scenario

```powershell
python runner.py --multi-agent-scenario
```

Expected:

- Runs support, sales, mixed, and direct-answer checks in one session.
- Tool traces are printed by default for this scenario.
