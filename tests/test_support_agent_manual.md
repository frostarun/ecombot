# Manual Test Plan: eComBot Day 04

Use `python runner.py --scenario`, `python runner.py --repl`, or ADK Web.
Record observed results and pass/fail during the lab.

## Happy Path

| Scenario | Input | Expected tool call | Expected behavior | Observed | Pass/Fail |
|---|---|---|---|---|---|
| Store name | `Hi, my name is Priya.` | `save_customer_name` | Stores `current_customer_name=Priya`. | | |
| Valid order | `Where is my order ORD-001?` | `get_order_status` | Returns status, ETA, carrier, product, and amount from PostgreSQL. | | |
| Order follow-up | `What about that same order?` | `get_order_status` | Reuses `current_order_id` if available. | | |
| Product by ID | `Show me PRD-101.` | `lookup_product` | Returns product name, price, stock, description, warranty. | | |
| Product follow-up | `What is the price again?` | `lookup_product` or conversation context | Uses the last product context; does not guess. | | |
| Cancel order | `Cancel ORD-002.` | `cancel_order` | Updates order to Cancelled if cancellable. | | |

## Failure Cases

| Scenario | Input | Expected behavior | Observed | Pass/Fail |
|---|---|---|---|---|
| Invalid order ID | `Track XYZ-100.` | Safe invalid-format error. | | |
| Missing order | `Where is ORD-999?` | Safe not-found error. | | |
| Already cancelled | `Cancel ORD-004.` | Says the order is already cancelled. | | |
| Delivered order cancellation | `Cancel ORD-003.` | Says delivered order cannot be cancelled. | | |
| Missing product | `Show me PRD-999.` | Safe not-found error. | | |
| Empty product input | Ask vaguely for product details | Agent asks for product name or ID. | | |
| PostgreSQL unavailable | Stop Postgres, then ask for order | Safe service-unavailable message; no stack trace. | | |
| Redis unavailable | Stop Redis, continue conversation | App continues; cache warning only. | | |

## Restart Continuity

1. Run:

   ```powershell
   python runner.py --scenario
   ```

2. Copy the printed `user_id` and `session_id`.
3. Restart the script with the same IDs:

   ```powershell
   python runner.py --user-id USER --session-id SESSION "What do you know about my order?"
   ```

Expected:

- Database session state is reused when `SESSION_BACKEND=database`.
- Redis may show a cached state snapshot if Redis is running.
- Conversation history can be printed:

  ```powershell
  python runner.py --history SESSION
  ```
