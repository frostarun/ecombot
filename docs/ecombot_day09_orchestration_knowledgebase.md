# eComBot Multi-Agent Orchestration Knowledgebase

## Goal

eComBot now uses a primary Orchestrator agent instead of exposing the Support
agent directly as the ADK Web root. The Orchestrator receives every user
message, decides whether the task is support, sales, mixed, or simple meta
conversation, and delegates only when a specialist is needed.

## Agent Responsibilities

| Agent | File | Responsibility |
|---|---|---|
| Orchestrator | `src/agents/orchestrator_agent.py` | Owns routing, delegation, mixed-task sequencing, and final response assembly. |
| Support specialist | `src/agents/support_agent.py` | Owns order status, delivery, cancellation, returns, refunds, warranty, complaints, and support policy answers. |
| Sales specialist | `src/agents/sales_agent.py` | Owns product discovery, recommendations, comparisons, buying guidance, variants, and stock-aware alternatives. |

## Runtime Path

```text
User
  -> ADK Web agent.py or runner.py
  -> LiteLLM route classifier chooses model route
  -> orchestrator_agent
       -> direct answer for simple capability/meta questions
       -> delegate_to_support_agent for support tasks
       -> delegate_to_sales_agent for sales tasks
       -> support first, then sales for mixed tasks
  -> specialist agent
       -> retrieves ChromaDB knowledge where useful
       -> calls its own tools
       -> returns plain-language answer to the Orchestrator
  -> Orchestrator final answer
```

The model route is still `fast-faq` or `deep-support`. That route chooses which
configured model group is used. It is separate from specialist routing, which
is handled by the Orchestrator prompt and delegation tools.

## Delegation Tools

The Orchestrator has only two tools:

```text
delegate_to_support_agent(request)
delegate_to_sales_agent(request)
```

It does not call order, product, inventory, or MCP backend tools directly. That
keeps orchestration separate from execution:

- Orchestrator decides what should happen.
- Specialist agents perform domain work using their own instructions and tools.
- Orchestrator combines specialist results for the user.

## Support Specialist

The Support specialist keeps the existing support implementation:

- Dynamic support instruction variants.
- ChromaDB grounding for policy, warranty, shipping, return, and support text.
- PostgreSQL tools:
  - `get_order_status`
  - `cancel_order`
  - `lookup_product`
  - `save_customer_name`
- MCP backend tools when `ECOMBOT_ENABLE_MCP_TOOLS=true`.

It is used for order-centric and service-centric requests.

## Sales Specialist

The Sales specialist is a separate ADK agent with its own instruction:

- Uses ChromaDB retrieval for product and policy context.
- Uses `lookup_product` for catalog confirmation.
- Uses MCP inventory tools for stock counts, variants, and warehouse
  availability.

It is used for recommendations, comparisons, and buying guidance.

## Mixed Planner-Executor Flow

For a prompt such as:

```text
My phone order ORD-001 was delayed. Check the order status and suggest an alternative phone that is currently in stock.
```

the Orchestrator should:

1. Call `delegate_to_support_agent` with the order-status task.
2. Read the Support specialist answer.
3. Call `delegate_to_sales_agent` with the product-alternative task plus useful
   support context.
4. Return one response with the support update first and the product option
   second.

This is the Planner-Executor pattern. The Orchestrator plans and sequences the
work; specialists execute.

## Tracing

Use:

```powershell
python runner.py --multi-agent-scenario
python runner.py --trace-tools --route auto "Where is my order ORD-001?"
```

Trace output has two layers:

```text
Tool call:        delegate_to_support_agent(...)
Tool result:      delegate_to_support_agent -> ...
Specialist call:  ecombot_support_fast_faq -> get_order_status(...)
Specialist result:ecombot_support_fast_faq -> get_order_status -> ...
```

The first layer shows what the Orchestrator delegated. The second layer shows
what the selected specialist did internally.

## Key Files

| File | Purpose |
|---|---|
| `agent.py` | ADK Web entrypoint. Imports Orchestrator `root_agent`. |
| `runner.py` | Local runner, route checks, retrieval checks, tool traces, multi-agent scenario. |
| `src/agents/orchestrator_agent.py` | Primary Orchestrator and delegation tools. |
| `src/agents/support_agent.py` | Support specialist. |
| `src/agents/sales_agent.py` | Sales specialist. |
| `tests/test_multi_agent_manual.md` | Manual validation checklist. |

## Commands

Run a support-only request:

```powershell
python runner.py --trace-tools --route auto "Where is my order ORD-001?"
```

Run a sales-only request:

```powershell
python runner.py --trace-tools --route auto "Compare Galaxy A55 and Redmi Note 13 Pro."
```

Run a mixed request:

```powershell
python runner.py --trace-tools --route auto "My phone order ORD-001 was delayed. Check the order status and suggest an alternative phone that is currently in stock."
```

Run the bundled scenario:

```powershell
python runner.py --multi-agent-scenario
```

For MCP stock and variant checks, start the backend first:

```powershell
$env:ECOMBOT_MCP_TRANSPORT="streamable-http"
python -m src.services.mcp_servers.ecom_backend_server
```

## Validation Checklist

- ADK Web loads `agent.py` and shows the Orchestrator as the root agent.
- Support prompts call `delegate_to_support_agent`.
- Sales prompts call `delegate_to_sales_agent`.
- Mixed prompts call Support first, then Sales.
- Capability/meta prompts can be answered without delegation.
- Specialist traces show internal tool calls when `--trace-tools` is used.
