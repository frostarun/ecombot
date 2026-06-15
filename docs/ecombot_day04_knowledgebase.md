# eComBot Day 04 Knowledgebase

This document explains the current eComBot program as a system, not just as a
list of files. The goal is to make the Day 04 architecture easy to reason about
before the project grows into later capstone modules.

## 1. What eComBot Is Right Now

eComBot is an ADK-based electronics e-commerce support agent. It can answer
customer questions about orders and products, and it can call tools instead of
guessing facts.

Through Day 04, the bot has four layers:

1. The LLM agent decides what the user wants.
2. Tools perform real lookups or updates.
3. Session state remembers short-term context.
4. PostgreSQL and Redis provide persistence boundaries.

The active ADK Web entrypoint is `agent.py`. It exports one `root_agent`, which
comes from `src/agents/support_agent.py`.

## 2. The Main Runtime Flow

When you run:

```powershell
python runner.py --scenario
```

the program does this:

1. Loads `.env` values.
2. Builds the support agent from `support_agent.py`.
3. Creates an ADK `Runner` through `src/services/session_service.py`.
4. Creates or reconnects to a session.
5. Sends each user message to the agent.
6. Captures tool calls made by the agent.
7. Saves user/model turns to PostgreSQL `session_history`.
8. Snapshots session state to Redis.
9. Prints the final model reply.

ADK Web follows the same agent/tool logic, but ADK Web owns the UI and its own
request lifecycle. `runner.py` is better for understanding the program because
you can see exactly where sessions, history, and snapshots are handled.

## 3. What the Agent Does

The support agent is defined in:

```text
src/agents/support_agent.py
```

It creates an ADK `LlmAgent` with:

- model: `openrouter/google/gemini-2.5-flash`
- instruction: loaded from `support_instructions_v3.txt`
- tools:
  - `get_order_status`
  - `cancel_order`
  - `lookup_product`
  - `save_customer_name`

The instruction is important. It tells the model:

- Use tools for facts.
- Ask for missing IDs.
- Reuse session context for follow-up questions.
- Do not invent order status, prices, stock, discounts, warranties, or ETAs.
- Return safe explanations if a tool returns an error.

## 4. Tool Layer

Tools are regular typed Python functions. In this installed ADK version, there
is no `@tool` decorator exposed; ADK accepts Python callables directly in
`LlmAgent(tools=[...])`.

### Order Tools

File:

```text
src/tools/order_tools.py
```

Tools:

- `get_order_status(order_id, tool_context)`
- `cancel_order(order_id, tool_context)`
- `save_customer_name(name, tool_context)`

`get_order_status` validates IDs such as `ORD-001`, queries PostgreSQL, and
stores useful session values:

```python
tool_context.state["current_order_id"] = "ORD-001"
tool_context.state["current_customer_name"] = "Priya Sharma"
tool_context.state["last_intent"] = "get_order_status"
tool_context.state["last_lookup_key"] = "ORD-001"
```

`cancel_order` also uses session state. If the user says "cancel the same
order", the tool can use `current_order_id` instead of forcing the user to
repeat the ID.

### Product Tools

File:

```text
src/tools/product_tools.py
```

Tool:

- `lookup_product(product_name, tool_context)`

It accepts either a product ID like `PRD-101` or a product/category search term
like `Galaxy A55` or `phone`. It queries PostgreSQL `products` and stores:

```python
tool_context.state["current_product_id"] = "PRD-101"
tool_context.state["last_intent"] = "lookup_product"
tool_context.state["last_lookup_key"] = "PRD-101"
```

## 5. PostgreSQL: Durable Business Data

PostgreSQL is started by:

```text
docker-compose.yml
```

The schema and seed data live in:

```text
scripts/init_db.sql
```

Tables:

- `orders`: durable order information.
- `products`: durable product catalog information.
- `session_history`: durable conversation/audit history.

PostgreSQL is the source of truth for business facts. If the user asks,
"Where is ORD-001?", the agent should not guess; it should call
`get_order_status`, and that tool should read from PostgreSQL.

## 6. Redis: Fast Working-Memory Cache

Redis is also started by `docker-compose.yml`.

Redis is used by:

```text
src/services/redis_client.py
```

It stores:

- a short-lived session-state snapshot
- latest session reference for a user

Redis is intentionally not used as durable business history. If Redis is down,
the bot can still continue; history and business data remain in PostgreSQL.

## 7. ADK Session State

ADK session state is the short-term memory available to tools through
`tool_context.state`.

Examples:

```python
current_order_id
current_customer_name
current_product_id
last_intent
last_lookup_key
```

This is different from conversation history. State is the compact working
memory the agent uses for follow-ups. History is the full record of what was
said.

## 8. Session Service

File:

```text
src/services/session_service.py
```

It creates the ADK `Runner` and session service.

Supported backends:

- `SESSION_BACKEND=database`: uses ADK `DatabaseSessionService` with
  PostgreSQL.
- `SESSION_BACKEND=redis`: uses
  `adk_extra_services.sessions.RedisSessionService`, matching the trainer's
  fixed Day04 implementation.
- `SESSION_BACKEND=memory`: local fallback only; state is lost after process
  exit.

The default remains `database`, because it gives the strongest restart
durability through PostgreSQL. Redis can now be used in two ways: as the ADK
session backend when `SESSION_BACKEND=redis`, and as the fast snapshot/cache
layer through `src/services/redis_client.py`.

## 9. Conversation History

File:

```text
src/services/history_service.py
```

Every turn can be stored in `session_history`:

- `session_id`
- `user_id`
- `role`
- `content`
- `tool_calls`
- `created_at`

This is useful for debugging, replaying a conversation, audit review, and later
observability/evaluation modules.

You can print history with:

```powershell
python runner.py --history SESSION_ID
```

## 10. Important Boundaries

The Day 04 architecture is mostly about correct boundaries:

| Concern | Stored In | Why |
|---|---|---|
| Orders/products | PostgreSQL | Durable business facts |
| Conversation turns | PostgreSQL `session_history` | Durable audit trail |
| Current order/product/name | ADK session state | Short-term working context |
| State snapshot/session ref | Redis | Fast recovery/cache |
| Prompt behavior | instruction file | Tells the LLM when to use tools |

Do not put business facts only in Redis. Do not use PostgreSQL history as the
agent's short-term scratchpad. Keep each layer focused.

## 11. Failure Handling

Tools validate before querying:

- Invalid order IDs return a safe format error.
- Empty product lookups return a clarification error.
- Missing rows return not-found errors.
- Database failures return temporary-unavailable messages.

The user should never see stack traces, SQL errors, passwords, or internal
exception details.

## 12. How To Run It

Install dependencies:

```powershell
pip install -r requirements.txt
```

The application database layer uses one current PostgreSQL driver path for
tool queries. ADK's `DatabaseSessionService` uses `asyncpg` through the
SQLAlchemy URL in `src/config/settings.py`. The trainer-style Redis session
backend is provided by `adk-extra-services`.

Configure:

```powershell
Copy-Item .env.example .env
```

Start services:

```powershell
docker compose up -d
```

Run scenario:

```powershell
python runner.py --scenario
```

Run with same session after restart:

```powershell
python runner.py --user-id USER_ID --session-id SESSION_ID "What do you know about my order?"
```

## 13. How This Evolves Later

Day 04 is the base for later modules:

- Product lookup can become RAG-backed.
- PostgreSQL tools can move behind FastMCP.
- Session state can support multi-agent routing.
- `session_history` can feed observability and evals.
- Redis can support faster reconnect and short-lived UI context.

The important design choice is that tool interfaces stay stable while the data
source behind them becomes more production-like.
