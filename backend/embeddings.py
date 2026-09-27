from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from supabase import Client

from . import db
from .config import HUGGINGFACE_API_KEY

if TYPE_CHECKING:
    from .document_parser import StructuredChunk

HF_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
HF_EMBED_URL = f"https://router.huggingface.co/hf-inference/models/{HF_EMBED_MODEL}/pipeline/feature-extraction"
EMBED_DIMENSIONS = 384


def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    if not HUGGINGFACE_API_KEY:
        return None
    try:
        response = httpx.post(
            HF_EMBED_URL,
            headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"},
            json={"inputs": texts, "options": {"wait_for_model": True}},
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list) and result and isinstance(result[0], list):
            return result
        return None
    except Exception as exc:
        print(f"[EMBED] HuggingFace embedding failed: {exc}")
        return None


def embed_text(text: str) -> list[float] | None:
    result = _embed_batch([text])
    return result[0] if result else None


def embed_texts(texts: list[str], batch_size: int = 20) -> list[list[float]] | None:
    if not texts:
        return []
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = _embed_batch(texts[i:i + batch_size])
        if batch is None:
            return None
        all_embeddings.extend(batch)
    return all_embeddings


def add_structured_chunks(dbc: Client, document_id: int, user_id: str, chunks: list["StructuredChunk"]) -> int:
    if not chunks:
        return 0
    texts = [chunk.text for chunk in chunks]
    vectors = embed_texts(texts)

    rows: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        rows.append({
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "page_number": chunk.page_number,
            "section_heading": chunk.section_heading,
            "clause_number": chunk.clause_number,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "embedding": vectors[i] if vectors else None,
        })
    db.insert_document_chunks(dbc, document_id, user_id, rows)
    return len(rows)


def query_document_chunks(dbc: Client, document_id: int, user_id: str, query: str, limit: int = 4) -> list[dict[str, Any]]:
    embedding = embed_text(query)
    if not embedding:
        return []
    matches = db.match_chunks(dbc, document_id, user_id, embedding, limit=limit)
    return [
        {
            "id": m["id"],
            "text": m["text"],
            "metadata": {
                "page_number": m.get("page_number"),
                "section_heading": m.get("section_heading"),
                "clause_number": m.get("clause_number"),
            },
            "distance": 1 - m.get("similarity", 0),
        }
        for m in matches
    ]
