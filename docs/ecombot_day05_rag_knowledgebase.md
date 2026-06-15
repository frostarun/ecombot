# eComBot Day 05 RAG Knowledgebase

Day 05 adds a grounding layer on top of the Day 04 system. The existing
PostgreSQL tools, Redis snapshots, ADK sessions, and history writes remain in
place. The new layer answers factual product and support-policy questions from
a local ChromaDB vector store.

## What Changed

New files:

```text
data/products.json
data/faq.json
src/rag/embed_catalog.py
src/rag/retriever.py
tests/test_rag_manual.md
```

Updated files:

```text
src/agents/support_agent.py
src/config/settings.py
runner.py
requirements.txt
README.md
```

## Data Flow

1. `data/products.json` and `data/faq.json` hold the trusted source material.
2. `python -m src.rag.embed_catalog` converts that source material into text
   chunks.
3. The embedding script embeds each chunk with the configured embedding model.
4. ChromaDB stores the chunk text, vector, ID, and metadata in `.chroma/`.
5. On each user turn, `support_agent.py` retrieves the top matching chunks.
6. The agent instruction receives a `Retrieved knowledge` section.
7. The model must answer factual policy/product questions from retrieved
   knowledge or tool output only.

## Why This Is Separate From Tools

Tools answer live operational questions:

- order status
- order cancellation
- database-backed product lookup

RAG answers knowledge questions:

- return rules
- warranty guidance
- shipping timelines
- product specs from the local support catalog

This split matters because tools change business state or query live tables,
while RAG provides read-only explanatory evidence.

## Grounding Rules

The support agent now has explicit Day 05 rules:

- Use retrieved knowledge for factual product, shipping, return, refund,
  warranty, and support-policy claims.
- Use tool output for live order and catalog lookups.
- Do not invent policies, deadlines, warranty decisions, prices, stock levels,
  or specifications.
- If retrieval is empty or weak, say the current eComBot knowledge base does
  not contain enough information.
- Greetings, name capture, order lookup, cancellation, and clarifying questions
  do not require retrieved knowledge.

## Commands

Install dependencies:

```powershell
pip install -r requirements.txt
```

Build or refresh the vector store:

```powershell
python -m src.rag.embed_catalog
```

Inspect retrieval without calling the chat model:

```powershell
python runner.py --retrieve "What is the replacement window for electronics?"
```

Run the Day 05 scenario:

```powershell
python runner.py --rag-scenario
```

Run ADK Web from `lab/demo/arun`:

```powershell
adk web ecombot
```

## Failure Behavior

The retriever returns an empty list when:

- ChromaDB is not installed.
- The vector store has not been built.
- The collection is empty.
- The embedding request fails.
- No result passes the similarity threshold.

The agent then receives a fallback instruction instead of raw exception text.
This keeps user-facing answers safe and predictable.

## Rebuild Rule

Whenever `data/products.json` or `data/faq.json` changes, rebuild ChromaDB:

```powershell
python -m src.rag.embed_catalog
```

The script deletes and recreates the `ecombot_kb` collection so stale chunks do
not remain after source edits.
