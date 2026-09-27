from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi
from supabase import Client

from . import db
from .embeddings import embed_text


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 1]


def bm25_search(query: str, chunks: list[dict[str, Any]], top_k: int = 10) -> list[tuple[dict[str, Any], float]]:
    if not chunks:
        return []
    corpus = [tokenize(chunk["text"]) for chunk in chunks]
    bm25 = BM25Okapi(corpus)
    query_tokens = tokenize(query)
    scores = bm25.get_scores(query_tokens)
    scored_chunks = list(zip(chunks, scores))
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    return scored_chunks[:top_k]


def vector_search(dbc: Client, document_id: int, user_id: str, query: str, top_k: int = 10) -> list[dict[str, Any]]:
    embedding = embed_text(query)
    if not embedding:
        return []
    matches = db.match_chunks(dbc, document_id, user_id, embedding, limit=top_k)
    return [
        {
            "id": str(m["id"]),
            "text": m["text"],
            "metadata": {
                "page_number": m.get("page_number"),
                "section_heading": m.get("section_heading"),
            },
            "vector_score": m.get("similarity", 0.0),
        }
        for m in matches
    ]


def reciprocal_rank_fusion(results_list: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    chunk_map: dict[str, dict[str, Any]] = {}
    for results in results_list:
        for rank, chunk in enumerate(results):
            chunk_id = chunk["id"]
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk
            scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (k + rank + 1)
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    fused = []
    for chunk_id in sorted_ids:
        chunk = chunk_map[chunk_id].copy()
        chunk["rrf_score"] = scores[chunk_id]
        fused.append(chunk)
    return fused


def rerank_chunks(query: str, chunks: list[dict[str, Any]], top_k: int = 4) -> list[dict[str, Any]]:
    if not chunks:
        return []
    query_tokens = set(tokenize(query))
    scored = []
    for chunk in chunks:
        text_lower = chunk["text"].lower()
        text_tokens = set(tokenize(chunk["text"]))
        token_overlap = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
        exact_match_bonus = sum(0.1 for token in query_tokens if token in text_lower)
        section_bonus = 0.0
        heading = (chunk.get("metadata") or {}).get("section_heading")
        if heading and any(t in heading.lower() for t in query_tokens):
            section_bonus = 0.2
        final_score = (
            0.3 * chunk.get("rrf_score", 0.5) * 10
            + 0.2 * chunk.get("vector_score", 0.5)
            + 0.25 * token_overlap
            + 0.15 * exact_match_bonus
            + 0.1 * section_bonus
        )
        chunk_copy = chunk.copy()
        chunk_copy["rerank_score"] = final_score
        scored.append(chunk_copy)
    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored[:top_k]


def hybrid_search(
    dbc: Client,
    document_id: int,
    user_id: str,
    query: str,
    top_k: int = 4,
    vector_candidates: int = 15,
    bm25_candidates: int = 15,
) -> list[dict[str, Any]]:
    all_chunks = db.get_all_chunks(dbc, document_id)
    if not all_chunks:
        return []
    all_chunks_normalized = [{"id": str(c["id"]), "text": c["text"], "metadata": {
        "page_number": c.get("page_number"), "section_heading": c.get("section_heading"),
    }} for c in all_chunks]

    vector_results = vector_search(dbc, document_id, user_id, query, top_k=vector_candidates)
    bm25_results_raw = bm25_search(query, all_chunks_normalized, top_k=bm25_candidates)
    bm25_results = [chunk for chunk, score in bm25_results_raw if score > 0]

    fused = reciprocal_rank_fusion([vector_results, bm25_results])
    return rerank_chunks(query, fused, top_k=top_k)


def expand_legal_query(query: str) -> str:
    expansions = {
        "ipc": "indian penal code section crime criminal offense",
        "bns": "bharatiya nyaya sanhita criminal code",
        "crpc": "criminal procedure code procedural",
        "bnss": "bharatiya nagarik suraksha sanhita procedure",
        "cpc": "civil procedure code civil suit",
        "420": "cheating dishonest inducement fraud",
        "302": "murder culpable homicide death",
        "304": "culpable homicide death",
        "306": "abetment suicide",
        "376": "rape sexual assault",
        "498a": "cruelty husband relatives dowry harassment",
        "termination": "end terminate cancel expiry notice period",
        "penalty": "fine damages liquidated compensation",
        "indemnity": "indemnify hold harmless liability protection",
        "confidentiality": "confidential secret non-disclosure nda proprietary",
        "arbitration": "dispute resolution arbitrator mediation",
        "jurisdiction": "court venue governing law applicable",
        "breach": "violation default non-compliance failure",
        "notice period": "prior notice termination advance intimation",
        "force majeure": "act of god unforeseen circumstances",
        "landlord": "lessor owner property rental",
        "tenant": "lessee renter occupant",
        "eviction": "vacate possession removal",
        "rti": "right to information public authority transparency government records",
        "pocso": "child sexual offence minor protection special court",
        "domestic violence": "PWDVA protection order shared household monetary relief",
        "maintenance": "alimony monthly allowance wife children parents 125 crpc",
        "mortgage": "home loan property loan security bank TPA",
        "retrenchment": "layoff termination notice compensation IDA labour",
        "evidence": "admissibility witness burden proof BSA electronic record",
        "stalking": "following harassment cyberstalking 354D BNS 78",
        "sexual harassment": "workplace POSH unwelcome advances 354A BNS 75",
        "forgery": "fake document false record 463 467 468 BNS 334",
        "conspiracy": "criminal conspiracy 120B joint plan abetment",
        "dacoity": "gang robbery five persons 395 BNS 310",
    }
    query_lower = query.lower()
    expanded_terms = [expansion for term, expansion in expansions.items() if term in query_lower]
    return f"{query} {' '.join(expanded_terms)}" if expanded_terms else query


def search_with_expansion(dbc: Client, document_id: int, user_id: str, query: str, top_k: int = 4) -> list[dict[str, Any]]:
    expanded_query = expand_legal_query(query)
    return hybrid_search(dbc, document_id, user_id, expanded_query, top_k=top_k)
