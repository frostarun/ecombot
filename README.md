# eComBot

eComBot is an ADK-based electronics support assistant. It combines:

- ADK `LlmAgent` orchestration with Support and Sales specialist agents.
- PostgreSQL-backed order and product tools.
- Redis session snapshots and optional Redis-backed ADK sessions.
- ChromaDB retrieval over product, FAQ, and PDF knowledge.
- LiteLLM/OpenRouter model routing with optional LiteLLM proxy mode.
- FastMCP external order and inventory tools over Streamable HTTP.

The runtime entrypoints are:

- `agent.py` for ADK Web.
- `runner.py` for local scripted, REPL, retrieval, route, and tool-trace checks.
- `src/ui/chainlit_app.py` for the Chainlit browser UI.

## Setup

From `lab/demo/arun/ecombot`:

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set:

```text
OPENROUTER_API_KEY=your_openrouter_key
```

Start PostgreSQL and Redis:

```powershell
docker compose up -d
docker compose ps
```

Build the local knowledge index:

```powershell
python scripts/generate_sample_pdfs.py
python -m src.rag.embed_catalog
```

## Runtime Flow

```text
User prompt
  -> runner.py, ADK Web, or Chainlit UI
  -> route classifier chooses a model route: fast-faq or deep-support
  -> orchestrator_agent receives the user request
  -> orchestrator either:
       - answers simple capability questions directly
       - delegates support work to support_agent
       - delegates sales/product work to sales_agent
       - runs support_agent first, then sales_agent for mixed requests
  -> specialists build dynamic instructions with ChromaDB context
  -> specialists use the tools they own:
       - support_agent: order, cancellation, product, customer, MCP backend tools
       - sales_agent: product lookup and MCP inventory tools
  -> orchestrator combines specialist replies when needed
  -> runner or Chainlit stores durable history and Redis snapshots when configured
```

## Common Commands

Run a basic local prompt:

```powershell
python runner.py "Hi, my name is Priya." "Where is my order ORD-001?"
```

Run with memory sessions only:

```powershell
$env:SESSION_BACKEND="memory"
python runner.py --scenario
```

Inspect retrieval without a chat-model call:

```powershell
python runner.py --retrieve "What documents are needed to claim warranty?"
```

Inspect model route selection without a model call:

```powershell
python runner.py --route-check "Where is my order ORD-001?"
python runner.py --route-check "Compare Galaxy A55 and Redmi Note 13 Pro."
```

Run with automatic route selection:

```powershell
python runner.py --route auto "Where is my order ORD-001?" "Compare Galaxy A55 and Redmi Note 13 Pro."
```

Trace tool calls:

```powershell
python runner.py --trace-tools --route auto "Where is my order ORD-001?"
```

Run multi-agent orchestration checks. For the full stock/variant trace, start
the FastMCP backend first. For an orchestration-only check without external MCP
tools, set `ECOMBOT_ENABLE_MCP_TOOLS=false`.

```powershell
python runner.py --multi-agent-scenario
```

Trace a mixed support plus sales request:

```powershell
python runner.py --trace-tools --route auto "My phone order ORD-001 was delayed. Check the order status and suggest an alternative phone that is currently in stock."
```

Start an interactive REPL:

```powershell
python runner.py --repl
```

Run ADK Web from the parent folder:

```powershell
cd ..
adk web ecombot
```

## Chainlit UI

Chainlit is the generative UI layer. It reuses the same Orchestrator backend
and adds visible steps, structured cards, action buttons, and UI session state.

Chainlit currently supports Python `>=3.10,<3.14`. The repo Python `3.14`
venv can run the backend, but Chainlit needs a Python `3.10`, `3.11`, `3.12`,
or `3.13` environment.

Run from `lab/demo/arun/ecombot`:

```powershell
py -3.13 -m venv .venv-chainlit
.\.venv-chainlit\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SESSION_BACKEND="memory"
chainlit run src/ui/chainlit_app.py -w
```

Useful UI prompts:

```text
Where is my order ORD-001?
Show me PRD-101.
Compare Galaxy A55 and Redmi Note 13 Pro for battery and camera.
My phone order ORD-001 was delayed. Check the order status and suggest an alternative phone that is currently in stock.
Show me how you made this answer.
```

What Chainlit adds:

- Orchestrator delegation and specialist tool calls appear as expandable steps.
- Order, product, and inventory tool outputs render as structured cards.
- Sales prompts can show budget buttons such as `Under INR 15000`.
- Chainlit session state remembers current order ID, product ID, and budget
  preference for follow-up turns.

## FastMCP Backend

The FastMCP backend exposes external-style order and inventory tools.
eComBot connects to it over Streamable HTTP.

Terminal 1:

```powershell
$env:ECOMBOT_MCP_TRANSPORT="streamable-http"
python -m src.services.mcp_servers.ecom_backend_server
```

Terminal 2:

```powershell
$env:SESSION_BACKEND="memory"
$env:ECOMBOT_ENABLE_MCP_TOOLS="true"
$env:ECOMBOT_MCP_URL="http://127.0.0.1:8775/mcp"
python runner.py --trace-tools --route auto "Do we have PRD-101 in stock and what variants are available?"
```

Check backend behavior without ADK/MCP:

```powershell
python scripts/check_mcp_backend.py
```

## LiteLLM Proxy

Direct mode is the default. In direct mode, ADK uses the configured OpenRouter
model names directly through LiteLLM.

```powershell
$env:LLM_GATEWAY_MODE="direct"
python runner.py --route auto "What is the return policy?"
```

To route chat calls through a local LiteLLM proxy, start the proxy:

```powershell
$env:OPENROUTER_API_KEY="your key"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
litellm --config litellm_config.yaml --host 127.0.0.1 --port 4000
```

Then run eComBot in another terminal:

```powershell
$env:LLM_GATEWAY_MODE="proxy"
$env:LITELLM_PROXY_BASE_URL="http://127.0.0.1:4000"
$env:LITELLM_PROXY_API_KEY="sk-ecombot-local"
python runner.py --route auto "What is the return policy?"
```

## Environment Reference

### Required

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Used for chat model calls and embedding calls. |

### Sessions

| Variable | Default | Purpose |
|---|---:|---|
| `SESSION_BACKEND` | `database` | `database`, `redis`, or `memory` ADK session storage. |

Examples:

```powershell
$env:SESSION_BACKEND="database"
$env:SESSION_BACKEND="redis"
$env:SESSION_BACKEND="memory"
```

Use `memory` for local checks when PostgreSQL/Redis are not needed. Use
`database` for the normal persistent local stack.

### PostgreSQL

| Variable | Default | Purpose |
|---|---:|---|
| `PG_HOST` | `localhost` | PostgreSQL host. |
| `PG_PORT` | `5433` | PostgreSQL port. |
| `PG_DB` | `ecombot` | Database name. |
| `PG_USER` | `ecombot` | Database user. |
| `PG_PASSWORD` | `pg_secret` | Database password. |

### Redis

| Variable | Default | Purpose |
|---|---:|---|
| `REDIS_HOST` | `localhost` | Redis host. |
| `REDIS_PORT` | `6380` | Redis port. |
| `REDIS_PASSWORD` | `redis_secret` | Redis password. |
| `REDIS_SESSION_TTL` | `3600` | TTL for Redis session refs/snapshots. |

### Gateway

| Variable | Default | Purpose |
|---|---:|---|
| `LLM_GATEWAY_MODE` | `direct` | `direct` or `proxy`. |
| `LITELLM_PROXY_BASE_URL` | `http://127.0.0.1:4000` | LiteLLM proxy base URL. |
| `LITELLM_PROXY_API_KEY` | `sk-ecombot-local` | Proxy master key. |
| `ECOMBOT_FAST_ROUTE` | `fast-faq` | Logical route for simple requests. |
| `ECOMBOT_DEEP_ROUTE` | `deep-support` | Logical route for complex requests. |
| `ECOMBOT_FAST_MODEL` | `openrouter/google/gemini-2.5-flash` | Direct-mode fast model. |
| `ECOMBOT_DEEP_MODEL` | `openrouter/google/gemini-2.5-flash` | Direct-mode deep model. |

### FastMCP

| Variable | Default | Purpose |
|---|---:|---|
| `ECOMBOT_ENABLE_MCP_TOOLS` | `true` | Enables the ADK MCP toolset. |
| `ECOMBOT_MCP_TIMEOUT_SECONDS` | `8` | MCP tool-call timeout. |
| `ECOMBOT_MCP_HOST` | `127.0.0.1` | FastMCP server host. |
| `ECOMBOT_MCP_PORT` | `8775` | FastMCP server port. |
| `ECOMBOT_MCP_URL` | `http://127.0.0.1:8775/mcp` | Full MCP endpoint used by ADK. |
| `ECOMBOT_MCP_TRANSPORT` | `streamable-http` | FastMCP transport. |

Disable MCP tools:

```powershell
$env:ECOMBOT_ENABLE_MCP_TOOLS="false"
python runner.py "Do we have PRD-101 in stock?"
```

Enable MCP tools:

```powershell
$env:ECOMBOT_ENABLE_MCP_TOOLS="true"
$env:ECOMBOT_MCP_URL="http://127.0.0.1:8775/mcp"
python runner.py --trace-tools --route auto "Do we have PRD-101 in stock?"
```

## Project Structure

```text
ecombot/
|-- agent.py                         # ADK Web entrypoint
|-- runner.py                        # Programmatic runtime and debug commands
|-- docker-compose.yml               # PostgreSQL + Redis
|-- litellm_config.yaml              # LiteLLM proxy model groups
|-- litellm_config.fallback_demo.yaml
|-- data/
|   |-- products.json                # Product knowledge source
|   |-- faq.json                     # Policy/FAQ knowledge source
|   `-- pdf/                         # PDF knowledge source
|-- scripts/
|   |-- init_db.sql                  # PostgreSQL schema and seed data
|   |-- generate_sample_pdfs.py      # Builds local PDF examples
|   |-- check_gateway_routes.py      # Route/debug helper
|   `-- check_mcp_backend.py         # MCP backend/debug helper
|-- src/
|   |-- agents/orchestrator_agent.py # Primary ADK Web agent and delegation tools
|   |-- agents/support_agent.py      # Support specialist and support tools
|   |-- agents/sales_agent.py        # Sales specialist and product/inventory tools
|   |-- config/settings.py           # Environment-driven settings
|   |-- gateway/                     # Route classification and model resolver
|   |-- rag/                         # ChromaDB indexing and retrieval
|   |-- services/                    # DB, Redis, sessions, FastMCP server
|   |-- tools/                       # In-process tools and MCP toolset factory
|   `-- ui/chainlit_app.py           # Chainlit browser UI adapter
|-- tests/                           # Manual validation guides
`-- docs/                            # Architecture and learning guides
```

## Learning Guides

Day-wise implementation notes live under [docs](docs/). Start with
[docs/ecombot_learning_guides.md](docs/ecombot_learning_guides.md) for the
ordered list.
