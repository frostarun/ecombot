# eComBot Day 05 Manual RAG Tests

These tests validate the ChromaDB retrieval layer and the grounded support
agent behavior.

## Setup

From `lab/demo/arun/ecombot` with the `adk-june` virtual environment active:

```powershell
pip install -r requirements.txt
python -m src.rag.embed_catalog
```

If PowerShell has blackhole proxy variables, clear them before embedding or
chat runs:

```powershell
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY -ErrorAction SilentlyContinue
```

## Retrieval Inspection

Use this command to inspect chunks without calling the chat model:

```powershell
python runner.py --retrieve "What is the replacement window for electronics?"
```

Expected:

- Top result includes `faq:return-window`.
- The answer text mentions replacement within 7 days for eligible conditions.

## Case 1: Clean Match

Prompt:

```text
What is the replacement window for electronics?
```

Expected retrieval:

- `faq:return-window`
- Possibly `faq:return-open-box`

Expected agent behavior:

- Answers from retrieved return policy.
- Mentions the 7-day replacement window.
- Does not invent a refund or return policy beyond the retrieved text.

## Case 2: Partial Match

Prompt:

```text
What warranty does the Galaxy A55 5G have?
```

Expected retrieval:

- `product:PRD-101:warranty`
- Possibly `product:PRD-101:overview`

Expected agent behavior:

- States that Galaxy A55 5G has a 1 year manufacturer warranty for device
  defects.
- Mentions exclusions only if present in the retrieved chunk.

## Case 3: Fallback

Prompt:

```text
Do you sell refrigerator compressors?
```

Expected retrieval:

- No strong relevant chunk, or unrelated chunks below useful confidence.

Expected agent behavior:

- Does not claim eComBot sells refrigerator compressors.
- Says the current knowledge base does not contain enough information.
- Redirects to phones, TV decoders, accessories, or asks for a product ID/name.

## Case 4: Hallucination Trap

Prompt:

```text
Can I return opened earbuds after 45 days if I simply changed my mind?
```

Expected retrieval:

- `faq:return-open-box`
- `product:PRD-104:fulfillment`

Expected agent behavior:

- Does not invent a 45-day policy.
- Says opened electronics are not eligible for buyer's-remorse returns.
- Mentions replacement only for verified defects within the supported window.

## Pass Criteria

- Retrieved chunks are visible and relevant.
- The final answer cites only retrieved evidence or tool output.
- Missing knowledge triggers a clear fallback.
- No raw ChromaDB, embedding, PostgreSQL, or Redis exceptions are shown to the
  user.
