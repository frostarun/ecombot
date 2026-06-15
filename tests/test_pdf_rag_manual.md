# eComBot PDF RAG Manual Tests

Use these checks after building the vector store:

```powershell
python scripts/generate_sample_pdfs.py
python -m src.rag.embed_catalog
```

## Direct Matches

```powershell
python runner.py --retrieve "What documents are needed to claim warranty?"
python runner.py --retrieve "How long does standard delivery take?"
python runner.py --retrieve "What warranty does the StreamMax decoder have?"
```

Expected:

- Results include PDF chunks.
- Metadata shows `source_file`, `page`, and `section`.
- The matching support, shipping, or warranty section ranks near the top.

## Partial Matches

```powershell
python runner.py --retrieve "How many days do I have to send back a defective phone?"
python runner.py --retrieve "What information should I give support for a brand service case?"
python runner.py --retrieve "Can remote locations take longer for delivery?"
```

Expected:

- Results still map to the correct returns, warranty, or shipping section.
- Similar wording is enough; exact wording is not required.

## Unsupported Questions

```powershell
python runner.py --retrieve "What is tomorrow's weather?"
python runner.py --retrieve "Do you repair refrigerator compressors?"
python runner.py --retrieve "What is the CEO's phone number?"
```

Expected:

- Retrieval should return no chunks or low-confidence unrelated chunks.
- Agent answers should use the knowledge-base fallback instead of guessing.
