"""Retrieve grounded knowledge chunks from the eComBot ChromaDB store."""

import logging
import os
from typing import Any

import litellm

from ..config.settings import (
    CHROMA_DIR,
    EMBEDDING_MODEL,
    OPENROUTER_API_KEY_ENV,
    RAG_COLLECTION_NAME,
)

log = logging.getLogger(__name__)

MIN_SIMILARITY = 0.45


def embed_query(query: str) -> list[float]:
    """Embed one user query with the same model used during indexing."""
    if not os.getenv(OPENROUTER_API_KEY_ENV):
        raise RuntimeError(f"{OPENROUTER_API_KEY_ENV} is not set.")

    response = litellm.embedding(
        model=EMBEDDING_MODEL,
        input=[query],
        api_key=os.getenv(OPENROUTER_API_KEY_ENV),
    )
    return response.data[0]["embedding"]


def _get_collection():
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is not installed. Run: pip install -r requirements.txt") from exc

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(name=RAG_COLLECTION_NAME)


def _score(distance: float) -> float:
    return 1.0 / (1.0 + distance)


def retrieve(query: str, n_results: int = 3) -> list[dict[str, Any]]:
    """Return top matching knowledge chunks for a query.

    Empty, missing, or failed retrieval returns an empty list so callers can
    apply a grounded fallback without exposing internal errors to the user.
    """
    if not query or not query.strip():
        return []

    try:
        collection = _get_collection()
        count = collection.count()
        if count == 0:
            log.warning("RAG collection '%s' is empty.", RAG_COLLECTION_NAME)
            return []

        result = collection.query(
            query_embeddings=[embed_query(query.strip())],
            n_results=min(max(n_results, 1), count),
        )
    except Exception as exc:
        log.warning("RAG retrieval skipped: %s", exc)
        return []

    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    matches: list[dict[str, Any]] = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        similarity = _score(float(distance))
        if similarity < MIN_SIMILARITY:
            continue
        matches.append(
            {
                "id": chunk_id,
                "text": text,
                "metadata": metadata or {},
                "score": similarity,
            }
        )

    return matches


def format_retrieved_context(results: list[dict[str, Any]]) -> str:
    """Render retrieved chunks as a prompt section for the support agent."""
    if not results:
        return (
            "Retrieved knowledge: NOTHING RELEVANT FOUND.\n"
            "Use the fallback rule. Say that the current eComBot knowledge base "
            "does not contain enough information to answer, then ask for the "
            "missing product, policy, or order detail if useful."
        )

    lines = ["Retrieved knowledge. Use only this evidence for factual policy, product, shipping, return, and warranty claims:"]
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        label = metadata.get("title") or result["id"]
        source = metadata.get("source_file") or metadata.get("source")
        page = metadata.get("page")
        section = metadata.get("section")
        citation = f"; citation={source}" if source else ""
        if source and page:
            citation = f"; citation={source} p. {page}; source={source}; page={page}"
            if section:
                citation += f"; section={section}"
        lines.append(
            f"{index}. [{result['id']}; score={result['score']:.2f}; title={label}{citation}] "
            f"{result['text']}"
        )
    return "\n".join(lines)
