# eComBot PDF RAG Knowledgebase

This note explains the PDF-backed knowledge layer added on top of the existing
eComBot retrieval flow.

## What Changed

The project now supports two knowledge source types in one ChromaDB collection:

- Structured JSON from `data/products.json` and `data/faq.json`.
- PDF documents from `data/pdf/*.pdf`.

The existing support agent does not need a second retriever. It still calls
`src.rag.retriever.retrieve()`. The index builder now adds PDF chunks into the
same collection, and the retriever formats PDF metadata so the model can cite
source file and page.

## PDF Pipeline

1. `scripts/generate_sample_pdfs.py` creates small local e-commerce PDF
   documents for returns, refunds, shipping, warranty, and support privacy.
2. `src.rag.pdf_ingest.load_pdf_chunks()` reads every `*.pdf` under
   `data/pdf/` with `pypdf.PdfReader`.
3. Text is cleaned page by page.
4. The loader detects heading-like lines and keeps chunks aligned to sections.
5. Long sections are split into overlapping chunks so nearby context is not lost.
6. Every chunk is returned as `{id, text, metadata}`.
7. `src.rag.embed_catalog.rebuild_vector_store()` embeds all JSON and PDF
   chunks and writes them to ChromaDB.

## Metadata Contract

Each PDF chunk contains:

```json
{
  "source_file": "ecombot-support-policies.pdf",
  "document_title": "eComBot Support Policies",
  "section": "Warranty Claims",
  "page": 2,
  "doc_type": "pdf"
}
```

Compatibility fields such as `source`, `kind`, and `title` are also included so
the current retrieval formatter can treat JSON and PDF chunks consistently.

## Runtime Flow

1. User sends a message in ADK Web or `runner.py`.
2. `support_agent.py` extracts the latest user text.
3. The retriever embeds that query with the same embedding model used at index
   time.
4. ChromaDB returns nearest chunks from both JSON and PDF knowledge.
5. The support-agent instruction is built dynamically with those chunks.
6. Grounding rules tell the model to answer from retrieved evidence and tool
   output only.
7. If retrieval is empty or not relevant, the agent must say the current
   knowledge base does not contain enough information.

## Why PDF Metadata Matters

PDF chunks can contain overlapping policy language. Metadata lets you inspect
which document, page, and section caused an answer. This is useful for:

- Debugging weak retrieval.
- Explaining why one answer was selected.
- Citing policy sources in model responses.
- Filtering by document type later if the knowledge base grows.

## Commands

From `lab/demo/arun/ecombot`:

```powershell
python scripts/generate_sample_pdfs.py
python -m src.rag.embed_catalog
python runner.py --retrieve "What documents are needed to claim warranty?"
python runner.py --retrieve "How long does standard delivery take?"
python runner.py "What documents are needed to claim warranty?"
```

## Design Boundary

The PDF layer is read-only knowledge. It should not replace tools:

- Use tools for live order status, cancellation, product DB lookup, and session
  state changes.
- Use retrieval for policy, warranty, shipping, return, refund, and support
  explanation.

This boundary keeps deterministic business actions separate from semantic
document lookup.
