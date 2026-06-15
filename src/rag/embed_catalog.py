"""Build the local ChromaDB knowledge store for eComBot.

Run from the ecombot directory:

    python -m src.rag.embed_catalog

The script reads structured JSON files and PDF files from ``data/``, embeds
their chunks with the configured embedding model, and writes them to the
persistent ChromaDB collection used by the support agent.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import litellm
from dotenv import load_dotenv

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.config.settings import (  # type: ignore
        CHROMA_DIR,
        DATA_DIR,
        EMBEDDING_MODEL,
        OPENROUTER_API_KEY_ENV,
        PDF_DIR,
        RAG_COLLECTION_NAME,
        ROOT_DIR,
    )
    from src.rag.pdf_ingest import load_pdf_chunks  # type: ignore
else:
    from ..config.settings import (
        CHROMA_DIR,
        DATA_DIR,
        EMBEDDING_MODEL,
        OPENROUTER_API_KEY_ENV,
        PDF_DIR,
        RAG_COLLECTION_NAME,
        ROOT_DIR,
    )
    from .pdf_ingest import load_pdf_chunks

load_dotenv(ROOT_DIR / ".env")
litellm.suppress_debug_info = True


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _spec_lines(specs: dict[str, Any]) -> str:
    return "; ".join(f"{key.replace('_', ' ')}: {value}" for key, value in specs.items())


def load_structured_chunks() -> list[dict[str, Any]]:
    """Load product and FAQ source files and convert them into text chunks."""
    products = _read_json(DATA_DIR / "products.json")
    faqs = _read_json(DATA_DIR / "faq.json")

    chunks: list[dict[str, Any]] = []

    for product in products:
        product_id = product["product_id"]
        name = product["name"]
        category = product["category"]

        chunks.append(
            {
                "id": f"product:{product_id}:overview",
                "text": (
                    f"{name} ({product_id}) is a {category}. "
                    f"{product['summary']} Key specs: {_spec_lines(product['specs'])}."
                ),
                "metadata": {
                    "source": "products.json",
                    "kind": "product_overview",
                    "product_id": product_id,
                    "category": category,
                    "title": name,
                },
            }
        )
        chunks.append(
            {
                "id": f"product:{product_id}:warranty",
                "text": f"Warranty for {name} ({product_id}): {product['warranty']}",
                "metadata": {
                    "source": "products.json",
                    "kind": "product_warranty",
                    "product_id": product_id,
                    "category": category,
                    "title": name,
                },
            }
        )
        chunks.append(
            {
                "id": f"product:{product_id}:fulfillment",
                "text": (
                    f"Shipping and returns for {name} ({product_id}): "
                    f"{product['shipping']} {product['returns']}"
                ),
                "metadata": {
                    "source": "products.json",
                    "kind": "product_fulfillment",
                    "product_id": product_id,
                    "category": category,
                    "title": name,
                },
            }
        )

    for faq in faqs:
        chunks.append(
            {
                "id": f"faq:{faq['id']}",
                "text": f"FAQ - {faq['question']} Answer: {faq['answer']}",
                "metadata": {
                    "source": "faq.json",
                    "kind": "faq",
                    "faq_id": faq["id"],
                    "category": faq["category"],
                    "title": faq["question"],
                },
            }
        )

    return chunks


def load_knowledge_chunks() -> list[dict[str, Any]]:
    """Load all knowledge sources supported by the local RAG index."""
    chunks = load_structured_chunks()
    chunks.extend(load_pdf_chunks(PDF_DIR))
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed text chunks with the configured OpenAI-compatible embedding model."""
    if not os.getenv(OPENROUTER_API_KEY_ENV):
        raise RuntimeError(f"{OPENROUTER_API_KEY_ENV} is not set.")

    response = litellm.embedding(
        model=EMBEDDING_MODEL,
        input=texts,
        api_key=os.getenv(OPENROUTER_API_KEY_ENV),
    )
    return [item["embedding"] for item in response.data]


def _get_chroma_client():
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is not installed. Run: pip install -r requirements.txt") from exc

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def rebuild_vector_store() -> int:
    """Recreate the ChromaDB collection from the current source files."""
    chunks = load_knowledge_chunks()
    if not chunks:
        raise RuntimeError("No knowledge chunks were loaded.")

    client = _get_chroma_client()
    try:
        client.delete_collection(RAG_COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(name=RAG_COLLECTION_NAME)
    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
        embeddings=embed_texts([chunk["text"] for chunk in chunks]),
    )
    return len(chunks)


def main() -> None:
    count = rebuild_vector_store()
    print(
        f"Indexed {count} chunks into ChromaDB collection "
        f"'{RAG_COLLECTION_NAME}' at {CHROMA_DIR}."
    )


if __name__ == "__main__":
    main()
