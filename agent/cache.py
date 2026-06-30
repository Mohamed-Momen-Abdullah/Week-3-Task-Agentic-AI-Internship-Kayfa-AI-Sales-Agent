"""
agent/cache.py
--------------
Semantic caching layer using sentence-transformers + MongoDB.

How it works:
1. On every user message, embed the query with the same model used for RAG.
2. Search MongoDB's semantic_cache collection for a stored embedding
   with cosine similarity >= SIMILARITY_THRESHOLD.
3. Cache HIT  → return the stored response instantly (zero LLM tokens).
4. Cache MISS → let the agent run, then store (embedding, query, response).

The same SentenceTransformer singleton from rag.py is reused so the model
is only loaded once.
"""

from __future__ import annotations

import numpy as np
from database.mongo import cache_lookup, cache_store

# ── Threshold ─────────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.95


def _get_model():
    """Reuse the singleton already loaded by rag.py (lazy import to avoid cycles)."""
    from agent.rag import _load
    _, _, model = _load()
    return model


def _embed(text: str) -> list[float]:
    """Embed a single string and return a plain Python list (for MongoDB storage)."""
    model = _get_model()
    vec = model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
    return vec[0].tolist()


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two already-normalised vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    return float(np.dot(va, vb))


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════════════════

def get_cached_response(user_message: str) -> str | None:
    """
    Try to find a semantically similar cached query.

    Returns the cached response string on a HIT, or None on a MISS.
    """
    query_vec = _embed(user_message)

    # Pull all cached embeddings from MongoDB and score them in Python.
    # For typical cache sizes (< 10 000 entries) this is fast enough.
    # If you ever need to scale, swap this for a proper vector index.
    candidates = cache_lookup()  # returns list of {embedding, response, query}

    best_score  = -1.0
    best_response = None

    for doc in candidates:
        stored_vec = doc.get("embedding")
        if not stored_vec:
            continue
        score = _cosine(query_vec, stored_vec)
        if score > best_score:
            best_score    = score
            best_response = doc.get("response")

    if best_score >= SIMILARITY_THRESHOLD:
        print(f"[SemanticCache] HIT  — similarity={best_score:.3f}")
        return best_response

    print(f"[SemanticCache] MISS — best similarity={best_score:.3f}")
    return None


def store_in_cache(user_message: str, response: str) -> None:
    """
    Store a (query, response) pair in the cache after a successful LLM call.
    """
    query_vec = _embed(user_message)
    cache_store({
        "query":     user_message,
        "embedding": query_vec,
        "response":  response,
    })
    print(f"[SemanticCache] Stored new entry for: {user_message[:60]}…")