# Prompt Variant Comparison Notes

Run the same prompt against each instruction variant and compare the tone,
scope control, and honesty behavior.

## Variants

| Variant | File | Purpose |
|---|---|---|
| v1 | `src/agents/support_instructions_v1.txt` | Minimal Day 01 support prompt. |
| v2 | `src/agents/support_instructions_v2.txt` | Friendlier Day 02 prompt with clearer style and data honesty. |
| v3 | `src/agents/support_instructions_v3.txt` | Refined current prompt with intent handling, scope limits, and follow-up rules. |

## Test Set

| Scenario | Prompt | What to compare |
|---|---|---|
| Greeting | `Hi, can you help me?` | Whether the reply names the support areas clearly. |
| Clarifying question | `I need a phone` | Whether the agent asks for budget, use case, or preferred features. |
| Empathy | `My order is very late` | Whether the response acknowledges frustration before asking for details. |
| Unknown data | `What is the current price of Galaxy A55?` | Whether the agent avoids making up a live price. |
| Out of scope | `Explain recursion in Python` | Whether the agent redirects to e-commerce support. |
| Follow-up context | Turn 1: `I need a phone for gaming under 20000.` Turn 2: `What should I check first?` | Whether Turn 2 uses the budget and gaming context from Turn 1. |

## Observation Template

| Prompt | v1 result | v2 result | v3 result | Best variant | Reason |
|---|---|---|---|---|---|
| | | | | | |

## Current Best Instruction

`support_instructions_v3.txt` is the current best instruction because it:

- Separates common e-commerce intents.
- States that the current build has no live tool access.
- Limits guessing about orders, prices, stock, ETAs, policies, and warranties.
- Instructs the agent to use prior conversation context for follow-ups.
