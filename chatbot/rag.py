"""
rag.py — Retrieval-Augmented Generation: ingest and retrieve knowledge base docs.

Design:
- Chunk documents at ~500 tokens with 50-token overlap (character-based approximation).
- Use all-MiniLM-L6-v2 (sentence-transformers) for local embeddings — no API key needed.
- Store in ChromaDB (persistent). Ingest is idempotent via content hash deduplication.
- retrieve() applies a minimum similarity score threshold; below it, returns [] so
  the bot says "I don't know" rather than hallucinating.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from config import (
    CHROMA_PATH,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    DOCS_PATH,
    EMBEDDING_MODEL,
    RAG_MIN_SCORE,
    RAG_TOP_K,
)


# ─────────────────────────────────────────────────────────────────────────────
# Lazy imports (heavy — only loaded when needed)
# ─────────────────────────────────────────────────────────────────────────────

def _get_chroma_client():
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client


def _get_embedding_fn():
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    return SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)


def _get_collection(client=None, embedding_fn=None):
    if client is None:
        client = _get_chroma_client()
    if embedding_fn is None:
        embedding_fn = _get_embedding_fn()
    return client.get_or_create_collection(
        name="fin_docs",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────

_CHARS_PER_TOKEN = 4  # rough approximation for English text


def _chunk_text(text: str, source: str) -> list[dict]:
    """
    Split text into overlapping chunks.
    Returns list of {text, source, chunk_id, char_start}.
    """
    chunk_chars = CHUNK_SIZE_TOKENS * _CHARS_PER_TOKEN
    overlap_chars = CHUNK_OVERLAP_TOKENS * _CHARS_PER_TOKEN

    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "text": chunk_text,
                "source": source,
                "chunk_id": f"{source}::{idx}",
                "char_start": start,
            })
            idx += 1
        start += chunk_chars - overlap_chars
        if start >= len(text):
            break

    return chunks


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def ingest(path: str | Path | None = None) -> dict:
    """
    Ingest documents from a directory into ChromaDB.

    Parameters
    ----------
    path : Directory containing .md or .txt files. Defaults to DOCS_PATH.

    Returns
    -------
    dict with keys: added, skipped, total_chunks, files_processed.

    Idempotent: documents already stored (by content hash) are skipped.
    """
    docs_dir = Path(path) if path else DOCS_PATH
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs directory not found: {docs_dir}")

    collection = _get_collection()

    files = list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.txt"))
    if not files:
        return {"added": 0, "skipped": 0, "total_chunks": 0, "files_processed": 0}

    added = 0
    skipped = 0

    for file_path in files:
        source = file_path.name
        text = file_path.read_text(encoding="utf-8")
        chunks = _chunk_text(text, source)

        for chunk in chunks:
            chunk_hash = _content_hash(chunk["text"])
            doc_id = f"{source}::{chunk_hash}"

            # Check if already exists
            existing = collection.get(ids=[doc_id])
            if existing["ids"]:
                skipped += 1
                continue

            collection.add(
                ids=[doc_id],
                documents=[chunk["text"]],
                metadatas=[{
                    "source": source,
                    "chunk_id": chunk["chunk_id"],
                    "char_start": chunk["char_start"],
                }],
            )
            added += 1

    return {
        "added": added,
        "skipped": skipped,
        "total_chunks": added + skipped,
        "files_processed": len(files),
    }


def retrieve(query: str, k: int = RAG_TOP_K, min_score: float = RAG_MIN_SCORE) -> list[dict]:
    """
    Retrieve the top-k most relevant document chunks for a query.

    Parameters
    ----------
    query     : User query string.
    k         : Number of chunks to retrieve.
    min_score : Minimum cosine similarity score (0–1). Chunks below this are dropped.
                Returns [] if no chunk meets the threshold.

    Returns
    -------
    list of dicts: [{text, source, score}]
    Empty list means: no sufficiently relevant context found.
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        # ChromaDB cosine distance: similarity = 1 - distance
        similarity = 1.0 - dist
        if similarity >= min_score:
            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "score": round(similarity, 4),
            })

    return chunks


def collection_stats() -> dict:
    """Return stats about the current ChromaDB collection."""
    try:
        collection = _get_collection()
        return {"total_documents": collection.count(), "path": str(CHROMA_PATH)}
    except Exception as e:
        return {"error": str(e)}

